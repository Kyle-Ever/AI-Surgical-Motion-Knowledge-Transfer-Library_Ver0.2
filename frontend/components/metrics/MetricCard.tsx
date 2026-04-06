'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Info } from 'lucide-react'

interface MetricCardProps {
  label: string
  score: number        // -1 = N/A (データ不足)
  rawText?: string
  color: string
  barColorClass: string
  /** 常時表示の1行説明 */
  subtitle?: string
  /** (i)クリック時の詳細説明 */
  detail?: string
}

function DetailPopover({ detail, onClose }: { detail: string; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="absolute z-50 left-0 top-full mt-1 w-72 px-3 py-2.5 text-xs leading-relaxed text-gray-700 bg-white border border-gray-200 rounded-lg shadow-lg"
    >
      {detail}
    </div>
  )
}

const MetricCard: React.FC<MetricCardProps> = ({ label, score, rawText, barColorClass, subtitle, detail }) => {
  const [showDetail, setShowDetail] = useState(false)
  const isNA = score < 0

  if (isNA) {
    return (
      <div className="flex items-center gap-3 py-2 opacity-50">
        <div className="w-32 shrink-0">
          <div className="flex items-center gap-1">
            <span className="text-xs font-medium text-gray-700 truncate">{label}</span>
          </div>
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
      <div className="w-32 shrink-0 relative">
        <div className="flex items-center gap-1">
          <span className="text-xs font-medium text-gray-700 truncate">{label}</span>
          {detail && (
            <button
              onClick={(e) => { e.stopPropagation(); setShowDetail(!showDetail) }}
              className="text-gray-300 hover:text-blue-500 transition-colors shrink-0"
            >
              <Info className="w-3 h-3" />
            </button>
          )}
        </div>
        {subtitle && <div className="text-[11px] text-gray-500 leading-tight">{subtitle}</div>}
        {rawText && <div className="text-[10px] text-gray-400 truncate">{rawText}</div>}
        {showDetail && detail && (
          <DetailPopover detail={detail} onClose={() => setShowDetail(false)} />
        )}
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
