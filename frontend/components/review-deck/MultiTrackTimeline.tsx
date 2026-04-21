'use client'

import { useMemo, useRef, useState } from 'react'
import { cn, formatTime } from '@/lib/utils'
import {
  INDICATOR_LABELS,
  INDICATOR_ORDER,
  INDICATOR_GROUPS,
} from '@/types/review-deck'
import type { EventIndicator, ReviewEvent } from '@/types/review-deck'

interface MultiTrackTimelineProps {
  totalDuration: number
  events: ReviewEvent[]
  selectedEventId: string | null
  currentTime: number
  onSelectEvent: (id: string) => void
  onSeek: (time: number) => void
}

const GROUP_COLOR: Record<EventIndicator, string> = {
  A1: '#0D8A8C',
  A2: '#0D8A8C',
  A3: '#0D8A8C',
  B1: '#C2410C',
  B2: '#C2410C',
  B3: '#C2410C',
}

const HOT_COLOR = '#DC2626'

export default function MultiTrackTimeline({
  totalDuration,
  events,
  selectedEventId,
  currentTime,
  onSelectEvent,
  onSeek,
}: MultiTrackTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoveredEventId, setHoveredEventId] = useState<string | null>(null)

  const eventsByLane = useMemo(() => {
    const map: Record<EventIndicator, ReviewEvent[]> = {
      A1: [], A2: [], A3: [], B1: [], B2: [], B3: [],
    }
    for (const ev of events) {
      map[ev.indicator].push(ev)
    }
    return map
  }, [events])

  if (totalDuration <= 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-3 text-xs text-gray-400">
        動画の長さが取得できないためタイムラインを表示できません。
      </div>
    )
  }

  const pctOf = (t: number) => Math.max(0, Math.min(100, (t / totalDuration) * 100))

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-3 py-1.5 flex items-center justify-between border-b border-gray-100">
        <h3 className="text-xs font-semibold text-gray-700">
          6指標タイムライン
        </h3>
        <div className="flex items-center gap-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: '#0D8A8C' }} />
            動作品質 (A)
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: '#C2410C' }} />
            むだ検出 (B)
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: HOT_COLOR }} />
            重要
          </span>
        </div>
      </div>

      <div ref={containerRef} className="relative">
        {INDICATOR_ORDER.map((ind) => (
          <div key={ind} className="flex items-center border-t border-gray-50">
            <div
              className={cn(
                'w-16 flex-shrink-0 px-2 py-1 text-[10px] font-medium text-gray-600 bg-gray-50 border-r border-gray-100',
                INDICATOR_GROUPS[ind] === 'motion_quality' ? 'text-teal-700' : 'text-orange-700'
              )}
            >
              <div>{ind}</div>
              <div className="text-[9px] text-gray-400 truncate">
                {INDICATOR_LABELS[ind]}
              </div>
            </div>
            <div
              className="relative flex-1 h-7 bg-white cursor-pointer"
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect()
                const pct = (e.clientX - rect.left) / rect.width
                onSeek(pct * totalDuration)
              }}
            >
              {/* イベントマーカー */}
              {eventsByLane[ind].map((ev) => {
                const isDuration = (ev.duration ?? 0) > 0.1
                const left = pctOf(ev.timestamp)
                const width = isDuration ? pctOf(ev.duration!) : 0
                const color = ev.severity === 'hot' ? HOT_COLOR : GROUP_COLOR[ind]
                const isSelected = ev.id === selectedEventId
                const isHovered = ev.id === hoveredEventId
                return (
                  <button
                    key={ev.id}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectEvent(ev.id)
                    }}
                    onMouseEnter={() => setHoveredEventId(ev.id)}
                    onMouseLeave={() => setHoveredEventId(null)}
                    title={`${formatTime(ev.timestamp)}  ${ev.title}`}
                    className={cn(
                      'absolute top-1/2 -translate-y-1/2 rounded-sm transition-all',
                      isSelected
                        ? 'h-5 ring-2 ring-blue-500 z-20'
                        : isHovered
                        ? 'h-4 z-10'
                        : 'h-3'
                    )}
                    style={{
                      left: `${left}%`,
                      width: isDuration ? `${Math.max(width, 0.3)}%` : '6px',
                      background: color,
                      opacity: isSelected ? 1 : 0.85,
                      marginLeft: isDuration ? 0 : '-3px',
                    }}
                    aria-label={`${ev.indicator} ${ev.title}`}
                  />
                )
              })}
            </div>
          </div>
        ))}

        {/* 再生ヘッド (全レーン貫通) */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-blue-600 pointer-events-none z-30"
          style={{ left: `calc(64px + ${pctOf(currentTime)}% - ${pctOf(currentTime) * 0.64 / 100}px)` }}
        />
      </div>

      {/* 時間軸 */}
      <div className="flex border-t border-gray-100">
        <div className="w-16 flex-shrink-0 bg-gray-50" />
        <div className="flex-1 relative h-5 text-[10px] text-gray-400">
          <span className="absolute left-1 top-0.5">{formatTime(0)}</span>
          <span className="absolute right-1 top-0.5">{formatTime(totalDuration)}</span>
          <span className="absolute top-0.5 tabular-nums font-mono text-blue-600"
                style={{ left: `${pctOf(currentTime)}%`, transform: 'translateX(-50%)' }}>
            {formatTime(currentTime)}
          </span>
        </div>
      </div>
    </div>
  )
}
