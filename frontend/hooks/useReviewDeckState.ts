'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchMetricsTimeline, fetchReviewEvents } from '@/lib/review-deck'
import type {
  EventIndicator,
  EventSeverity,
  ReviewEvent,
  TimelineSample,
} from '@/types/review-deck'

export interface ReviewDeckFilter {
  indicators: Set<EventIndicator>
  severities: Set<EventSeverity>
}

interface UseReviewDeckStateResult {
  loading: boolean
  error: string | null
  hasEvents: boolean
  events: ReviewEvent[]
  filteredEvents: ReviewEvent[]
  timeline: TimelineSample[]
  selectedEventId: string | null
  selectedEvent: ReviewEvent | null
  selectEvent: (id: string | null) => void
  goNextEvent: () => void
  goPrevEvent: () => void
  filter: ReviewDeckFilter
  toggleIndicator: (ind: EventIndicator) => void
  toggleSeverity: (sev: EventSeverity) => void
  resetFilter: () => void
  seekSignal: { time: number; token: number } | undefined
  triggerSeek: (time: number) => void
  refresh: () => Promise<void>
  thresholdsVersion: string | null
}

const ALL_INDICATORS: EventIndicator[] = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3']
const ALL_SEVERITIES: EventSeverity[] = ['normal', 'notable', 'hot']

const STORAGE_KEY_PREFIX = 'review-deck-selection:'

export function useReviewDeckState(
  analysisId: string | undefined,
  options?: { enabled?: boolean }
): UseReviewDeckStateResult {
  const enabled = options?.enabled ?? true

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasEvents, setHasEvents] = useState(false)
  const [events, setEvents] = useState<ReviewEvent[]>([])
  const [timeline, setTimeline] = useState<TimelineSample[]>([])
  const [thresholdsVersion, setThresholdsVersion] = useState<string | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const [seekSignal, setSeekSignal] = useState<{ time: number; token: number }>()

  const [filter, setFilter] = useState<ReviewDeckFilter>({
    indicators: new Set(ALL_INDICATORS),
    severities: new Set(ALL_SEVERITIES),
  })

  const seekTokenRef = useRef(0)

  // --- fetch ---
  const load = useCallback(async () => {
    if (!analysisId) return
    setLoading(true)
    setError(null)
    try {
      const [eventsRes, timelineRes] = await Promise.all([
        fetchReviewEvents(analysisId),
        fetchMetricsTimeline(analysisId, 0.5).catch(() => ({
          analysis_id: analysisId,
          interval_sec: 0.5,
          samples: [] as TimelineSample[],
        })),
      ])
      setHasEvents(eventsRes.has_events)
      setEvents(eventsRes.events)
      setTimeline(timelineRes.samples)
      setThresholdsVersion(eventsRes.thresholds_version)

      // 選択状態の復元 (sessionStorage)
      const stored =
        typeof window !== 'undefined'
          ? window.sessionStorage.getItem(STORAGE_KEY_PREFIX + analysisId)
          : null
      if (stored && eventsRes.events.some((e) => e.id === stored)) {
        setSelectedEventId(stored)
      } else if (eventsRes.events.length > 0) {
        setSelectedEventId(eventsRes.events[0].id)
      } else {
        setSelectedEventId(null)
      }
    } catch (err) {
      console.error('[useReviewDeckState] fetch failed', err)
      setError(err instanceof Error ? err.message : '読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }, [analysisId])

  useEffect(() => {
    if (!enabled || !analysisId) return
    load()
  }, [enabled, analysisId, load])

  // --- persistence ---
  useEffect(() => {
    if (!analysisId || typeof window === 'undefined') return
    if (selectedEventId) {
      window.sessionStorage.setItem(
        STORAGE_KEY_PREFIX + analysisId,
        selectedEventId
      )
    }
  }, [analysisId, selectedEventId])

  // --- filters ---
  const toggleIndicator = useCallback((ind: EventIndicator) => {
    setFilter((prev) => {
      const next = new Set(prev.indicators)
      if (next.has(ind)) next.delete(ind)
      else next.add(ind)
      return { ...prev, indicators: next }
    })
  }, [])

  const toggleSeverity = useCallback((sev: EventSeverity) => {
    setFilter((prev) => {
      const next = new Set(prev.severities)
      if (next.has(sev)) next.delete(sev)
      else next.add(sev)
      return { ...prev, severities: next }
    })
  }, [])

  const resetFilter = useCallback(() => {
    setFilter({
      indicators: new Set(ALL_INDICATORS),
      severities: new Set(ALL_SEVERITIES),
    })
  }, [])

  const filteredEvents = useMemo(() => {
    return events.filter(
      (e) => filter.indicators.has(e.indicator) && filter.severities.has(e.severity)
    )
  }, [events, filter])

  const selectedEvent = useMemo(
    () => events.find((e) => e.id === selectedEventId) ?? null,
    [events, selectedEventId]
  )

  // --- navigation ---
  const triggerSeek = useCallback((time: number) => {
    seekTokenRef.current += 1
    setSeekSignal({ time, token: seekTokenRef.current })
  }, [])

  const selectEvent = useCallback(
    (id: string | null) => {
      setSelectedEventId(id)
      if (id) {
        const target = events.find((e) => e.id === id)
        if (target) {
          triggerSeek(target.timestamp)
        }
      }
    },
    [events, triggerSeek]
  )

  const moveBy = useCallback(
    (delta: 1 | -1) => {
      if (filteredEvents.length === 0) return
      const currentIdx = filteredEvents.findIndex((e) => e.id === selectedEventId)
      const nextIdx =
        currentIdx < 0
          ? delta > 0
            ? 0
            : filteredEvents.length - 1
          : (currentIdx + delta + filteredEvents.length) % filteredEvents.length
      selectEvent(filteredEvents[nextIdx].id)
    },
    [filteredEvents, selectedEventId, selectEvent]
  )

  const goNextEvent = useCallback(() => moveBy(1), [moveBy])
  const goPrevEvent = useCallback(() => moveBy(-1), [moveBy])

  return {
    loading,
    error,
    hasEvents,
    events,
    filteredEvents,
    timeline,
    selectedEventId,
    selectedEvent,
    selectEvent,
    goNextEvent,
    goPrevEvent,
    filter,
    toggleIndicator,
    toggleSeverity,
    resetFilter,
    seekSignal,
    triggerSeek,
    refresh: load,
    thresholdsVersion,
  }
}
