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
}

export default function VideoPlayer({
  videoUrl,
  skeletonData = [],
  toolData = [],
  width = 640,
  height = 360,
  autoPlay = false
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const animationFrameRef = useRef<number>()

  // 現在のフレームに対応するデータを取得
  const getCurrentData = (timestamp: number) => {
    const currentSkeleton = skeletonData.find(
      data => Math.abs(data.timestamp - timestamp) < 0.1
    )
    const currentTools = toolData.find(
      data => Math.abs(data.timestamp - timestamp) < 0.1
    )
    return { skeleton: currentSkeleton, tools: currentTools }
  }

  // オーバーレイを描画
  const drawOverlay = () => {
    if (!videoRef.current || !canvasRef.current) return
    
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const video = videoRef.current
    const currentTimestamp = video.currentTime

    // キャンバスをクリア
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const { skeleton, tools } = getCurrentData(currentTimestamp)

    // 骨格データを描画
    if (skeleton?.landmarks) {
      ctx.strokeStyle = '#00FF00'
      ctx.lineWidth = 2
      ctx.fillStyle = '#00FF00'

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

      // 点を描画
      Object.values(skeleton.landmarks).forEach((point) => {
        if (point) {
          ctx.beginPath()
          ctx.arc(
            point.x * canvas.width,
            point.y * canvas.height,
            4,
            0,
            2 * Math.PI
          )
          ctx.fill()
        }
      })
    }

    // 器具検出データを描画
    if (tools?.detections) {
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
    setCurrentTime(videoRef.current.currentTime)
    drawOverlay()
  }

  // 動画のメタデータ読み込み完了
  const handleLoadedMetadata = () => {
    if (!videoRef.current) return
    setDuration(videoRef.current.duration)
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

  // 時間フォーマット
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  // テスト用のサンプル動画URL（実際のAPIからの動画URLがない場合）
  const sampleVideoUrl = videoUrl || '/sample-video.mp4'

  return (
    <div className="video-player-container w-full">
      <div className="relative w-full" style={{ aspectRatio: '16/9', maxHeight: height }}>
        {/* ビデオ要素 */}
        <video
          ref={videoRef}
          src={sampleVideoUrl}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          autoPlay={autoPlay}
          className="absolute top-0 left-0 w-full h-full bg-black object-contain"
          controls={false}
        />
        
        {/* オーバーレイキャンバス */}
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
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
            <input type="checkbox" defaultChecked />
            <span>骨格表示</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" defaultChecked />
            <span>器具検出表示</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" />
            <span>軌跡表示</span>
          </label>
        </div>
      </div>
    </div>
  )
}