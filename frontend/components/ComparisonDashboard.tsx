'use client'

import { useState, useEffect } from 'react'
import { Loader2, AlertCircle } from 'lucide-react'
import DualVideoPlayer from './DualVideoPlayer'
import MetricsDifferenceChart from './MetricsDifferenceChart'
import { useComparisonResult } from '@/hooks/useScoring'

interface ComparisonDashboardProps {
  comparisonId: string
}

export default function ComparisonDashboard({ comparisonId }: ComparisonDashboardProps) {
  const { result, isLoading, error } = useComparisonResult(comparisonId)
  const [currentVideoTime, setCurrentVideoTime] = useState(0)
  const [syncPlay, setSyncPlay] = useState(true)
  const [playbackRate, setPlaybackRate] = useState(1)

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

  // ローディング中
  if (isLoading || !result) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-12 h-12 animate-spin text-blue-600 mb-4" />
        <p className="text-gray-600">比較データを読み込み中...</p>
      </div>
    )
  }

  // エラー
  if (error || result.status === 'failed') {
    return (
      <div className="bg-red-50 rounded-lg p-8 text-center">
        <AlertCircle className="w-12 h-12 text-red-600 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-red-900 mb-2">比較データの読み込みに失敗しました</h2>
        <p className="text-red-700">
          {result?.error_message || error || 'エラーが発生しました'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* デュアルビデオプレイヤー */}
      <DualVideoPlayer
        referenceVideoId={result.reference_video_id}
        learnerVideoId={result.learner_video_id}
        referenceAnalysisId={result.reference_analysis_id}
        learnerAnalysisId={result.learner_analysis_id}
        syncPlay={syncPlay}
        playbackRate={playbackRate}
        onTimeUpdate={setCurrentVideoTime}
      />

      {/* 同期コントロールバー */}
      <div className="bg-white rounded-lg shadow-sm p-4">
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <button
            onClick={() => setSyncPlay(!syncPlay)}
            className={`px-4 py-2 rounded-md transition ${
              syncPlay
                ? 'bg-purple-600 text-white hover:bg-purple-700'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {syncPlay ? '同期再生 ON' : '同期再生 OFF'}
          </button>
          <div className="flex gap-2">
            <button
              onClick={() => setPlaybackRate(0.5)}
              className={`px-3 py-2 rounded-md transition ${
                playbackRate === 0.5
                  ? 'bg-purple-100 border-2 border-purple-500'
                  : 'bg-gray-200 hover:bg-gray-300'
              }`}
            >
              0.5x
            </button>
            <button
              onClick={() => setPlaybackRate(1)}
              className={`px-3 py-2 rounded-md transition ${
                playbackRate === 1
                  ? 'bg-purple-100 border-2 border-purple-500'
                  : 'bg-gray-200 hover:bg-gray-300'
              }`}
            >
              標準
            </button>
            <button
              onClick={() => setPlaybackRate(2)}
              className={`px-3 py-2 rounded-md transition ${
                playbackRate === 2
                  ? 'bg-purple-100 border-2 border-purple-500'
                  : 'bg-gray-200 hover:bg-gray-300'
              }`}
            >
              2.0x
            </button>
          </div>
        </div>
      </div>

      {/* スコア比較セクション */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* 総合スコア */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-sm font-medium text-gray-600 mb-2">総合スコア</h3>
          <div className={`text-3xl font-bold ${getScoreColor(result.overall_score)}`}>
            {result.overall_score?.toFixed(1) || '--'}
          </div>
          <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                result.overall_score && result.overall_score >= 80 ? 'bg-green-500' :
                result.overall_score && result.overall_score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
              }`}
              style={{ width: `${result.overall_score || 0}%` }}
            />
          </div>
        </div>

        {/* 速度スコア */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-sm font-medium text-gray-600 mb-2">速度</h3>
          <div className={`text-3xl font-bold ${getScoreColor(result.speed_score)}`}>
            {result.speed_score?.toFixed(1) || '--'}
          </div>
          <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                result.speed_score && result.speed_score >= 80 ? 'bg-green-500' :
                result.speed_score && result.speed_score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
              }`}
              style={{ width: `${result.speed_score || 0}%` }}
            />
          </div>
        </div>

        {/* 滑らかさスコア */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-sm font-medium text-gray-600 mb-2">滑らかさ</h3>
          <div className={`text-3xl font-bold ${getScoreColor(result.smoothness_score)}`}>
            {result.smoothness_score?.toFixed(1) || '--'}
          </div>
          <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                result.smoothness_score && result.smoothness_score >= 80 ? 'bg-green-500' :
                result.smoothness_score && result.smoothness_score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
              }`}
              style={{ width: `${result.smoothness_score || 0}%` }}
            />
          </div>
        </div>

        {/* 安定性スコア */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-sm font-medium text-gray-600 mb-2">安定性</h3>
          <div className={`text-3xl font-bold ${getScoreColor(result.stability_score)}`}>
            {result.stability_score?.toFixed(1) || '--'}
          </div>
          <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                result.stability_score && result.stability_score >= 80 ? 'bg-green-500' :
                result.stability_score && result.stability_score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
              }`}
              style={{ width: `${result.stability_score || 0}%` }}
            />
          </div>
        </div>
      </div>

      {/* リアルタイム差分メトリクス */}
      <MetricsDifferenceChart
        comparisonData={result.metrics_comparison}
        currentTime={currentVideoTime}
      />

      {/* フィードバックセクション */}
      {result.feedback && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="font-semibold mb-4">AI分析による詳細フィードバック</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* 良い点 */}
            {result.feedback.strengths && result.feedback.strengths.length > 0 && (
              <div className="bg-green-50 rounded-lg p-4 border border-green-200">
                <h4 className="font-medium text-green-800 mb-3">良い点</h4>
                <ul className="space-y-2 text-sm text-green-700">
                  {result.feedback.strengths.map((item: any, index: number) => (
                    <li key={index} className="flex items-start">
                      <span className="mr-2">•</span>
                      <span>{item.message || item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 改善点 */}
            {result.feedback.weaknesses && result.feedback.weaknesses.length > 0 && (
              <div className="bg-yellow-50 rounded-lg p-4 border border-yellow-200">
                <h4 className="font-medium text-yellow-800 mb-3">改善点</h4>
                <ul className="space-y-2 text-sm text-yellow-700">
                  {result.feedback.weaknesses.map((item: any, index: number) => (
                    <li key={index} className="flex items-start">
                      <span className="mr-2">•</span>
                      <span>{item.message || item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 練習提案 */}
            {result.feedback.suggestions && result.feedback.suggestions.length > 0 && (
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <h4 className="font-medium text-blue-800 mb-3">練習提案</h4>
                <ul className="space-y-2 text-sm text-blue-700">
                  {result.feedback.suggestions.map((item: any, index: number) => (
                    <li key={index} className="flex items-start">
                      <span className="mr-2">{index + 1}.</span>
                      <span>{item.message || item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}