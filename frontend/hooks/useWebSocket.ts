import { useEffect, useRef, useState, useCallback } from 'react'

export interface WebSocketMessage {
  type: string
  progress?: number
  status?: string
  step?: string
  message?: string
  data?: any
}

interface UseWebSocketOptions {
  autoReconnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  onMessage?: (message: WebSocketMessage) => void
}

export function useWebSocket(
  url: string | null,
  options: UseWebSocketOptions = {}
) {
  const {
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
    heartbeatInterval = 30000,
    onOpen,
    onClose,
    onError,
    onMessage,
  } = options

  const ws = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null)
  const heartbeatTimer = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)

  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const [error, setError] = useState<Error | null>(null)

  // Heartbeat機能
  const sendHeartbeat = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'ping' }))
    }
  }, [])

  const startHeartbeat = useCallback(() => {
    stopHeartbeat()
    heartbeatTimer.current = setInterval(sendHeartbeat, heartbeatInterval)
  }, [sendHeartbeat, heartbeatInterval])

  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
      heartbeatTimer.current = null
    }
  }, [])

  // WebSocket接続
  const connect = useCallback(() => {
    if (!url || ws.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const fullUrl = url.startsWith('ws')
        ? url
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${
            window.location.host
          }${url}`

      ws.current = new WebSocket(fullUrl)

      ws.current.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setError(null)
        reconnectAttempts.current = 0
        startHeartbeat()
        onOpen?.()
      }

      ws.current.onclose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)
        stopHeartbeat()
        onClose?.()

        // 自動再接続
        if (
          autoReconnect &&
          reconnectAttempts.current < maxReconnectAttempts
        ) {
          reconnectTimer.current = setTimeout(() => {
            reconnectAttempts.current++
            console.log(
              `Reconnecting... (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`
            )
            connect()
          }, reconnectInterval)
        }
      }

      ws.current.onerror = (event) => {
        console.error('WebSocket error:', event)
        setError(new Error('WebSocket connection error'))
        onError?.(event)
      }

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage

          // Pong応答は無視
          if (message.type === 'pong') {
            return
          }

          setLastMessage(message)
          onMessage?.(message)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }
    } catch (err) {
      console.error('Failed to create WebSocket:', err)
      setError(err as Error)
    }
  }, [
    url,
    autoReconnect,
    reconnectInterval,
    maxReconnectAttempts,
    startHeartbeat,
    stopHeartbeat,
    onOpen,
    onClose,
    onError,
    onMessage,
  ])

  // 切断
  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }

    stopHeartbeat()

    if (ws.current) {
      ws.current.close()
      ws.current = null
    }

    setIsConnected(false)
  }, [stopHeartbeat])

  // メッセージ送信
  const sendMessage = useCallback((message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const data = typeof message === 'string' ? message : JSON.stringify(message)
      ws.current.send(data)
      return true
    }
    return false
  }, [])

  // 初期接続とクリーンアップ
  useEffect(() => {
    if (url) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [url]) // connectとdisconnectは依存関係から除外（無限ループ防止）

  return {
    isConnected,
    lastMessage,
    error,
    sendMessage,
    connect,
    disconnect,
  }
}

// 解析進捗用の特化したフック
export function useAnalysisWebSocket(analysisId: string | null) {
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<string>('pending')
  const [currentStep, setCurrentStep] = useState<string>('')
  const [message, setMessage] = useState<string>('')

  const wsUrl = analysisId
    ? `${process.env.NEXT_PUBLIC_WS_URL || ''}/ws/analysis/${analysisId}`
    : null

  const { isConnected, lastMessage, error } = useWebSocket(wsUrl, {
    onMessage: (msg) => {
      if (msg.type === 'progress') {
        setProgress(msg.progress || 0)
        setStatus(msg.status || 'processing')
        setCurrentStep(msg.step || '')
        setMessage(msg.message || '')
      }
    },
  })

  return {
    isConnected,
    progress,
    status,
    currentStep,
    message,
    error,
    lastMessage,
  }
}