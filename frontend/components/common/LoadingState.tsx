'use client'

import { Loader2 } from 'lucide-react'

interface LoadingStateProps {
  type?: 'analysis' | 'video' | 'comparison' | 'default'
  message?: string
  progress?: number
  size?: 'sm' | 'md' | 'lg'
}

export default function LoadingState({
  type = 'default',
  message,
  progress,
  size = 'md'
}: LoadingStateProps) {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-12 h-12',
    lg: 'w-16 h-16'
  }

  const defaultMessages = {
    analysis: '解析を実行中...',
    video: '動画を読み込み中...',
    comparison: '比較データを処理中...',
    default: '読み込み中...'
  }

  const displayMessage = message || defaultMessages[type]

  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="relative">
        <Loader2
          className={`${sizeClasses[size]} animate-spin text-blue-600 mb-4`}
        />
        {progress !== undefined && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-semibold text-blue-600">
              {Math.round(progress)}%
            </span>
          </div>
        )}
      </div>
      <p className="text-gray-600">{displayMessage}</p>
      {progress !== undefined && (
        <div className="w-64 mt-4">
          <div className="bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 rounded-full h-2 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}