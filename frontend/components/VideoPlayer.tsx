'use client'

import { useRef, useEffect, useState, useCallback } from 'react'

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
  track_id?: number
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
}

export default function VideoPlayer({
  videoUrl,
  skeletonData = [],
  toolData = [],
  width = 640,
  height = 360,
  autoPlay = false,
  videoType,
  onTimeUpdate
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

  // Debug log
  useEffect(() => {
    console.log('VideoPlayer received data:', {
      videoUrl,
      skeletonData_length: skeletonData?.length,
      toolData_length: toolData?.length,
      first_skeleton: skeletonData?.[0],
      first_tool: toolData?.[0]
    })
  }, [videoUrl, skeletonData, toolData])
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [canvasSize, setCanvasSize] = useState({ width: 640, height: 360 })
  const animationFrameRef = useRef<number>()
  const trajectoryRef = useRef<Map<number, Array<{x: number, y: number, timestamp: number}>>>(new Map())
  const lastDrawnFrameRef = useRef<number>(-1)
  const lastCanvasStateRef = useRef<ImageData | null>(null)
  const frameSkipCountRef = useRef<number>(0)

  // オーバーレイ表示設定
  const [showSkeleton, setShowSkeleton] = useState(true)
  const [showInstruments, setShowInstruments] = useState(hasInstrumentData)
  const [showTrajectory, setShowTrajectory] = useState(false)

  // 現在のフレームに対応するデータを取得（新形式対応）
  const getCurrentData = (timestamp: number) => {
    // タイムスタンプのわずかな調整（同期改善のため）
    const adjustedTimestamp = timestamp + 0.02

    // 最も近いフレームを探す（新形式: 1フレーム = 1レコード）
    let currentSkeletonFrame: SkeletonData | undefined
    if (skeletonData.length > 0) {
      currentSkeletonFrame = skeletonData.find(
        data => Math.abs(data.timestamp - adjustedTimestamp) < 0.04
      )

      // 見つからない場合は最近傍
      if (!currentSkeletonFrame) {
        currentSkeletonFrame = skeletonData.reduce((prev, curr) => {
          const prevDiff = Math.abs(prev.timestamp - adjustedTimestamp)
          const currDiff = Math.abs(curr.timestamp - adjustedTimestamp)
          return currDiff < prevDiff ? curr : prev
        })
      }
    }

    let currentTools = toolData.find(
      data => Math.abs(data.timestamp - adjustedTimestamp) < 0.04
    )

    if (!currentTools && toolData.length > 0) {
      currentTools = toolData.reduce((prev, curr) =>
        Math.abs(curr.timestamp - timestamp) < Math.abs(prev.timestamp - timestamp) ? curr : prev
      )
    }

    return { skeletonFrame: currentSkeletonFrame, tools: currentTools }
  }

  // オーバーレイを描画（最適化版）
  const drawOverlay = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const video = videoRef.current
    const currentTimestamp = video.currentTime

    // フレームスキップ最適化（同じフレームを再描画しない）
    const currentFrame = Math.floor(currentTimestamp * 30) // 30fpsと仮定
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

        // バウンディングボックスを描画（外部カメラ用の器具は紫色）
        const isExternalInstrument = videoType === 'external_with_instruments'
        ctx.strokeStyle = isExternalInstrument ? '#9333EA' : '#FF0000'
        ctx.lineWidth = 3

        // Phase 2.5: 回転BBoxが存在する場合は回転矩形を描画
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
          // 従来の矩形BBox
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
        }

        // 背景付きラベルを描画
        ctx.fillStyle = isExternalInstrument ? '#9333EA' : '#FF0000'
        ctx.font = 'bold 14px Arial'
        const label = `${detection.class_name} (${(detection.confidence * 100).toFixed(0)}%)`
        const textWidth = ctx.measureText(label).width

        // ラベル背景
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
        ctx.fillRect(x1, y1 - 22, textWidth + 8, 20)

        // ラベルテキスト
        ctx.fillStyle = '#FFFFFF'
        ctx.fillText(label, x1 + 4, y1 - 6)

        // 追跡IDがある場合
        if (detection.track_id !== undefined) {
          ctx.fillStyle = 'rgba(255, 255, 0, 0.9)'
          ctx.font = 'bold 12px Arial'
          ctx.fillText(`ID: ${detection.track_id}`, x2 - 35, y1 - 6)
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

        // 軌跡データの更新と描画
        if (showTrajectory && detection.track_id !== undefined) {
          // 軌跡データを更新
          if (!trajectoryRef.current.has(detection.track_id)) {
            trajectoryRef.current.set(detection.track_id, [])
          }
          const trajectory = trajectoryRef.current.get(detection.track_id)!
          trajectory.push({ x: centerX, y: centerY, timestamp: currentTimestamp })

          // 古いデータを削除（最大100点保持）
          if (trajectory.length > 100) {
            trajectory.shift()
          }

          // 軌跡を描画
          if (trajectory.length > 1) {
            ctx.strokeStyle = isExternalInstrument ? 'rgba(147, 51, 234, 0.5)' : 'rgba(255, 0, 0, 0.5)'
            ctx.lineWidth = 2
            ctx.setLineDash([5, 5])
            ctx.beginPath()

            for (let i = 1; i < trajectory.length; i++) {
              const prev = trajectory[i - 1]
              const curr = trajectory[i]

              // 時間による透明度のグラデーション
              const age = (currentTimestamp - curr.timestamp) / 3 // 3秒でフェードアウト
              const opacity = Math.max(0, 1 - age)
              ctx.globalAlpha = opacity * 0.7

              if (i === 1) {
                ctx.moveTo(prev.x, prev.y)
              }
              ctx.lineTo(curr.x, curr.y)
            }

            ctx.stroke()
            ctx.setLineDash([])
            ctx.globalAlpha = 1
          }
        }
      })
    }

    // 次のフレームで再描画（最適化されたRAF）
    if (isPlaying) {
      animationFrameRef.current = requestAnimationFrame(drawOverlay)
    }
  }, [isPlaying, showSkeleton, showInstruments, showTrajectory, skeletonData, toolData, videoType])

  // 動画の再生/一時停止
  const togglePlay = () => {
    if (!videoRef.current) return
    
    if (videoRef.current.paused) {
      videoRef.current.play()
      setIsPlaying(true)
    } else {
      videoRef.current.pause()
      setIsPlaying(false)
    }
  }

  // 動画の時間更新（デバウンス付き）
  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current) return
    const time = videoRef.current.currentTime
    setCurrentTime(time)

    // 描画をスロットル（再生中のみ）
    if (!isPlaying || Math.abs(time - currentTime) > 0.033) { // 30fps以上の更新を制限
      drawOverlay()
    }

    // 外部にも通知
    if (onTimeUpdate) {
      onTimeUpdate(time)
    }
  }, [currentTime, isPlaying, drawOverlay, onTimeUpdate])

  // 動画のメタデータ読み込み完了
  const handleLoadedMetadata = () => {
    if (!videoRef.current) return
    setDuration(videoRef.current.duration)

    // 初期描画を実行
    drawOverlay()
  }

  // シーク処理
  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (!videoRef.current) return
    const newTime = parseFloat(e.target.value)
    videoRef.current.currentTime = newTime
    setCurrentTime(newTime)
    lastDrawnFrameRef.current = -1 // フレームキャッシュをリセット
    drawOverlay()
  }, [drawOverlay])

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
      setIsPlaying(true)
      drawOverlay()
    }
    const handlePause = () => {
      setIsPlaying(false)
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }

    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)

    return () => {
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [])

  // データが更新されたら再描画
  useEffect(() => {
    if (skeletonData.length > 0 || toolData.length > 0) {
      console.log('Data updated, triggering redraw')
      drawOverlay()
    }
  }, [skeletonData, toolData])

  // 表示設定が変更されたら再描画
  useEffect(() => {
    drawOverlay()
  }, [showSkeleton, showInstruments, showTrajectory])

  // 時間フォーマット
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

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
            onCanPlay={(e) => console.log('Video can play:', e.currentTarget.src)}
            onLoadStart={(e) => console.log('Video load started:', e.currentTarget.src)}
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
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={showTrajectory}
              onChange={(e) => setShowTrajectory(e.target.checked)}
            />
            <span>軌跡表示</span>
          </label>
        </div>
      </div>
    </div>
  )
}