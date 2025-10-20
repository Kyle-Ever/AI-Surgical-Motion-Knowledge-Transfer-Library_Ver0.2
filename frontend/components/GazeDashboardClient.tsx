'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Eye, Activity, TrendingUp, Download, Share2, Play, Pause } from 'lucide-react'

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
  gaze_data?: {
    frames: {
      frame_index: number
      saliency_map: number[][]
      fixations: { x: number; y: number }[]
      stats: {
        max_value: number
        mean_value: number
        high_attention_ratio: number
      }
    }[]
    summary: {
      total_frames: number
      avg_fixations_per_frame: number
      attention_hotspots: { x: number; y: number; intensity: number }[]
    }
  }
}

export default function GazeDashboardClient({ analysisId }: { analysisId: string }) {
  const router = useRouter()
  const [analysis, setAnalysis] = useState<GazeAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [selectedView, setSelectedView] = useState<'heatmap' | 'fixations' | 'both'>('both')
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const playIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    fetchAnalysisData()
  }, [analysisId])

  useEffect(() => {
    if (analysis && analysis.gaze_data) {
      renderFrame(currentFrameIndex)
    }
  }, [currentFrameIndex, selectedView, analysis])

  useEffect(() => {
    // Auto-play cleanup
    return () => {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current)
      }
    }
  }, [])

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

  const renderFrame = (frameIndex: number) => {
    if (!analysis?.gaze_data || !canvasRef.current) return

    const frames = analysis.gaze_data.frames
    if (!frames || frames.length === 0 || frameIndex >= frames.length) return

    const frame = frames[frameIndex]
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw saliency heatmap
    if (selectedView === 'heatmap' || selectedView === 'both') {
      drawHeatmap(ctx, frame.saliency_map)
    }

    // Draw fixation points
    if (selectedView === 'fixations' || selectedView === 'both') {
      drawFixations(ctx, frame.fixations)
    }
  }

  const drawHeatmap = (ctx: CanvasRenderingContext2D, saliencyMap: number[][]) => {
    if (!saliencyMap || saliencyMap.length === 0) return

    const canvas = ctx.canvas
    const width = canvas.width
    const height = canvas.height
    const mapHeight = saliencyMap.length
    const mapWidth = saliencyMap[0].length

    const scaleX = width / mapWidth
    const scaleY = height / mapHeight

    // Create image data for heatmap
    const imageData = ctx.createImageData(width, height)
    const data = imageData.data

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const mapY = Math.floor(y / scaleY)
        const mapX = Math.floor(x / scaleX)
        const value = saliencyMap[mapY]?.[mapX] || 0

        // JET colormap approximation
        const index = (y * width + x) * 4
        const color = getJetColor(value)
        data[index] = color[0]     // R
        data[index + 1] = color[1] // G
        data[index + 2] = color[2] // B
        data[index + 3] = Math.floor(value * 180) // Alpha (transparency)
      }
    }

    ctx.putImageData(imageData, 0, 0)
  }

  const drawFixations = (ctx: CanvasRenderingContext2D, fixations: { x: number; y: number }[]) => {
    if (!fixations || fixations.length === 0) return

    const canvas = ctx.canvas

    // Draw lines connecting fixations
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)'
    ctx.lineWidth = 2
    ctx.beginPath()
    fixations.forEach((point, i) => {
      const x = (point.x / 1920) * canvas.width
      const y = (point.y / 1080) * canvas.height
      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })
    ctx.stroke()

    // Draw fixation circles
    fixations.forEach((point, i) => {
      const x = (point.x / 1920) * canvas.width
      const y = (point.y / 1080) * canvas.height

      // White outline
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.beginPath()
      ctx.arc(x, y, 8, 0, 2 * Math.PI)
      ctx.fill()

      // Green center
      ctx.fillStyle = 'rgba(0, 255, 0, 0.8)'
      ctx.beginPath()
      ctx.arc(x, y, 6, 0, 2 * Math.PI)
      ctx.fill()

      // Number label (optional for first 5)
      if (i < 5) {
        ctx.fillStyle = 'white'
        ctx.font = 'bold 12px sans-serif'
        ctx.fillText(String(i + 1), x + 10, y - 10)
      }
    })
  }

  const getJetColor = (value: number): [number, number, number] => {
    // Normalized value [0, 1]
    const v = Math.max(0, Math.min(1, value))

    let r, g, b
    if (v < 0.25) {
      r = 0
      g = 0
      b = Math.floor(128 + v * 4 * 127)
    } else if (v < 0.5) {
      r = 0
      g = Math.floor((v - 0.25) * 4 * 255)
      b = 255
    } else if (v < 0.75) {
      r = Math.floor((v - 0.5) * 4 * 255)
      g = 255
      b = Math.floor(255 - (v - 0.5) * 4 * 255)
    } else {
      r = 255
      g = Math.floor(255 - (v - 0.75) * 4 * 255)
      b = 0
    }

    return [r, g, b]
  }

  const handlePlayPause = () => {
    if (!analysis?.gaze_data) return

    if (isPlaying) {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current)
        playIntervalRef.current = null
      }
      setIsPlaying(false)
    } else {
      playIntervalRef.current = setInterval(() => {
        setCurrentFrameIndex(prev => {
          const totalFrames = analysis.gaze_data!.frames.length
          const next = prev + 1
          if (next >= totalFrames) {
            if (playIntervalRef.current) {
              clearInterval(playIntervalRef.current)
              playIntervalRef.current = null
            }
            setIsPlaying(false)
            return 0
          }
          return next
        })
      }, 100) // 10 FPS playback
      setIsPlaying(true)
    }
  }

  const handleExport = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'
      const response = await fetch(`${apiUrl}/analysis/${analysisId}/export`)
      const blob = await response.blob()
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
  const currentFrame = gazeData?.frames?.[currentFrameIndex]

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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
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
                <p className="text-sm text-gray-600">平均固視点数/フレーム</p>
                <p className="text-2xl font-bold text-gray-900">
                  {gazeData.summary.avg_fixations_per_frame.toFixed(1)}
                </p>
              </div>
              <TrendingUp className="w-10 h-10 text-green-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">注目ホットスポット</p>
                <p className="text-2xl font-bold text-gray-900">
                  {gazeData.summary.attention_hotspots.length}
                </p>
              </div>
              <Eye className="w-10 h-10 text-purple-500" />
            </div>
          </div>
        </div>
      )}

      {/* Main Visualization */}
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">視線注目度マップ</h2>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setSelectedView('heatmap')}
              className={`px-3 py-1 rounded-lg text-sm ${
                selectedView === 'heatmap' ? 'bg-orange-600 text-white' : 'bg-gray-200 text-gray-700'
              }`}
            >
              ヒートマップ
            </button>
            <button
              onClick={() => setSelectedView('fixations')}
              className={`px-3 py-1 rounded-lg text-sm ${
                selectedView === 'fixations' ? 'bg-orange-600 text-white' : 'bg-gray-200 text-gray-700'
              }`}
            >
              固視点
            </button>
            <button
              onClick={() => setSelectedView('both')}
              className={`px-3 py-1 rounded-lg text-sm ${
                selectedView === 'both' ? 'bg-orange-600 text-white' : 'bg-gray-200 text-gray-700'
              }`}
            >
              両方
            </button>
          </div>
        </div>

        {/* Canvas for visualization */}
        <div className="relative bg-black rounded-lg overflow-hidden">
          <canvas
            ref={canvasRef}
            width={1920}
            height={1080}
            className="w-full h-auto"
          />
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
                max={(gazeData?.frames?.length || 1) - 1}
                value={currentFrameIndex}
                onChange={(e) => setCurrentFrameIndex(Number(e.target.value))}
                className="w-full"
              />
            </div>
            <span className="text-sm text-gray-600">
              {currentFrameIndex + 1} / {gazeData?.frames?.length || 0}
            </span>
          </div>
        </div>

        {/* Current Frame Stats */}
        {currentFrame && (
          <div className="mt-4 grid grid-cols-3 gap-4">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-600">最大注目度</p>
              <p className="text-lg font-semibold text-gray-900">
                {(currentFrame.stats.max_value * 100).toFixed(1)}%
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

      {/* Color Legend */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">カラーマップの見方</h3>
        <div className="flex items-center space-x-4">
          <div className="flex-1">
            <div className="h-8 rounded-lg" style={{
              background: 'linear-gradient(to right, #000080, #0000FF, #00FFFF, #00FF00, #FFFF00, #FF0000)'
            }}></div>
          </div>
          <div className="flex justify-between text-xs text-gray-600 w-full">
            <span>低注目度</span>
            <span>中注目度</span>
            <span>高注目度</span>
          </div>
        </div>
        <p className="text-sm text-gray-600 mt-2">
          緑色の円: 固視点（視線が留まった箇所）<br/>
          白色の線: 視線の移動経路
        </p>
      </div>
    </div>
  )
}
