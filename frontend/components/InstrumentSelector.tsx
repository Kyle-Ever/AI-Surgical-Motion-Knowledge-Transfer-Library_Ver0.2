'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Loader2, MousePointer, Square, Check, X, RotateCcw } from 'lucide-react'

interface InstrumentSelectorProps {
  videoId: string
  onInstrumentsSelected: (instruments: SelectedInstrument[]) => void
  onBack?: () => void
}

interface SelectedInstrument {
  name: string
  mask: string  // Base64 encoded mask
  bbox: [number, number, number, number]
  frameNumber: number
}

interface Point {
  x: number
  y: number
  label: number  // 1 = foreground, 0 = background
}

type SelectionMode = 'point' | 'box'

export default function InstrumentSelector({ 
  videoId, 
  onInstrumentsSelected,
  onBack 
}: InstrumentSelectorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imageRef = useRef<HTMLImageElement | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null)
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('point')
  const [isSelecting, setIsSelecting] = useState(false)
  const [points, setPoints] = useState<Point[]>([])
  const [box, setBox] = useState<[number, number, number, number] | null>(null)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [currentMask, setCurrentMask] = useState<string | null>(null)
  const [currentVisualization, setCurrentVisualization] = useState<string | null>(null)
  const [selectedInstruments, setSelectedInstruments] = useState<SelectedInstrument[]>([])
  const [instrumentName, setInstrumentName] = useState('')
  const [isSegmenting, setIsSegmenting] = useState(false)

  // Load thumbnail
  useEffect(() => {
    const loadThumbnail = async () => {
      try {
        setIsLoading(true)
        const response = await fetch(`http://localhost:8000/api/v1/videos/${videoId}/thumbnail`)
        if (!response.ok) {
          throw new Error('Failed to load thumbnail')
        }
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        setThumbnailUrl(url)
        
        // Load image for canvas
        const img = new Image()
        img.onload = () => {
          imageRef.current = img
          drawCanvas()
          setIsLoading(false)
        }
        img.src = url
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load thumbnail')
        setIsLoading(false)
      }
    }

    loadThumbnail()

    return () => {
      if (thumbnailUrl) {
        URL.revokeObjectURL(thumbnailUrl)
      }
    }
  }, [videoId])

  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    const img = imageRef.current

    if (!canvas || !ctx || !img) return

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw thumbnail
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    // Draw current visualization if exists
    if (currentVisualization) {
      const visImg = new Image()
      visImg.onload = () => {
        ctx.globalAlpha = 0.7
        ctx.drawImage(visImg, 0, 0, canvas.width, canvas.height)
        ctx.globalAlpha = 1.0
      }
      visImg.src = `data:image/jpeg;base64,${currentVisualization}`
    }

    // Draw selection points
    points.forEach(point => {
      ctx.beginPath()
      ctx.arc(point.x, point.y, 5, 0, 2 * Math.PI)
      ctx.fillStyle = point.label === 1 ? '#22c55e' : '#ef4444'
      ctx.fill()
      ctx.strokeStyle = 'white'
      ctx.lineWidth = 2
      ctx.stroke()
    })

    // Draw selection box
    if (box) {
      ctx.strokeStyle = '#3b82f6'
      ctx.lineWidth = 2
      // ドラッグ中は点線、完了後は実線
      if (isSelecting && selectionMode === 'box') {
        ctx.setLineDash([5, 5])
      }
      ctx.strokeRect(box[0], box[1], box[2] - box[0], box[3] - box[1])
      ctx.setLineDash([])
    }
  }, [points, box, dragStart, isSelecting, selectionMode, currentVisualization])

  useEffect(() => {
    drawCanvas()
  }, [drawCanvas])

  const getCanvasCoordinates = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }

    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height

    return {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY)
    }
  }

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (selectionMode !== 'point' || isSegmenting) return

    const coords = getCanvasCoordinates(e)
    const label = e.shiftKey ? 0 : 1  // Shift+click for background points

    setPoints([...points, { ...coords, label }])
  }

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (selectionMode !== 'box' || isSegmenting) return

    const coords = getCanvasCoordinates(e)
    setDragStart(coords)
    setIsSelecting(true)
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isSelecting || selectionMode !== 'box' || !dragStart) return

    const coords = getCanvasCoordinates(e)
    const newBox: [number, number, number, number] = [
      Math.min(dragStart.x, coords.x),
      Math.min(dragStart.y, coords.y),
      Math.max(dragStart.x, coords.x),
      Math.max(dragStart.y, coords.y)
    ]
    setBox(newBox)
    drawCanvas()  // リアルタイムで描画更新
  }

  const handleMouseUp = () => {
    if (selectionMode === 'box') {
      setIsSelecting(false)
      setDragStart(null)
    }
  }

  const performSegmentation = async () => {
    if ((selectionMode === 'point' && points.length === 0) ||
        (selectionMode === 'box' && !box)) {
      return
    }

    setIsSegmenting(true)
    setError(null)

    try {
      // Canvas座標を実際の画像座標にスケーリング
      // キャンバスは640x480、実際の画像サイズは異なる可能性がある
      const canvas = canvasRef.current
      const img = imageRef.current
      if (!canvas || !img) return

      const scaleX = img.naturalWidth / canvas.width
      const scaleY = img.naturalHeight / canvas.height

      const requestBody = {
        prompt_type: selectionMode,
        coordinates: selectionMode === 'point'
          ? points.map(p => [Math.round(p.x * scaleX), Math.round(p.y * scaleY)])
          : [[Math.round(box[0] * scaleX), Math.round(box[1] * scaleY),
              Math.round(box[2] * scaleX), Math.round(box[3] * scaleY)]],
        labels: selectionMode === 'point'
          ? points.map(p => p.label)
          : undefined,
        frame_number: 0
      }

      const response = await fetch(
        `http://localhost:8000/api/v1/videos/${videoId}/segment`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody)
        }
      )

      if (!response.ok) {
        throw new Error('Segmentation failed')
      }

      const result = await response.json()
      setCurrentMask(result.mask)
      setCurrentVisualization(result.visualization)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Segmentation failed')
    } finally {
      setIsSegmenting(false)
    }
  }

  const addInstrument = () => {
    if (!currentMask || !instrumentName.trim()) return

    const bbox = box || [0, 0, 100, 100] // Use box or default
    const newInstrument: SelectedInstrument = {
      name: instrumentName.trim(),
      mask: currentMask,
      bbox: bbox as [number, number, number, number],
      frameNumber: 0
    }

    setSelectedInstruments([...selectedInstruments, newInstrument])
    resetSelection()
    setInstrumentName('')
  }

  const resetSelection = () => {
    setPoints([])
    setBox(null)
    setCurrentMask(null)
    setCurrentVisualization(null)
    drawCanvas()
  }

  const removeInstrument = (index: number) => {
    setSelectedInstruments(selectedInstruments.filter((_, i) => i !== index))
  }

  const handleComplete = async () => {
    if (selectedInstruments.length === 0) {
      onInstrumentsSelected([])
      return
    }

    try {
      // Register instruments on backend
      const response = await fetch(
        `http://localhost:8000/api/v1/videos/${videoId}/instruments`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ instruments: selectedInstruments })
        }
      )

      if (!response.ok) {
        throw new Error('Failed to register instruments')
      }

      onInstrumentsSelected(selectedInstruments)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register instruments')
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <span className="ml-2">サムネイルを読み込み中...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">エラー: {error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow-sm p-4">
        <h2 className="text-lg font-semibold mb-4">器具をクリックまたはボックスで選択</h2>
        
        {/* Selection mode toggle */}
        <div className="flex items-center space-x-4 mb-4">
          <button
            onClick={() => setSelectionMode('point')}
            className={`flex items-center px-3 py-2 rounded-md ${
              selectionMode === 'point'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <MousePointer className="w-4 h-4 mr-2" />
            ポイント選択
          </button>
          <button
            onClick={() => setSelectionMode('box')}
            className={`flex items-center px-3 py-2 rounded-md ${
              selectionMode === 'box'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <Square className="w-4 h-4 mr-2" />
            ボックス選択
          </button>
          <button
            onClick={resetSelection}
            className="flex items-center px-3 py-2 rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            リセット
          </button>
        </div>

        {/* Canvas for selection */}
        <div className="relative border-2 border-gray-300 rounded-lg overflow-hidden">
          <canvas
            ref={canvasRef}
            width={640}
            height={480}
            className="w-full cursor-crosshair"
            onClick={selectionMode === 'point' ? handleCanvasClick : undefined}
            onMouseDown={selectionMode === 'box' ? handleMouseDown : undefined}
            onMouseMove={selectionMode === 'box' ? handleMouseMove : undefined}
            onMouseUp={selectionMode === 'box' ? handleMouseUp : undefined}
            onMouseLeave={selectionMode === 'box' ? handleMouseUp : undefined}
          />
        </div>

        {/* Instructions */}
        <div className="mt-2 text-sm text-gray-600">
          {selectionMode === 'point' ? (
            <p>器具をクリックして選択。Shift+クリックで背景を指定。</p>
          ) : (
            <p>ドラッグして器具を囲むボックスを描画。</p>
          )}
        </div>

        {/* Segment button */}
        <div className="mt-4 flex items-center space-x-4">
          <button
            onClick={performSegmentation}
            disabled={isSegmenting || (selectionMode === 'point' ? points.length === 0 : !box)}
            className="px-4 py-2 bg-green-600 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-green-700"
          >
            {isSegmenting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin inline" />
                セグメント中...
              </>
            ) : (
              'セグメント実行'
            )}
          </button>

          {currentMask && (
            <>
              <input
                type="text"
                value={instrumentName}
                onChange={(e) => setInstrumentName(e.target.value)}
                placeholder="器具名を入力"
                className="px-3 py-2 border border-gray-300 rounded-md"
              />
              <button
                onClick={addInstrument}
                disabled={!instrumentName.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50 hover:bg-blue-700"
              >
                <Check className="w-4 h-4 mr-2 inline" />
                追加
              </button>
            </>
          )}
        </div>
      </div>

      {/* Selected instruments list */}
      {selectedInstruments.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-4">
          <h3 className="font-semibold mb-3">選択した器具</h3>
          <div className="space-y-2">
            {selectedInstruments.map((inst, index) => (
              <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <span>{inst.name}</span>
                <button
                  onClick={() => removeInstrument(index)}
                  className="text-red-600 hover:text-red-800"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
        >
          戻る
        </button>
        <button
          onClick={handleComplete}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          {selectedInstruments.length > 0 ? '選択完了' : 'スキップ'}
        </button>
      </div>
    </div>
  )
}