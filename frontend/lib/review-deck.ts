/**
 * Review Deck API クライアント。
 * バックエンド GET /api/v1/analysis/{id}/events と /timeline を叩く。
 */

import { api } from '@/lib/api'
import type {
  ReviewEventsResponse,
  TimelineResponse,
} from '@/types/review-deck'

export async function fetchReviewEvents(
  analysisId: string
): Promise<ReviewEventsResponse> {
  const { data } = await api.get<ReviewEventsResponse>(
    `/analysis/${analysisId}/events`
  )
  return data
}

export async function fetchMetricsTimeline(
  analysisId: string,
  intervalSec = 0.5
): Promise<TimelineResponse> {
  const { data } = await api.get<TimelineResponse>(
    `/analysis/${analysisId}/timeline`,
    { params: { interval_sec: intervalSec } }
  )
  return data
}
