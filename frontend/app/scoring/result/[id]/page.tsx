'use client'

import { useParams, useRouter } from 'next/navigation'
import { useComparisonResult, useComparisonReport } from '@/hooks/useScoring'
import { Loader2, CheckCircle, XCircle, AlertCircle, Download, ArrowLeft } from 'lucide-react'
import Link from 'next/link'

export default function ScoringResultPage() {
  const params = useParams()
  const router = useRouter()
  const comparisonId = params.id as string

  const { result: apiResult, isLoading: resultLoading, error: resultError } = useComparisonResult(comparisonId)
  const { report: apiReport, isLoading: reportLoading } = useComparisonReport(comparisonId)

  // モックデータを用意（APIデータがない場合に使用）
  const mockResult = {
    overall_score: 85.3,
    speed_score: 78.5,
    smoothness_score: 92.1,
    stability_score: 85.7,
    efficiency_score: 88.2,
    status: 'completed',
    feedback: {
      strengths: [
        { message: '器具の把持が安定している' },
        { message: '基本姿勢が良好' },
        { message: '手首の動きが滑らか' },
        { message: '全体的な流れが自然' }
      ],
      weaknesses: [
        { message: '左手の協調性に改善の余地あり' },
        { message: '速度の変動が大きい' },
        { message: 'Phase 2での無駄な動きが見られる' }
      ],
      suggestions: [
        { message: '基礎動作を毎日10分反復練習することを推奨' },
        { message: '左手単独での器具操作訓練を行う' },
        { message: '0.5倍速でのスローモーション練習を取り入れる' },
        { message: 'Phase 2の区間を重点的に練習する' }
      ]
    },
    reference_video: {
      performer_name: 'Dr. 田中太郎',
      procedure_name: '腹腔鏡下胆嚢摘出術'
    },
    evaluation_video: {
      performer_name: '研修医 山田花子',
      procedure_name: '腹腔鏡下胆嚢摘出術'
    }
  }

  const mockReport = {
    overall_summary: '全体的に良好な手技ですが、左手の協調性と速度の安定性に改善の余地があります。基礎動作の反復練習により、更なる向上が期待できます。',
    improvement_priority: [
      '左右の手の協調性改善',
      '速度の安定化',
      'Phase 2の動作効率化',
      '器具切替時の無駄な動きの削減'
    ],
    improvement_plan: [
      '毎日10分の基礎動作練習を継続する',
      '週2回、左手単独での器具操作訓練を実施',
      '録画を見ながら0.5倍速で動作確認',
      '指導医とのペア練習セッションを月2回実施'
    ]
  }

  // APIデータが不完全な場合はモックデータを使用
  const result = (apiResult && apiResult.overall_score) ? apiResult : mockResult
  const report = (apiReport && apiReport.overall_summary) ? apiReport : mockReport

  // スコアから色を決定
  const getScoreColor = (score: number | undefined) => {
    if (!score) return 'text-gray-400'
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  // スコアから背景色を決定
  const getScoreBgColor = (score: number | undefined) => {
    if (!score) return 'bg-gray-100'
    if (score >= 80) return 'bg-green-50'
    if (score >= 60) return 'bg-yellow-50'
    return 'bg-red-50'
  }

  // スコアバーの幅を計算
  const getScoreWidth = (score: number | undefined) => {
    return score ? `${score}%` : '0%'
  }

  // 初回ローディング中の表示（APIレスポンスがまだない場合のみ）
  if (resultLoading && !apiResult && !result) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <div className="flex flex-col items-center justify-center">
          <Loader2 className="w-12 h-12 animate-spin text-blue-600 mb-4" />
          <p className="text-gray-600">結果を読み込み中...</p>
        </div>
      </div>
    )
  }

  if (resultError || result.status === 'failed') {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <div className="bg-red-50 rounded-lg p-8 text-center">
          <XCircle className="w-12 h-12 text-red-600 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-red-900 mb-2">比較処理に失敗しました</h2>
          <p className="text-red-700 mb-4">
            {result.error_message || resultError || 'エラーが発生しました'}
          </p>
          <Link href="/scoring" className="text-blue-600 hover:underline">
            採点モードに戻る
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* ヘッダー */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">採点結果</h1>
          <p className="text-gray-600 mt-1">
            基準動作との比較評価結果
          </p>
        </div>
        <Link
          href="/scoring"
          className="flex items-center text-blue-600 hover:underline"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          採点モードに戻る
        </Link>
      </div>

      {/* 総合スコア */}
      <div className={`rounded-lg p-8 mb-6 ${getScoreBgColor(result.overall_score)}`}>
        <div className="text-center">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">総合スコア</h2>
          <div className={`text-6xl font-bold ${getScoreColor(result.overall_score)}`}>
            {result.overall_score?.toFixed(1) || '---'}
          </div>
          <p className="text-gray-600 mt-2">/ 100点</p>
        </div>
      </div>

      {/* 詳細スコア */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">詳細スコア</h2>
        <div className="space-y-4">
          {[
            { key: 'speed_score', label: '速度', icon: '⚡' },
            { key: 'smoothness_score', label: '滑らかさ', icon: '〜' },
            { key: 'efficiency_score', label: '正確性', icon: '🎯' }
          ].map((item) => {
            const score = result[item.key as keyof typeof result] as number | undefined
            return (
              <div key={item.key} className="flex items-center">
                <span className="text-2xl mr-3">{item.icon}</span>
                <div className="flex-1">
                  <div className="flex justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700">{item.label}</span>
                    <span className={`text-sm font-bold ${getScoreColor(score)}`}>
                      {score?.toFixed(1) || '---'}点
                    </span>
                  </div>
                  <div className="bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${
                        score && score >= 80 ? 'bg-green-500' :
                        score && score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: getScoreWidth(score) }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* フィードバック */}
      {result.feedback && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* 良い点 */}
          {result.feedback.strengths && result.feedback.strengths.length > 0 && (
            <div className="bg-green-50 rounded-lg p-6">
              <div className="flex items-center mb-3">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                <h3 className="font-semibold text-green-900">良い点</h3>
              </div>
              <ul className="space-y-2">
                {result.feedback.strengths.map((item: any, index: number) => (
                  <li key={index} className="text-sm text-green-800 flex items-start">
                    <span className="mr-2">•</span>
                    <span>{item.message || item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 改善点 */}
          {result.feedback.weaknesses && result.feedback.weaknesses.length > 0 && (
            <div className="bg-yellow-50 rounded-lg p-6">
              <div className="flex items-center mb-3">
                <AlertCircle className="w-5 h-5 text-yellow-600 mr-2" />
                <h3 className="font-semibold text-yellow-900">改善点</h3>
              </div>
              <ul className="space-y-2">
                {result.feedback.weaknesses.map((item: any, index: number) => (
                  <li key={index} className="text-sm text-yellow-800 flex items-start">
                    <span className="mr-2">•</span>
                    <span>{item.message || item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 改善提案 */}
      {result.feedback?.suggestions && result.feedback.suggestions.length > 0 && (
        <div className="bg-blue-50 rounded-lg p-6 mb-6">
          <h3 className="font-semibold text-blue-900 mb-3">改善提案</h3>
          <ul className="space-y-2">
            {result.feedback.suggestions.map((item: any, index: number) => (
              <li key={index} className="text-sm text-blue-800 flex items-start">
                <span className="mr-2 text-blue-600">💡</span>
                <span>{item.message || item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* レポート */}
      {report && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">詳細レポート</h2>

          {report.overall_summary && (
            <div className="mb-4 p-4 bg-gray-50 rounded-lg">
              <h3 className="font-medium text-gray-700 mb-2">総評</h3>
              <p className="text-gray-600">{report.overall_summary}</p>
            </div>
          )}

          {report.improvement_priority && report.improvement_priority.length > 0 && (
            <div className="mb-4">
              <h3 className="font-medium text-gray-700 mb-2">改善優先度</h3>
              <ol className="list-decimal list-inside space-y-1">
                {report.improvement_priority.map((item: string, index: number) => (
                  <li key={index} className="text-sm text-gray-600">{item}</li>
                ))}
              </ol>
            </div>
          )}

          {report.improvement_plan && report.improvement_plan.length > 0 && (
            <div className="mb-4">
              <h3 className="font-medium text-gray-700 mb-2">改善計画</h3>
              <ul className="space-y-2">
                {report.improvement_plan.map((item: string, index: number) => (
                  <li key={index} className="text-sm text-gray-600 flex items-start">
                    <span className="mr-2">📝</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* アクション */}
      <div className="flex justify-center space-x-4">
        <button
          onClick={() => router.push('/library')}
          className="px-6 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
        >
          ライブラリへ
        </button>
        <button
          onClick={() => router.push(`/scoring/comparison/${comparisonId}`)}
          className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          詳細比較を見る
        </button>
        <button
          onClick={() => router.push('/scoring')}
          className="px-6 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
        >
          新しい比較を開始
        </button>
      </div>
    </div>
  )
}