'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Eye, Activity, TrendingUp, Download, Play, Pause, MapPin } from 'lucide-react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)


interface GazeAnalysis {
  id: string
  video_id: string
  video?: {
    original_filename: string
    surgery_name?: string
    surgeon_name?: string
  }
  status: string
  created_at: string
  completed_at?: string
  total_frames: number
  gaze_data?: {
    frames: {
      frame_index: number
      timestamp: number
      fixations: ({ x: number; y: number } | [number, number])[]
      stats: {
        max_value: number
        mean_value: number
        high_attention_ratio: number
      }
    }[]
    summary: {
      total_frames: number
      total_fixations: number
      average_fixations_per_frame: number
      attention_hotspots?: number[][]
      effective_fps?: number
      total_duration?: number
      source_frame_resolution?: [number, number]
      target_video_resolution?: [number, number]
      scale_factor?: number
    }
    params?: Record<string, unknown>
  }
}

export default function GazeDashboardClient({ analysisId }: { analysisId: string }) {
  const router = useRouter()
  const [analysis, setAnalysis] = useState<GazeAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [heatmapWindow, setHeatmapWindow] = useState(1.0) // ±1秒の時間窓（合計2秒）

  const videoRef = useRef<HTMLVideoElement>(null)
  const leftCanvasRef = useRef<HTMLCanvasElement>(null)
  const rightCanvasRef = useRef<HTMLCanvasElement>(null)
  const animationFrameRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    fetchAnalysisData()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId])

  useEffect(() => {
    if (analysis && analysis.gaze_data && videoRef.current) {
      const video = videoRef.current

      const handleTimeUpdate = () => {
        setCurrentTime(video.currentTime)
      }

      video.addEventListener('timeupdate', handleTimeUpdate)

      return () => {
        video.removeEventListener('timeupdate', handleTimeUpdate)
      }
    }
  }, [analysis])

  useEffect(() => {
    if (!analysis?.gaze_data || !videoRef.current) return

    const animate = () => {
      if (videoRef.current && leftCanvasRef.current && rightCanvasRef.current) {
        drawBothCanvases()
      }
      animationFrameRef.current = requestAnimationFrame(animate)
    }

    animationFrameRef.current = requestAnimationFrame(animate)

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysis, heatmapWindow])

  const fetchAnalysisData = async () => {
    try {
      setLoading(true)
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'
      const response = await fetch(`${apiUrl}/analysis/${analysisId}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch analysis data: ${response.statusText}`)
      }

      const data = await response.json()
      setAnalysis(data)
    } catch (err) {
      console.error('Error fetching analysis:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const normalizePoint = (point: { x: number; y: number } | [number, number]) => {
    if (Array.isArray(point)) {
      return { x: point[0], y: point[1] }
    }
    return point
  }

  const getCurrentFrameIndex = useCallback((): number => {
    if (!analysis?.gaze_data || !videoRef.current) return 0

    const currentTime = videoRef.current.currentTime
    const frames = analysis.gaze_data.frames

    // Find the closest frame to current time
    let closestIndex = 0
    let minDiff = Math.abs(frames[0].timestamp - currentTime)

    for (let i = 1; i < frames.length; i++) {
      const diff = Math.abs(frames[i].timestamp - currentTime)
      if (diff < minDiff) {
        minDiff = diff
        closestIndex = i
      }
    }

    return closestIndex
  }, [analysis])

  const getFramesInTimeWindow = useCallback((centerTime: number, windowSeconds: number) => {
    if (!analysis?.gaze_data) return []

    const frames = analysis.gaze_data.frames
    return frames.filter(f =>
      Math.abs(f.timestamp - centerTime) <= windowSeconds
    )
  }, [analysis])

  const drawBothCanvases = useCallback(() => {
    if (!analysis?.gaze_data || !videoRef.current || !leftCanvasRef.current || !rightCanvasRef.current) return

    const video = videoRef.current
    if (video.readyState < 2) return // Wait for video to be ready

    const leftCanvas = leftCanvasRef.current
    const rightCanvas = rightCanvasRef.current
    const leftCtx = leftCanvas.getContext('2d')
    const rightCtx = rightCanvas.getContext('2d')

    if (!leftCtx || !rightCtx) return

    const currentFrameIndex = getCurrentFrameIndex()
    const currentFrame = analysis.gaze_data.frames[currentFrameIndex]

    if (!currentFrame) return

    // 左Canvas: 動画 + ゲーズプロットオーバーレイ
    leftCtx.clearRect(0, 0, leftCanvas.width, leftCanvas.height)
    leftCtx.drawImage(video, 0, 0, leftCanvas.width, leftCanvas.height)
    drawFixationsOverlay(leftCtx, currentFrame, leftCanvas)

    // 右Canvas: 動画 + リアルタイムヒートマップ
    rightCtx.clearRect(0, 0, rightCanvas.width, rightCanvas.height)
    rightCtx.drawImage(video, 0, 0, rightCanvas.width, rightCanvas.height)
    drawRealtimeHeatmap(rightCtx, currentFrame.timestamp, rightCanvas)
  }, [analysis, getCurrentFrameIndex, getFramesInTimeWindow, heatmapWindow])

  const drawFixationsOverlay = (
    ctx: CanvasRenderingContext2D,
    frame: NonNullable<GazeAnalysis['gaze_data']>['frames'][0],
    canvas: HTMLCanvasElement
  ) => {
    const fixations = frame.fixations
    if (!fixations || fixations.length === 0) return

    // Get actual video resolution from summary (fallback to 362x260 - actual video size)
    const videoWidth = analysis?.gaze_data?.summary?.target_video_resolution?.[0] || 362
    const videoHeight = analysis?.gaze_data?.summary?.target_video_resolution?.[1] || 260

    // Draw lines connecting fixations
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)'
    ctx.lineWidth = 3
    ctx.beginPath()
    fixations.forEach((point: { x: number; y: number } | [number, number], i: number) => {
      const normalized = normalizePoint(point)
      const x = (normalized.x / videoWidth) * canvas.width
      const y = (normalized.y / videoHeight) * canvas.height
      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })
    ctx.stroke()

    // Draw fixation circles
    fixations.forEach((point: { x: number; y: number } | [number, number], i: number) => {
      const normalized = normalizePoint(point)
      const x = (normalized.x / videoWidth) * canvas.width
      const y = (normalized.y / videoHeight) * canvas.height

      // White outline
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.beginPath()
      ctx.arc(x, y, 10, 0, 2 * Math.PI)
      ctx.fill()

      // Green center
      ctx.fillStyle = 'rgba(0, 255, 0, 0.8)'
      ctx.beginPath()
      ctx.arc(x, y, 7, 0, 2 * Math.PI)
      ctx.fill()

      // Number label for first 10
      if (i < 10) {
        ctx.fillStyle = 'white'
        ctx.font = 'bold 14px sans-serif'
        ctx.strokeStyle = 'black'
        ctx.lineWidth = 3
        ctx.strokeText(String(i + 1), x + 15, y - 10)
        ctx.fillText(String(i + 1), x + 15, y - 10)
      }
    })
  }

  const drawRealtimeHeatmap = (
    ctx: CanvasRenderingContext2D,
    centerTime: number,
    canvas: HTMLCanvasElement
  ) => {
    const relevantFrames = getFramesInTimeWindow(centerTime, heatmapWindow)

    if (relevantFrames.length === 0) return

    const width = canvas.width
    const height = canvas.height

    // Get actual video resolution from summary (fallback to 1920x1080 if not available)
    const videoWidth = analysis?.gaze_data?.summary?.target_video_resolution?.[0] || 1920
    const videoHeight = analysis?.gaze_data?.summary?.target_video_resolution?.[1] || 1080

    // Create heat accumulation map
    const heatMap: number[][] = Array(height).fill(0).map(() => Array(width).fill(0))

    // Accumulate fixations from time window
    relevantFrames.forEach(frame => {
      frame.fixations.forEach(point => {
        const normalized = normalizePoint(point)
        const x = Math.floor((normalized.x / videoWidth) * width)
        const y = Math.floor((normalized.y / videoHeight) * height)

        // Add gaussian blur around each fixation (smaller radius for focused heatmap)
        const radius = 30
        for (let dy = -radius; dy <= radius; dy++) {
          for (let dx = -radius; dx <= radius; dx++) {
            const px = x + dx
            const py = y + dy
            if (px >= 0 && px < width && py >= 0 && py < height) {
              const distance = Math.sqrt(dx * dx + dy * dy)
              if (distance <= radius) {
                const intensity = Math.exp(-(distance * distance) / (2 * (radius / 3) ** 2))
                heatMap[py][px] += intensity
              }
            }
          }
        }
      })
    })

    // Find max value for normalization
    let maxHeat = 0
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        maxHeat = Math.max(maxHeat, heatMap[y][x])
      }
    }

    // Draw heatmap overlay on top of existing video
    // Use fillRect to blend heatmap colors over video
    // Enhanced sensitivity: lower threshold, higher opacity, stronger normalization
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        // Enhanced contrast by dividing by 15% of maxHeat (was 30%)
        const normalizedValue = maxHeat > 0 ? heatMap[y][x] / (maxHeat * 0.15) : 0
        const value = Math.min(1.0, normalizedValue) // Clamp to 1.0

        if (value > 0.005) { // Lower threshold for more visible changes (was 0.01)
          const color = getJetColor(value)
          const alpha = Math.min(0.7, value * 0.6) // Semi-transparent for subtle overlay

          // Blend heatmap color over video
          ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`
          ctx.fillRect(x, y, 1, 1)
        }
      }
    }
  }

  const getJetColor = (value: number): [number, number, number] => {
    const v = Math.max(0, Math.min(1, value))

    let r, g, b
    if (v < 0.25) {
      r = 0
      g = Math.floor(v * 4 * 255)
      b = 255
    } else if (v < 0.5) {
      r = 0
      g = 255
      b = Math.floor(255 - (v - 0.25) * 4 * 255)
    } else if (v < 0.75) {
      r = Math.floor((v - 0.5) * 4 * 255)
      g = 255
      b = 0
    } else {
      r = 255
      g = Math.floor(255 - (v - 0.75) * 4 * 255)
      b = 0
    }

    return [r, g, b]
  }

  const handlePlayPause = () => {
    if (!videoRef.current) return

    if (isPlaying) {
      videoRef.current.pause()
      setIsPlaying(false)
    } else {
      videoRef.current.play()
      setIsPlaying(true)
    }
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!videoRef.current || !analysis?.gaze_data) return

    const newTime = Number(e.target.value)
    videoRef.current.currentTime = newTime
    setCurrentTime(newTime)
  }

  const handleExport = async () => {
    try {
      const dataStr = JSON.stringify(analysis, null, 2)
      const blob = new Blob([dataStr], { type: 'application/json' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `gaze_analysis_${analysisId}.json`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export failed:', error)
      alert('エクスポートに失敗しました')
    }
  }

  // Prepare chart data for fixation coordinates over time
  const getFixationChartData = () => {
    if (!analysis?.gaze_data) return null

    const frames = analysis.gaze_data.frames

    // 現在の動画再生位置までのフレームのみを表示
    const currentFrameIndex = getCurrentFrameIndex()
    const visibleFrames = frames.slice(0, currentFrameIndex + 1)

    const timestamps = visibleFrames.map(f => f.timestamp.toFixed(2))

    // Average X and Y coordinates per frame
    const avgX = visibleFrames.map(f => {
      if (f.fixations.length === 0) return null
      const sum = f.fixations.reduce((acc, p) => {
        const normalized = normalizePoint(p)
        return acc + normalized.x
      }, 0)
      return sum / f.fixations.length
    })

    const avgY = visibleFrames.map(f => {
      if (f.fixations.length === 0) return null
      const sum = f.fixations.reduce((acc, p) => {
        const normalized = normalizePoint(p)
        return acc + normalized.y
      }, 0)
      return sum / f.fixations.length
    })

    // Y軸の範囲を動的に調整（変化量を体感しやすくする）
    const validX = avgX.filter((v): v is number => v !== null)
    const validY = avgY.filter((v): v is number => v !== null)
    const minX = validX.length > 0 ? Math.min(...validX) : 0
    const maxX = validX.length > 0 ? Math.max(...validX) : 362
    const minY = validY.length > 0 ? Math.min(...validY) : 0
    const maxY = validY.length > 0 ? Math.max(...validY) : 260

    return {
      labels: timestamps,
      datasets: [
        {
          label: 'X座標',
          data: avgX,
          borderColor: 'rgb(255, 99, 132)',
          backgroundColor: 'rgba(255, 99, 132, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'Y座標',
          data: avgY,
          borderColor: 'rgb(54, 162, 235)',
          backgroundColor: 'rgba(54, 162, 235, 0.1)',
          fill: true,
          tension: 0.4
        }
      ],
      // Y軸の範囲を指定（マージンを追加）
      suggestedMin: Math.floor(Math.min(minX, minY) * 0.9),
      suggestedMax: Math.ceil(Math.max(maxX, maxY) * 1.1)
    }
  }

  // Prepare chart data for attention stats over time
  const getAttentionChartData = () => {
    if (!analysis?.gaze_data) return null

    const frames = analysis.gaze_data.frames

    // 現在の動画再生位置までのフレームのみを表示
    const currentFrameIndex = getCurrentFrameIndex()
    const visibleFrames = frames.slice(0, currentFrameIndex + 1)

    const timestamps = visibleFrames.map(f => f.timestamp.toFixed(2))
    const maxValues = visibleFrames.map(f => f.stats.max_value * 100)
    const meanValues = visibleFrames.map(f => f.stats.mean_value * 100)
    const highRatios = visibleFrames.map(f => f.stats.high_attention_ratio * 100)

    // Y軸の範囲を動的に調整（変化量を体感しやすくする）
    const allValues = [...meanValues, ...highRatios]
    const validValues = allValues.filter(v => v !== null && !isNaN(v))
    const minValue = validValues.length > 0 ? Math.min(...validValues) : 0
    const maxValue = validValues.length > 0 ? Math.max(...validValues) : 100

    return {
      labels: timestamps,
      datasets: [
        {
          label: '最大注目度 (%)',
          data: maxValues,
          borderColor: 'rgb(255, 206, 86)',
          backgroundColor: 'rgba(255, 206, 86, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: '平均注目度 (%)',
          data: meanValues,
          borderColor: 'rgb(75, 192, 192)',
          backgroundColor: 'rgba(75, 192, 192, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: '高注目領域比率 (%)',
          data: highRatios,
          borderColor: 'rgb(153, 102, 255)',
          backgroundColor: 'rgba(153, 102, 255, 0.1)',
          fill: true,
          tension: 0.4
        }
      ],
      // Y軸の範囲を指定（変化量を見やすくする）
      suggestedMin: Math.max(0, Math.floor(minValue * 0.8)),
      suggestedMax: Math.min(100, Math.ceil(maxValue * 1.2))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-gray-600">視線解析データを読み込み中...</p>
        </div>
      </div>
    )
  }

  if (error || !analysis) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Eye className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">データの読み込みに失敗しました</h2>
          <p className="text-gray-600 mb-4">{error || '不明なエラー'}</p>
          <button
            onClick={() => router.push('/library')}
            className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
          >
            ライブラリに戻る
          </button>
        </div>
      </div>
    )
  }

  const gazeData = analysis.gaze_data
  const currentFrameIndex = getCurrentFrameIndex()
  const currentFrame = gazeData?.frames?.[currentFrameIndex]
  const fixationChartData = getFixationChartData()
  const attentionChartData = getAttentionChartData()
  const totalDuration = gazeData?.summary?.total_duration || 0

  const videoUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'}/videos/${analysis.video_id}/stream`

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center">
              <Eye className="w-8 h-8 text-orange-600 mr-3" />
              視線解析ダッシュボード
            </h1>
            <p className="text-gray-600 mt-2">
              {analysis.video?.surgery_name || analysis.video?.original_filename || 'Unknown Video'}
            </p>
            {analysis.video?.surgeon_name && (
              <p className="text-sm text-gray-500">執刀医: {analysis.video.surgeon_name}</p>
            )}
          </div>
          <div className="flex space-x-2">
            <button
              onClick={handleExport}
              className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
            >
              <Download className="w-4 h-4" />
              <span>エクスポート</span>
            </button>
            <button
              onClick={() => router.push('/library')}
              className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
            >
              ライブラリに戻る
            </button>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      {gazeData?.summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">総フレーム数</p>
                <p className="text-2xl font-bold text-gray-900">{gazeData.summary.total_frames}</p>
              </div>
              <Activity className="w-10 h-10 text-orange-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">総ゲーズプロット数</p>
                <p className="text-2xl font-bold text-gray-900">
                  {gazeData.summary.total_fixations}
                </p>
              </div>
              <MapPin className="w-10 h-10 text-blue-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">平均ゲーズプロット数/フレーム</p>
                <p className="text-2xl font-bold text-gray-900">
                  {gazeData.summary.average_fixations_per_frame.toFixed(1)}
                </p>
              </div>
              <TrendingUp className="w-10 h-10 text-green-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">動画時間</p>
                <p className="text-2xl font-bold text-gray-900">
                  {totalDuration.toFixed(1)}秒
                </p>
              </div>
              <Eye className="w-10 h-10 text-purple-500" />
            </div>
          </div>
        </div>
      )}

      {/* 左右2分割動画プレイヤー */}
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">視線解析動画（左: ゲーズプロット / 右: ヒートマップ）</h2>

        {/* 隠しvideo要素（Canvasソース用） */}
        <video
          ref={videoRef}
          src={videoUrl}
          style={{ position: 'absolute', visibility: 'hidden', width: '1px', height: '1px' }}
          muted
          playsInline
        />

        {/* 左右2列グリッド（縮小版） */}
        <div className="grid grid-cols-2 gap-6 mb-4 max-w-4xl mx-auto">
          {/* 左: ゲーズプロットオーバーレイ */}
          <div className="relative">
            <div className="relative bg-black rounded-lg overflow-hidden shadow-md" style={{ aspectRatio: '362/260' }}>
              <canvas
                ref={leftCanvasRef}
                width={362}
                height={260}
                className="w-full h-full object-contain"
              />
            </div>
            <p className="text-center text-sm text-gray-600 mt-2 font-medium">ゲーズプロットの動き</p>
          </div>

          {/* 右: リアルタイムヒートマップ */}
          <div className="relative">
            <div className="relative bg-black rounded-lg overflow-hidden shadow-md" style={{ aspectRatio: '362/260' }}>
              <canvas
                ref={rightCanvasRef}
                width={362}
                height={260}
                className="w-full h-full object-contain"
              />
            </div>
            <p className="text-center text-sm text-gray-600 mt-2 font-medium">
              視線ヒートマップ（±{heatmapWindow}秒）
            </p>
          </div>
        </div>

        {/* Playback Controls */}
        <div className="mt-4">
          <div className="flex items-center space-x-4">
            <button
              onClick={handlePlayPause}
              className="flex items-center space-x-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              <span>{isPlaying ? '一時停止' : '再生'}</span>
            </button>
            <div className="flex-1">
              <input
                type="range"
                min="0"
                max={totalDuration}
                step="0.1"
                value={currentTime}
                onChange={handleSeek}
                className="w-full"
              />
            </div>
            <span className="text-sm text-gray-600 min-w-[120px] text-right">
              {currentTime.toFixed(2)}秒 / {totalDuration.toFixed(1)}秒
            </span>
          </div>

          {/* ヒートマップ時間窓調整 */}
          <div className="mt-3 flex items-center space-x-3">
            <label className="text-sm text-gray-600">ヒートマップ時間窓:</label>
            <select
              value={heatmapWindow}
              onChange={(e) => setHeatmapWindow(Number(e.target.value))}
              className="px-3 py-1 border border-gray-300 rounded-lg text-sm"
            >
              <option value={1}>±1秒</option>
              <option value={2}>±2秒</option>
              <option value={3}>±3秒</option>
              <option value={5}>±5秒</option>
            </select>
          </div>
        </div>

        {/* Current Frame Stats */}
        {currentFrame && (
          <div className="mt-4 grid grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-600">フレーム時刻</p>
              <p className="text-lg font-semibold text-gray-900">
                {currentFrame.timestamp.toFixed(2)}秒
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-600">ゲーズプロット数</p>
              <p className="text-lg font-semibold text-gray-900">
                {currentFrame.fixations.length}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-600">平均注目度</p>
              <p className="text-lg font-semibold text-gray-900">
                {(currentFrame.stats.mean_value * 100).toFixed(1)}%
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-600">高注目領域比率</p>
              <p className="text-lg font-semibold text-gray-900">
                {(currentFrame.stats.high_attention_ratio * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Fixation Coordinate Charts */}
      {fixationChartData && (
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">ゲーズプロット座標の時系列変化</h2>
          <Line
            data={fixationChartData}
            options={{
              responsive: true,
              maintainAspectRatio: true,
              aspectRatio: 2.5,
              animation: {
                duration: 0 // アニメーションを無効化してスムーズに
              },
              plugins: {
                legend: {
                  position: 'top' as const,
                },
                title: {
                  display: false
                }
              },
              scales: {
                y: {
                  min: fixationChartData.suggestedMin,
                  max: fixationChartData.suggestedMax,
                  title: {
                    display: true,
                    text: '座標 (px)'
                  }
                },
                x: {
                  title: {
                    display: true,
                    text: '時間 (秒)'
                  }
                }
              }
            }}
          />
        </div>
      )}

      {/* Attention Stats Charts */}
      {attentionChartData && (
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">注目度の時系列変化</h2>
          <Line
            data={attentionChartData}
            options={{
              responsive: true,
              maintainAspectRatio: true,
              aspectRatio: 2.5,
              animation: {
                duration: 0 // アニメーションを無効化してスムーズに
              },
              plugins: {
                legend: {
                  position: 'top' as const,
                },
                title: {
                  display: false
                }
              },
              scales: {
                y: {
                  min: attentionChartData.suggestedMin,
                  max: attentionChartData.suggestedMax,
                  title: {
                    display: true,
                    text: '注目度 (%)'
                  }
                },
                x: {
                  title: {
                    display: true,
                    text: '時間 (秒)'
                  }
                }
              }
            }}
          />
        </div>
      )}

      {/* Color Legend */}
      <div className="bg-white rounded-lg shadow p-6 mt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">表示の見方</h3>

        <div className="mb-4">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">ヒートマップカラー:</h4>
          <div className="flex-1">
            <div className="h-8 rounded-lg" style={{
              background: 'linear-gradient(to right, #0000FF, #00FFFF, #00FF00, #FFFF00, #FF0000)'
            }}></div>
          </div>
          <div className="flex justify-between text-xs text-gray-600 mt-2">
            <span>低注目度</span>
            <span>中注目度</span>
            <span>高注目度</span>
          </div>
        </div>

        <div className="text-sm text-gray-600 space-y-2">
          <p><strong>左動画（ゲーズプロットの動き）:</strong></p>
          <ul className="list-disc list-inside ml-2 space-y-1">
            <li>緑色の円（1-10の番号付き）: 現在フレームのゲーズプロット</li>
            <li>白色の線: 視線の移動経路</li>
          </ul>

          <p className="mt-3"><strong>右動画（ヒートマップ）:</strong></p>
          <ul className="list-disc list-inside ml-2 space-y-1">
            <li>現在時刻 ±{heatmapWindow}秒の視線密度を表示</li>
            <li>赤色: 視線が最も集中している領域</li>
            <li>青色: 視線が少ない領域</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
