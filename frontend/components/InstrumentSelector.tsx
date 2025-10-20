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
  frame_number: number  // バックエンドのスネークケースに統一
}

interface Point {
  x: number
  y: number
  label: number  // 1 = foreground, 0 = background
}

interface DetectedInstrument {
  id: number
  bbox: [number, number, number, number]
  confidence: number
  class_name: string
  suggested_name: string
  center: { x: number; y: number }
}

type SelectionMode = 'point' | 'box' | 'auto'

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
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('auto')  // デフォルトを自動検出に
  const [isSelecting, setIsSelecting] = useState(false)
  const [points, setPoints] = useState<Point[]>([])
  const [box, setBox] = useState<[number, number, number, number] | null>(null)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [currentMask, setCurrentMask] = useState<string | null>(null)
  const [currentVisualization, setCurrentVisualization] = useState<string | null>(null)
  const [selectedInstruments, setSelectedInstruments] = useState<SelectedInstrument[]>([])
  const [instrumentName, setInstrumentName] = useState('')
  const [isSegmenting, setIsSegmenting] = useState(false)
  const [canvasSize, setCanvasSize] = useState({ width: 640, height: 480 })
  // 自動検出モード用の状態
  const [detectedInstruments, setDetectedInstruments] = useState<DetectedInstrument[]>([])
  const [isDetecting, setIsDetecting] = useState(false)
  const [hoveredDetectionId, setHoveredDetectionId] = useState<number | null>(null)

  // Load thumbnail
  useEffect(() => {
    const loadThumbnail = async () => {
      try {
        setIsLoading(true)
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
        const response = await fetch(`${apiUrl}/videos/${videoId}/thumbnail`)
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
          // Set canvas size to match image natural size
          setCanvasSize({ width: img.naturalWidth, height: img.naturalHeight })
          console.log('Image loaded:', {
            naturalWidth: img.naturalWidth,
            naturalHeight: img.naturalHeight,
            width: img.width,
            height: img.height,
            src: img.src.substring(0, 50) + '...'
          })
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

  // 自動検出: サムネイル読み込み後に実行
  useEffect(() => {
    const detectInstruments = async () => {
      if (!thumbnailUrl || selectionMode !== 'auto' || isLoading) return

      setIsDetecting(true)
      setError(null)

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
        // Use SAM2 automatic mask generation for better accuracy
        const response = await fetch(
          `${apiUrl}/videos/${videoId}/detect-instruments-sam2`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              frame_number: 0,
              min_confidence: 0.5,
              max_results: 10
            })
          }
        )

        if (!response.ok) {
          throw new Error('Instrument detection failed')
        }

        const result = await response.json()
        console.log('Detection result:', result)
        setDetectedInstruments(result.instruments || [])

        if (result.instruments.length === 0) {
          setError('器具が検出されませんでした。手動選択モードに切り替えてください。')
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Detection failed')
        console.error('Detection error:', err)
      } finally {
        setIsDetecting(false)
      }
    }

    if (selectionMode === 'auto') {
      detectInstruments()
    }
  }, [thumbnailUrl, selectionMode, isLoading, videoId])

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

    // Draw detected instruments (auto mode)
    if (selectionMode === 'auto' && detectedInstruments.length > 0) {
      detectedInstruments.forEach((inst) => {
        const [x1, y1, x2, y2] = inst.bbox
        const width = x2 - x1
        const height = y2 - y1

        // ホバー時は緑、通常は黄色
        const isHovered = hoveredDetectionId === inst.id
        ctx.strokeStyle = isHovered ? '#22c55e' : '#fbbf24'
        ctx.lineWidth = isHovered ? 3 : 2
        ctx.strokeRect(x1, y1, width, height)

        // ラベルの背景
        const label = `${inst.suggested_name} (${(inst.confidence * 100).toFixed(0)}%)`
        ctx.font = '14px sans-serif'
        const textMetrics = ctx.measureText(label)
        const textWidth = textMetrics.width
        const textHeight = 16

        ctx.fillStyle = isHovered ? '#22c55e' : '#fbbf24'
        ctx.fillRect(x1, y1 - textHeight - 4, textWidth + 8, textHeight + 4)

        // ラベルテキスト
        ctx.fillStyle = '#ffffff'
        ctx.fillText(label, x1 + 4, y1 - 6)
      })
    }
  }, [points, box, dragStart, isSelecting, selectionMode, currentVisualization, detectedInstruments, hoveredDetectionId])

  useEffect(() => {
    drawCanvas()
  }, [drawCanvas])

  const getCanvasCoordinates = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }

    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height

    const x = Math.round((e.clientX - rect.left) * scaleX)
    const y = Math.round((e.clientY - rect.top) * scaleY)

    console.log('Canvas click debug:', {
      clientX: e.clientX,
      clientY: e.clientY,
      rectLeft: rect.left,
      rectTop: rect.top,
      rectWidth: rect.width,
      rectHeight: rect.height,
      canvasWidth: canvas.width,
      canvasHeight: canvas.height,
      scaleX,
      scaleY,
      resultX: x,
      resultY: y
    })

    return { x, y }
  }

  const handleCanvasClick = async (e: React.MouseEvent<HTMLCanvasElement>) => {
    // 自動検出モード: クリックされた検出ボックスを特定
    if (selectionMode === 'auto') {
      if (isSegmenting) return

      const coords = getCanvasCoordinates(e)

      // クリック座標が検出ボックス内かチェック
      const clickedInstrument = detectedInstruments.find(inst => {
        const [x1, y1, x2, y2] = inst.bbox
        return coords.x >= x1 && coords.x <= x2 && coords.y >= y1 && coords.y <= y2
      })

      if (!clickedInstrument) return

      // クリックされた器具のマスクを生成
      setIsSegmenting(true)
      setError(null)

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
        const response = await fetch(
          `${apiUrl}/videos/${videoId}/segment-from-detection`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              bbox: clickedInstrument.bbox,
              detection_id: clickedInstrument.id,
              frame_number: 0
            })
          }
        )

        if (!response.ok) {
          throw new Error('Segmentation from detection failed')
        }

        const result = await response.json()
        console.log('Segmentation from detection result:', result)

        setCurrentMask(result.mask)
        setCurrentVisualization(result.visualization)
        setBox(result.bbox as [number, number, number, number])

        // 検出器具の名前を自動設定
        setInstrumentName(clickedInstrument.suggested_name)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Segmentation failed')
        console.error('Segmentation error:', err)
      } finally {
        setIsSegmenting(false)
      }

      return
    }

    // ポイント選択モード
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
    // 自動検出モード: ホバー検出
    if (selectionMode === 'auto') {
      const coords = getCanvasCoordinates(e)

      const hoveredInst = detectedInstruments.find(inst => {
        const [x1, y1, x2, y2] = inst.bbox
        return coords.x >= x1 && coords.x <= x2 && coords.y >= y1 && coords.y <= y2
      })

      setHoveredDetectionId(hoveredInst ? hoveredInst.id : null)
      return
    }

    // ボックス選択モード: ドラッグ中の描画更新
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
      // サムネイルは既にバックエンドで640x480にリサイズされているため、
      // スケーリングは不要（1:1マッピング）
      const canvas = canvasRef.current
      if (!canvas) return

      // デバッグログ
      console.log('Canvas dimensions:', canvas.width, 'x', canvas.height)
      console.log('Selection mode:', selectionMode)
      if (selectionMode === 'point') {
        console.log('Points:', points)
      } else {
        console.log('Box:', box)
      }

      const requestBody = {
        prompt_type: selectionMode,
        coordinates: selectionMode === 'point'
          ? points.map(p => [p.x, p.y])  // スケーリング不要
          : [[box[0], box[1], box[2], box[3]]],  // スケーリング不要
        labels: selectionMode === 'point'
          ? points.map(p => p.label)
          : undefined,
        frame_number: 0
      }

      console.log('Sending segmentation request:', JSON.stringify(requestBody, null, 2))

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
      const response = await fetch(
        `${apiUrl}/videos/${videoId}/segment`,
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
      console.log('Segmentation result:', {
        bbox: result.bbox,
        score: result.score,
        area: result.area,
        prompt_type: result.prompt_type,
        hasVisualization: !!result.visualization
      })
      setCurrentMask(result.mask)
      setCurrentVisualization(result.visualization)

      // SAMの結果からbboxを取得して設定
      if (result.bbox && Array.isArray(result.bbox) && result.bbox.length === 4) {
        setBox(result.bbox as [number, number, number, number])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Segmentation failed')
    } finally {
      setIsSegmenting(false)
    }
  }

  const addInstrument = () => {
    if (!currentMask || !instrumentName.trim()) return

    // bboxが存在しない場合はエラー（セグメンテーションが失敗している）
    if (!box) {
      setError('器具の位置を検出できませんでした。もう一度選択してください。')
      return
    }

    const newInstrument: SelectedInstrument = {
      name: instrumentName.trim(),
      mask: currentMask,
      bbox: box as [number, number, number, number],
      frame_number: 0  // バックエンドのスネークケースに統一
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
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
      const response = await fetch(
        `${apiUrl}/videos/${videoId}/instruments`,
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
            onClick={() => setSelectionMode('auto')}
            disabled={isDetecting}
            className={`flex items-center px-3 py-2 rounded-md ${
              selectionMode === 'auto'
                ? 'bg-green-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            } disabled:opacity-50`}
          >
            {isDetecting ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Check className="w-4 h-4 mr-2" />
            )}
            自動検出
          </button>
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
        <div className="relative border-2 border-gray-300 rounded-lg overflow-hidden inline-block">
          <canvas
            ref={canvasRef}
            width={canvasSize.width}
            height={canvasSize.height}
            style={{ display: 'block', maxWidth: '100%', height: 'auto' }}
            className={selectionMode === 'auto' ? 'cursor-pointer' : 'cursor-crosshair'}
            onClick={handleCanvasClick}
            onMouseDown={selectionMode === 'box' ? handleMouseDown : undefined}
            onMouseMove={handleMouseMove}
            onMouseUp={selectionMode === 'box' ? handleMouseUp : undefined}
            onMouseLeave={selectionMode === 'box' ? handleMouseUp : undefined}
          />
        </div>

        {/* Instructions */}
        <div className="mt-2 text-sm text-gray-600">
          {selectionMode === 'auto' ? (
            <p>
              {isDetecting ? (
                '器具を自動検出中...'
              ) : detectedInstruments.length > 0 ? (
                `${detectedInstruments.length}個の器具が検出されました。クリックして選択してください。`
              ) : (
                '器具が検出されませんでした。手動選択モードに切り替えてください。'
              )}
            </p>
          ) : selectionMode === 'point' ? (
            <p>器具をクリックして選択。Shift+クリックで背景を指定。</p>
          ) : (
            <p>ドラッグして器具を囲むボックスを描画。</p>
          )}
        </div>

        {/* Segment button - 手動モード時のみ表示 */}
        {selectionMode !== 'auto' && (
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
          </div>
        )}

        {/* 器具名入力と追加ボタン - マスク生成後に表示 */}
        {currentMask && (
          <div className="mt-4 flex items-center space-x-4">
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
          </div>
        )}
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