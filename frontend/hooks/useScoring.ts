import { useState, useCallback, useEffect, useRef } from 'react'
import { api, endpoints } from '@/lib/api'

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
      setResult(response.data)

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