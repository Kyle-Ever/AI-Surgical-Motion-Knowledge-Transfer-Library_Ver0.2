'use client'

import React, { useState, useMemo } from 'react'
import { Activity, Timer, BarChart3, PlayCircle, Settings, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2 } from 'lucide-react'
import MetricCard from './MetricCard'

// === 指標の説明データ ===
const METRIC_INFO: Record<string, { subtitle: string; detail: string }> = {
  economy_of_motion: {
    subtitle: '手の総移動距離の短さ',
    detail: '手技中の左右の手の総移動距離を評価します。熟練した術者は必要最小限の動きで手技を完了するため移動距離が短くなります。高い＝効率的な動き。ICSAD (Dosis 2005) / JIGSAWS で検証済み。',
  },
  smoothness: {
    subtitle: '動きの滑らかさ',
    detail: 'SPARC（スペクトル弧長）で動作の滑らかさを定量化します。滑らかな動き＝周波数成分が単純＝高スコア。ぎこちない停止・再開が多いと低下します。Balasubramanian et al. (2012) IEEE Trans Biomed Eng。',
  },
  bimanual_coordination: {
    subtitle: '両手の連携の適切さ',
    detail: '両手が十分に検出されている場合は速度の同期度で評価。片手が保持・他方が操作する手技パターンでは、保持手の安定性で評価します。GOALS (Vassiliou 2005) の bimanual dexterity に対応。',
  },
  lost_time: {
    subtitle: '両手同時停止の少なさ',
    detail: '両手とも停止している時間を検出します。片手が保持のために静止している場合はカウントしません。3秒超の両手停止を「迷い・計画不足」として減点します。高い＝迷いが少ない。D\'Angelo et al. (2015) Am J Surg。',
  },
  movement_count: {
    subtitle: '動作回数の少なさ',
    detail: '手技中の離散的な動作回数をカウントします。熟練した術者は少ない動作回数で手技を完了します。ヒステリシス付き閾値で微振動の誤カウントを防止。高い＝効率的。ICSAD (Dosis 2005)。',
  },
  working_volume: {
    subtitle: '作業範囲の適切さ',
    detail: '手の移動範囲の凸包面積で作業空間の広さを評価します。熟練者は必要な範囲に集中して動作するため作業空間が小さくなります。エキスパート基準との比較時は広すぎ・狭すぎの双方を減点。D\'Angelo et al. (2016) Am J Surg。',
  },
}

// metric_id → metric_name のマッピング（リアルタイムモード用）
const METRIC_ID_TO_NAME: Record<string, string> = {
  a1: 'economy_of_motion',
  a2: 'smoothness',
  a3: 'bimanual_coordination',
  b1: 'lost_time',
  b2: 'movement_count',
  b3: 'working_volume',
}

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
  applied_config?: {
    weights: Record<string, number>
    thresholds: Record<string, number>
    scoring: Record<string, number>
    sparc: Record<string, number>
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
      const idleThresh = rawValues.applied_idle_threshold
      const threshStr = idleThresh != null ? ` (閾値${idleThresh})` : ''
      return `ロスト${lost.toFixed(1)}s / 確認${checks}回${threshStr}`
    }
    case 'movement_count': {
      const moveThresh = rawValues.applied_movement_threshold
      const threshStr = moveThresh != null ? ` (閾値${moveThresh})` : ''
      return `${rawValues.movements_per_minute?.toFixed(1) ?? '--'}回/分${threshStr}`
    }
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
  const [viewMode, setViewMode] = useState<ViewMode>('realtime')

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
              <span className="text-base font-semibold text-gray-700">総合スコア</span>
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
              <h3 className="text-base font-bold text-gray-800 flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-blue-600" />動作品質
              </h3>
              <span className="text-lg font-bold text-blue-700">{(e?.mq ?? 0).toFixed(1)}</span>
            </div>
            <MetricCard label="動作経済性" score={e?.a1 ?? 0} color="blue" barColorClass="bg-blue-500" subtitle={METRIC_INFO.economy_of_motion.subtitle} detail={METRIC_INFO.economy_of_motion.detail} />
            <MetricCard label="動作滑らかさ" score={e?.a2 ?? 0} color="blue" barColorClass="bg-indigo-500" subtitle={METRIC_INFO.smoothness.subtitle} detail={METRIC_INFO.smoothness.detail} />
            <MetricCard label="両手協調性" score={e?.a3 ?? 0} color="blue" barColorClass="bg-cyan-500" subtitle={METRIC_INFO.bimanual_coordination.subtitle} detail={METRIC_INFO.bimanual_coordination.detail} />
          </div>

          {/* Group B */}
          <div className="bg-gradient-to-br from-red-50 to-orange-50 rounded-lg border border-red-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-bold text-gray-800 flex items-center gap-1.5">
                <Timer className="w-4 h-4 text-red-600" />ムダ検出
              </h3>
              <span className="text-lg font-bold text-red-700">{(e?.wd ?? 0).toFixed(1)}</span>
            </div>
            <MetricCard label="ロスタイム" score={e?.b1 ?? 0} color="red" barColorClass="bg-red-500" subtitle={METRIC_INFO.lost_time.subtitle} detail={METRIC_INFO.lost_time.detail} />
            <MetricCard label="動作回数効率" score={e?.b2 ?? 0} color="red" barColorClass="bg-orange-500" subtitle={METRIC_INFO.movement_count.subtitle} detail={METRIC_INFO.movement_count.detail} />
            <MetricCard label="作業空間偏差" score={e?.b3 ?? 0} color="red" barColorClass="bg-yellow-500" subtitle={METRIC_INFO.working_volume.subtitle} detail={METRIC_INFO.working_volume.detail} />
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
            <span className="text-base font-semibold text-gray-700">総合スコア</span>
            {dataModeToggle}
            {evalModeToggle}
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
            <h3 className="text-base font-bold text-gray-800 flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-blue-600" />
              動作品質
            </h3>
            <span className="text-lg font-bold text-blue-700">{mq.group_score.toFixed(1)}</span>
          </div>
          {mqMetrics.map(([name, m]) => {
            const info = METRIC_INFO[name]
            return (
              <MetricCard
                key={m.metric_id}
                label={m.metric_label_ja}
                score={m.score}
                color="blue"
                barColorClass={
                  m.metric_id === 'A1' ? 'bg-blue-500' :
                  m.metric_id === 'A2' ? 'bg-indigo-500' :
                  'bg-cyan-500'
                }
                subtitle={info?.subtitle}
                detail={info?.detail}
              />
            )
          })}
        </div>

        {/* Group B: ムダ検出 */}
        <div className="bg-gradient-to-br from-red-50 to-orange-50 rounded-lg border border-red-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-gray-800 flex items-center gap-1.5">
              <Timer className="w-4 h-4 text-red-600" />
              ムダ検出
            </h3>
            <span className="text-lg font-bold text-red-700">{wd.group_score.toFixed(1)}</span>
          </div>
          {wdMetrics.map(([name, m]) => {
            const info = METRIC_INFO[name]
            return (
              <MetricCard
                key={m.metric_id}
                label={m.metric_label_ja}
                score={m.score}
                color="red"
                barColorClass={
                  m.metric_id === 'B1' ? 'bg-red-500' :
                  m.metric_id === 'B2' ? 'bg-orange-500' :
                  'bg-yellow-500'
                }
                subtitle={info?.subtitle}
                detail={info?.detail}
              />
            )
          })}
        </div>
      </div>

      {/* 適用パラメータ表示 */}
      <AppliedConfigSection config={data?.applied_config ?? null} />
    </div>
  )
}

// === デフォルト値（管理者パネルのDEFAULTSと同じ） ===
const DEFAULTS: Record<string, Record<string, number>> = {
  weights: { a1: 0.40, a2: 0.35, a3: 0.25, b1: 0.40, b2: 0.30, b3: 0.30, group_a: 0.50, group_b: 0.50 },
  thresholds: { idle_velocity_threshold: 0.005, idle_velocity_threshold_pixel: 5.0, micro_pause_max_sec: 1.0, check_pause_max_sec: 3.0, movement_velocity_threshold: 0.008, movement_velocity_threshold_pixel: 8.0, smoothing_window: 5, hysteresis_ratio: 0.7, adaptive_threshold: 1, idle_percentile: 15, movement_percentile: 30 },
  scoring: { a1_max_path_pixel: 50000, a1_max_path_normalized: 10.0, a2_sparc_min: -7.0, a2_sparc_max: -1.0, a3_both_hands_min_ratio: 0.30, a3_correlation_weight: 0.60, a3_balance_weight: 0.40, b1_max_idle_ratio: 0.30, b2_max_movements_per_minute: 60.0, b3_max_area_pixel: 500000, b3_max_area_normalized: 0.10 },
  sparc: { freq_cutoff_hz: 20.0, amplitude_threshold: 0.05 },
}

const PARAM_LABELS: Record<string, string> = {
  a1: 'A1重み', a2: 'A2重み', a3: 'A3重み', b1: 'B1重み', b2: 'B2重み', b3: 'B3重み',
  group_a: 'GroupA重み', group_b: 'GroupB重み',
  idle_velocity_threshold: '停止閾値(正規化)', idle_velocity_threshold_pixel: '停止閾値(px)',
  micro_pause_max_sec: 'マイクロポーズ上限', check_pause_max_sec: '確認停止上限',
  movement_velocity_threshold: '動作閾値(正規化)', movement_velocity_threshold_pixel: '動作閾値(px)',
  smoothing_window: '平滑化窓', hysteresis_ratio: 'ヒステリシス係数',
  adaptive_threshold: '適応的閾値', idle_percentile: '停止百分位数', movement_percentile: '動作百分位数',
  a1_max_path_pixel: 'A1最大パス(px)', a1_max_path_normalized: 'A1最大パス(正規化)',
  a2_sparc_min: 'SPARC下限', a2_sparc_max: 'SPARC上限',
  a3_both_hands_min_ratio: 'A3両手最低比率', a3_correlation_weight: 'A3相関重み', a3_balance_weight: 'A3バランス重み',
  b1_max_idle_ratio: 'B1最大idle比率', b2_max_movements_per_minute: 'B2最大動作/分',
  b3_max_area_pixel: 'B3最大面積(px)', b3_max_area_normalized: 'B3最大面積(正規化)',
  freq_cutoff_hz: 'FFTカットオフ', amplitude_threshold: '振幅閾値',
}

function AppliedConfigSection({ config }: { config: SixMetricsData['applied_config'] | null }) {
  const [open, setOpen] = useState(false)

  if (!config) {
    return (
      <div className="mt-3 px-3 py-2 bg-gray-50 rounded-lg border border-gray-200">
        <div className="flex items-center gap-1.5 text-xs text-gray-400">
          <Settings className="w-3.5 h-3.5" />
          適用パラメータ: 記録なし（再解析すると表示されます）
        </div>
      </div>
    )
  }

  const isAdaptive = !!(config.thresholds as any)?.adaptive_threshold

  // デフォルトから変更されたパラメータを検出
  const changes: { section: string; key: string; value: number; defaultVal: number }[] = []
  for (const [section, params] of Object.entries(config)) {
    const defaults = DEFAULTS[section]
    if (!defaults || typeof params !== 'object') continue
    for (const [key, value] of Object.entries(params as Record<string, number>)) {
      if (key === 'adaptive_threshold') continue  // booleanは別表示
      const def = defaults[key]
      if (def !== undefined && typeof value === 'number' && Math.abs(value - def) > 1e-6) {
        changes.push({ section, key, value, defaultVal: def })
      }
    }
  }

  const hasChanges = changes.length > 0

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-3 py-2 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors text-left"
      >
        {open
          ? <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
          : <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
        }
        <Settings className="w-3.5 h-3.5 text-gray-500" />
        <span className="text-xs text-gray-600 font-medium">適用パラメータ</span>
        {/* 適応的閾値バッジ */}
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${
          isAdaptive ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-600'
        }`}>
          適応閾値{isAdaptive ? ' ON' : ' OFF'}
        </span>
        {hasChanges ? (
          <span className="flex items-center gap-1 ml-auto text-xs text-amber-600">
            <AlertTriangle className="w-3 h-3" />
            {changes.length}件カスタマイズ
          </span>
        ) : (
          <span className="flex items-center gap-1 ml-auto text-xs text-emerald-600">
            <CheckCircle2 className="w-3 h-3" />
            デフォルト設定
          </span>
        )}
      </button>

      {open && (
        <div className="mt-1 px-3 py-3 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
          {/* カスタマイズされたパラメータ */}
          {hasChanges && (
            <div>
              <h4 className="text-xs font-semibold text-amber-700 mb-1.5">変更されたパラメータ</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                {changes.map(({ key, value, defaultVal }) => (
                  <div key={key} className="flex items-center justify-between px-2 py-1 bg-amber-50 rounded text-xs border border-amber-100">
                    <span className="text-gray-700">{PARAM_LABELS[key] || key}</span>
                    <span className="font-mono">
                      <span className="text-gray-400 line-through mr-1">{defaultVal}</span>
                      <span className="text-amber-700 font-semibold">{value}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 全パラメータ一覧 */}
          {(['weights', 'thresholds', 'scoring', 'sparc'] as const).map(section => {
            const params = config[section]
            if (!params || typeof params !== 'object') return null
            const sectionLabel = { weights: '重み', thresholds: '閾値', scoring: 'スコアリング', sparc: 'SPARC' }[section]
            return (
              <div key={section}>
                <h4 className="text-xs font-semibold text-gray-500 mb-1">{sectionLabel}</h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-0.5">
                  {Object.entries(params as Record<string, number>).map(([key, value]) => {
                    const def = DEFAULTS[section]?.[key]
                    const isChanged = def !== undefined && Math.abs(value - def) > 1e-6
                    return (
                      <div key={key} className="flex items-center justify-between text-[11px] py-0.5">
                        <span className={isChanged ? 'text-amber-700 font-medium' : 'text-gray-500'}>
                          {PARAM_LABELS[key] || key}
                        </span>
                        <span className={`font-mono ${isChanged ? 'text-amber-700 font-semibold' : 'text-gray-600'}`}>
                          {value}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default SixMetricsPanel
