'use client'

import { useEffect } from 'react'
import dynamic from 'next/dynamic'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { API_BASE_URL } from '@/lib/api'
import { useReviewDeckState } from '@/hooks/useReviewDeckState'
import EventListPanel from './EventListPanel'
import MultiTrackTimeline from './MultiTrackTimeline'

const VideoPlayer = dynamic(() => import('@/components/VideoPlayer'), { ssr: false })

interface ReviewDeckViewProps {
  analysisId: string
  videoId?: string
  videoType?: string
  skeletonData: unknown[]
  toolData: unknown[]
  totalDuration: number
  currentVideoTime: number
  onTimeUpdate: (time: number) => void
}

export default function ReviewDeckView({
  analysisId,
  videoId,
  videoType,
  skeletonData,
  toolData,
  totalDuration,
  currentVideoTime,
  onTimeUpdate,
}: ReviewDeckViewProps) {
  const state = useReviewDeckState(analysisId)

  // キーボードショートカット
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) {
        return
      }
      if (e.key === 'ArrowRight') {
        e.preventDefault()
        state.goNextEvent()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        state.goPrevEvent()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [state])

  if (state.loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
        <p className="mt-3 text-xs text-gray-500">フィードバックを読み込み中...</p>
      </div>
    )
  }

  if (state.error) {
    return (
      <div className="bg-white border border-red-200 rounded-lg p-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="text-sm font-semibold text-red-700">読み込み失敗</div>
            <div className="mt-1 text-xs text-gray-600">{state.error}</div>
            <button
              onClick={() => state.refresh()}
              className="mt-3 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
            >
              <RefreshCw className="w-3 h-3" />
              再試行
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!state.hasEvents) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="text-sm font-semibold text-amber-800">
              この解析にはフィードバックが生成されていません
            </div>
            <div className="mt-1 text-xs text-gray-600 leading-relaxed">
              フィードバックはバージョン 0.2 以降に新規解析された動画で利用できます。
              この解析は既存データのため、再解析するとフィードバックが表示されます。
            </div>
          </div>
        </div>
      </div>
    )
  }

  const videoUrl = videoId ? `${API_BASE_URL}/videos/${videoId}/stream` : undefined

  return (
    <div className="grid grid-cols-12 gap-3">
      {/* 左 (4/12): めくれる気づきカード + ミニタイムライン */}
      <div className="col-span-12 lg:col-span-4 min-h-[32rem] lg:min-h-[40rem]">
        <EventListPanel
          events={state.events}
          filteredEvents={state.filteredEvents}
          selectedEventId={state.selectedEventId}
          onSelect={state.selectEvent}
          onPrev={state.goPrevEvent}
          onNext={state.goNextEvent}
          onJumpVideo={state.triggerSeek}
          filter={state.filter}
          onToggleIndicator={state.toggleIndicator}
          onToggleSeverity={state.toggleSeverity}
          onResetFilter={state.resetFilter}
          thresholdsVersion={state.thresholdsVersion}
        />
      </div>

      {/* 右 (8/12): 動画 + 6 レーンタイムライン */}
      <div className="col-span-12 lg:col-span-8 space-y-3">
        <div className="bg-white rounded-lg shadow-sm p-2">
          <VideoPlayer
            videoUrl={videoUrl}
            skeletonData={skeletonData as never[]}
            toolData={toolData as never[]}
            videoType={videoType}
            onTimeUpdate={onTimeUpdate}
            seekSignal={state.seekSignal}
          />
        </div>
        <MultiTrackTimeline
          totalDuration={totalDuration}
          events={state.events}
          selectedEventId={state.selectedEventId}
          currentTime={currentVideoTime}
          onSelectEvent={state.selectEvent}
          onSeek={state.triggerSeek}
        />
      </div>
    </div>
  )
}
