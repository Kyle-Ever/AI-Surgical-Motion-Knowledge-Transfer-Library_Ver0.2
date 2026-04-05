'use client'

import React from 'react'

interface MetricCardProps {
  label: string
  score: number        // -1 = N/A (データ不足)
  rawText?: string
  color: string
  barColorClass: string
}

const MetricCard: React.FC<MetricCardProps> = ({ label, score, rawText, barColorClass }) => {
  const isNA = score < 0

  if (isNA) {
    return (
      <div className="flex items-center gap-3 py-2 opacity-50">
        <div className="w-28 shrink-0">
          <div className="text-xs font-medium text-gray-700 truncate">{label}</div>
          <div className="text-[10px] text-gray-400 truncate">データ不足</div>
        </div>
        <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
          <div className="h-full rounded-full bg-gray-300" style={{ width: '0%' }} />
        </div>
        <div className="w-10 text-right text-sm font-bold text-gray-400">
          N/A
        </div>
      </div>
    )
  }

  const pct = Math.min(Math.max(score, 0), 100)

  const scoreColor =
    pct >= 80 ? 'text-green-600' :
    pct >= 60 ? 'text-yellow-600' :
    'text-red-600'

  return (
    <div className="flex items-center gap-3 py-2">
      <div className="w-28 shrink-0">
        <div className="text-xs font-medium text-gray-700 truncate">{label}</div>
        {rawText && <div className="text-[10px] text-gray-400 truncate">{rawText}</div>}
      </div>
      <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${barColorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className={`w-10 text-right text-sm font-bold ${scoreColor}`}>
        {pct.toFixed(0)}
      </div>
    </div>
  )
}

export default MetricCard
