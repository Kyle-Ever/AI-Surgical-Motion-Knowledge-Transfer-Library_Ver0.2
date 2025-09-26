'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Download, Activity, Target, Move, Wrench, AlertCircle, CheckCircle } from 'lucide-react'
import dynamic from 'next/dynamic'

// 動的インポート（SSR対策）
const VideoPlayer = dynamic(() => import('@/components/VideoPlayer'), { ssr: false })
const ScoreComparison = dynamic(() => import('@/components/ScoreComparison'), { ssr: false })
const FeedbackPanel = dynamic(() => import('@/components/FeedbackPanel'), { ssr: false })
const MotionAnalysisPanel = dynamic(() => import('@/components/MotionAnalysisPanel'), { ssr: false })

interface DashboardClientProps {
  analysisId: string
}

interface MetricsData {
  position?: any
  velocity?: any
  angles?: any
  coordination?: any
  summary?: {
    detection_rate?: { left: number; right: number }
    average_velocity?: { left: number; right: number }
    average_coordination?: number
    total_frames?: number
  }
}

export default function DashboardClient({ analysisId }: DashboardClientProps) {
  const router = useRouter()
  const [analysisData, setAnalysisData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentVideoTime, setCurrentVideoTime] = useState(0)
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [videoInfo, setVideoInfo] = useState<any>(null)
  const [comparisonId, setComparisonId] = useState<string | null>(null)
  const [selectedReferenceId, setSelectedReferenceId] = useState<string | null>(null)
  const [isComparing, setIsComparing] = useState(false)

  // APIから解析結果を取得
  useEffect(() => {
    const fetchAnalysisData = async () => {
      try {
        setLoading(true)
        setError(null)

        // test-idの場合はモックデータを使用
        if (analysisId === 'test-id') {
          const mockData = {
            id: 'test-id',
            video_id: 'test-video-id',
            video_type: 'external',
            status: 'completed',
            progress: 100,
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
            video: {
              id: 'test-video-id',
              filename: 'test_video.mp4',
              title: 'テスト動画',
              url: '/api/v1/videos/test-video-id/file'
            },
            skeleton_data: [],
            motion_analysis: {
              metrics: {
                summary: {
                  detection_rate: { left: 0.95, right: 0.93 },
                  average_velocity: { left: 15.2, right: 14.8 },
                  average_coordination: 0.85,
                  total_frames: 1800
                }
              }
            }
          }
          setAnalysisData(mockData)
          setVideoInfo(mockData.video)
          setMetrics(mockData.motion_analysis.metrics)
          setLoading(false)
          return
        }

        const response = await fetch(`http://localhost:8000/api/v1/analysis/${analysisId}`)
        if (!response.ok) {
          throw new Error(`解析データの取得に失敗しました: ${response.status}`)
        }

        const data = await response.json()
        console.log('Analysis data received:', {
          id: data.id,
          video_id: data.video_id,
          video_type: data.video_type,
          status: data.status,
          has_skeleton_data: !!data.skeleton_data?.length,
          has_instrument_data: !!data.instrument_data?.length,
          has_motion_analysis: !!data.motion_analysis,
          has_metrics: !!data.motion_analysis?.metrics
        })

        setAnalysisData(data)

        // 動画情報を設定
        if (data.video) {
          setVideoInfo(data.video)
        }

        // メトリクスを抽出（nullチェック付き）
        if (data.motion_analysis?.metrics) {
          setMetrics(data.motion_analysis.metrics)
        } else {
          // メトリクスがない場合、skeleton_dataから簡易的に計算
          if (data.skeleton_data?.length > 0) {
            const detectionRate = calculateDetectionRate(data.skeleton_data)
            setMetrics({
              summary: {
                detection_rate: detectionRate,
                total_frames: data.total_frames || 0
              }
            })
          }
        }
      } catch (error) {
        console.error('Failed to fetch analysis data:', error)
        setError(error instanceof Error ? error.message : 'データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    fetchAnalysisData()
  }, [analysisId])

  // 基準モデルとの比較を実行
  const handleCompareWithReference = async (referenceId: string) => {
    if (!analysisData || isComparing) return

    try {
      setIsComparing(true)
      setSelectedReferenceId(referenceId)

      // 比較を実行
      const response = await fetch('http://localhost:8000/api/v1/scoring/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          analysis_id: analysisId,
          reference_id: referenceId
        })
      })

      if (!response.ok) {
        throw new Error('比較に失敗しました')
      }

      const comparison = await response.json()
      setComparisonId(comparison.id)
      console.log('Comparison created:', comparison.id)
    } catch (error) {
      console.error('Comparison failed:', error)
      alert('比較に失敗しました')
    } finally {
      setIsComparing(false)
    }
  }

  // 検出率を計算するヘルパー関数
  const calculateDetectionRate = (skeletonData: any[]) => {
    const leftCount = skeletonData.filter(d => d.hand_type === 'Left').length
    const rightCount = skeletonData.filter(d => d.hand_type === 'Right').length
    const maxFrames = Math.max(...skeletonData.map(d => d.frame_number || 0))

    return {
      left: maxFrames > 0 ? leftCount / maxFrames : 0,
      right: maxFrames > 0 ? rightCount / maxFrames : 0
    }
  }

  const handleExport = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/analysis/${analysisId}/export`)
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `analysis_${analysisId}.csv`
        a.click()
        window.URL.revokeObjectURL(url)
      }
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  // ローディング中
  if (loading) {
    return (
      <div className="max-w-7xl mx-auto p-4">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">解析結果</h1>
        <div className="flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">解析データを読み込んでいます...</p>
          </div>
        </div>
      </div>
    )
  }

  // エラー表示
  if (error) {
    return (
      <div className="max-w-7xl mx-auto p-4">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">解析結果</h1>
        <div className="flex items-center justify-center">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <p className="text-red-600">{error}</p>
            <button
              onClick={() => router.push('/library')}
              className="mt-4 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
            >
              ライブラリに戻る
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            解析結果
          </h1>
          {videoInfo && (
            <p className="text-gray-600 mt-1">
              {videoInfo.original_filename} - {videoInfo.video_type === 'external' ? '外部視点' : '内部視点'}
            </p>
          )}
        </div>
        <button
          onClick={handleExport}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          <Download className="w-4 h-4" />
          <span>エクスポート</span>
        </button>
      </div>

      {/* 動画プレーヤーとスコア表示 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* 動画プレーヤー */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2" />
            解析動画
          </h2>
          <VideoPlayer
            videoUrl={analysisData?.video_id ? `http://localhost:8000/api/v1/videos/${analysisData.video_id}/stream` : undefined}
            skeletonData={analysisData?.skeleton_data || []}
            toolData={analysisData?.instrument_data || []}
            videoType={analysisData?.video_type}
            onTimeUpdate={setCurrentVideoTime}
          />
        </div>

        {/* スコア比較 */}
        <div className="space-y-4">
          <ScoreComparison
            analysisId={analysisId}
            onComparisonStart={(id) => setComparisonId(id)}
          />
        </div>
      </div>

      {/* 手技の動き分析とフィードバック */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* 1. 手技の動き分析 */}
        <MotionAnalysisPanel
          analysisData={analysisData}
          currentVideoTime={currentVideoTime}
        />

        {/* 2. フィードバック */}
        <FeedbackPanel comparisonId={comparisonId} />
      </div>


      {/* 器具の動きセクション（internal videoのみ） */}
      {analysisData?.video_type === 'internal' && (
        <div className="mb-8">
          <h2 className="text-xl font-bold mb-4 flex items-center">
            <Wrench className="w-5 h-5 mr-2" />
            器具の動き分析
          </h2>

          <div className="bg-white rounded-lg shadow-sm p-6">
            {analysisData?.instrument_data && analysisData.instrument_data.length > 0 ? (
              <div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-sm text-gray-600">検出フレーム数</div>
                    <div className="text-2xl font-semibold text-purple-600">
                      {analysisData.instrument_data.length}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-sm text-gray-600">総フレーム数</div>
                    <div className="text-2xl font-semibold text-gray-700">
                      {analysisData.total_frames || '--'}
                    </div>
                  </div>
                </div>

                {/* 器具検出タイムライン */}
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">器具検出タイムライン</h4>
                  <div className="h-20 bg-gray-100 rounded-lg p-2">
                    <div className="relative h-full">
                      {analysisData.instrument_data.slice(0, 100).map((item: any, index: number) => (
                        <div
                          key={index}
                          className="absolute h-full w-1 bg-purple-500 opacity-50"
                          style={{
                            left: `${(item.frame_number / (analysisData.total_frames || 1)) * 100}%`
                          }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-gray-500 text-center py-8">
                <AlertCircle className="w-8 h-8 mx-auto mb-2" />
                器具データがありません
              </div>
            )}
          </div>
        </div>
      )}

      {/* サマリー */}
      <div className="bg-gray-50 rounded-lg p-6 mb-8">
        <h2 className="text-lg font-semibold mb-4 flex items-center">
          <CheckCircle className="w-5 h-5 mr-2" />
          解析サマリー
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center">
            <div className="text-sm text-gray-600">解析ステータス</div>
            <div className="text-xl font-semibold">
              {analysisData?.status === 'completed' ? '完了' : analysisData?.status || '--'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-600">総フレーム数</div>
            <div className="text-xl font-semibold">
              {analysisData?.total_frames || '--'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-600">動画タイプ</div>
            <div className="text-xl font-semibold">
              {analysisData?.video_type === 'external' ? '外部視点' : '内部視点'}
            </div>
          </div>
        </div>
      </div>

      {/* アクションボタン */}
      <div className="flex justify-center space-x-4">
        <button
          onClick={() => router.push('/library')}
          className="px-6 py-3 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
        >
          ライブラリに戻る
        </button>
        <button
          onClick={() => router.push('/upload')}
          className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          新しい動画を解析
        </button>
      </div>
    </div>
  )
}