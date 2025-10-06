'use client'

import { AlertCircle, RefreshCw, Home } from 'lucide-react'
import { useRouter } from 'next/navigation'

interface ErrorStateProps {
  error?: string | Error
  title?: string
  message?: string
  onRetry?: () => void
  showHomeButton?: boolean
  type?: 'error' | 'warning' | 'info'
}

export default function ErrorState({
  error,
  title = 'エラーが発生しました',
  message,
  onRetry,
  showHomeButton = true,
  type = 'error'
}: ErrorStateProps) {
  const router = useRouter()

  const bgColors = {
    error: 'bg-red-50',
    warning: 'bg-yellow-50',
    info: 'bg-blue-50'
  }

  const iconColors = {
    error: 'text-red-600',
    warning: 'text-yellow-600',
    info: 'text-blue-600'
  }

  const titleColors = {
    error: 'text-red-900',
    warning: 'text-yellow-900',
    info: 'text-blue-900'
  }

  const messageColors = {
    error: 'text-red-700',
    warning: 'text-yellow-700',
    info: 'text-blue-700'
  }

  const errorMessage = message || (error instanceof Error ? error.message : error) || 'エラーが発生しました'

  return (
    <div className={`${bgColors[type]} rounded-lg p-8 text-center`}>
      <AlertCircle className={`w-12 h-12 ${iconColors[type]} mx-auto mb-4`} />
      <h2 className={`text-xl font-semibold ${titleColors[type]} mb-2`}>
        {title}
      </h2>
      <p className={`${messageColors[type]} mb-6`}>
        {errorMessage}
      </p>
      <div className="flex gap-3 justify-center">
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition"
          >
            <RefreshCw className="w-4 h-4" />
            再試行
          </button>
        )}
        {showHomeButton && (
          <button
            onClick={() => router.push('/')}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition"
          >
            <Home className="w-4 h-4" />
            ホームに戻る
          </button>
        )}
      </div>
    </div>
  )
}