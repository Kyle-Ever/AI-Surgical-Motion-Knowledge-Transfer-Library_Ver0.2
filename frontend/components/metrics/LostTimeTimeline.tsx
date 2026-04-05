'use client'

import React from 'react'
import { formatTime } from '@/lib/utils'

interface LostTimeSegment {
  start_frame: number
  end_frame: number
  duration_seconds: number
  start_time: number
}

interface LostTimeTimelineProps {
  totalDuration: number   // 動画の総時間（秒）
  lostSegments: LostTimeSegment[]
  checkPauseCount: number
  checkPauseTotalSeconds: number
  lostTimeSeconds: number
  currentTime?: number    // 動画の現在時刻
  onSeek?: (time: number) => void
  className?: string
}

const LostTimeTimeline: React.FC<LostTimeTimelineProps> = ({
  totalDuration,
  lostSegments,
  checkPauseCount,
  checkPauseTotalSeconds,
  lostTimeSeconds,
  currentTime = 0,
  onSeek,
  className = '',
}) => {
  if (totalDuration <= 0) return null

  const playheadPct = (currentTime / totalDuration) * 100

  return (
    <div className={`bg-white rounded-lg border border-gray-200 shadow-sm p-3 overflow-hidden ${className}`}>
      <div className="flex items-center justify-between mb-1.5 min-w-0">
        <h3 className="text-xs font-semibold text-gray-600">ロスタイム タイムライン</h3>
        <div className="flex items-center gap-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 bg-red-400 rounded-sm" />
            ロスタイム {lostTimeSeconds.toFixed(1)}s
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-b-[6px] border-b-yellow-500" />
            確認停止 {checkPauseCount}回 ({checkPauseTotalSeconds.toFixed(1)}s)
          </span>
        </div>
      </div>

      {/* タイムライン */}
      <div
        className="relative h-6 bg-gray-100 rounded cursor-pointer w-full overflow-hidden"
        onClick={(e) => {
          if (!onSeek) return
          const rect = e.currentTarget.getBoundingClientRect()
          const pct = (e.clientX - rect.left) / rect.width
          onSeek(pct * totalDuration)
        }}
      >
        {/* ロスタイム区間（赤） */}
        {lostSegments.map((seg, i) => {
          const left = (seg.start_time / totalDuration) * 100
          const width = (seg.duration_seconds / totalDuration) * 100
          return (
            <div
              key={i}
              className="absolute top-0 h-full bg-red-400 opacity-70 rounded-sm hover:opacity-100 transition-opacity"
              style={{ left: `${left}%`, width: `${Math.max(width, 0.3)}%` }}
              title={`${formatTime(seg.start_time)} - ${seg.duration_seconds.toFixed(1)}s`}
            />
          )
        })}

        {/* 再生位置 */}
        <div
          className="absolute top-0 h-full w-0.5 bg-blue-600 z-10"
          style={{ left: `${playheadPct}%` }}
        />

        {/* 時間ラベル */}
        <div className="absolute bottom-0 left-1 text-[9px] text-gray-400 leading-6">
          {formatTime(0)}
        </div>
        <div className="absolute bottom-0 right-1 text-[9px] text-gray-400 leading-6">
          {formatTime(totalDuration)}
        </div>
      </div>
    </div>
  )
}

export default LostTimeTimeline
