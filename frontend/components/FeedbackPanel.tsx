'use client'

import { CheckCircle, AlertTriangle, Target, TrendingUp } from 'lucide-react'

interface MetricData {
  metric_id: string
  metric_label_ja: string
  score: number
  ratio_to_expert: number | null
  evaluation_mode: string
  raw_values: Record<string, any>
}

interface SixMetricsData {
  evaluation_mode: string
  expert_baseline_used: boolean
  overall_score: number
  motion_quality: {
    group_score: number
    metrics: Record<string, MetricData>
  }
  waste_detection: {
    group_score: number
    metrics: Record<string, MetricData>
  }
}

interface FeedbackPanelProps {
  comparisonId?: string | null
  sixMetrics?: SixMetricsData | null
  className?: string
}

// 指標名と解釈のマッピング
const METRIC_CONTEXT: Record<string, {
  name: string
  goodMsg: string        // スコアが高い場合
  badMsg: string         // スコアが低い場合
  ratioGoodMsg: string   // 基準より良い場合
  ratioBadMsg: string    // 基準より悪い場合
  unit?: string
}> = {
  economy_of_motion: {
    name: '動作経済性',
    goodMsg: '手の移動距離が短く、効率的な動作ができています',
    badMsg: '手の移動距離が長く、無駄な動きが多くなっています',
    ratioGoodMsg: '基準より移動距離が短く、より効率的な動作です',
    ratioBadMsg: '基準より移動距離が長く、動作の効率化が必要です',
  },
  smoothness: {
    name: '動作滑らかさ',
    goodMsg: '動きが滑らかで、停止・再開の少ない安定した手技です',
    badMsg: '動きにぎこちなさがあり、停止・再開が多くなっています',
    ratioGoodMsg: '基準と同等以上の滑らかさで動作できています',
    ratioBadMsg: '基準と比べて動きのぎこちなさが見られます。一連の動作を途切れなく行うことを意識してください',
  },
  bimanual_coordination: {
    name: '両手協調性',
    goodMsg: '両手の連携が適切に取れています',
    badMsg: '両手の連携に改善の余地があります',
    ratioGoodMsg: '基準と同等以上の両手連携ができています',
    ratioBadMsg: '基準と比べて両手の連携が不十分です。保持手の安定性を意識してください',
  },
  lost_time: {
    name: 'ロスタイム',
    goodMsg: '迷いや停止が少なく、テンポよく手技を進められています',
    badMsg: '両手が同時に停止する時間が長く、計画性の向上が求められます',
    ratioGoodMsg: '基準と比べてロスタイムが少なく、効率的です',
    ratioBadMsg: '基準と比べてロスタイムが多くなっています。次の手順を事前に考えることで改善できます',
  },
  movement_count: {
    name: '動作回数効率',
    goodMsg: '少ない動作回数で効率的に手技を進められています',
    badMsg: '動作回数が多く、より少ない動作で完遂する意識が必要です',
    ratioGoodMsg: '基準より少ない動作回数で効率的に手技を行えています',
    ratioBadMsg: '基準と比べて動作回数が多くなっています。1回の動作の精度を上げることで改善できます',
  },
  working_volume: {
    name: '作業空間偏差',
    goodMsg: '必要な範囲に集中した動作ができています',
    badMsg: '作業範囲が広がりすぎています。対象部位に集中した動きを心がけてください',
    ratioGoodMsg: '基準と同等の作業範囲で動作できています',
    ratioBadMsg: '基準と比べて作業範囲にずれがあります。対象部位に適切に手を集中させてください',
  },
}

function generateFeedback(sixMetrics: SixMetricsData) {
  const isRelative = sixMetrics.evaluation_mode === 'relative'
  const allMetrics: { name: string; data: MetricData }[] = []

  for (const [name, data] of Object.entries(sixMetrics.motion_quality.metrics)) {
    allMetrics.push({ name, data })
  }
  for (const [name, data] of Object.entries(sixMetrics.waste_detection.metrics)) {
    allMetrics.push({ name, data })
  }

  const strengths: string[] = []
  const improvements: string[] = []
  const summary: string[] = []

  // 総合評価
  const overall = sixMetrics.overall_score
  if (overall >= 80) {
    summary.push('全体的に高い水準の手技パフォーマンスです')
  } else if (overall >= 60) {
    summary.push('全体的に良好なパフォーマンスですが、一部に改善の余地があります')
  } else if (overall >= 40) {
    summary.push('基本的な手技の流れは理解できていますが、複数の指標で改善が必要です')
  } else {
    summary.push('手技の基礎的な部分から見直しが必要です')
  }

  // グループ別評価
  const mqScore = sixMetrics.motion_quality.group_score
  const wdScore = sixMetrics.waste_detection.group_score
  if (mqScore >= 70 && wdScore < 60) {
    summary.push('動作の質は良好ですが、効率面（ロスタイム・動作回数・作業範囲）に改善の余地があります')
  } else if (wdScore >= 70 && mqScore < 60) {
    summary.push('効率面は良好ですが、動作の質（経済性・滑らかさ・協調性）を向上させましょう')
  }

  // 各指標の詳細フィードバック
  for (const { name, data } of allMetrics) {
    const ctx = METRIC_CONTEXT[name]
    if (!ctx || data.score < 0) continue

    if (isRelative && data.ratio_to_expert != null) {
      const ratio = data.ratio_to_expert
      // 相対評価の場合
      if (data.score >= 80) {
        strengths.push(ctx.ratioGoodMsg)
      } else if (data.score < 50) {
        // ratio情報を含めた具体的なフィードバック
        const ratioText = ratio > 1
          ? `（基準の${ratio.toFixed(1)}倍）`
          : `（基準の${(ratio * 100).toFixed(0)}%）`
        improvements.push(`${ctx.ratioBadMsg}${ratioText}`)
      }
    } else {
      // 絶対評価の場合
      if (data.score >= 80) {
        strengths.push(ctx.goodMsg)
      } else if (data.score < 50) {
        improvements.push(ctx.badMsg)
      }
    }
  }

  // 最も改善が必要な指標を特定
  const sorted = allMetrics
    .filter(m => m.data.score >= 0)
    .sort((a, b) => a.data.score - b.data.score)
  if (sorted.length > 0 && sorted[0].data.score < 70) {
    const worst = sorted[0]
    const ctx = METRIC_CONTEXT[worst.name]
    if (ctx) {
      summary.push(`最も改善効果が高いのは「${ctx.name}」（スコア${worst.data.score.toFixed(0)}）です`)
    }
  }

  return { summary, strengths, improvements }
}

export default function FeedbackPanel({ sixMetrics, className = '' }: FeedbackPanelProps) {
  if (!sixMetrics) {
    return (
      <div className={`bg-white rounded-lg border border-gray-200 shadow-sm p-6 ${className}`}>
        <h3 className="text-base font-semibold mb-3 flex items-center text-gray-700">
          <TrendingUp className="w-4 h-4 mr-2" />
          フィードバック
        </h3>
        <p className="text-sm text-gray-400">解析データがありません</p>
      </div>
    )
  }

  const { summary, strengths, improvements } = generateFeedback(sixMetrics)
  const isRelative = sixMetrics.evaluation_mode === 'relative'

  return (
    <div className={`bg-white rounded-lg border border-gray-200 shadow-sm p-5 ${className}`}>
      <h3 className="text-base font-semibold mb-3 flex items-center text-gray-700">
        <TrendingUp className="w-4 h-4 mr-2" />
        フィードバック
        {isRelative && (
          <span className="ml-2 px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-[10px] font-bold">
            基準比較
          </span>
        )}
      </h3>

      <div className="space-y-3">
        {/* 総合評価 */}
        {summary.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-3">
            <h4 className="text-xs font-semibold text-gray-600 mb-1.5 flex items-center">
              <Target className="w-3.5 h-3.5 mr-1.5" />
              総合評価
            </h4>
            <ul className="space-y-1">
              {summary.map((msg, i) => (
                <li key={i} className="text-sm text-gray-700 flex items-start">
                  <span className="text-gray-400 mr-2 mt-0.5 shrink-0">•</span>
                  {msg}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 良かった点 */}
        {strengths.length > 0 && (
          <div className="bg-green-50 rounded-lg p-3">
            <h4 className="text-xs font-semibold text-green-700 mb-1.5 flex items-center">
              <CheckCircle className="w-3.5 h-3.5 mr-1.5" />
              良かった点
            </h4>
            <ul className="space-y-1">
              {strengths.map((msg, i) => (
                <li key={i} className="text-sm text-gray-700 flex items-start">
                  <span className="text-green-500 mr-2 mt-0.5 shrink-0">✓</span>
                  {msg}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 改善点 */}
        {improvements.length > 0 && (
          <div className="bg-amber-50 rounded-lg p-3">
            <h4 className="text-xs font-semibold text-amber-700 mb-1.5 flex items-center">
              <AlertTriangle className="w-3.5 h-3.5 mr-1.5" />
              改善点
            </h4>
            <ul className="space-y-1">
              {improvements.map((msg, i) => (
                <li key={i} className="text-sm text-gray-700 flex items-start">
                  <span className="text-amber-500 mr-2 mt-0.5 shrink-0">!</span>
                  {msg}
                </li>
              ))}
            </ul>
          </div>
        )}

        {strengths.length === 0 && improvements.length === 0 && (
          <p className="text-sm text-gray-500">すべての指標が中程度のスコアです。各指標をバランスよく向上させましょう。</p>
        )}
      </div>
    </div>
  )
}
