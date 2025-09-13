'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft, Save, Play, Pause, SkipBack, SkipForward, MousePointer, Square } from 'lucide-react'
import axios from 'axios'

interface BoundingBox {
  id: string
  x: number
  y: number
  width: number
  height: number
  label: string
  color: string
}

interface Frame {
  frameNumber: number
  imageUrl: string
  annotations: BoundingBox[]
}

const TOOL_TYPES = [
  { value: 'forceps', label: '鉗子', color: '#FF6B6B' },
  { value: 'scissors', label: 'ハサミ', color: '#4ECDC4' },
  { value: 'needle_holder', label: '持針器', color: '#45B7D1' },
  { value: 'scalpel', label: 'メス', color: '#FFA07A' },
  { value: 'suction', label: '吸引器', color: '#98D8C8' },
  { value: 'other', label: 'その他', color: '#FDCB6E' },
]

export default function AnnotationPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const videoId = searchParams.get('video_id')

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [currentFrame, setCurrentFrame] = useState(0)
  const [frames, setFrames] = useState<Frame[]>([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [selectedTool, setSelectedTool] = useState(TOOL_TYPES[0])
  const [isDrawing, setIsDrawing] = useState(false)
  const [startPoint, setStartPoint] = useState({ x: 0, y: 0 })
  const [currentBox, setCurrentBox] = useState<BoundingBox | null>(null)
  const [annotations, setAnnotations] = useState<BoundingBox[]>([])
  const [isSaving, setIsSaving] = useState(false)

  // Canvas drawing
  const drawFrame = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || frames.length === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const frame = frames[currentFrame]
    const img = new Image()

    img.onload = () => {
      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Draw image
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

      // Draw existing annotations
      frame.annotations.forEach(box => {
        ctx.strokeStyle = box.color
        ctx.lineWidth = 2
        ctx.strokeRect(box.x, box.y, box.width, box.height)

        // Draw label
        ctx.fillStyle = box.color
        ctx.fillRect(box.x, box.y - 20, box.label.length * 10 + 10, 20)
        ctx.fillStyle = 'white'
        ctx.font = '14px sans-serif'
        ctx.fillText(box.label, box.x + 5, box.y - 5)
      })

      // Draw current box being drawn
      if (currentBox && isDrawing) {
        ctx.strokeStyle = currentBox.color
        ctx.lineWidth = 2
        ctx.setLineDash([5, 5])
        ctx.strokeRect(currentBox.x, currentBox.y, currentBox.width, currentBox.height)
        ctx.setLineDash([])
      }
    }

    img.src = frame.imageUrl
  }, [frames, currentFrame, currentBox, isDrawing])

  useEffect(() => {
    drawFrame()
  }, [drawFrame])

  // Mouse events for drawing
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setIsDrawing(true)
    setStartPoint({ x, y })
    setCurrentBox({
      id: `box-${Date.now()}`,
      x,
      y,
      width: 0,
      height: 0,
      label: selectedTool.label,
      color: selectedTool.color,
    })
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !currentBox) return

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setCurrentBox({
      ...currentBox,
      width: x - startPoint.x,
      height: y - startPoint.y,
    })
  }

  const handleMouseUp = () => {
    if (!isDrawing || !currentBox) return

    // Add box to current frame annotations
    if (Math.abs(currentBox.width) > 10 && Math.abs(currentBox.height) > 10) {
      const normalizedBox = {
        ...currentBox,
        x: currentBox.width < 0 ? currentBox.x + currentBox.width : currentBox.x,
        y: currentBox.height < 0 ? currentBox.y + currentBox.height : currentBox.y,
        width: Math.abs(currentBox.width),
        height: Math.abs(currentBox.height),
      }

      const updatedFrames = [...frames]
      updatedFrames[currentFrame].annotations.push(normalizedBox)
      setFrames(updatedFrames)
    }

    setIsDrawing(false)
    setCurrentBox(null)
  }

  // Frame navigation
  const handlePrevFrame = () => {
    if (currentFrame > 0) {
      setCurrentFrame(currentFrame - 1)
    }
  }

  const handleNextFrame = () => {
    if (currentFrame < frames.length - 1) {
      setCurrentFrame(currentFrame + 1)
    }
  }

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying)
  }

  useEffect(() => {
    if (isPlaying && frames.length > 0) {
      const interval = setInterval(() => {
        setCurrentFrame(prev => {
          if (prev >= frames.length - 1) {
            setIsPlaying(false)
            return prev
          }
          return prev + 1
        })
      }, 200) // 5fps

      return () => clearInterval(interval)
    }
  }, [isPlaying, frames.length])

  // Load frames
  useEffect(() => {
    if (videoId) {
      // Mock frames - 実際にはAPIから取得
      const mockFrames: Frame[] = Array.from({ length: 30 }, (_, i) => ({
        frameNumber: i,
        imageUrl: `/api/frames/${videoId}/${i}`, // 実際のエンドポイントに置き換え
        annotations: [],
      }))
      setFrames(mockFrames)
    }
  }, [videoId])

  // Save annotations
  const handleSave = async () => {
    if (!videoId) return

    setIsSaving(true)
    try {
      const annotationData = frames.map(frame => ({
        frameNumber: frame.frameNumber,
        annotations: frame.annotations.map(box => ({
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
          label: box.label,
        })),
      }))

      await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/annotations/save`, {
        video_id: videoId,
        annotations: annotationData,
      })

      alert('アノテーションを保存しました')
    } catch (error) {
      console.error('Failed to save annotations:', error)
      alert('保存に失敗しました')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.back()}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <h1 className="text-xl font-semibold">器具アノテーション</h1>
            </div>

            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {isSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main Canvas */}
          <div className="lg:col-span-3 space-y-4">
            <div className="bg-white rounded-lg shadow-md p-4">
              <canvas
                ref={canvasRef}
                width={800}
                height={450}
                className="w-full border border-gray-200 cursor-crosshair"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              />

              {/* Controls */}
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    onClick={handlePrevFrame}
                    className="p-2 hover:bg-gray-100 rounded-lg"
                    disabled={currentFrame === 0}
                  >
                    <SkipBack className="h-5 w-5" />
                  </button>

                  <button
                    onClick={handlePlayPause}
                    className="p-2 hover:bg-gray-100 rounded-lg"
                  >
                    {isPlaying ? (
                      <Pause className="h-5 w-5" />
                    ) : (
                      <Play className="h-5 w-5" />
                    )}
                  </button>

                  <button
                    onClick={handleNextFrame}
                    className="p-2 hover:bg-gray-100 rounded-lg"
                    disabled={currentFrame === frames.length - 1}
                  >
                    <SkipForward className="h-5 w-5" />
                  </button>

                  <span className="ml-4 text-sm text-gray-600">
                    フレーム {currentFrame + 1} / {frames.length}
                  </span>
                </div>

                <div className="text-sm text-gray-600">
                  {frames[currentFrame]?.annotations.length || 0} アノテーション
                </div>
              </div>
            </div>

            {/* Timeline */}
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="relative h-2 bg-gray-200 rounded-full">
                <div
                  className="absolute h-2 bg-blue-600 rounded-full"
                  style={{
                    width: `${((currentFrame + 1) / frames.length) * 100}%`
                  }}
                />
              </div>
              <div className="mt-2 flex justify-between text-xs text-gray-500">
                <span>0:00</span>
                <span>{Math.floor(frames.length / 5)}s</span>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Tool Selection */}
            <div className="bg-white rounded-lg shadow-md p-4">
              <h3 className="font-semibold mb-3">器具タイプ</h3>
              <div className="space-y-2">
                {TOOL_TYPES.map(tool => (
                  <button
                    key={tool.value}
                    onClick={() => setSelectedTool(tool)}
                    className={`w-full text-left px-3 py-2 rounded-lg border ${
                      selectedTool.value === tool.value
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className="w-4 h-4 rounded"
                        style={{ backgroundColor: tool.color }}
                      />
                      <span className="text-sm">{tool.label}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Instructions */}
            <div className="bg-white rounded-lg shadow-md p-4">
              <h3 className="font-semibold mb-3">操作方法</h3>
              <div className="space-y-2 text-sm text-gray-600">
                <div className="flex items-start gap-2">
                  <MousePointer className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>マウスドラッグで器具を囲む</span>
                </div>
                <div className="flex items-start gap-2">
                  <Square className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>器具タイプを選択してから描画</span>
                </div>
                <div className="flex items-start gap-2">
                  <Play className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>再生ボタンで動画を確認</span>
                </div>
              </div>
            </div>

            {/* Statistics */}
            <div className="bg-white rounded-lg shadow-md p-4">
              <h3 className="font-semibold mb-3">統計</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">総フレーム数</span>
                  <span className="font-medium">{frames.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">アノテーション済み</span>
                  <span className="font-medium">
                    {frames.filter(f => f.annotations.length > 0).length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">総アノテーション数</span>
                  <span className="font-medium">
                    {frames.reduce((sum, f) => sum + f.annotations.length, 0)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}