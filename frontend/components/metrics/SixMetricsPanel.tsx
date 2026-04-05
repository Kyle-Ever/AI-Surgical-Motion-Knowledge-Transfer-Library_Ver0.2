'use client'

import React, { useState, useMemo } from 'react'
import { Activity, Timer, BarChart3, PlayCircle } from 'lucide-react'
import MetricCard from './MetricCard'

interface SixMetricsData {
  evaluation_mode: string
  expert_baseline_used: boolean
  overall_score: number
  motion_quality: {
    group_score: number
    metrics: Record<string, {
      metric_id: string
      metric_label_ja: string
      score: number
      ratio_to_expert: number | null
      evaluation_mode: string
      raw_values: Record<string, any>
    }>
  }
  waste_detection: {
    group_score: number
    metrics: Record<string, {
      metric_id: string
      metric_label_ja: string
      score: number
      ratio_to_expert: number | null
      evaluation_mode: string
      raw_values: Record<string, any>
    }>
  }
}

interface TimelineEntry {
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

interface SixMetricsPanelProps {
  data: SixMetricsData | null
  timeline?: TimelineEntry[]
  currentVideoTime?: number
  evaluationTab?: 'absolute' | 'relative'
  hasRelativeData?: boolean
  onEvaluationTabChange?: (tab: 'absolute' | 'relative') => void
}

type ViewMode = 'total' | 'realtime'

function getRawText(metricName: string, rawValues: Record<string, any>): string {
  switch (metricName) {
    case 'economy_of_motion':
      return `${rawValues.total_path_length?.toFixed(2) ?? '--'} (${rawValues.path_length_per_second?.toFixed(2) ?? '--'}/s)`
    case 'smoothness':
      return `SPARC: ${rawValues.sparc_value?.toFixed(2) ?? '--'}`
    case 'bimanual_coordination':
      return `相関: ${rawValues.velocity_correlation?.toFixed(2) ?? '--'}`
    case 'lost_time': {
      const lost = rawValues.lost_time_seconds ?? 0
      const checks = rawValues.check_pause_count ?? 0
      return `ロスト${lost.toFixed(1)}s / 確認${checks}回`
    }
    case 'movement_count':
      return `${rawValues.movements_per_minute?.toFixed(1) ?? '--'}回/分`
    case 'working_volume': {
      const ratio = rawValues.ratio_to_expert
      if (ratio) {
        const dir = rawValues.deviation_direction === 'larger' ? 'やや広い' : 'やや狭い'
        return `Expert×${ratio.toFixed(2)} (${dir})`
      }
      return `面積: ${rawValues.convex_hull_area?.toFixed(4) ?? '--'}`
    }
    default:
      return ''
  }
}

// === Timeline Lookup（バックエンドで事前計算された累積スコアを参照） ===
function lookupTimeline(timeline: TimelineEntry[] | undefined, currentTime: number): TimelineEntry | null {
  if (!timeline || timeline.length === 0 || currentTime <= 0) return null
  // currentTime以下の最後のエントリを返す
  let result: TimelineEntry | null = null
  for (const entry of timeline) {
    if (entry.timestamp <= currentTime) {
      result = entry
    } else {
      break
    }
  }
  return result
}

const SixMetricsPanel: React.FC<SixMetricsPanelProps> = ({
  data, timeline, currentVideoTime,
  evaluationTab, hasRelativeData, onEvaluationTabChange,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('total')

  const realtimeEntry = useMemo(() => {
    if (viewMode !== 'realtime') return null
    return lookupTimeline(timeline, currentVideoTime || 0)
  }, [viewMode, timeline, currentVideoTime])

  if (!data && !timeline) {
    return (
      <div className="text-center text-gray-400 py-8">
        6指標データなし
      </div>
    )
  }

  // データ表示モード切替（総合/リアルタイム） — inline JSXとして定義
  const dataModeToggle = (
    <div className="inline-flex rounded-md border border-gray-300 overflow-hidden text-xs">
      <button
        onClick={(e) => { e.stopPropagation(); setViewMode('total') }}
        className={`px-2.5 py-1 flex items-center gap-1 ${
          viewMode === 'total'
            ? 'bg-gray-800 text-white'
            : 'bg-white text-gray-600 hover:bg-gray-50'
        }`}
      >
        <BarChart3 className="w-3 h-3" />
        総合
      </button>
      <button
        onClick={(e) => { e.stopPropagation(); setViewMode('realtime') }}
        className={`px-2.5 py-1 flex items-center gap-1 ${
          viewMode === 'realtime'
            ? 'bg-gray-800 text-white'
            : 'bg-white text-gray-600 hover:bg-gray-50'
        }`}
      >
        <PlayCircle className="w-3 h-3" />
        リアルタイム
      </button>
    </div>
  )

  // 評価モード切替（絶対/相対）
  const evalModeToggle = (hasRelativeData && onEvaluationTabChange) ? (
    <div className="inline-flex rounded-md border border-gray-300 overflow-hidden text-xs">
      <button
        onClick={(e) => { e.stopPropagation(); onEvaluationTabChange('absolute') }}
        className={`px-2.5 py-1 ${
          evaluationTab === 'absolute'
            ? 'bg-gray-800 text-white'
            : 'bg-white text-gray-600 hover:bg-gray-50'
        }`}
      >
        絶対評価
      </button>
      <button
        onClick={(e) => { e.stopPropagation(); onEvaluationTabChange('relative') }}
        className={`px-2.5 py-1 ${
          evaluationTab === 'relative'
            ? 'bg-purple-700 text-white'
            : 'bg-white text-gray-600 hover:bg-gray-50'
        }`}
      >
        相対評価
      </button>
    </div>
  ) : null

  // === リアルタイムモード（timeline lookup） ===
  if (viewMode === 'realtime') {
    const e = realtimeEntry
    const overall = e?.overall ?? 0
    const overallColor = overall >= 80 ? 'text-green-600' : overall >= 60 ? 'text-yellow-600' : 'text-red-600'
    const overallBarColor = overall >= 80 ? 'bg-green-500' : overall >= 60 ? 'bg-yellow-500' : 'bg-red-500'

    return (
      <div className="space-y-4">
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold text-gray-700">総合スコア</span>
              {dataModeToggle}
              {evalModeToggle}
            </div>
            <span className={`text-3xl font-bold ${overallColor}`}>{overall.toFixed(1)}</span>
          </div>
          <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-300 ${overallBarColor}`} style={{ width: `${Math.min(overall, 100)}%` }} />
          </div>
          {!e && <div className="text-xs text-gray-400 mt-1">動画を再生するとスコアが表示されます</div>}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Group A */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border border-blue-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-blue-600" />動作品質
              </h3>
              <span className="text-lg font-bold text-blue-700">{(e?.mq ?? 0).toFixed(1)}</span>
            </div>
            <MetricCard label="動作経済性" score={e?.a1 ?? 0} color="blue" barColorClass="bg-blue-500" />
            <MetricCard label="動作滑らかさ" score={e?.a2 ?? 0} color="blue" barColorClass="bg-indigo-500" />
            <MetricCard label="両手協調性" score={e?.a3 ?? 0} color="blue" barColorClass="bg-cyan-500" />
          </div>

          {/* Group B */}
          <div className="bg-gradient-to-br from-red-50 to-orange-50 rounded-lg border border-red-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
                <Timer className="w-4 h-4 text-red-600" />ムダ検出
              </h3>
              <span className="text-lg font-bold text-red-700">{(e?.wd ?? 0).toFixed(1)}</span>
            </div>
            <MetricCard label="ロスタイム" score={e?.b1 ?? 0} color="red" barColorClass="bg-red-500" />
            <MetricCard label="動作回数効率" score={e?.b2 ?? 0} color="red" barColorClass="bg-orange-500" />
            <MetricCard label="作業空間偏差" score={e?.b3 ?? 0} color="red" barColorClass="bg-yellow-500" />
          </div>
        </div>
      </div>
    )
  }

  // === 総合評価モード ===
  const mq = data!.motion_quality
  const wd = data!.waste_detection
  const mqMetrics = Object.entries(mq.metrics)
  const wdMetrics = Object.entries(wd.metrics)

  const overallColor =
    data!.overall_score >= 80 ? 'text-green-600' :
    data!.overall_score >= 60 ? 'text-yellow-600' :
    'text-red-600'

  const overallBarColor =
    data!.overall_score >= 80 ? 'bg-green-500' :
    data!.overall_score >= 60 ? 'bg-yellow-500' :
    'bg-red-500'

  const modeLabel = data!.evaluation_mode === 'relative' ? '相対評価' : '絶対評価'
  const modeBadgeColor = data!.evaluation_mode === 'relative'
    ? 'bg-purple-100 text-purple-700'
    : 'bg-gray-100 text-gray-600'

  return (
    <div className="space-y-4">
      {/* 総合スコアバナー */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-gray-700">総合スコア</span>
            <DataModeToggle />
            <EvalModeToggle />
          </div>
          <span className={`text-3xl font-bold ${overallColor}`}>
            {data!.overall_score.toFixed(1)}
          </span>
        </div>
        <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${overallBarColor}`}
            style={{ width: `${Math.min(data!.overall_score, 100)}%` }}
          />
        </div>
      </div>

      {/* Group A + Group B 左右配置 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Group A: 動作品質 */}
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border border-blue-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-blue-600" />
              動作品質
            </h3>
            <span className="text-lg font-bold text-blue-700">{mq.group_score.toFixed(1)}</span>
          </div>
          {mqMetrics.map(([name, m]) => (
            <MetricCard
              key={m.metric_id}
              label={m.metric_label_ja}
              score={m.score}
              rawText={getRawText(name, m.raw_values)}
              color="blue"
              barColorClass={
                m.metric_id === 'A1' ? 'bg-blue-500' :
                m.metric_id === 'A2' ? 'bg-indigo-500' :
                'bg-cyan-500'
              }
            />
          ))}
        </div>

        {/* Group B: ムダ検出 */}
        <div className="bg-gradient-to-br from-red-50 to-orange-50 rounded-lg border border-red-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
              <Timer className="w-4 h-4 text-red-600" />
              ムダ検出
            </h3>
            <span className="text-lg font-bold text-red-700">{wd.group_score.toFixed(1)}</span>
          </div>
          {wdMetrics.map(([name, m]) => (
            <MetricCard
              key={m.metric_id}
              label={m.metric_label_ja}
              score={m.score}
              rawText={getRawText(name, m.raw_values)}
              color="red"
              barColorClass={
                m.metric_id === 'B1' ? 'bg-red-500' :
                m.metric_id === 'B2' ? 'bg-orange-500' :
                'bg-yellow-500'
              }
            />
          ))}
        </div>
      </div>
    </div>
  )
}

export default SixMetricsPanel
