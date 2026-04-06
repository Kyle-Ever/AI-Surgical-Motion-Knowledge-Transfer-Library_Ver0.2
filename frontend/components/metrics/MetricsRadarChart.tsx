'use client'

import React, { useRef, useEffect } from 'react'

interface Scores {
  a1: number  // 動作経済性
  a2: number  // 動作滑らかさ
  a3: number  // 両手協調性
  b1: number  // ロスタイム
  b2: number  // 動作回数
  b3: number  // 作業空間
}

interface MetricsRadarChartProps {
  scores: Scores
  /** 基準モデルのスコア（相対評価時に重ねて表示） */
  expertScores?: Scores | null
  className?: string
}

const LABELS = ['動作経済性', '動作滑らかさ', '両手協調性', 'ロスタイム', '動作回数効率', '作業空間偏差']
const GROUP = ['A', 'A', 'A', 'B', 'B', 'B']

const COLORS = {
  // 学習者
  learnerFill: 'rgba(59, 130, 246, 0.15)',
  learnerStroke: 'rgba(59, 130, 246, 0.8)',
  learnerPoint: 'rgba(59, 130, 246, 1)',
  // 基準（エキスパート）
  expertFill: 'rgba(34, 197, 94, 0.10)',
  expertStroke: 'rgba(34, 197, 94, 0.6)',
  expertPoint: 'rgba(34, 197, 94, 0.8)',
  expertDash: [6, 3],
  // 共通
  grid: 'rgba(0, 0, 0, 0.08)',
  groupA: '#2563EB',
  groupB: '#DC2626',
  score: '#6B7280',
  expertScore: '#16A34A',
}

function toValues(s: Scores): number[] {
  return [s.a1, s.a2, s.a3, s.b1, s.b2, s.b3].map(v => v < 0 ? 0 : v)
}

const MetricsRadarChart: React.FC<MetricsRadarChartProps> = ({ scores, expertScores, className = '' }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const values = toValues(scores)
  const rawValues = [scores.a1, scores.a2, scores.a3, scores.b1, scores.b2, scores.b3]
  const expertValues = expertScores ? toValues(expertScores) : null
  const hasExpert = expertValues !== null

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
    const startAngle = -Math.PI / 2

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

    // --- 基準データ（背面に描画） ---
    if (hasExpert && expertValues) {
      // 塗りつぶし
      ctx.beginPath()
      for (let i = 0; i <= n; i++) {
        const idx = i % n
        const angle = startAngle + idx * angleStep
        const r = (expertValues[idx] / 100) * maxR
        const x = cx + r * Math.cos(angle)
        const y = cy + r * Math.sin(angle)
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.fillStyle = COLORS.expertFill
      ctx.fill()

      // 破線ストローク
      ctx.setLineDash(COLORS.expertDash)
      ctx.strokeStyle = COLORS.expertStroke
      ctx.lineWidth = 2
      ctx.stroke()
      ctx.setLineDash([])

      // 点
      for (let i = 0; i < n; i++) {
        const angle = startAngle + i * angleStep
        const r = (expertValues[i] / 100) * maxR
        const x = cx + r * Math.cos(angle)
        const y = cy + r * Math.sin(angle)
        ctx.beginPath()
        ctx.arc(x, y, 3, 0, 2 * Math.PI)
        ctx.fillStyle = COLORS.expertPoint
        ctx.fill()
      }
    }

    // --- 学習者データ（前面に描画） ---
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
    ctx.fillStyle = COLORS.learnerFill
    ctx.fill()
    ctx.strokeStyle = COLORS.learnerStroke
    ctx.lineWidth = 2
    ctx.stroke()

    // 点
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep
      const r = (values[i] / 100) * maxR
      const x = cx + r * Math.cos(angle)
      const y = cy + r * Math.sin(angle)
      ctx.beginPath()
      ctx.arc(x, y, 4, 0, 2 * Math.PI)
      ctx.fillStyle = COLORS.learnerPoint
      ctx.fill()
    }

    // --- ラベル + スコア ---
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep
      const labelR = maxR + (hasExpert ? 44 : 36)
      const lx = cx + labelR * Math.cos(angle)
      const ly = cy + labelR * Math.sin(angle)

      // 指標名
      ctx.font = '10px sans-serif'
      ctx.fillStyle = GROUP[i] === 'A' ? COLORS.groupA : COLORS.groupB
      ctx.fillText(LABELS[i], lx, ly - (hasExpert ? 12 : 7))

      // 学習者スコア
      ctx.font = 'bold 12px sans-serif'
      ctx.fillStyle = COLORS.score
      const scoreText = rawValues[i] < 0 ? 'N/A' : `${values[i].toFixed(0)}`
      if (hasExpert && expertValues) {
        // 2段表示: 上に学習者、下に基準
        ctx.fillStyle = COLORS.learnerPoint
        ctx.fillText(scoreText, lx, ly + 1)

        ctx.font = '10px sans-serif'
        ctx.fillStyle = COLORS.expertScore
        ctx.fillText(`基準: ${expertValues[i].toFixed(0)}`, lx, ly + 15)
      } else {
        ctx.fillText(scoreText, lx, ly + 8)
      }
    }
  }, [values, expertValues, hasExpert])

  return (
    <div className={`bg-white rounded-lg border border-gray-200 shadow-sm p-4 ${className}`}>
      <h3 className="text-base font-semibold text-gray-700 mb-2">6指標レーダー</h3>
      {hasExpert && (
        <div className="flex items-center gap-4 mb-2 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-0.5 bg-blue-500 rounded" />
            <span className="text-gray-600">学習者</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-0.5 bg-green-500 rounded" style={{ borderTop: '2px dashed #16A34A' }} />
            <span className="text-gray-600">基準（エキスパート）</span>
          </span>
        </div>
      )}
      <canvas
        ref={canvasRef}
        className="w-full aspect-square max-w-[340px] mx-auto"
      />
    </div>
  )
}

export default MetricsRadarChart
