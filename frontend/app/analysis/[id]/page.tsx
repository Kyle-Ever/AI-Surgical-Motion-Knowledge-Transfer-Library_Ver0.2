'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Check, X, Loader2 } from 'lucide-react'
import { ProcessingStep } from '@/types'
import { useAnalysisStatus, useWebSocket } from '@/hooks/useApi'

export default function AnalysisPage({ params }: { params: { id: string } }) {
  const router = useRouter()
  const { status, error } = useAnalysisStatus(params.id, 2000)
  const { lastMessage, isConnected } = useWebSocket(params.id)
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
          router.push(`/dashboard/${params.id}`)
        }, 1500)
      }
    }
  }, [status, params.id, router])

  // WebSocketメッセージを処理
  useEffect(() => {
    if (lastMessage) {
      console.log('WebSocket message:', lastMessage)
      // 追加の進捗更新処理をここに実装可能
    }
  }, [lastMessage])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}分${secs}秒`
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">解析処理中...</h1>
        <p className="text-gray-600 mt-2">
          動画を解析しています。処理が完了するまでお待ちください。
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm p-6">
        {/* 処理ステータス */}
        <div className="space-y-4 mb-8">
          <h2 className="text-lg font-semibold">処理ステータス</h2>
          <div className="space-y-3">
            {(status?.steps || []).map((step, index) => (
              <div key={index} className="flex items-center space-x-3">
                {step.status === 'completed' && (
                  <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                    <Check className="w-4 h-4 text-white" />
                  </div>
                )}
                {step.status === 'processing' && (
                  <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                    <Loader2 className="w-4 h-4 text-white animate-spin" />
                  </div>
                )}
                {step.status === 'pending' && (
                  <div className="w-6 h-6 bg-gray-300 rounded-full" />
                )}
                {step.status === 'failed' && (
                  <div className="w-6 h-6 bg-red-500 rounded-full flex items-center justify-center">
                    <X className="w-4 h-4 text-white" />
                  </div>
                )}
                
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className={`font-medium ${
                      step.status === 'completed' ? 'text-green-600' :
                      step.status === 'processing' ? 'text-blue-600' :
                      step.status === 'failed' ? 'text-red-600' :
                      'text-gray-400'
                    }`}>
                      {step.name}
                    </span>
                    {step.status === 'processing' && step.progress !== undefined && (
                      <span className="text-sm text-blue-600">{step.progress}%</span>
                    )}
                  </div>
                  {step.status === 'processing' && step.progress !== undefined && (
                    <div className="mt-1 w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${step.progress}%` }}
                      />
                    </div>
                  )}
                  {step.message && (
                    <p className="text-sm text-gray-500 mt-1">{step.message}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 全体の進捗 */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="font-medium">全体の進捗</span>
            <span className="text-blue-600 font-semibold">{overallProgress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div 
              className="bg-blue-600 h-3 rounded-full transition-all duration-500"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>

        {/* 推定残り時間 */}
        <div className="mt-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">推定残り時間</p>
            <p className="text-lg font-semibold text-gray-900">
              約 {formatTime(estimatedTime)}
            </p>
          </div>
          <div className="space-x-3">
            <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50">
              キャンセル
            </button>
            <button className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700">
              バックグラウンドで実行
            </button>
          </div>
        </div>
      </div>

      {/* 処理中のヒント */}
      <div className="mt-6 bg-blue-50 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          💡 ヒント: 処理中でも他の機能をご利用いただけます。処理が完了したら通知でお知らせします。
        </p>
      </div>
    </div>
  )
}