'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Calendar, Clock, CheckCircle, XCircle, AlertCircle, Loader, Award } from 'lucide-react'
import { format } from 'date-fns'
import { getCompletedComparisons } from '@/lib/api'

interface Video {
  id: string
  filename: string
  original_filename: string
  surgery_name?: string
  surgeon_name?: string
  surgery_date?: string
  video_type?: string
  duration?: number
  created_at: string
}

interface AnalysisResult {
  id: string
  video_id: string
  status: string
  skeleton_data?: any
  instrument_data?: any
  motion_analysis?: any
  scores?: any
  avg_velocity?: number
  max_velocity?: number
  total_distance?: number
  total_frames?: number
  created_at: string
  completed_at?: string
  video?: Video
}

const statusConfig = {
  completed: {
    icon: CheckCircle,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    label: '完了',
  },
  processing: {
    icon: AlertCircle,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    label: '処理中',
  },
  failed: {
    icon: XCircle,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    label: '失敗',
  },
  pending: {
    icon: AlertCircle,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50',
    label: '待機中',
  },
}

export default function HistoryPage() {
  const router = useRouter()
  const [analyses, setAnalyses] = useState<AnalysisResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    fetchAnalyses()
  }, [])

  const fetchAnalyses = async () => {
    try {
      setLoading(true)

      // 完了した分析、採点結果、ビデオ情報を並列で取得
      const [completedRes, comparisonsData, videosRes] = await Promise.all([
        fetch(`${process.env.NEXT_PUBLIC_API_URL}/analysis/completed`),
        getCompletedComparisons(),
        fetch(`${process.env.NEXT_PUBLIC_API_URL}/videos`)
      ])

      if (!completedRes.ok) {
        throw new Error('分析履歴の取得に失敗しました')
      }
      const completedData = await completedRes.json()

      if (!videosRes.ok) {
        throw new Error('ビデオ一覧の取得に失敗しました')
      }
      const videosData = await videosRes.json()

      // 各ビデオの分析結果を取得
      const allAnalyses: any[] = []
      for (const video of videosData) {
        try {
          const analysisRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/videos/${video.id}`)
          if (analysisRes.ok) {
            const videoDetail = await analysisRes.json()
            if (videoDetail.analyses && videoDetail.analyses.length > 0) {
              videoDetail.analyses.forEach((analysis: AnalysisResult) => {
                allAnalyses.push({
                  ...analysis,
                  video: {
                    ...video,
                    surgery_name: video.surgery_name || '手術名未設定',
                    surgeon_name: video.surgeon_name || '執刀医未設定',
                  },
                  type: 'analysis'
                })
              })
            }
          }
        } catch (err) {
          console.error(`Error fetching analysis for video ${video.id}:`, err)
        }
      }

      // 採点結果を履歴用に整形
      if (comparisonsData && comparisonsData.length > 0) {
        comparisonsData.forEach((comparison: any) => {
          allAnalyses.push({
            id: comparison.id,
            video_id: comparison.learner_video_id || comparison.evaluation_video_id,
            status: comparison.status || 'completed',
            scores: {
              overall: comparison.overall_score
            },
            created_at: comparison.created_at,
            completed_at: comparison.completed_at,
            video: {
              surgery_name: `【採点】${comparison.learner_analysis?.video?.surgery_name || '手術名未設定'}`,
              surgeon_name: comparison.learner_analysis?.video?.surgeon_name || '学習者',
            },
            type: 'comparison'
          })
        })
      }

      // 完了した分析と全分析をマージ（重複を除く）
      const mergedAnalyses = [...completedData]
      allAnalyses.forEach(analysis => {
        if (!mergedAnalyses.find(a => a.id === analysis.id)) {
          mergedAnalyses.push(analysis)
        }
      })

      // 作成日時でソート（新しいものが上）
      mergedAnalyses.sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )

      setAnalyses(mergedAnalyses)
    } catch (err) {
      setError(err instanceof Error ? err.message : '不明なエラーが発生しました')
    } finally {
      setLoading(false)
    }
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-'
    const minutes = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
    } catch {
      return dateString
    }
  }

  const handleViewResult = (analysisId: string) => {
    router.push(`/dashboard/${analysisId}`)
  }

  const handleViewProgress = (analysisId: string) => {
    router.push(`/dashboard/${analysisId}`)
  }

  const handleRetry = async (videoId: string) => {
    // 再実行のロジックを実装
    console.log('Retry analysis for video:', videoId)
  }

  const filteredAnalyses = statusFilter
    ? analyses.filter(a => a.status === statusFilter)
    : analyses

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto flex items-center justify-center h-64">
        <div className="flex items-center space-x-2">
          <Loader className="w-6 h-6 animate-spin text-blue-600" />
          <span className="text-gray-600">分析履歴を読み込み中...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700">{error}</p>
          <button
            onClick={fetchAnalyses}
            className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            再試行
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">解析履歴</h1>
        <p className="text-gray-600 mt-1">過去の解析処理を確認できます</p>
      </div>

      {/* フィルター */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
        <div className="flex items-center space-x-4">
          <select
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">すべてのステータス</option>
            <option value="completed">完了</option>
            <option value="processing">処理中</option>
            <option value="failed">失敗</option>
            <option value="pending">待機中</option>
          </select>
          <button
            onClick={fetchAnalyses}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
          >
            更新
          </button>
        </div>
      </div>

      {/* 履歴テーブル */}
      {filteredAnalyses.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm p-8 text-center">
          <p className="text-gray-500">分析履歴がありません</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ファイル名
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  手術名
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  執刀医
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  日時
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  動画時間
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ステータス
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  アクション
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredAnalyses.map((item) => {
                const status = statusConfig[item.status as keyof typeof statusConfig] || statusConfig.pending
                const StatusIcon = status.icon

                return (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {item.video?.original_filename || item.video?.filename || 'ファイル名不明'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {item.video?.surgery_name || '手術名未設定'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {item.video?.surgeon_name || '執刀医未設定'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(item.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center">
                        <Clock className="w-4 h-4 mr-1" />
                        {formatDuration(item.video?.duration)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${status.bgColor} ${status.color}`}>
                        <StatusIcon className="w-3 h-3 mr-1" />
                        {status.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {item.status === 'completed' && (
                        <button
                          onClick={() => handleViewResult(item.id)}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          結果を見る
                        </button>
                      )}
                      {item.status === 'processing' && (
                        <button
                          onClick={() => handleViewProgress(item.id)}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          進捗確認
                        </button>
                      )}
                      {item.status === 'failed' && (
                        <button
                          onClick={() => handleRetry(item.video_id)}
                          className="text-orange-600 hover:text-orange-800"
                        >
                          再実行
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 件数表示 */}
      <div className="mt-6 flex items-center justify-between">
        <div className="text-sm text-gray-700">
          全 {filteredAnalyses.length} 件
        </div>
      </div>
    </div>
  )
}