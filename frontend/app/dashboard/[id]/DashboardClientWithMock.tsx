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

// モック器具データ生成関数
function generateMockInstrumentData(totalFrames: number) {
  const instrumentData = []
  const instruments = ['forceps', 'scissors', 'needle_holder']

  for (let frame = 0; frame < totalFrames; frame += 5) {
    const detections = []

    // 各器具に対してランダムに検出を生成
    instruments.forEach((instrument, idx) => {
      if (Math.random() > 0.3) { // 70%の確率で検出
        const centerX = 320 + Math.sin(frame * 0.1 + idx) * 100
        const centerY = 180 + Math.cos(frame * 0.1 + idx) * 80
        const width = 60 + Math.random() * 40
        const height = 40 + Math.random() * 30

        detections.push({
          bbox: [
            centerX - width/2,
            centerY - height/2,
            centerX + width/2,
            centerY + height/2
          ],
          confidence: 0.85 + Math.random() * 0.14,
          class_name: instrument,
          track_id: idx
        })
      }
    })

    if (detections.length > 0) {
      instrumentData.push({
        frame_number: frame,
        timestamp: frame / 30, // 30fps想定
        detections: detections
      })
    }
  }

  return instrumentData
}

export default function DashboardClient({ analysisId }: DashboardClientProps) {
  const router = useRouter()
  const [analysisData, setAnalysisData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentVideoTime, setCurrentVideoTime] = useState(0)
  const [metrics, setMetrics] = useState<any>(null)
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

        const response = await fetch(`http://localhost:8000/api/v1/analysis/${analysisId}`)
        if (!response.ok) {
          throw new Error(`解析データの取得に失敗しました: ${response.status}`)
        }

        const data = await response.json()

        // external_with_instrumentsの場合、モックデータを追加
        if (data.video_type === 'external_with_instruments' &&
            (!data.instrument_data || data.instrument_data.length === 0)) {
          console.log('Generating mock instrument data for external_with_instruments')
          const totalFrames = data.total_frames || 900 // デフォルト30秒分
          data.instrument_data = generateMockInstrumentData(totalFrames)
        }

        console.log('Analysis data received:', {
          id: data.id,
          video_id: data.video_id,
          video_type: data.video_type,
          status: data.status,
          has_skeleton_data: !!data.skeleton_data?.length,
          has_instrument_data: !!data.instrument_data?.length,
          instrument_data_count: data.instrument_data?.length || 0
        })

        setAnalysisData(data)

        // 動画情報を設定
        if (data.video) {
          setVideoInfo(data.video)
        }

        // メトリクスを抽出
        if (data.motion_analysis?.metrics) {
          setMetrics(data.motion_analysis.metrics)
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
              {videoInfo.original_filename} -
              {analysisData?.video_type === 'external' && '外部視点'}
              {analysisData?.video_type === 'external_with_instruments' && '外部視点（器具あり）'}
              {analysisData?.video_type === 'internal' && '内部視点'}
            </p>
          )}
        </div>
        <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          <Download className="w-4 h-4" />
          <span>エクスポート</span>
        </button>
      </div>

      {/* モックデータ通知 */}
      {analysisData?.video_type === 'external_with_instruments' && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertCircle className="h-5 w-5 text-yellow-400" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-yellow-700">
                デモモード: 器具検出のモックデータを表示しています。
                実際の検出を行うには、バックエンドで器具検出処理を実行してください。
              </p>
            </div>
          </div>
        </div>
      )}

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
          videoType={analysisData?.video_type}
        />

        {/* 2. フィードバック */}
        <FeedbackPanel comparisonId={comparisonId} />
      </div>

      {/* 器具の動きセクション（internalまたはexternal_with_instruments） */}
      {(analysisData?.video_type === 'internal' || analysisData?.video_type === 'external_with_instruments') && (
        <div className="mb-8">
          <h2 className="text-xl font-bold mb-4 flex items-center">
            <Wrench className="w-5 h-5 mr-2" />
            器具の動き分析
          </h2>

          <div className="bg-white rounded-lg shadow-sm p-6">
            {analysisData?.instrument_data && analysisData.instrument_data.length > 0 ? (
              <div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-sm text-gray-600">検出タイプ</div>
                    <div className="text-xl font-semibold text-purple-600">
                      {analysisData.video_type === 'external_with_instruments' ? '外部カメラ' : '内部カメラ'}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="text-sm text-gray-600">検出精度</div>
                    <div className="text-2xl font-semibold text-green-600">
                      {analysisData.instrument_data[0]?.detections?.[0]?.confidence
                        ? `${(analysisData.instrument_data[0].detections[0].confidence * 100).toFixed(0)}%`
                        : '--'}
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
              {analysisData?.video_type === 'external' && '外部視点'}
              {analysisData?.video_type === 'external_with_instruments' && '外部視点（器具あり）'}
              {analysisData?.video_type === 'internal' && '内部視点'}
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