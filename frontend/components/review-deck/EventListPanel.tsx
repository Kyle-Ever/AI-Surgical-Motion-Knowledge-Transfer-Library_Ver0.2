'use client'

import { useMemo } from 'react'
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Info,
  PlayCircle,
  Sparkles,
} from 'lucide-react'
import { cn, formatTime } from '@/lib/utils'
import {
  INDICATOR_LABELS,
  INDICATOR_ORDER,
  INDICATOR_GROUPS,
} from '@/types/review-deck'
import type {
  EventIndicator,
  EventSeverity,
  ReviewEvent,
} from '@/types/review-deck'

interface EventListPanelProps {
  events: ReviewEvent[]
  filteredEvents: ReviewEvent[]
  selectedEventId: string | null
  onSelect: (id: string) => void
  onPrev: () => void
  onNext: () => void
  onJumpVideo: (time: number) => void
  filter: {
    indicators: Set<EventIndicator>
    severities: Set<EventSeverity>
  }
  onToggleIndicator: (ind: EventIndicator) => void
  onToggleSeverity: (sev: EventSeverity) => void
  onResetFilter: () => void
  thresholdsVersion: string | null
}

// severity を日本語化: 元の「気づき (notable)」はリスト全体と重複するので「注目」に
const SEVERITY_CHIPS: { key: EventSeverity; label: string }[] = [
  { key: 'hot', label: '重要' },
  { key: 'notable', label: '注目' },
  { key: 'normal', label: '通常' },
]

const SEVERITY_BADGE: Record<EventSeverity, string> = {
  normal: 'bg-gray-100 text-gray-700 border border-gray-300',
  notable: 'bg-amber-100 text-amber-800 border border-amber-300',
  hot: 'bg-red-100 text-red-700 border border-red-300',
}

const SEVERITY_LABEL_JA: Record<EventSeverity, string> = {
  normal: '通常',
  notable: '注目',
  hot: '重要',
}

const GROUP_COLOR = {
  motion_quality: '#0D8A8C',
  waste_detection: '#C2410C',
}
const HOT_COLOR = '#DC2626'

export default function EventListPanel({
  events,
  filteredEvents,
  selectedEventId,
  onSelect,
  onPrev,
  onNext,
  onJumpVideo,
  filter,
  onToggleIndicator,
  onToggleSeverity,
  onResetFilter,
  thresholdsVersion,
}: EventListPanelProps) {
  const hotCount = useMemo(
    () => events.filter((e) => e.severity === 'hot').length,
    [events]
  )

  const selectedIndex = filteredEvents.findIndex((e) => e.id === selectedEventId)
  const selected =
    selectedIndex >= 0 ? filteredEvents[selectedIndex] : filteredEvents[0]
  const currentIndex = selectedIndex >= 0 ? selectedIndex : 0
  const total = filteredEvents.length

  return (
    <div className="flex flex-col h-full bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
      {/* ヘッダー */}
      <div className="px-4 py-3 border-b border-gray-100">
        <div className="flex items-baseline justify-between">
          <h3 className="text-base font-bold text-gray-900">フィードバック</h3>
          <span className="text-xs text-gray-500">
            {filteredEvents.length} / {events.length} 件
            {hotCount > 0 && (
              <span className="ml-1 text-red-600 font-semibold">
                （重要 {hotCount}）
              </span>
            )}
          </span>
        </div>
        {thresholdsVersion && (
          <div className="mt-0.5 text-[10px] text-gray-400">
            判定バージョン {thresholdsVersion}
          </div>
        )}
      </div>

      {/* フィルタ */}
      <div className="px-4 py-2 border-b border-gray-100 space-y-1.5 bg-gray-50">
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-[10px] text-gray-500 mr-1">指標</span>
          {INDICATOR_ORDER.map((ind) => {
            const active = filter.indicators.has(ind)
            return (
              <button
                key={ind}
                onClick={() => onToggleIndicator(ind)}
                className={cn(
                  'text-[11px] font-medium px-1.5 py-0.5 rounded border transition-colors',
                  active
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400'
                )}
                title={INDICATOR_LABELS[ind]}
              >
                {ind}
              </button>
            )
          })}
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-[10px] text-gray-500 mr-1">重要度</span>
          {SEVERITY_CHIPS.map(({ key, label }) => {
            const active = filter.severities.has(key)
            return (
              <button
                key={key}
                onClick={() => onToggleSeverity(key)}
                className={cn(
                  'text-[11px] font-medium px-1.5 py-0.5 rounded border transition-colors',
                  active
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400'
                )}
              >
                {label}
              </button>
            )
          })}
          <button
            onClick={onResetFilter}
            className="ml-auto text-[10px] text-gray-400 hover:text-gray-700"
          >
            リセット
          </button>
        </div>
      </div>

      {/* 本体: カード 1 件 */}
      <div className="flex-1 flex flex-col min-h-0">
        {total === 0 ? (
          <div className="flex-1 flex items-center justify-center p-6 text-sm text-gray-400 text-center">
            条件に一致するフィードバックがありません
          </div>
        ) : selected ? (
          <FeedbackCard
            event={selected}
            index={currentIndex + 1}
            total={total}
            onPrev={onPrev}
            onNext={onNext}
            onJumpVideo={onJumpVideo}
          />
        ) : null}

        {total > 0 && (
          <MiniDotStrip
            events={filteredEvents}
            selectedId={selectedEventId}
            onSelect={onSelect}
          />
        )}
      </div>
    </div>
  )
}


// ================================================================
// フィードバックカード
// ================================================================

function FeedbackCard({
  event,
  index,
  total,
  onPrev,
  onNext,
  onJumpVideo,
}: {
  event: ReviewEvent
  index: number
  total: number
  onPrev: () => void
  onNext: () => void
  onJumpVideo: (time: number) => void
}) {
  const groupLabel =
    INDICATOR_GROUPS[event.indicator] === 'motion_quality'
      ? '動作品質'
      : 'むだ検出'

  return (
    <div className="flex-1 flex flex-col overflow-y-auto">
      {/* ナビバー */}
      <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-2 bg-white border-b border-gray-100">
        <button
          onClick={onPrev}
          className="flex items-center gap-0.5 px-2 py-1 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded"
          aria-label="前のフィードバック"
        >
          <ChevronLeft className="w-4 h-4" />
          前へ
        </button>
        <span className="text-sm text-gray-700 font-medium tabular-nums">
          <span className="text-blue-600 font-bold">{index}</span>
          <span className="text-gray-400"> / {total}</span>
        </span>
        <button
          onClick={onNext}
          className="flex items-center gap-0.5 px-2 py-1 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded"
          aria-label="次のフィードバック"
        >
          次へ
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      <div className="px-4 py-4 space-y-4">
        {/* バッジ行 */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className={cn(
              'text-xs font-bold px-2 py-0.5 rounded-full',
              SEVERITY_BADGE[event.severity]
            )}
          >
            {SEVERITY_LABEL_JA[event.severity]}
          </span>
          <span className="text-xs font-semibold bg-gray-900 text-white px-2 py-0.5 rounded-full">
            {event.indicator}
          </span>
          <span className="text-xs text-gray-600">{groupLabel}</span>
          <span className="text-gray-300">·</span>
          <span className="text-xs text-gray-700 font-medium">
            {INDICATOR_LABELS[event.indicator]}
          </span>
        </div>

        {/* 時刻とタイトル */}
        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-3xl font-bold text-gray-900 tabular-nums">
              {formatTime(event.timestamp)}
            </span>
            {event.duration && event.duration > 0.1 && (
              <span className="text-sm text-gray-500">
                持続 {event.duration.toFixed(1)} 秒
              </span>
            )}
          </div>
          <div className="mt-1 text-base font-bold text-gray-900">
            {event.title}
          </div>
        </div>

        {/* 動画ジャンプボタン */}
        <button
          onClick={() => onJumpVideo(event.timestamp)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md transition-colors"
        >
          <PlayCircle className="w-4 h-4" />
          この時刻から動画を再生
        </button>

        {/* セクション: 起きていたこと */}
        {event.coaching_fact && (
          <Section
            icon={<AlertTriangle className="w-4 h-4 text-gray-600" />}
            title="起きていたこと"
            titleClass="text-gray-800"
            body={event.coaching_fact}
            bodyClass="text-gray-900"
          />
        )}

        {/* セクション: どうして気にするか */}
        {event.coaching_why && (
          <Section
            icon={<Info className="w-4 h-4 text-amber-600" />}
            title="どうして気にするか"
            titleClass="text-amber-700"
            body={event.coaching_why}
            bodyClass="text-gray-700"
          />
        )}

        {/* セクション: 次に意識すること (青背景で強調) */}
        {event.coaching_action && (
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
            <div className="flex items-center gap-1.5 text-sm font-bold text-blue-800">
              <Sparkles className="w-4 h-4" />
              次に意識すること
            </div>
            <p className="mt-1.5 text-sm text-gray-800 leading-relaxed">
              {event.coaching_action}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}


// ================================================================
// セクション (fact / why)
// ================================================================

function Section({
  icon,
  title,
  titleClass,
  body,
  bodyClass,
}: {
  icon: React.ReactNode
  title: string
  titleClass: string
  body: string
  bodyClass: string
}) {
  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-1.5 text-sm font-bold mb-1',
          titleClass
        )}
      >
        {icon}
        {title}
      </div>
      <p className={cn('text-sm leading-relaxed', bodyClass)}>{body}</p>
    </div>
  )
}


// ================================================================
// ミニタイムライン (ドット)
// ================================================================

function MiniDotStrip({
  events,
  selectedId,
  onSelect,
}: {
  events: ReviewEvent[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  if (events.length === 0) return null
  return (
    <div className="flex items-center gap-1.5 px-4 py-2.5 border-t border-gray-100 bg-gray-50 overflow-x-auto">
      <span className="text-[10px] text-gray-500 mr-1 flex-shrink-0">
        一覧
      </span>
      {events.map((ev) => {
        const selected = ev.id === selectedId
        const color = ev.severity === 'hot' ? HOT_COLOR : GROUP_COLOR[ev.category]
        return (
          <button
            key={ev.id}
            data-event-id={ev.id}
            onClick={() => onSelect(ev.id)}
            title={`${formatTime(ev.timestamp)}  ${ev.title}`}
            className={cn(
              'flex-shrink-0 transition-all rounded-full',
              selected
                ? 'w-3.5 h-3.5 ring-2 ring-blue-500 ring-offset-1'
                : 'w-2.5 h-2.5 hover:w-3 hover:h-3'
            )}
            style={{ background: color }}
            aria-label={`${ev.indicator} at ${formatTime(ev.timestamp)}`}
          />
        )
      })}
    </div>
  )
}
