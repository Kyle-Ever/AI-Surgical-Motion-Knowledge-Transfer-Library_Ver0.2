import { useState, useCallback, useEffect, useRef } from 'react'
import { api, endpoints, wsEndpoints } from '@/lib/api'
import { AnalysisStatus } from '@/types'

// 動画アップロード用フック
export function useUploadVideo() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)

  const uploadVideo = useCallback(async (
    file: File,
    metadata: {
      video_type: string
      surgery_name?: string
      surgery_date?: string
      surgeon_name?: string
      memo?: string
    }
  ) => {
    setIsLoading(true)
    setError(null)
    setProgress(0)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('video_type', metadata.video_type)
    if (metadata.surgery_name) formData.append('surgery_name', metadata.surgery_name)
    if (metadata.surgery_date) formData.append('surgery_date', metadata.surgery_date)
    if (metadata.surgeon_name) formData.append('surgeon_name', metadata.surgeon_name)
    if (metadata.memo) formData.append('memo', metadata.memo)

    try {
      const response = await api.post(endpoints.videos.upload, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000, // 5分タイムアウト（動画アップロード用）
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            setProgress(percentCompleted)
          }
        },
      })

      setIsLoading(false)
      return response.data
    } catch (err: any) {
      setError(err.message || 'アップロードに失敗しました')
      setIsLoading(false)
      throw err
    }
  }, [])

  return {
    uploadVideo,
    isLoading,
    error,
    progress,
  }
}

// 解析開始用フック
export function useStartAnalysis() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startAnalysis = useCallback(async (
    videoId: string,
    instruments?: any[],
    samplingRate: number = 5
  ) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.post(endpoints.analysis.start(videoId), {
        video_id: videoId,
        instruments,
        sampling_rate: samplingRate,
      })

      setIsLoading(false)
      return response.data
    } catch (err: any) {
      setError(err.message || '解析の開始に失敗しました')
      setIsLoading(false)
      throw err
    }
  }, [])

  return {
    startAnalysis,
    isLoading,
    error,
  }
}

// 解析ステータス取得用フック
export function useAnalysisStatus(analysisId: string | null, interval: number = 2000) {
  const [status, setStatus] = useState<AnalysisStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!analysisId) return

    const fetchStatus = async () => {
      setIsLoading(true)
      try {
        const response = await api.get(endpoints.analysis.status(analysisId))
        setStatus(response.data)
        setError(null)
      } catch (err: any) {
        setError(err.message || 'ステータスの取得に失敗しました')
      } finally {
        setIsLoading(false)
      }
    }

    // 初回実行
    fetchStatus()

    // 定期的に実行
    const intervalId = setInterval(fetchStatus, interval)

    return () => clearInterval(intervalId)
  }, [analysisId, interval])

  return {
    status,
    isLoading,
    error,
  }
}

// WebSocket接続用フック
export function useWebSocket(analysisId: string | null) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<any>(null)
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!analysisId) return

    const connect = () => {
      try {
        ws.current = new WebSocket(wsEndpoints.analysis(analysisId))

        ws.current.onopen = () => {
          console.log('WebSocket connected')
          setIsConnected(true)
        }

        ws.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            setLastMessage(data)
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error)
          }
        }

        ws.current.onerror = (error) => {
          // WebSocket errorイベントは詳細を提供しない（仕様）
          // 接続状態の変化はoncloseで処理される
          console.debug('WebSocket error event (normal during disconnect):', error)
        }

        ws.current.onclose = () => {
          console.log('WebSocket disconnected')
          setIsConnected(false)
          
          // 自動再接続（5秒後）
          setTimeout(() => {
            if (ws.current?.readyState === WebSocket.CLOSED) {
              connect()
            }
          }, 5000)
        }
      } catch (error) {
        console.error('Failed to connect WebSocket:', error)
      }
    }

    connect()

    return () => {
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [analysisId])

  const sendMessage = useCallback((message: any) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message))
    }
  }, [])

  return {
    isConnected,
    lastMessage,
    sendMessage,
  }
}

// 解析結果取得用フック
export function useAnalysisResult(analysisId: string | null) {
  const [result, setResult] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!analysisId) return

    const fetchResult = async () => {
      setIsLoading(true)
      try {
        const response = await api.get(endpoints.analysis.result(analysisId))
        setResult(response.data)
        setError(null)
      } catch (err: any) {
        setError(err.message || '結果の取得に失敗しました')
      } finally {
        setIsLoading(false)
      }
    }

    fetchResult()
  }, [analysisId])

  return {
    result,
    isLoading,
    error,
  }
}