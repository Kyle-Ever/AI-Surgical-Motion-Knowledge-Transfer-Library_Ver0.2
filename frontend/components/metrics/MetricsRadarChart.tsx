'use client'

import React, { useRef, useEffect } from 'react'

interface MetricsRadarChartProps {
  scores: {
    a1: number  // 動作経済性
    a2: number  // 動作滑らかさ
    a3: number  // 両手協調性
    b1: number  // ロスタイム
    b2: number  // 動作回数
    b3: number  // 作業空間
  }
  className?: string
}

const LABELS = ['動作経済性', '動作滑らかさ', '両手協調性', 'ロスタイム', '動作回数効率', '作業空間偏差']
const COLORS = {
  fill: 'rgba(59, 130, 246, 0.15)',
  stroke: 'rgba(59, 130, 246, 0.8)',
  grid: 'rgba(0, 0, 0, 0.08)',
  label: '#374151',
  score: '#6B7280',
  // Group別の色（ラベル用）
  groupA: '#2563EB',  // blue-600
  groupB: '#DC2626',  // red-600
}
// 各軸がどのグループか（A=0-2, B=3-5）
const GROUP = ['A', 'A', 'A', 'B', 'B', 'B']

const MetricsRadarChart: React.FC<MetricsRadarChartProps> = ({ scores, className = '' }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const rawValues = [scores.a1, scores.a2, scores.a3, scores.b1, scores.b2, scores.b3]
  const values = rawValues.map(v => v < 0 ? 0 : v)  // N/A(-1) → 0 for drawing

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const size = canvas.clientWidth
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.scale(dpr, dpr)

    const cx = size / 2
    const cy = size / 2
    const maxR = size * 0.30
    const n = 6
    const angleStep = (2 * Math.PI) / n
    const startAngle = -Math.PI / 2  // 12時方向から開始

    ctx.clearRect(0, 0, size, size)

    // グリッド（20, 40, 60, 80, 100）
    for (let level = 1; level <= 5; level++) {
      const r = (level / 5) * maxR
      ctx.beginPath()
      for (let i = 0; i <= n; i++) {
        const angle = startAngle + i * angleStep
        const x = cx + r * Math.cos(angle)
        const y = cy + r * Math.sin(angle)
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.strokeStyle = COLORS.grid
      ctx.lineWidth = 1
      ctx.stroke()
    }

    // 軸線
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(cx + maxR * Math.cos(angle), cy + maxR * Math.sin(angle))
      ctx.strokeStyle = COLORS.grid
      ctx.lineWidth = 1
      ctx.stroke()
    }

    // データ領域
    ctx.beginPath()
    for (let i = 0; i <= n; i++) {
      const idx = i % n
      const angle = startAngle + idx * angleStep
      const r = (values[idx] / 100) * maxR
      const x = cx + r * Math.cos(angle)
      const y = cy + r * Math.sin(angle)
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    }
    ctx.closePath()
    ctx.fillStyle = COLORS.fill
    ctx.fill()
    ctx.strokeStyle = COLORS.stroke
    ctx.lineWidth = 2
    ctx.stroke()

    // データ点
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep
      const r = (values[i] / 100) * maxR
      const x = cx + r * Math.cos(angle)
      const y = cy + r * Math.sin(angle)
      ctx.beginPath()
      ctx.arc(x, y, 4, 0, 2 * Math.PI)
      ctx.fillStyle = COLORS.stroke
      ctx.fill()
    }

    // ラベル + スコア
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep
      const labelR = maxR + 36
      const lx = cx + labelR * Math.cos(angle)
      const ly = cy + labelR * Math.sin(angle)

      ctx.font = '10px sans-serif'
      ctx.fillStyle = GROUP[i] === 'A' ? COLORS.groupA : COLORS.groupB
      ctx.fillText(LABELS[i], lx, ly - 7)

      ctx.font = 'bold 12px sans-serif'
      ctx.fillStyle = COLORS.score
      ctx.fillText(rawValues[i] < 0 ? 'N/A' : `${values[i].toFixed(0)}`, lx, ly + 8)
    }
  }, [values])

  return (
    <div className={`bg-white rounded-lg border border-gray-200 shadow-sm p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">6指標レーダー</h3>
      <canvas
        ref={canvasRef}
        className="w-full aspect-square max-w-[320px] mx-auto"
      />
    </div>
  )
}

export default MetricsRadarChart
