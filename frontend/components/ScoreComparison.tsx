'use client'

import { useState, useEffect } from 'react'
import { Trophy, TrendingUp, TrendingDown, Minus, AlertCircle, CheckCircle, Target } from 'lucide-react'
import { useReferenceModels, useStartComparison, useComparisonResult } from '@/hooks/useScoring'

interface ScoreComparisonProps {
  analysisId: string
  className?: string
  onComparisonStart?: (comparisonId: string) => void
}

export default function ScoreComparison({ analysisId, className = '', onComparisonStart }: ScoreComparisonProps) {
  const { models, isLoading: modelsLoading, error: modelsError } = useReferenceModels()
  const { startComparison, isLoading: compareLoading } = useStartComparison()
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)
  const [comparisonId, setComparisonId] = useState<string | null>(null)
  const { result, isLoading: resultLoading } = useComparisonResult(comparisonId)
  const [showMockData, setShowMockData] = useState(false)

  // モックデータを生成
  const mockResult = {
    overall_score: 78,
    scores: {
      speed_score: 82,
      smoothness_score: 75,
      stability_score: 80,
      efficiency_score: 72
    },
    metrics: {
      dtw_distance: 0.35,
      path_similarity: 0.78,
      timing_difference: 1.2,
      coordination_score: 0.85
    }
  }

  // デフォルトの基準モデルを選択
  useEffect(() => {
    // モデルがない場合はモックデータを表示
    if (models.length === 0 && !modelsLoading) {
      setShowMockData(true)
    } else if (models.length > 0 && !selectedModelId) {
      // 上級者モデルをデフォルトに
      const expertModel = models.find(m => m.name?.includes('上級')) || models[0]
      setSelectedModelId(expertModel.id)
      handleCompare(expertModel.id)
    }
  }, [models, modelsLoading])

  // resultがnullの場合もモックデータを表示
  useEffect(() => {
    if (!result && !resultLoading && !comparisonId) {
      setShowMockData(true)
    }
  }, [result, resultLoading, comparisonId])

  // 比較を実行
  const handleCompare = async (modelId: string) => {
    try {
      const comparison = await startComparison(modelId, analysisId)
      setComparisonId(comparison.id)
      if (onComparisonStart) {
        onComparisonStart(comparison.id)
      }
    } catch (error) {
      console.error('Failed to start comparison:', error)
    }
  }

  // モデルを変更
  const handleModelChange = (modelId: string) => {
    setSelectedModelId(modelId)
    handleCompare(modelId)
  }

  // スコアの矢印アイコンを取得
  const getScoreTrend = (score: number | undefined) => {
    if (!score) return <Minus className="w-4 h-4 text-gray-400" />
    if (score >= 85) return <TrendingUp className="w-4 h-4 text-green-500" />
    if (score >= 70) return <Minus className="w-4 h-4 text-yellow-500" />
    return <TrendingDown className="w-4 h-4 text-red-500" />
  }

  // スコアの色を取得
  const getScoreColor = (score: number | undefined) => {
    if (!score) return 'text-gray-500'
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  // レベル判定
  const getLevel = (score: number | undefined) => {
    if (!score) return '未評価'
    if (score >= 90) return '上級'
    if (score >= 80) return '中上級'
    if (score >= 70) return '中級'
    if (score >= 60) return '初中級'
    return '初級'
  }

  // ローディング中
  if (modelsLoading || compareLoading || resultLoading) {
    return (
      <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-8 bg-gray-200 rounded"></div>
            <div className="h-8 bg-gray-200 rounded"></div>
            <div className="h-8 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  // エラー表示
  if (modelsError) {
    return (
      <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
        <div className="text-red-600 flex items-center">
          <AlertCircle className="w-5 h-5 mr-2" />
          基準モデルの読み込みに失敗しました
        </div>
      </div>
    )
  }

  return (
    <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
      <div className="mb-4">
        <h3 className="text-lg font-semibold mb-2 flex items-center">
          <Trophy className="w-5 h-5 mr-2 text-yellow-500" />
          スコア評価
        </h3>

        {/* 基準モデル選択 */}
        <div className="mb-4">
          <label className="text-sm text-gray-600 mb-1 block">比較基準</label>
          {models.length > 0 ? (
            <select
              value={selectedModelId || ''}
              onChange={(e) => handleModelChange(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-md text-sm"
            >
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
          ) : (
            <select className="w-full p-2 border border-gray-300 rounded-md text-sm">
              <option>熟練医モデル（モック）</option>
              <option>中級医モデル（モック）</option>
              <option>初級医モデル（モック）</option>
            </select>
          )}
        </div>

        {/* 総合スコア（実データまたはモック） */}
        {(result?.status === 'completed' || showMockData) && (
          <>
            <div className="text-center mb-6 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
              <div className="text-sm text-gray-600 mb-1">総合スコア</div>
              <div className={`text-4xl font-bold ${getScoreColor(showMockData ? mockResult.overall_score : result?.overall_score)}`}>
                {showMockData ? mockResult.overall_score : (result?.overall_score ? Math.round(result.overall_score) : '--')}
                <span className="text-2xl">点</span>
              </div>
              <div className="text-sm mt-2 font-medium">
                レベル: {getLevel(showMockData ? mockResult.overall_score : result?.overall_score)}
              </div>
            </div>

            {/* 個別スコア */}
            <div className="space-y-2">
              {/* 速度スコア */}
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <div className="flex items-center">
                  <div className="w-2 h-6 bg-blue-500 rounded mr-2"></div>
                  <span className="text-xs font-medium">動作速度</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`text-sm font-semibold ${getScoreColor(showMockData ? mockResult.scores.speed_score : result?.speed_score)}`}>
                    {showMockData ? mockResult.scores.speed_score : (result?.speed_score ? Math.round(result.speed_score) : '--')}
                  </span>
                  {getScoreTrend(showMockData ? mockResult.scores.speed_score : result?.speed_score)}
                </div>
              </div>

              {/* 滑らかさスコア */}
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <div className="flex items-center">
                  <div className="w-2 h-6 bg-green-500 rounded mr-2"></div>
                  <span className="text-xs font-medium">滑らかさ</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`text-sm font-semibold ${getScoreColor(showMockData ? mockResult.scores.smoothness_score : result?.smoothness_score)}`}>
                    {showMockData ? mockResult.scores.smoothness_score : (result?.smoothness_score ? Math.round(result.smoothness_score) : '--')}
                  </span>
                  {getScoreTrend(showMockData ? mockResult.scores.smoothness_score : result?.smoothness_score)}
                </div>
              </div>

              {/* 安定性スコア */}
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <div className="flex items-center">
                  <div className="w-2 h-6 bg-yellow-500 rounded mr-2"></div>
                  <span className="text-xs font-medium">安定性</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`text-sm font-semibold ${getScoreColor(showMockData ? mockResult.scores.stability_score : result?.stability_score)}`}>
                    {showMockData ? mockResult.scores.stability_score : (result?.stability_score ? Math.round(result.stability_score) : '--')}
                  </span>
                  {getScoreTrend(showMockData ? mockResult.scores.stability_score : result?.stability_score)}
                </div>
              </div>

              {/* 効率性スコア */}
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <div className="flex items-center">
                  <div className="w-2 h-6 bg-purple-500 rounded mr-2"></div>
                  <span className="text-xs font-medium">効率性</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`text-sm font-semibold ${getScoreColor(showMockData ? mockResult.scores.efficiency_score : result?.efficiency_score)}`}>
                    {showMockData ? mockResult.scores.efficiency_score : (result?.efficiency_score ? Math.round(result.efficiency_score) : '--')}
                  </span>
                  {getScoreTrend(showMockData ? mockResult.scores.efficiency_score : result?.efficiency_score)}
                </div>
              </div>
            </div>

            {/* DTW距離（類似度） */}
            {((showMockData && mockResult.metrics?.dtw_distance !== undefined) ||
              (!showMockData && result?.dtw_distance !== undefined)) && (
              <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">動作パターン類似度</span>
                  <div className="flex items-center">
                    <Target className="w-4 h-4 mr-1 text-blue-600" />
                    <span className="text-sm font-medium text-blue-600">
                      {(() => {
                        const distance = showMockData ? mockResult.metrics.dtw_distance : result?.dtw_distance
                        return distance < 0.3 ? '高' : distance < 0.6 ? '中' : '低'
                      })()}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* 処理中表示 */}
        {result && result.status === 'processing' && (
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-sm text-gray-600">
              スコアを計算中... {result.progress}%
            </p>
          </div>
        )}
      </div>
    </div>
  )
}