'use client'

import { CheckCircle, AlertTriangle, Lightbulb, Target, Award } from 'lucide-react'
import { useComparisonResult } from '@/hooks/useScoring'

interface FeedbackPanelProps {
  comparisonId: string | null
  className?: string
}

export default function FeedbackPanel({ comparisonId, className = '' }: FeedbackPanelProps) {
  const { result, isLoading } = useComparisonResult(comparisonId)

  // モックフィードバックデータ（将来的にAIが生成）
  const mockFeedback = {
    current_status: [
      { message: '基本的な手技の流れは理解できており、全体的な動作の順序は適切です' },
      { message: '両手の協調性は基準の85%のレベルに到達しています' },
      { message: '器具の把持方法は概ね正しいですが、角度に改善の余地があります' }
    ],
    strengths: [
      { message: '手首の動きが非常に滑らかで、基準モデルと同等のレベルです' },
      { message: '両手の協調性が優れており、効率的な動作ができています' },
      { message: '器具の把持が安定しており、無駄な動きが少ないです' }
    ],
    improvements: [
      { message: '左手の動作速度が基準より15%遅くなっています' },
      { message: '縫合時の針の角度が不適切な場合があります' },
      { message: '動作の開始時に若干の迷いが見られます' },
      { message: '右手の動作範囲が狭く、より大きな動きが必要です' }
    ]
  }

  // 実際のデータがない場合はモックデータを使用
  const feedbackData = result?.feedback || mockFeedback
  const { current_status = mockFeedback.current_status,
          strengths = mockFeedback.strengths,
          improvements = mockFeedback.improvements } = feedbackData

  return (
    <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
      <h3 className="text-lg font-semibold mb-4 flex items-center">
        <Award className="w-5 h-5 mr-2 text-blue-500" />
        フィードバック
      </h3>

      <div className="space-y-4">
        {/* 現状 */}
        {current_status.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="font-medium text-gray-800 mb-2 flex items-center">
              <Target className="w-4 h-4 mr-2" />
              現状
            </h4>
            <ul className="space-y-2">
              {current_status.map((item, index) => (
                <li key={index} className="flex items-start">
                  <span className="text-gray-600 mr-2 mt-0.5">•</span>
                  <span className="text-sm text-gray-700">{item.message}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 良かった点 */}
        {strengths.length > 0 && (
          <div className="bg-green-50 rounded-lg p-4">
            <h4 className="font-medium text-green-800 mb-2 flex items-center">
              <CheckCircle className="w-4 h-4 mr-2" />
              良かった点
            </h4>
            <ul className="space-y-2">
              {strengths.map((item, index) => (
                <li key={index} className="flex items-start">
                  <span className="text-green-600 mr-2 mt-0.5">✓</span>
                  <span className="text-sm text-gray-700">{item.message}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 改善点 */}
        {improvements.length > 0 && (
          <div className="bg-yellow-50 rounded-lg p-4">
            <h4 className="font-medium text-yellow-800 mb-2 flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2" />
              改善点
            </h4>
            <ul className="space-y-2">
              {improvements.map((item, index) => (
                <li key={index} className="flex items-start">
                  <span className="text-yellow-600 mr-2 mt-0.5">!</span>
                  <span className="text-sm text-gray-700">{item.message}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* AI分析予定の注記 */}
        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
          <p className="text-xs text-blue-700 flex items-center">
            <Lightbulb className="w-4 h-4 mr-1" />
            将来的にAIが動作を詳細に分析し、個別のアドバイスを生成します
          </p>
        </div>
      </div>
    </div>
  )
}