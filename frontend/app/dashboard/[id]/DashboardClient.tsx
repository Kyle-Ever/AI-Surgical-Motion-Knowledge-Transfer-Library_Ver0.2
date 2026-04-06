'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Download, Activity, Target, Move, Wrench, AlertCircle, CheckCircle } from 'lucide-react'
import dynamic from 'next/dynamic'
import GazeDashboardClient from '@/components/GazeDashboardClient'
import { api, API_BASE_URL } from '@/lib/api'

// 相対評価のスコアをフロントで構築
function buildRelativeMetrics(learnerMetrics: any, expertMetrics: any): any {
  const result = JSON.parse(JSON.stringify(learnerMetrics))
  result.evaluation_mode = 'relative'
  result.expert_baseline_used = true

  const calcRelativeScore = (learnerVal: number, expertVal: number, inverted = false) => {
    if (!expertVal || expertVal === 0) return { score: learnerVal <= 0 ? 100 : 50, ratio: null }
    const ratio = inverted ? (expertVal / learnerVal) : (learnerVal / expertVal)
    const score = Math.max(0, Math.min(100, (2.0 - ratio) * 100))
    return { score: Math.round(score * 10) / 10, ratio: Math.round(ratio * 1000) / 1000 }
  }

  // 各指標のrawValuesを取得してratioを計算
  const groups = [
    { key: 'motion_quality', metrics: [
      { name: 'economy_of_motion', rawKey: 'total_path_length', inverted: false },
      { name: 'smoothness', rawKey: 'sparc_value', inverted: false, useAbs: true },
      { name: 'bimanual_coordination', rawKey: 'coordination_value', inverted: true },
    ]},
    { key: 'waste_detection', metrics: [
      { name: 'lost_time', rawKey: 'lost_time_ratio', inverted: false },
      { name: 'movement_count', rawKey: 'movements_per_minute', inverted: false },
      { name: 'working_volume', rawKey: 'convex_hull_area', inverted: false, bidirectional: true },
    ]},
  ]

  let mqTotal = 0, mqWeightSum = 0
  let wdTotal = 0, wdWeightSum = 0
  const mqWeights: Record<string, number> = { economy_of_motion: 0.40, smoothness: 0.35, bimanual_coordination: 0.25 }
  const wdWeights: Record<string, number> = { lost_time: 0.40, movement_count: 0.30, working_volume: 0.30 }

  for (const group of groups) {
    const isMQ = group.key === 'motion_quality'
    for (const m of group.metrics) {
      const learnerMetric = result[group.key]?.metrics?.[m.name]
      const expertMetric = expertMetrics[group.key]?.metrics?.[m.name]
      if (!learnerMetric || !expertMetric) continue

      let lVal = learnerMetric.raw_values?.[m.rawKey] ?? 0
      let eVal = expertMetric.raw_values?.[m.rawKey] ?? 0

      if ((m as any).useAbs) { lVal = Math.abs(lVal); eVal = Math.abs(eVal) }

      if ((m as any).bidirectional && eVal > 0) {
        const ratio = lVal / eVal
        const deviation = Math.abs(ratio - 1.0)
        const score = Math.max(0, Math.min(100, (1.0 - deviation) * 100))
        learnerMetric.score = Math.round(score * 10) / 10
        learnerMetric.ratio_to_expert = Math.round(ratio * 1000) / 1000
      } else {
        const { score, ratio } = calcRelativeScore(lVal, eVal, m.inverted)
        learnerMetric.score = score
        learnerMetric.ratio_to_expert = ratio
      }
      learnerMetric.evaluation_mode = 'relative'

      const w = isMQ ? (mqWeights[m.name] || 0) : (wdWeights[m.name] || 0)
      if (learnerMetric.score >= 0) {
        if (isMQ) { mqTotal += learnerMetric.score * w; mqWeightSum += w }
        else { wdTotal += learnerMetric.score * w; wdWeightSum += w }
      }
    }
  }

  result.motion_quality.group_score = mqWeightSum > 0 ? Math.round(mqTotal / mqWeightSum * 10) / 10 : 0
  result.waste_detection.group_score = wdWeightSum > 0 ? Math.round(wdTotal / wdWeightSum * 10) / 10 : 0
  result.overall_score = Math.round((result.motion_quality.group_score * 0.5 + result.waste_detection.group_score * 0.5) * 10) / 10

  return result
}

// 動的インポート（SSR対策）
const VideoPlayer = dynamic(() => import('@/components/VideoPlayer'), { ssr: false })
const ScoreComparison = dynamic(() => import('@/components/ScoreComparison'), { ssr: false })
const FeedbackPanel = dynamic(() => import('@/components/FeedbackPanel'), { ssr: false })
const MotionAnalysisPanel = dynamic(() => import('@/components/MotionAnalysisPanel'), { ssr: false })

// 6指標コンポーネント
const SixMetricsPanel = dynamic(() => import('@/components/metrics/SixMetricsPanel'), { ssr: false })
const MetricsRadarChart = dynamic(() => import('@/components/metrics/MetricsRadarChart'), { ssr: false })
const LostTimeTimeline = dynamic(() => import('@/components/metrics/LostTimeTimeline'), { ssr: false })
const ComparisonSettingsPanel = dynamic(() => import('@/components/metrics/ComparisonSettingsPanel'), { ssr: false })

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
  const [videoType, setVideoType] = useState<string | null>(null)
  const [sixMetrics, setSixMetrics] = useState<any>(null)
  const [sixMetricsAbsolute, setSixMetricsAbsolute] = useState<any>(null)  // 絶対評価（常に保持）
  const [sixMetricsRelative, setSixMetricsRelative] = useState<any>(null)  // 相対評価（基準選択後）
  const [evaluationTab, setEvaluationTab] = useState<'absolute' | 'relative'>('absolute')
  const [dualVideoMode, setDualVideoMode] = useState(false)  // 横並びモード
  const [refVideoUrl, setRefVideoUrl] = useState<string | null>(null)
  const [refSkeletonData, setRefSkeletonData] = useState<any[]>([])
  const [refToolData, setRefToolData] = useState<any[]>([])
  const [refVideoType, setRefVideoType] = useState<string | undefined>(undefined)
  const [refSixMetricsAbsolute, setRefSixMetricsAbsolute] = useState<any>(null)
  const [refVideoLoading, setRefVideoLoading] = useState(false)

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

        const { data } = await api.get(`/analysis/${analysisId}`)

        // 視線解析の場合は専用ダッシュボードへ
        if (data.video_type === 'eye_gaze') {
          setVideoType('eye_gaze')
          setAnalysisData(data)
          setLoading(false)
          return
        }

        setAnalysisData(data)

        // 6指標データを抽出（絶対評価として保持）
        if (data.motion_analysis?.six_metrics) {
          setSixMetrics(data.motion_analysis.six_metrics)
          setSixMetricsAbsolute(data.motion_analysis.six_metrics)
        }

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
      const { data: comparison } = await api.post('/scoring/compare', {
        analysis_id: analysisId,
        reference_id: referenceId
      })
      setComparisonId(comparison.id)
    } catch (error) {
      console.error('Comparison failed:', error)
      alert('比較に失敗しました')
    } finally {
      setIsComparing(false)
    }
  }

  // 基準モデル選択時に相対評価を取得
  const handleReferenceSelect = async (modelId: string) => {
    setSelectedReferenceId(modelId || null)

    if (!modelId) {
      // 基準解除 → 絶対評価に戻す
      setSixMetricsRelative(null)
      setSixMetrics(sixMetricsAbsolute)
      setEvaluationTab('absolute')
      setRefVideoUrl(null)
      setRefSixMetricsAbsolute(null)
      setDualVideoMode(false)
      return
    }

    // 相対評価をバックエンドに依頼（新しいAPIエンドポイント or フロントで計算）
    // 現在はバックエンド側に相対評価計算のAPIがないため、
    // 基準モデルの解析結果からフロントで簡易的にratioを計算
    try {
      setRefVideoLoading(true)

      // 基準モデル情報を取得
      const { data: refModel } = await api.get(`/scoring/reference/${modelId}`)

      if (refModel?.analysis_id) {
        // 基準の解析結果を取得
        const { data: refAnalysis } = await api.get(`/analysis/${refModel.analysis_id}`)

        // 基準動画URL・骨格データを設定
        if (refAnalysis?.video_id) {
          setRefVideoUrl(`${API_BASE_URL}/videos/${refAnalysis.video_id}/stream`)
        }
        setRefSkeletonData(refAnalysis?.skeleton_data || [])
        setRefToolData(refAnalysis?.instrument_data || [])
        setRefVideoType(refAnalysis?.video_type)

        // 基準の6指標を現在の設定で再計算（ロジック変更が基準にも反映されるように）
        let refSixMetrics = null
        try {
          const { data: smData } = await api.get(`/scoring/six-metrics/${refModel.analysis_id}?recalculate=true`)
          refSixMetrics = smData
        } catch (e) {
          console.error('Failed to calculate six_metrics for reference:', e)
          // フォールバック: 保存済みデータを使用
          refSixMetrics = refAnalysis?.motion_analysis?.six_metrics
        }

        if (refSixMetrics) {
          setRefSixMetricsAbsolute(refSixMetrics)
        }

        if (refSixMetrics && sixMetricsAbsolute) {
          // フロント側で相対スコアを算出
          const relative = buildRelativeMetrics(sixMetricsAbsolute, refSixMetrics)
          setSixMetricsRelative(relative)
          setSixMetrics(relative)
          setEvaluationTab('relative')
        }
      }
    } catch (err) {
      console.error('Failed to fetch reference data:', err)
    } finally {
      setRefVideoLoading(false)
    }
  }

  // タブ切替
  const handleEvaluationTabChange = (tab: 'absolute' | 'relative') => {
    setEvaluationTab(tab)
    if (tab === 'absolute') {
      setSixMetrics(sixMetricsAbsolute)
    } else if (sixMetricsRelative) {
      setSixMetrics(sixMetricsRelative)
    }
  }

  // 検出率を計算するヘルパー関数（新形式・旧形式両対応）
  const calculateDetectionRate = (skeletonData: any[]) => {
    if (!skeletonData || skeletonData.length === 0) {
      return { left: 0, right: 0 }
    }

    let leftCount = 0
    let rightCount = 0
    let maxFrames = 0

    // データ形式を判定
    const firstItem = skeletonData[0]
    const isNewFormat = firstItem && 'hands' in firstItem && Array.isArray(firstItem.hands)

    if (isNewFormat) {
      // 新形式: 1フレーム = 1レコード（複数の手を含む）
      skeletonData.forEach(frame => {
        if (frame.hands && Array.isArray(frame.hands)) {
          frame.hands.forEach((hand: any) => {
            if (hand.hand_type === 'Left') leftCount++
            if (hand.hand_type === 'Right') rightCount++
          })
        }
      })
      maxFrames = skeletonData.length
    } else {
      // 旧形式: 1手 = 1レコード
      leftCount = skeletonData.filter(d => d.hand_type === 'Left').length
      rightCount = skeletonData.filter(d => d.hand_type === 'Right').length
      maxFrames = Math.max(...skeletonData.map(d => d.frame_number || 0), 0)
    }

    return {
      left: maxFrames > 0 ? leftCount / maxFrames : 0,
      right: maxFrames > 0 ? rightCount / maxFrames : 0
    }
  }

  const handleExport = async () => {
    try {
      const response = await api.get(`/analysis/${analysisId}/export`, {
        responseType: 'blob'
      })
      const url = window.URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `analysis_${analysisId}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
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

  // 視線解析の場合は専用ダッシュボードを表示
  if (videoType === 'eye_gaze') {
    return <GazeDashboardClient analysisId={analysisId} />
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
        <button
          onClick={handleExport}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          <Download className="w-4 h-4" />
          <span>エクスポート</span>
        </button>
      </div>

      {/* Row 1: 動画プレーヤー + 比較設定 */}
      {dualVideoMode ? (
        /* === 横並びモード === */
        <div className="mb-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold flex items-center text-gray-700">
              <Activity className="w-4 h-4 mr-1.5" />
              動画比較
            </h2>
            <button
              onClick={() => setDualVideoMode(false)}
              className="text-xs px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-50 text-gray-600"
            >
              通常表示に戻す
            </button>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="bg-white rounded-lg shadow-sm p-3">
              <div className="text-xs font-medium text-blue-600 mb-1">学習者</div>
              <VideoPlayer
                videoUrl={analysisData?.video_id ? `${API_BASE_URL}/videos/${analysisData.video_id}/stream` : undefined}
                skeletonData={analysisData?.skeleton_data || []}
                toolData={analysisData?.instrument_data || []}
                videoType={analysisData?.video_type}
                onTimeUpdate={setCurrentVideoTime}
              />
            </div>
            <div className="bg-white rounded-lg shadow-sm p-3">
              <div className="text-xs font-medium text-purple-600 mb-1">エキスパート（基準）</div>
              {refVideoUrl ? (
                <VideoPlayer
                  videoUrl={refVideoUrl}
                  skeletonData={refSkeletonData}
                  toolData={refToolData}
                  videoType={refVideoType}
                />
              ) : (
                <div className="w-full aspect-video bg-gray-100 rounded flex items-center justify-center text-sm text-gray-400">
                  基準動画なし
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* === 通常モード === */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-3">
          {/* 動画プレーヤー（2/3幅） */}
          <div className="lg:col-span-2 bg-white rounded-lg shadow-sm p-4">
            <h2 className="text-sm font-semibold mb-2 flex items-center text-gray-700">
              <Activity className="w-4 h-4 mr-1.5" />
              解析動画
            </h2>
            <VideoPlayer
              videoUrl={analysisData?.video_id ? `${API_BASE_URL}/videos/${analysisData.video_id}/stream` : undefined}
              skeletonData={analysisData?.skeleton_data || []}
              toolData={analysisData?.instrument_data || []}
              videoType={analysisData?.video_type}
              onTimeUpdate={setCurrentVideoTime}
            />
          </div>

          {/* 比較設定パネル（1/3幅） */}
          <ComparisonSettingsPanel
            analysisId={analysisId}
            videoType={analysisData?.video_type}
            totalFrames={analysisData?.total_frames}
            detectionRate={analysisData?.motion_analysis?.skeleton_metrics?.summary?.detection_rate}
            evaluationMode={evaluationTab}
            selectedReferenceId={selectedReferenceId}
            sixMetrics={sixMetrics}
            onReferenceSelect={handleReferenceSelect}
            onDualVideoMode={() => setDualVideoMode(true)}
          />
        </div>
      )}

      {/* Row 2: ロスタイム タイムライン（動画幅に合わせる） */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-3">
        <div className="lg:col-span-2">
          <LostTimeTimeline
            totalDuration={
              sixMetrics?.waste_detection?.metrics?.lost_time?.raw_values?.total_duration_seconds || 0
            }
            lostSegments={
              sixMetrics?.waste_detection?.metrics?.lost_time?.raw_values?.lost_time_segments || []
            }
            checkPauseCount={
              sixMetrics?.waste_detection?.metrics?.lost_time?.raw_values?.check_pause_count || 0
            }
            checkPauseTotalSeconds={
              sixMetrics?.waste_detection?.metrics?.lost_time?.raw_values?.check_pause_total_seconds || 0
            }
            lostTimeSeconds={
              sixMetrics?.waste_detection?.metrics?.lost_time?.raw_values?.lost_time_seconds || 0
            }
            currentTime={currentVideoTime}
          />
        </div>
      </div>

      {/* Row 3: 6指標パネル（総合スコア内に切替ボタン統合済み） */}
      <SixMetricsPanel
        data={sixMetrics}
        timeline={analysisData?.motion_analysis?.six_metrics_timeline}
        currentVideoTime={currentVideoTime}
        evaluationTab={evaluationTab}
        hasRelativeData={!!sixMetricsRelative}
        onEvaluationTabChange={handleEvaluationTabChange}
      />

      {/* Row 4: ���ーダーチャート + フィードバック */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4 mb-6">
        <MetricsRadarChart
          scores={{
            a1: sixMetrics?.motion_quality?.metrics?.economy_of_motion?.score || 0,
            a2: sixMetrics?.motion_quality?.metrics?.smoothness?.score || 0,
            a3: sixMetrics?.motion_quality?.metrics?.bimanual_coordination?.score || 0,
            b1: sixMetrics?.waste_detection?.metrics?.lost_time?.score || 0,
            b2: sixMetrics?.waste_detection?.metrics?.movement_count?.score || 0,
            b3: sixMetrics?.waste_detection?.metrics?.working_volume?.score || 0,
          }}
          expertScores={refSixMetricsAbsolute ? {
            a1: refSixMetricsAbsolute?.motion_quality?.metrics?.economy_of_motion?.score || 0,
            a2: refSixMetricsAbsolute?.motion_quality?.metrics?.smoothness?.score || 0,
            a3: refSixMetricsAbsolute?.motion_quality?.metrics?.bimanual_coordination?.score || 0,
            b1: refSixMetricsAbsolute?.waste_detection?.metrics?.lost_time?.score || 0,
            b2: refSixMetricsAbsolute?.waste_detection?.metrics?.movement_count?.score || 0,
            b3: refSixMetricsAbsolute?.waste_detection?.metrics?.working_volume?.score || 0,
          } : null}
        />
        <FeedbackPanel sixMetrics={sixMetrics} />
      </div>

      {/* アクショ��ボタン */}
      <div className="flex justify-center space-x-4 mb-8">
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