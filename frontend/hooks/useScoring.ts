import { useState, useCallback, useEffect, useRef } from 'react'
import { api, endpoints } from '@/lib/api'

// モック骨格データを生成する関数
function generateMockSkeletonData(frameCount: number) {
  const skeletonData = []

  for (let i = 0; i < frameCount; i++) {
    const landmarks: any = {}

    // 手の中心位置（円運動）
    const centerX = 0.5 + 0.2 * Math.sin(i * 0.05)
    const centerY = 0.5 + 0.2 * Math.cos(i * 0.05)

    // 21個の手のランドマーク
    const handStructure = [
      [0, 0],      // 0: 手首
      [-0.02, -0.04], // 1: 親指CMC
      [-0.03, -0.08], // 2: 親指MCP
      [-0.04, -0.12], // 3: 親指IP
      [-0.05, -0.15], // 4: 親指先端
      [0, -0.05],   // 5: 人差し指MCP
      [0, -0.10],   // 6: 人差し指PIP
      [0, -0.14],   // 7: 人差し指DIP
      [0, -0.17],   // 8: 人差し指先端
      [0.02, -0.05],  // 9: 中指MCP
      [0.02, -0.10],  // 10: 中指PIP
      [0.02, -0.14],  // 11: 中指DIP
      [0.02, -0.17],  // 12: 中指先端
      [0.04, -0.05],  // 13: 薬指MCP
      [0.04, -0.10],  // 14: 薬指PIP
      [0.04, -0.14],  // 15: 薬指DIP
      [0.04, -0.17],  // 16: 薬指先端
      [0.06, -0.05],  // 17: 小指MCP
      [0.06, -0.09],  // 18: 小指PIP
      [0.06, -0.13],  // 19: 小指DIP
      [0.06, -0.16],  // 20: 小指先端
    ]

    handStructure.forEach((offset, j) => {
      landmarks[`point_${j}`] = {
        x: Math.max(0.1, Math.min(0.9, centerX + offset[0] + (Math.random() - 0.5) * 0.01)),
        y: Math.max(0.1, Math.min(0.9, centerY + offset[1] + (Math.random() - 0.5) * 0.01)),
        z: (Math.random() - 0.5) * 0.1
      }
    })

    skeletonData.push({
      frame_number: i,
      timestamp: i * 0.033,
      landmarks: landmarks
    })
  }

  return skeletonData
}

// 採点関連の型定義
interface ReferenceModel {
  id: string
  name: string
  description?: string
  surgeon_name?: string
  surgery_type?: string
  surgery_date?: string
  created_at: string
}

interface ComparisonResult {
  id: string
  reference_model_id: string
  learner_analysis_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  overall_score?: number
  speed_score?: number
  smoothness_score?: number
  stability_score?: number
  efficiency_score?: number
  feedback?: {
    strengths: Array<any>
    weaknesses: Array<any>
    suggestions: Array<any>
    detailed_analysis?: any
  }
  error_message?: string
  created_at: string
  completed_at?: string
}

// 基準モデル一覧を取得するフック
export function useReferenceModels() {
  const [models, setModels] = useState<ReferenceModel[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchModels = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.get('/scoring/references')
      setModels(response.data)
    } catch (err: any) {
      setError(err.message || '基準モデルの取得に失敗しました')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchModels()
  }, [fetchModels])

  return { models, isLoading, error, refetch: fetchModels }
}

// 基準モデルを作成するフック
export function useCreateReferenceModel() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createModel = useCallback(async (
    analysisId: string,
    name: string,
    description?: string,
    metadata?: any
  ) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.post('/scoring/reference', {
        analysis_id: analysisId,
        name,
        description,
        reference_type: 'expert',
        ...metadata
      })

      return response.data
    } catch (err: any) {
      setError(err.message || '基準モデルの作成に失敗しました')
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { createModel, isLoading, error }
}

// 比較を開始するフック
export function useStartComparison() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startComparison = useCallback(async (
    referenceModelId: string,
    learnerAnalysisId: string
  ) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.post('/scoring/compare', {
        reference_model_id: referenceModelId,
        learner_analysis_id: learnerAnalysisId
      })

      return response.data
    } catch (err: any) {
      setError(err.message || '比較の開始に失敗しました')
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { startComparison, isLoading, error }
}

// 比較結果を取得するフック
export function useComparisonResult(comparisonId: string | null) {
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<NodeJS.Timer | null>(null)

  const fetchResult = useCallback(async () => {
    if (!comparisonId) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await api.get(`/scoring/comparison/${comparisonId}`, {
        params: { include_details: true }
      })

      // APIレスポンスにvideo_idとanalysis_idを追加（バックエンドから取得）
      const data = response.data

      // learner_analysis_idを使って詳細情報を取得
      if (data.learner_analysis_id) {
        try {
          const learnerRes = await api.get(`/analysis/${data.learner_analysis_id}`)
          if (learnerRes.data) {
            data.learner_video_id = learnerRes.data.video_id

            // 骨格データの確認（モックデータ生成は削除）
            if (learnerRes.data.skeleton_data) {
              console.log(`Learner video has ${learnerRes.data.skeleton_data.length} skeleton frames`)
            } else {
              console.log('[WARNING] No skeleton data found for learner video')
              // モックデータは生成しない - 実データのみ使用
              learnerRes.data.skeleton_data = []
            }

            data.learner_analysis = learnerRes.data
            console.log('Learner analysis:', learnerRes.data)
            console.log('Learner video ID:', data.learner_video_id)
          }
        } catch (err) {
          console.error('Failed to fetch learner analysis:', err)
        }
      }

      // reference_model_idを使って詳細情報を取得
      if (data.reference_model_id) {
        try {
          const refRes = await api.get(`/scoring/reference/${data.reference_model_id}`)
          if (refRes.data) {
            // reference modelから analysis_id を取得し、そこから video_id を取得
            if (refRes.data.analysis_id) {
              try {
                const refAnalysisRes = await api.get(`/analysis/${refRes.data.analysis_id}`)
                if (refAnalysisRes.data) {
                  data.reference_video_id = refAnalysisRes.data.video_id

                  // 骨格データの確認（モックデータ生成は削除）
                  if (refAnalysisRes.data.skeleton_data) {
                    console.log(`Reference video has ${refAnalysisRes.data.skeleton_data.length} skeleton frames`)
                  } else {
                    console.log('[WARNING] No skeleton data found for reference video')
                    // モックデータは生成しない - 実データのみ使用
                    refAnalysisRes.data.skeleton_data = []
                  }

                  data.reference_analysis = refAnalysisRes.data
                  console.log('Reference analysis:', refAnalysisRes.data)
                  console.log('Reference video ID:', data.reference_video_id)
                }
              } catch (err) {
                console.error('Failed to fetch reference analysis:', err)
              }
            }
            data.reference_model = refRes.data
          }
        } catch (err) {
          console.error('Failed to fetch reference model:', err)
        }
      }

      // 完全なデータをstateに保存
      setResult(data)

      console.log('Full comparison data with skeleton:', data);
      console.log('Learner analysis included:', !!data.learner_analysis);
      console.log('Reference analysis included:', !!data.reference_analysis);

      // 処理中の場合は定期的に更新
      if (response.data.status === 'processing' && !intervalRef.current) {
        intervalRef.current = setInterval(async () => {
          try {
            const update = await api.get(`/scoring/comparison/${comparisonId}/status`)
            setResult((prev) => prev ? { ...prev, ...update.data } : update.data)

            if (update.data.status !== 'processing') {
              if (intervalRef.current) {
                clearInterval(intervalRef.current)
                intervalRef.current = null
              }
              // 完了したら詳細を取得
              const detail = await api.get(`/scoring/comparison/${comparisonId}`, {
                params: { include_details: true }
              })
              setResult(detail.data)
            }
          } catch (err) {
            console.error('Failed to update comparison status:', err)
          }
        }, 2000)
      }
    } catch (err: any) {
      setError(err.message || '比較結果の取得に失敗しました')
    } finally {
      setIsLoading(false)
    }
  }, [comparisonId])

  useEffect(() => {
    if (comparisonId) {
      fetchResult()
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [comparisonId, fetchResult])

  return { result, isLoading, error, refetch: fetchResult }
}

// 比較レポートを取得するフック
export function useComparisonReport(comparisonId: string | null) {
  const [report, setReport] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchReport = useCallback(async () => {
    if (!comparisonId) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await api.get(`/scoring/report/${comparisonId}`)
      setReport(response.data)
    } catch (err: any) {
      setError(err.message || 'レポートの取得に失敗しました')
    } finally {
      setIsLoading(false)
    }
  }, [comparisonId])

  useEffect(() => {
    if (comparisonId) {
      fetchReport()
    }
  }, [comparisonId, fetchReport])

  return { report, isLoading, error, refetch: fetchReport }
}