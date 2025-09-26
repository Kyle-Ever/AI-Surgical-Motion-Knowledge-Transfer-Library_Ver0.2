'use client'

import { useRef, useEffect, useState } from 'react'

interface Coordinate {
  x: number
  y: number
  z?: number
}

interface SkeletonData {
  frame_number: number
  timestamp: number
  landmarks?: Record<string, Coordinate>
}

interface ToolDetection {
  bbox: [number, number, number, number]
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

  // Disable instrument overlay for external camera without instruments
  const isExternalCamera = videoType === 'external' || videoType === 'external_no_instruments'
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

  // オーバーレイ表示設定
  const [showSkeleton, setShowSkeleton] = useState(true)
  const [showInstruments, setShowInstruments] = useState(true)
  const [showTrajectory, setShowTrajectory] = useState(false)

  // 現在のフレームに対応するデータを取得
  const getCurrentData = (timestamp: number) => {
    // より柔軟なタイムスタンプマッチング
    // 複数の手（両手）のデータを取得
    let currentSkeletons = skeletonData.filter(
      data => Math.abs(data.timestamp - timestamp) < 0.05  // 0.1から0.05に変更
    )
    let currentTools = toolData.find(
      data => Math.abs(data.timestamp - timestamp) < 0.05
    )

    // データが見つからない場合、最も近いフレームを使用
    if (currentSkeletons.length === 0 && skeletonData.length > 0) {
      // 最も近いタイムスタンプを見つける
      const nearestTimestamp = skeletonData.reduce((prev, curr) =>
        Math.abs(curr.timestamp - timestamp) < Math.abs(prev.timestamp - timestamp) ? curr : prev
      ).timestamp

      // そのタイムスタンプの全ての手のデータを取得
      currentSkeletons = skeletonData.filter(
        data => Math.abs(data.timestamp - nearestTimestamp) < 0.01
      )

      if (currentSkeletons.length > 0) {
        console.log('Using nearest skeleton frames:', currentSkeletons.map(s => s.frame_number), 'for timestamp:', timestamp)
      }
    }

    if (!currentTools && toolData.length > 0) {
      currentTools = toolData.reduce((prev, curr) =>
        Math.abs(curr.timestamp - timestamp) < Math.abs(prev.timestamp - timestamp) ? curr : prev
      )
      console.log('Using nearest tool frame:', currentTools.frame_number, 'for timestamp:', timestamp)
    }

    return { skeletons: currentSkeletons, tools: currentTools }
  }

  // オーバーレイを描画
  const drawOverlay = () => {
    if (!videoRef.current || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const video = videoRef.current
    const currentTimestamp = video.currentTime

    // キャンバスサイズを動画サイズに合わせる
    if (video.videoWidth && video.videoHeight) {
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        setCanvasSize({ width: video.videoWidth, height: video.videoHeight })
        console.log('Canvas resized to:', video.videoWidth, 'x', video.videoHeight)
      }
    }

    // キャンバスをクリア
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const { skeletons, tools } = getCurrentData(currentTimestamp)

    // 骨格データを描画（複数の手に対応）
    if (showSkeleton && skeletons.length > 0) {
      skeletons.forEach((skeleton, handIndex) => {
        if (!skeleton?.landmarks) return

        // 手ごとに色を変える（左手：青、右手：緑）
        const isLeftHand = skeleton.hand_type === 'Left'
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
          const startPoint = skeleton.landmarks[`point_${start}`]
          const endPoint = skeleton.landmarks[`point_${end}`]

          if (startPoint && endPoint) {
            ctx.beginPath()
            ctx.moveTo(startPoint.x * canvas.width, startPoint.y * canvas.height)
            ctx.lineTo(endPoint.x * canvas.width, endPoint.y * canvas.height)
            ctx.stroke()
          }
        })

        // 点を描画（より大きく、目立つように）
        ctx.fillStyle = pointColor
        Object.entries(skeleton.landmarks).forEach(([key, point]: [string, any]) => {
          if (point && point.x !== undefined && point.y !== undefined) {
            // 座標変換（0-1の正規化座標を画面座標に変換）
            const screenX = point.x * canvas.width
            const screenY = point.y * canvas.height

            ctx.beginPath()
            ctx.arc(screenX, screenY, 5, 0, 2 * Math.PI)
            ctx.fill()

            // デバッグ用：主要ポイントのみランドマーク番号を表示
            const keyPoints = ['0', '4', '8', '12', '16', '20'] // 手首と各指先
            const num = key.replace('point_', '')
            if (keyPoints.includes(num)) {
              ctx.fillStyle = '#FFFFFF'
              ctx.font = 'bold 12px Arial'
              ctx.fillText(num, screenX + 8, screenY - 8)
              ctx.fillStyle = pointColor
            }
          }
        })

        // 手のタイプを表示
        if (skeleton.landmarks.point_0) {
          const wristPoint = skeleton.landmarks.point_0
          ctx.fillStyle = handColor
          ctx.font = 'bold 14px Arial'
          ctx.fillText(
            skeleton.hand_type || (isLeftHand ? 'Left' : 'Right'),
            wristPoint.x * canvas.width,
            wristPoint.y * canvas.height - 20
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
        
        // バウンディングボックスを描画
        ctx.strokeStyle = '#FF0000'
        ctx.lineWidth = 2
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
        
        // ラベルを描画
        ctx.fillStyle = '#FF0000'
        ctx.font = '12px Arial'
        const label = `${detection.class_name} (${(detection.confidence * 100).toFixed(0)}%)`
        ctx.fillText(label, x1, y1 - 5)
        
        // 追跡IDがある場合
        if (detection.track_id !== undefined) {
          ctx.fillStyle = '#FFFF00'
          ctx.fillText(`#${detection.track_id}`, x2 - 20, y1 - 5)
        }
      })
    }

    // 次のフレームで再描画
    if (isPlaying) {
      animationFrameRef.current = requestAnimationFrame(drawOverlay)
    }
  }

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

  // 動画の時間更新
  const handleTimeUpdate = () => {
    if (!videoRef.current) return
    const time = videoRef.current.currentTime
    setCurrentTime(time)
    drawOverlay()
    // 外部にも通知
    if (onTimeUpdate) {
      onTimeUpdate(time)
    }
  }

  // 動画のメタデータ読み込み完了
  const handleLoadedMetadata = () => {
    if (!videoRef.current) return
    setDuration(videoRef.current.duration)

    // 初期描画を実行
    drawOverlay()
  }

  // シーク処理
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!videoRef.current) return
    const newTime = parseFloat(e.target.value)
    videoRef.current.currentTime = newTime
    setCurrentTime(newTime)
    drawOverlay()
  }

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
            className={`flex items-center space-x-2 ${!hasInstrumentData || isExternalCamera ? 'opacity-50' : ''}`}
            title={
              isExternalCamera
                ? '外部カメラでは器具検出は利用できません'
                : !hasInstrumentData
                  ? '器具が登録されていません'
                  : ''
            }
          >
            <input
              type="checkbox"
              checked={showInstruments}
              onChange={(e) => setShowInstruments(e.target.checked)}
              disabled={!hasInstrumentData}
            />
            <span className={!hasInstrumentData ? 'text-gray-400' : ''}>
              器具検出表示
              {!hasInstrumentData ? ' (データなし)' : ''}
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