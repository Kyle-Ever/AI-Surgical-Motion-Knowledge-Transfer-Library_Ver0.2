'use client'

import { useEffect, useRef, useState } from 'react'

interface Point {
  x: number
  y: number
  intensity?: number
}

interface TrajectoryHeatmapProps {
  points?: Point[]
  width?: number
  height?: number
  mockData?: boolean
}

export function TrajectoryHeatmap({
  points,
  width = 800,
  height = 450,
  mockData = false,
}: TrajectoryHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [heatmapData, setHeatmapData] = useState<Point[]>([])

  useEffect(() => {
    if (mockData || !points) {
      // モックデータ生成 - 手術動作の軌跡をシミュレート
      const mockPoints: Point[] = []
      const centerX = width / 2
      const centerY = height / 2

      // 円形の動作パターン
      for (let i = 0; i < 200; i++) {
        const angle = (i / 200) * Math.PI * 4
        const radius = 100 + Math.sin(i * 0.1) * 50
        mockPoints.push({
          x: centerX + Math.cos(angle) * radius + Math.random() * 20,
          y: centerY + Math.sin(angle) * radius + Math.random() * 20,
          intensity: 0.5 + Math.random() * 0.5,
        })
      }

      // 直線的な動作パターン
      for (let i = 0; i < 100; i++) {
        mockPoints.push({
          x: 100 + i * 6 + Math.random() * 10,
          y: 100 + Math.sin(i * 0.2) * 50 + Math.random() * 10,
          intensity: 0.3 + Math.random() * 0.7,
        })
      }

      setHeatmapData(mockPoints)
    } else {
      setHeatmapData(points)
    }
  }, [points, mockData, width, height])

  useEffect(() => {
    if (!canvasRef.current || heatmapData.length === 0) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Canvas clear
    ctx.fillStyle = '#f9fafb'
    ctx.fillRect(0, 0, width, height)

    // Grid描画
    ctx.strokeStyle = '#e5e7eb'
    ctx.lineWidth = 1
    for (let x = 0; x <= width; x += 50) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, height)
      ctx.stroke()
    }
    for (let y = 0; y <= height; y += 50) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(width, y)
      ctx.stroke()
    }

    // ヒートマップ生成
    const heatmapCanvas = document.createElement('canvas')
    heatmapCanvas.width = width
    heatmapCanvas.height = height
    const heatCtx = heatmapCanvas.getContext('2d')
    if (!heatCtx) return

    // 各ポイントをグラデーションで描画
    heatmapData.forEach(point => {
      const gradient = heatCtx.createRadialGradient(
        point.x,
        point.y,
        0,
        point.x,
        point.y,
        30
      )

      const intensity = point.intensity || 0.5
      gradient.addColorStop(0, `rgba(255, 0, 0, ${intensity * 0.5})`)
      gradient.addColorStop(0.5, `rgba(255, 255, 0, ${intensity * 0.3})`)
      gradient.addColorStop(1, 'rgba(0, 0, 255, 0)')

      heatCtx.fillStyle = gradient
      heatCtx.fillRect(point.x - 30, point.y - 30, 60, 60)
    })

    // ヒートマップを本体キャンバスに転写
    ctx.globalAlpha = 0.7
    ctx.drawImage(heatmapCanvas, 0, 0)
    ctx.globalAlpha = 1

    // 軌跡線を描画
    if (heatmapData.length > 1) {
      ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(heatmapData[0].x, heatmapData[0].y)

      for (let i = 1; i < heatmapData.length; i++) {
        ctx.lineTo(heatmapData[i].x, heatmapData[i].y)
      }
      ctx.stroke()
    }

    // 開始点と終了点をマーク
    if (heatmapData.length > 0) {
      // 開始点
      ctx.fillStyle = '#10b981'
      ctx.beginPath()
      ctx.arc(heatmapData[0].x, heatmapData[0].y, 8, 0, Math.PI * 2)
      ctx.fill()

      // 終了点
      ctx.fillStyle = '#ef4444'
      ctx.beginPath()
      ctx.arc(
        heatmapData[heatmapData.length - 1].x,
        heatmapData[heatmapData.length - 1].y,
        8,
        0,
        Math.PI * 2
      )
      ctx.fill()
    }
  }, [heatmapData, width, height])

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold mb-4">動作軌跡ヒートマップ</h3>

      <div className="relative">
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          className="w-full border border-gray-200 rounded-lg"
        />

        <div className="absolute top-2 right-2 bg-white/90 p-2 rounded-lg text-xs">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span>開始点</span>
          </div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-3 h-3 bg-red-500 rounded-full"></div>
            <span>終了点</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-gradient-to-r from-red-500 via-yellow-500 to-blue-500 rounded"></div>
            <span>動作頻度</span>
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">総移動距離</div>
          <div className="text-xl font-bold text-blue-600">
            {heatmapData.length > 1
              ? Math.round(
                  heatmapData.reduce((sum, point, i) => {
                    if (i === 0) return 0
                    const dx = point.x - heatmapData[i - 1].x
                    const dy = point.y - heatmapData[i - 1].y
                    return sum + Math.sqrt(dx * dx + dy * dy)
                  }, 0)
                )
              : 0}{' '}
            px
          </div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">動作範囲</div>
          <div className="text-xl font-bold text-green-600">
            {heatmapData.length > 0
              ? Math.round(
                  (Math.max(...heatmapData.map(p => p.x)) -
                    Math.min(...heatmapData.map(p => p.x))) *
                    (Math.max(...heatmapData.map(p => p.y)) -
                      Math.min(...heatmapData.map(p => p.y)))
                )
              : 0}{' '}
            px²
          </div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">サンプル数</div>
          <div className="text-xl font-bold text-purple-600">
            {heatmapData.length}
          </div>
        </div>
      </div>
    </div>
  )
}