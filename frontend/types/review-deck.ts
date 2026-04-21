/**
 * Review Deck のイベント・タイムライン型。
 * バックエンド app/schemas/review_event.py と 1:1 対応する。
 */

export type EventSeverity = 'normal' | 'notable' | 'hot'

export type EventIndicator = 'A1' | 'A2' | 'A3' | 'B1' | 'B2' | 'B3'

export type EventCategory = 'motion_quality' | 'waste_detection'

export interface ReviewEvent {
  id: string
  timestamp: number
  duration: number | null
  indicator: EventIndicator
  category: EventCategory
  severity: EventSeverity
  title: string
  description: string
  /** 事実: 時刻 + 何が起きたか (定量付き) */
  coaching_fact: string
  /** なぜ問題か: 手技学的な意味 */
  coaching_why: string
  /** 次に意識すること: 実習生向けヒント */
  coaching_action: string
  related_event_ids: string[]
}

export interface ReviewEventsResponse {
  analysis_id: string
  has_events: boolean
  events: ReviewEvent[]
  generated_at: string | null
  thresholds_version: string | null
}

export interface TimelineSample {
  timestamp: number
  overall: number
  mq: number
  wd: number
  a1: number
  a2: number
  a3: number
  b1: number
  b2: number
  b3: number
}

export interface TimelineResponse {
  analysis_id: string
  interval_sec: number
  samples: TimelineSample[]
}

/**
 * 6指標の日本語ラベル。
 * SixMetricsPanel / MetricScorer (metric_label_ja) と統一して使う。
 */
export const INDICATOR_LABELS: Record<EventIndicator, string> = {
  A1: '動作経済性',
  A2: '動作滑らかさ',
  A3: '両手協調性',
  B1: 'ロスタイム',
  B2: '動作回数効率',
  B3: '作業空間偏差',
}

export const INDICATOR_GROUPS: Record<EventIndicator, EventCategory> = {
  A1: 'motion_quality',
  A2: 'motion_quality',
  A3: 'motion_quality',
  B1: 'waste_detection',
  B2: 'waste_detection',
  B3: 'waste_detection',
}

/** Aグループ: teal / Bグループ: orange / hot: red — 計画書§6.4 に合わせる */
export const SEVERITY_BG: Record<EventSeverity, string> = {
  normal: 'bg-gray-200 text-gray-700',
  notable: 'bg-teal-100 text-teal-800',
  hot: 'bg-red-100 text-red-700',
}

export const CATEGORY_ACCENT: Record<EventCategory, string> = {
  motion_quality: 'bg-teal-500',
  waste_detection: 'bg-orange-500',
}

export const INDICATOR_ORDER: EventIndicator[] = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3']
