'use client'

import { useRef, useEffect, useState, useCallback } from 'react'
import { formatTime } from '@/lib/utils'

interface Coordinate {
  x: number
  y: number
  z?: number
}

interface HandData {
  hand_type: string
  landmarks: any[]  // Array of 21 landmarks
  palm_center?: { x: number; y: number }
  finger_angles?: Record<string, number>
  hand_openness?: number
}

interface SkeletonData {
  frame: number
  frame_number: number
  timestamp: number
  hands: HandData[]
}

interface ToolDetection {
  bbox: [number, number, number, number]
  rotated_bbox?: [[number, number], [number, number], [number, number], [number, number]]  // Phase 2.5
  rotation_angle?: number  // Phase 2.5
  area_reduction?: number  // Phase 2.5
  confidence: number
  class_name: string
  name?: string  // SAM2 instrument name
  id?: number    // SAM2 instrument id
  track_id?: number
  contour?: [number, number][]  // Mask contour points for shape display
}

interface ToolData {
  frame_number: number
  timestamp: number
  detections: ToolDetection[]
}

interface VideoPlayerProps {
  videoUrl?: string
  skeletonData?: SkeletonData[]
  toolData?: ToolData[]
  width?: number
  height?: number
  autoPlay?: boolean
  videoType?: string
  onTimeUpdate?: (currentTime: number) => void
  /**
   * 外部からの「この秒数にジャンプせよ」シグナル。
   * `token` が変わる度に `time` へ seek する (同じ時刻でも token を変えれば再シーク)。
   * Review Deck の Event List / Timeline クリック連動で使用。
   */
  seekSignal?: { time: number; token: number }
}

export default function VideoPlayer({
  videoUrl,
  skeletonData = [],
  toolData = [],
  width = 640,
  height = 360,
  autoPlay = false,
  videoType,
  onTimeUpdate,
  seekSignal,
}: VideoPlayerProps) {
  // Check if instrument data exists and video type supports instruments
  const hasInstrumentData = (videoType === 'internal' ||
    videoType === 'external_with_instruments') &&
    toolData && toolData.length > 0 &&
    toolData.some(frame => frame.detections && frame.detections.length > 0)

  // Enable instrument display for external_with_instruments
  const canShowInstruments = videoType === 'internal' || videoType === 'external_with_instruments'
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [isPlaying, setIsPlaying] = useState(false)
  const isPlayingRef = useRef(false) // refで常に最新の再生状態を保持（クロージャ遅延回避）
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [videoFps, setVideoFps] = useState(30) // 🔧 追加: 動画の実際のFPSを保存
  const [canvasSize, setCanvasSize] = useState({ width: 640, height: 360 })
  const animationFrameRef = useRef<number | undefined>(undefined)
  const rvfcHandleRef = useRef<number | undefined>(undefined) // 🆕 RVFC用のハンドル
  const lastDrawnFrameRef = useRef<number>(-1)
  const lastCanvasStateRef = useRef<ImageData | null>(null)
  const frameSkipCountRef = useRef<number>(0)

  // オーバーレイ表示設定
  const [showSkeleton, setShowSkeleton] = useState(true)
  const [showInstruments, setShowInstruments] = useState(hasInstrumentData)

  // 現在のフレームに対応するデータを取得（新形式対応）
  const getCurrentData = (timestamp: number) => {
    // 骨格データのフレーム間隔に基づくtolerance（半フレーム分）
    // 例: 15FPS → 67ms間隔 → tolerance=33ms, 30FPS → 33ms間隔 → tolerance=16ms
    const skeletonInterval = skeletonData.length >= 2
      ? skeletonData[1].timestamp - skeletonData[0].timestamp
      : 1 / (videoFps || 30)
    const tolerance = skeletonInterval / 2

    // 二分探索で現在時刻に最も近いフレームを高速に探す
    let currentSkeletonFrame: SkeletonData | undefined
    if (skeletonData.length > 0) {
      let lo = 0
      let hi = skeletonData.length - 1
      while (lo < hi) {
        const mid = (lo + hi) >> 1
        if (skeletonData[mid].timestamp < timestamp) {
          lo = mid + 1
        } else {
          hi = mid
        }
      }
      // loは timestamp 以上の最初のインデックス。前後を比較して近い方を選ぶ
      const candidates = [lo - 1, lo].filter(i => i >= 0 && i < skeletonData.length)
      currentSkeletonFrame = candidates.reduce((best, i) => {
        if (!best) return skeletonData[i]
        return Math.abs(skeletonData[i].timestamp - timestamp) < Math.abs(best.timestamp - timestamp)
          ? skeletonData[i] : best
      }, undefined as SkeletonData | undefined)
    }

    // 器具データも同じtoleranceで検索
    const toolInterval = toolData.length >= 2
      ? toolData[1].timestamp - toolData[0].timestamp
      : skeletonInterval
    const toolTolerance = toolInterval / 2

    let currentTools = toolData.find(
      data => Math.abs(data.timestamp - timestamp) < toolTolerance
    )

    if (!currentTools && toolData.length > 0) {
      currentTools = toolData.reduce((prev, curr) =>
        Math.abs(curr.timestamp - timestamp) < Math.abs(prev.timestamp - timestamp) ? curr : prev
      )
    }

    return { skeletonFrame: currentSkeletonFrame, tools: currentTools }
  }

  // オーバーレイを指定時刻で描画（RVFC/RAF共通ロジック）
  const drawOverlayAtTime = useCallback((timestamp: number) => {
    if (!videoRef.current || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const video = videoRef.current
    const currentTimestamp = timestamp

    // フレームスキップ最適化（同じフレームを再描画しない）
    // 🔧 修正: ハードコードされた30fpsを実際のvideoFpsに置き換え
    const currentFrame = Math.floor(currentTimestamp * videoFps)
    if (currentFrame === lastDrawnFrameRef.current && !isPlaying) {
      return
    }

    // フレームスキップを削除してリアルタイム性を向上
    // 全フレームを描画することでより滑らかな追従を実現

    lastDrawnFrameRef.current = currentFrame

    // キャンバスサイズを動画サイズに合わせる
    if (video.videoWidth && video.videoHeight) {
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        setCanvasSize({ width: video.videoWidth, height: video.videoHeight })
      }
    }

    // 差分描画のための前回状態保存（必要時のみ）
    const saveCanvasState = () => {
      if (canvas.width > 0 && canvas.height > 0) {
        lastCanvasStateRef.current = ctx.getImageData(0, 0, canvas.width, canvas.height)
      }
    }

    // キャンバスをクリア（最適化：必要時のみ全体クリア）
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const { skeletonFrame, tools } = getCurrentData(currentTimestamp)

    // 骨格データを描画（新形式: frame.hands配列）
    if (showSkeleton && skeletonFrame?.hands && skeletonFrame.hands.length > 0) {
      skeletonFrame.hands.forEach((hand, handIndex) => {
        if (!hand?.landmarks || !Array.isArray(hand.landmarks)) return

        // 手ごとに色を変える（左手：青、右手：緑）
        const isLeftHand = hand.hand_type === 'Left'
        const handColor = isLeftHand ? '#00AAFF' : '#00FF00'
        const pointColor = isLeftHand ? '#0088FF' : '#FF0000'

        // より目立つ色とスタイル
        ctx.strokeStyle = handColor
        ctx.lineWidth = 3
        ctx.fillStyle = handColor
        ctx.shadowColor = handColor
        ctx.shadowBlur = 3

        // 手の骨格接続を描画（MediaPipeの手のランドマーク接続）
        const connections = [
          // 親指
          [0, 1], [1, 2], [2, 3], [3, 4],
          // 人差し指
          [0, 5], [5, 6], [6, 7], [7, 8],
          // 中指
          [0, 9], [9, 10], [10, 11], [11, 12],
          // 薬指
          [0, 13], [13, 14], [14, 15], [15, 16],
          // 小指
          [0, 17], [17, 18], [18, 19], [19, 20],
          // 手のひら
          [5, 9], [9, 13], [13, 17]
        ]

        // 線を描画
        connections.forEach(([start, end]) => {
          const startPoint = hand.landmarks[start]
          const endPoint = hand.landmarks[end]

          if (startPoint && endPoint) {
            ctx.beginPath()
            ctx.moveTo(startPoint.x, startPoint.y)
            ctx.lineTo(endPoint.x, endPoint.y)
            ctx.stroke()
          }
        })

        // 点を描画（より大きく、目立つように）
        ctx.fillStyle = pointColor
        hand.landmarks.forEach((point: any, index: number) => {
          if (point && point.x !== undefined && point.y !== undefined) {
            ctx.beginPath()
            ctx.arc(point.x, point.y, 5, 0, 2 * Math.PI)
            ctx.fill()

            // デバッグ用：主要ポイントのみランドマーク番号を表示
            const keyPoints = [0, 4, 8, 12, 16, 20] // 手首と各指先
            if (keyPoints.includes(index)) {
              ctx.fillStyle = '#FFFFFF'
              ctx.font = 'bold 12px Arial'
              ctx.fillText(String(index), point.x + 8, point.y - 8)
              ctx.fillStyle = pointColor
            }
          }
        })

        // 手のタイプを表示
        if (hand.landmarks[0]) {
          const wristPoint = hand.landmarks[0]
          ctx.fillStyle = handColor
          ctx.font = 'bold 14px Arial'
          ctx.fillText(
            hand.hand_type || (isLeftHand ? 'Left' : 'Right'),
            wristPoint.x,
            wristPoint.y - 20
          )
        }
      })

      // 影をリセット
      ctx.shadowBlur = 0
    }

    // 器具検出データを描画
    if (showInstruments && tools?.detections) {
      tools.detections.forEach((detection) => {
        const [x1, y1, x2, y2] = detection.bbox
        const isExternalInstrument = videoType === 'external_with_instruments'
        const color = isExternalInstrument ? '#9333EA' : '#FF0000'

        // ✨ 新機能: マスク形状を半透明で描画
        if (detection.contour && detection.contour.length > 2) {
          // 半透明塗りつぶし
          ctx.fillStyle = isExternalInstrument
            ? 'rgba(147, 51, 234, 0.35)'  // 紫色、35%透明
            : 'rgba(255, 0, 0, 0.35)'      // 赤色、35%透明

          ctx.beginPath()
          detection.contour.forEach(([x, y], idx) => {
            if (idx === 0) {
              ctx.moveTo(x, y)
            } else {
              ctx.lineTo(x, y)
            }
          })
          ctx.closePath()
          ctx.fill()

          // 輪郭線を描画（より明確に）
          ctx.strokeStyle = color
          ctx.lineWidth = 2.5
          ctx.stroke()

        } else {
          // フォールバック: contourがない場合は従来のbbox（安定版対応）
          ctx.strokeStyle = color
          ctx.lineWidth = 3

          // Phase 2.5対応: 回転BBoxがある場合
          if (detection.rotated_bbox && detection.rotated_bbox.length === 4) {
            ctx.beginPath()
            const [p1, p2, p3, p4] = detection.rotated_bbox
            ctx.moveTo(p1[0], p1[1])
            ctx.lineTo(p2[0], p2[1])
            ctx.lineTo(p3[0], p3[1])
            ctx.lineTo(p4[0], p4[1])
            ctx.closePath()
            ctx.stroke()

            // 従来の矩形BBoxを半透明で表示（比較用）
            ctx.strokeStyle = isExternalInstrument ? 'rgba(147, 51, 234, 0.3)' : 'rgba(255, 0, 0, 0.3)'
            ctx.setLineDash([5, 5])
            ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
            ctx.setLineDash([])
          } else {
            // 通常の矩形bbox
            ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
          }
        }

        // ラベル描画
        ctx.fillStyle = color
        ctx.font = 'bold 14px Arial'
        const labelName = detection.name || detection.class_name || 'Instrument'
        const label = `${labelName} (${(detection.confidence * 100).toFixed(0)}%)`
        const textWidth = ctx.measureText(label).width

        // ラベル背景
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
        ctx.fillRect(x1, y1 - 22, textWidth + 8, 20)

        // ラベルテキスト
        ctx.fillStyle = '#FFFFFF'
        ctx.fillText(label, x1 + 4, y1 - 6)

        // 追跡IDがある場合
        if (detection.track_id !== undefined || detection.id !== undefined) {
          const displayId = detection.track_id ?? detection.id
          ctx.fillStyle = 'rgba(255, 255, 0, 0.9)'
          ctx.font = 'bold 12px Arial'
          ctx.fillText(`ID: ${displayId}`, x2 - 35, y1 - 6)
        }

        // Phase 2.5: 面積削減率の表示（回転BBoxがある場合）
        if (detection.area_reduction !== undefined && detection.area_reduction > 0) {
          ctx.fillStyle = 'rgba(0, 255, 0, 0.9)'
          ctx.font = '11px Arial'
          ctx.fillText(`-${detection.area_reduction.toFixed(1)}%`, x1, y2 + 15)
        }

        // 中心点マーカー
        const centerX = (x1 + x2) / 2
        const centerY = (y1 + y2) / 2
        ctx.fillStyle = isExternalInstrument ? '#9333EA' : '#FF0000'
        ctx.beginPath()
        ctx.arc(centerX, centerY, 4, 0, 2 * Math.PI)
        ctx.fill()
      })
    }

    // 次のフレームをスケジュール（後で scheduleNextFrame() で実装）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showSkeleton, showInstruments, skeletonData, toolData, videoType, videoFps, getCurrentData])

  // 次のフレーム描画をスケジュール（RVFC優先、フォールバックRAF）
  const scheduleNextFrame = useCallback(() => {
    if (!videoRef.current || !isPlayingRef.current) return

    const video = videoRef.current
    // 1フレーム分の先読み補正値（RVFCは描画後に発火するため）
    const frameDuration = 1 / (videoFps || 30)

    // 🆕 RVFC対応ブラウザ: ビデオフレームと完全同期
    if (video.requestVideoFrameCallback) {
      rvfcHandleRef.current = video.requestVideoFrameCallback((now, metadata) => {
        // metadata.mediaTime + 1フレーム分で先読み補正
        drawOverlayAtTime(metadata.mediaTime + frameDuration)

        // 再生中なら次のフレームをスケジュール
        if (isPlayingRef.current) {
          scheduleNextFrame()
        }
      })

    }
    // ⚠️ フォールバック: RAF（Firefox等、RVFC非対応ブラウザ）
    else {
      animationFrameRef.current = requestAnimationFrame(() => {
        // RAFも同様に先読み補正
        drawOverlayAtTime(video.currentTime + frameDuration)

        if (isPlayingRef.current) {
          scheduleNextFrame()
        }
      })
    }
  }, [videoFps, drawOverlayAtTime])

  // 動画の再生/一時停止
  const togglePlay = () => {
    if (!videoRef.current) return
    
    if (videoRef.current.paused) {
      videoRef.current.play()
      isPlayingRef.current = true
      setIsPlaying(true)
    } else {
      videoRef.current.pause()
      isPlayingRef.current = false
      setIsPlaying(false)
    }
  }

  // 動画の時間更新
  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current) return
    const time = videoRef.current.currentTime
    setCurrentTime(time)

    // 🔧 修正: 一時停止中のみ描画（再生中はRVFC/RAFで自動描画）
    if (!isPlaying) {
      drawOverlayAtTime(time)
    }

    // 外部にも通知
    if (onTimeUpdate) {
      onTimeUpdate(time)
    }
  }, [isPlaying, drawOverlayAtTime, onTimeUpdate])

  // 動画のメタデータ読み込み完了
  const handleLoadedMetadata = () => {
    if (!videoRef.current) return

    // skeleton_data の最後のタイムスタンプを使って duration を設定
    let actualDuration = videoRef.current.duration
    if (skeletonData.length > 0) {
      const lastTimestamp = skeletonData[skeletonData.length - 1].timestamp
      actualDuration = Math.max(actualDuration, lastTimestamp)
    } else if (toolData.length > 0) {
      const lastTimestamp = toolData[toolData.length - 1].timestamp
      actualDuration = Math.max(actualDuration, lastTimestamp)
    }
    setDuration(actualDuration)

    // 🔧 追加: 動画の実際のFPSを推定
    // duration と skeletonData/toolData から FPS を推定
    const video = videoRef.current
    if (skeletonData.length > 1) {
      // skeleton_data から FPS を推定（最初の2フレームの時間差から）
      const firstTimestamp = skeletonData[0].timestamp
      const secondTimestamp = skeletonData[1].timestamp
      const frameDiff = secondTimestamp - firstTimestamp
      if (frameDiff > 0) {
        const estimatedFps = Math.round(1 / frameDiff)
        setVideoFps(estimatedFps)
      }
    } else if (toolData.length > 1) {
      // tool_data から FPS を推定
      const firstTimestamp = toolData[0].timestamp
      const secondTimestamp = toolData[1].timestamp
      const frameDiff = secondTimestamp - firstTimestamp
      if (frameDiff > 0) {
        const estimatedFps = Math.round(1 / frameDiff)
        setVideoFps(estimatedFps)
      }
    }

    // 初期描画を実行
    drawOverlayAtTime(0)
  }

  // シーク処理
  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (!videoRef.current) return
    const newTime = parseFloat(e.target.value)
    videoRef.current.currentTime = newTime
    setCurrentTime(newTime)
    lastDrawnFrameRef.current = -1 // フレームキャッシュをリセット
    drawOverlayAtTime(newTime)
  }, [drawOverlayAtTime])

  // 再生速度変更
  const handleSpeedChange = (speed: number) => {
    if (!videoRef.current) return
    videoRef.current.playbackRate = speed
  }

  // 再生状態の変更を監視
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handlePlay = () => {
      isPlayingRef.current = true // refは即座に反映（クロージャ遅延なし）
      setIsPlaying(true)
      // 🆕 再生開始時にフレームスケジューリングを開始
      scheduleNextFrame()
    }
    const handlePause = () => {
      isPlayingRef.current = false
      setIsPlaying(false)
      // 🔧 両方のハンドルをクリーンアップ
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = undefined
      }
      if (rvfcHandleRef.current && video.cancelVideoFrameCallback) {
        video.cancelVideoFrameCallback(rvfcHandleRef.current)
        rvfcHandleRef.current = undefined
      }
    }

    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)

    return () => {
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
      // クリーンアップ
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
      if (rvfcHandleRef.current && video.cancelVideoFrameCallback) {
        video.cancelVideoFrameCallback(rvfcHandleRef.current)
      }
    }
  }, [scheduleNextFrame])

  // データが更新されたら再描画
  useEffect(() => {
    if ((skeletonData.length > 0 || toolData.length > 0) && videoRef.current) {
      drawOverlayAtTime(videoRef.current.currentTime)
    }
  }, [skeletonData, toolData, drawOverlayAtTime])

  // 外部 seek シグナル (Review Deck の Event クリック連動)
  const lastSeekTokenRef = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (!seekSignal || !videoRef.current) return
    if (lastSeekTokenRef.current === seekSignal.token) return
    lastSeekTokenRef.current = seekSignal.token
    const t = Math.max(0, Math.min(seekSignal.time, videoRef.current.duration || seekSignal.time))
    videoRef.current.currentTime = t
    drawOverlayAtTime(t)
  }, [seekSignal, drawOverlayAtTime])

  // 表示設定が変更されたら再描画
  useEffect(() => {
    if (videoRef.current) {
      drawOverlayAtTime(videoRef.current.currentTime)
    }
  }, [showSkeleton, showInstruments, drawOverlayAtTime])


  // 動画のエラーハンドリング
  const handleVideoError = (e: React.SyntheticEvent<HTMLVideoElement, Event>) => {
    const video = e.currentTarget
    const errorDetails = {
      errorCode: video.error?.code,
      errorMessage: video.error?.message,
      networkState: video.networkState,
      readyState: video.readyState,
      src: video.src,
      videoUrl,
      currentSrc: video.currentSrc
    }
    console.error('Video loading error:', errorDetails)

    // エラーコードの意味を表示
    const errorMessages: {[key: number]: string} = {
      1: 'MEDIA_ERR_ABORTED - 動画の読み込みが中断されました',
      2: 'MEDIA_ERR_NETWORK - ネットワークエラーが発生しました',
      3: 'MEDIA_ERR_DECODE - 動画のデコードに失敗しました',
      4: 'MEDIA_ERR_SRC_NOT_SUPPORTED - 動画形式がサポートされていません'
    }

    if (video.error?.code) {
      console.error('Error type:', errorMessages[video.error.code] || 'Unknown error')
    }
  }

  return (
    <div className="video-player-container w-full">
      <div className="relative w-full" style={{ aspectRatio: '16/9', maxHeight: height }}>
        {/* ビデオ要素 */}
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onError={handleVideoError}
            autoPlay={autoPlay}
            className="absolute top-0 left-0 w-full h-full bg-black object-contain"
            controls={false}
          />
        ) : (
          <div className="absolute top-0 left-0 w-full h-full bg-gray-900 flex items-center justify-center">
            <p className="text-white">動画URLが指定されていません</p>
          </div>
        )}
        
        {/* オーバーレイキャンバス */}
        <canvas
          ref={canvasRef}
          width={canvasSize.width}
          height={canvasSize.height}
          className="absolute top-0 left-0 w-full h-full pointer-events-none"
          style={{ objectFit: 'contain' }}
        />
        
        {/* プレースホルダー（動画がない場合） */}
        {!videoUrl && (
          <div className="absolute top-0 left-0 w-full h-full bg-gray-900 flex flex-col items-center justify-center">
            <div className="text-white text-center">
              <p className="text-lg mb-2">サンプル動画</p>
              <p className="text-sm text-gray-400">解析結果のオーバーレイ表示デモ</p>
            </div>
          </div>
        )}
      </div>

      {/* コントロール */}
      <div className="mt-4 space-y-3">
        {/* 再生ボタンとプログレスバー */}
        <div className="flex items-center space-x-3">
          <button
            onClick={togglePlay}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            {isPlaying ? '一時停止' : '再生'}
          </button>
          
          <div className="flex-1 flex items-center space-x-2">
            <span className="text-sm text-gray-600">{formatTime(currentTime)}</span>
            <input
              type="range"
              min={0}
              max={duration || 100}
              value={currentTime}
              onChange={handleSeek}
              className="flex-1"
            />
            <span className="text-sm text-gray-600">{formatTime(duration)}</span>
          </div>
          
          {/* 再生速度 */}
          <select
            onChange={(e) => handleSpeedChange(parseFloat(e.target.value))}
            className="px-2 py-1 border border-gray-300 rounded text-sm"
            defaultValue="1"
          >
            <option value="0.5">0.5x</option>
            <option value="1">1x</option>
            <option value="1.5">1.5x</option>
            <option value="2">2x</option>
          </select>
        </div>

        {/* オーバーレイ表示コントロール */}
        <div className="flex items-center space-x-4 text-sm">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={showSkeleton}
              onChange={(e) => setShowSkeleton(e.target.checked)}
            />
            <span>骨格表示</span>
          </label>
          <label
            className={`flex items-center space-x-2 ${!canShowInstruments || !hasInstrumentData ? 'opacity-50' : ''}`}
            title={
              !canShowInstruments
                ? '器具検出は内部カメラまたは外部カメラ（器具あり）でのみ利用可能です'
                : !hasInstrumentData
                  ? '器具データが検出されていません'
                  : ''
            }
          >
            <input
              type="checkbox"
              checked={showInstruments}
              onChange={(e) => setShowInstruments(e.target.checked)}
              disabled={!canShowInstruments || !hasInstrumentData}
            />
            <span className={!hasInstrumentData ? 'text-gray-400' : ''}>
              器具検出表示
              {videoType === 'external_with_instruments' && hasInstrumentData ? ' (外部カメラ)' : ''}
              {!hasInstrumentData && canShowInstruments ? ' (データなし)' : ''}
            </span>
          </label>
        </div>
      </div>
    </div>
  )
}