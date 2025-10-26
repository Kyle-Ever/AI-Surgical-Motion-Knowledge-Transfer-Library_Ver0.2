'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Check, X, Loader2 } from 'lucide-react'
import { ProcessingStep } from '@/types'
import { useAnalysisStatus, useWebSocket } from '@/hooks/useApi'

interface AnalysisClientProps {
  analysisId: string
}

export default function AnalysisClient({ analysisId }: AnalysisClientProps) {
  const router = useRouter()
  const { status, error } = useAnalysisStatus(analysisId, 2000)
  const { lastMessage, isConnected } = useWebSocket(analysisId)
  const [overallProgress, setOverallProgress] = useState(0)
  const [estimatedTime, setEstimatedTime] = useState(300) // 5分

  // APIからのステータスを監視
  useEffect(() => {
    if (status) {
      setOverallProgress(status.overall_progress)

      if (status.estimated_time_remaining !== undefined) {
        setEstimatedTime(status.estimated_time_remaining)
      }

      // 完了したらダッシュボードへ遷移
      if (status.overall_progress >= 100) {
        setTimeout(() => {
          router.push(`/dashboard/${analysisId}`)
        }, 1500)
      }
    }
  }, [status, analysisId, router])

  // WebSocketメッセージを処理（強化版）
  useEffect(() => {
    if (lastMessage) {
      console.log('WebSocket message:', lastMessage)

      // WebSocketから進捗情報を取得して反映
      if (lastMessage.type === 'status_update') {
        // 進捗を更新
        if (lastMessage.progress !== undefined) {
          setOverallProgress(lastMessage.progress)
        }

        // 現在のステップを更新（stepsの再計算をトリガー）
        if (lastMessage.current_step) {
          // current_stepの変更はstatusを通じて反映される
          console.log('Current step updated:', lastMessage.current_step)
        }

        // メッセージがあれば表示（オプション）
        if (lastMessage.message) {
          console.log('Step message:', lastMessage.message)
        }

        // 完了したらダッシュボードへ遷移
        if (lastMessage.progress >= 100 || lastMessage.status === 'completed') {
          setTimeout(() => {
            router.push(`/dashboard/${analysisId}`)
          }, 1500)
        }
      }
    }
  }, [lastMessage, analysisId, router])

  // 視線解析かどうかを判定（video_typeで判定）
  const isGazeAnalysis = status?.video_type === 'eye_gaze'

  // 処理ステップの定義（解析タイプに応じて分岐）
  const steps: ProcessingStep[] = isGazeAnalysis ? [
    // 視線解析用ステップ
    {
      name: '動画読み込み',
      status: status?.current_step === 'initialization' || lastMessage?.current_step === 'initialization' ? 'processing' :
             (status && status.overall_progress >= 10) || overallProgress >= 10 ? 'completed' : 'pending'
    },
    {
      name: 'フレーム抽出',
      status: status?.current_step === 'frame_extraction' || lastMessage?.current_step === 'frame_extraction' ? 'processing' :
             (status && status.overall_progress >= 30) || overallProgress >= 30 ? 'completed' : 'pending'
    },
    {
      name: '視線検出',
      status: status?.current_step === 'gaze_detection' || lastMessage?.current_step === 'gaze_detection' ? 'processing' :
             (status && status.overall_progress >= 85) || overallProgress >= 85 ? 'completed' : 'pending'
    },
    {
      name: 'ヒートマップ生成',
      status: status?.current_step === 'report_generation' || lastMessage?.current_step === 'report_generation' ? 'processing' :
             (status && status.overall_progress >= 100) || overallProgress >= 100 ? 'completed' : 'pending'
    },
  ] : [
    // 通常の骨格・器具解析用ステップ
    {
      name: '動画読み込み',
      status: status?.current_step === 'initialization' || lastMessage?.current_step === 'initialization' ? 'processing' :
             (status && status.overall_progress >= 10) || overallProgress >= 10 ? 'completed' : 'pending'
    },
    {
      name: 'フレーム抽出',
      status: status?.current_step === 'frame_extraction' || lastMessage?.current_step === 'frame_extraction' ? 'processing' :
             (status && status.overall_progress >= 30) || overallProgress >= 30 ? 'completed' : 'pending'
    },
    {
      name: '骨格検出',
      status: status?.current_step === 'skeleton_detection' || lastMessage?.current_step === 'skeleton_detection' ? 'processing' :
             (status && status.overall_progress >= 50) || overallProgress >= 50 ? 'completed' : 'pending'
    },
    {
      name: '器具認識',
      status: status?.current_step === 'instrument_detection' || lastMessage?.current_step === 'instrument_detection' ? 'processing' :
             (status && status.overall_progress >= 70) || overallProgress >= 70 ? 'completed' : 'pending'
    },
    {
      name: 'モーション解析',
      status: status?.current_step === 'motion_analysis' || lastMessage?.current_step === 'motion_analysis' ? 'processing' :
             (status && status.overall_progress >= 85) || overallProgress >= 85 ? 'completed' : 'pending'
    },
    {
      name: 'レポート生成',
      status: status?.current_step === 'report_generation' || lastMessage?.current_step === 'report_generation' ? 'processing' :
             (status && status.overall_progress >= 100) || overallProgress >= 100 ? 'completed' : 'pending'
    },
  ]

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}分${secs}秒`
  }

  const getStatusIcon = (stepStatus: string) => {
    if (stepStatus === 'completed') {
      return <Check className="h-5 w-5 text-green-500" />
    } else if (stepStatus === 'processing') {
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
    } else if (stepStatus === 'failed') {
      return <X className="h-5 w-5 text-red-500" />
    }
    return <div className="h-5 w-5 rounded-full border-2 border-gray-300" />
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-red-500">
          エラーが発生しました: {error.message || 'Unknown error'}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white shadow-xl rounded-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-8" data-testid="analysis-title">解析処理中</h1>

          {/* WebSocket接続状態 */}
          <div className="mb-6">
            <div className="flex items-center">
              <div className={`h-3 w-3 rounded-full mr-2 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} data-testid="ws-connection-indicator" />
              <span className="text-sm text-gray-600" data-testid="ws-connection-status">
                {isConnected ? 'リアルタイム更新中' : '接続待機中...'}
              </span>
            </div>
          </div>

          {/* 全体の進捗バー */}
          <div className="mb-8">
            <div className="flex justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">全体進捗</span>
              <span className="text-sm font-medium text-gray-700" data-testid="progress-percentage">{overallProgress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${overallProgress}%` }}
              />
            </div>
            {estimatedTime > 0 && (
              <p className="text-sm text-gray-600 mt-2">
                推定残り時間: {formatTime(estimatedTime)}
              </p>
            )}
          </div>

          {/* 処理ステップリスト */}
          <div className="space-y-4">
            {steps.map((step, index) => (
              <div key={index} className="flex items-center space-x-3">
                {getStatusIcon(step.status)}
                <span className={`text-lg ${
                  step.status === 'processing' ? 'font-semibold text-blue-600' :
                  step.status === 'completed' ? 'text-green-600' :
                  'text-gray-500'
                }`}>
                  {step.name}
                </span>
              </div>
            ))}
          </div>

          {/* 現在のステップの詳細 */}
          {status?.current_step && (
            <div className="mt-8 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                現在処理中: {status.message || status.current_step}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}