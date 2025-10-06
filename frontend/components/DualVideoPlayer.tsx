'use client'

import { useRef, useEffect, useState } from 'react'
import { Play, Pause, SkipForward, SkipBack } from 'lucide-react'
import VideoPlayer from './VideoPlayer'

interface DualVideoPlayerProps {
  referenceVideoId?: string
  learnerVideoId?: string
  referenceAnalysisId?: string
  learnerAnalysisId?: string
  syncPlay?: boolean
  playbackRate?: number
  onTimeUpdate?: (time: number) => void
}

export default function DualVideoPlayer({
  referenceVideoId,
  learnerVideoId,
  referenceAnalysisId,
  learnerAnalysisId,
  syncPlay = true,
  playbackRate = 1,
  onTimeUpdate
}: DualVideoPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [referenceData, setReferenceData] = useState<any>(null)
  const [learnerData, setLearnerData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const referenceVideoRef = useRef<HTMLVideoElement>(null)
  const learnerVideoRef = useRef<HTMLVideoElement>(null)

  // 解析データを取得
  useEffect(() => {
    const fetchAnalysisData = async () => {
      try {
        setLoading(true)

        // 基準動画の解析データ取得
        if (referenceAnalysisId) {
          const refResponse = await fetch(`http://localhost:8000/api/v1/analysis/${referenceAnalysisId}`)
          if (refResponse.ok) {
            const refData = await refResponse.json()
            setReferenceData(refData)
          }
        }

        // 学習者動画の解析データ取得
        if (learnerAnalysisId) {
          const learnResponse = await fetch(`http://localhost:8000/api/v1/analysis/${learnerAnalysisId}`)
          if (learnResponse.ok) {
            const learnData = await learnResponse.json()
            setLearnerData(learnData)
          }
        }
      } catch (error) {
        console.error('Failed to fetch analysis data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchAnalysisData()
  }, [referenceAnalysisId, learnerAnalysisId])

  // 再生/停止の同期制御
  const handlePlayPause = () => {
    if (syncPlay) {
      if (isPlaying) {
        referenceVideoRef.current?.pause()
        learnerVideoRef.current?.pause()
      } else {
        referenceVideoRef.current?.play()
        learnerVideoRef.current?.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  // 時間更新の処理
  const handleTimeUpdate = (time: number) => {
    setCurrentTime(time)
    if (onTimeUpdate) {
      onTimeUpdate(time)
    }

    // 同期再生時は両方の動画の時間を同期
    if (syncPlay && referenceVideoRef.current && learnerVideoRef.current) {
      const diff = Math.abs(referenceVideoRef.current.currentTime - learnerVideoRef.current.currentTime)
      if (diff > 0.1) {
        learnerVideoRef.current.currentTime = referenceVideoRef.current.currentTime
      }
    }
  }

  // スキップ機能
  const handleSkip = (seconds: number) => {
    if (referenceVideoRef.current) {
      referenceVideoRef.current.currentTime += seconds
    }
    if (syncPlay && learnerVideoRef.current) {
      learnerVideoRef.current.currentTime += seconds
    }
  }

  // 再生速度の変更
  useEffect(() => {
    if (referenceVideoRef.current) {
      referenceVideoRef.current.playbackRate = playbackRate
    }
    if (learnerVideoRef.current) {
      learnerVideoRef.current.playbackRate = playbackRate
    }
  }, [playbackRate])

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-8 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">動画データを読み込み中...</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* デュアルビデオセクション */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 左側：基準動画 */}
        <div className="bg-white rounded-lg shadow-sm">
          <div className="px-4 py-3 border-b bg-green-50">
            <h2 className="font-semibold text-green-800 flex items-center">
              <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
              基準動作（指導医）
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {referenceData?.video?.original_filename || '基準動画'}
            </p>
          </div>
          <div className="p-4">
            <div className="relative">
              <VideoPlayer
                videoUrl={referenceVideoId ? `http://localhost:8000/api/v1/videos/${referenceVideoId}/stream` : undefined}
                skeletonData={referenceData?.skeleton_data || []}
                toolData={referenceData?.instrument_data || []}
                videoType={referenceData?.video_type}
                onTimeUpdate={handleTimeUpdate}
                autoPlay={false}
              />
              <video
                ref={referenceVideoRef}
                className="hidden"
                src={referenceVideoId ? `http://localhost:8000/api/v1/videos/${referenceVideoId}/stream` : undefined}
                onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
              />
            </div>
          </div>
        </div>

        {/* 右側：評価動画 */}
        <div className="bg-white rounded-lg shadow-sm">
          <div className="px-4 py-3 border-b bg-blue-50">
            <h2 className="font-semibold text-blue-800 flex items-center">
              <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
              評価動作（学習者）
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {learnerData?.video?.original_filename || '評価動画'}
            </p>
          </div>
          <div className="p-4">
            <div className="relative">
              <VideoPlayer
                videoUrl={learnerVideoId ? `http://localhost:8000/api/v1/videos/${learnerVideoId}/stream` : undefined}
                skeletonData={learnerData?.skeleton_data || []}
                toolData={learnerData?.instrument_data || []}
                videoType={learnerData?.video_type}
                onTimeUpdate={syncPlay ? undefined : setCurrentTime}
                autoPlay={false}
              />
              <video
                ref={learnerVideoRef}
                className="hidden"
                src={learnerVideoId ? `http://localhost:8000/api/v1/videos/${learnerVideoId}/stream` : undefined}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 統合再生コントロール（同期再生時のみ表示） */}
      {syncPlay && (
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="flex items-center gap-4">
            {/* スキップバック */}
            <button
              onClick={() => handleSkip(-10)}
              className="p-2 bg-gray-100 rounded hover:bg-gray-200 transition"
              title="10秒戻る"
            >
              <SkipBack className="w-5 h-5" />
            </button>

            {/* 再生/停止 */}
            <button
              onClick={handlePlayPause}
              className="p-3 bg-purple-600 text-white rounded-full hover:bg-purple-700 transition"
            >
              {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            </button>

            {/* スキップフォワード */}
            <button
              onClick={() => handleSkip(10)}
              className="p-2 bg-gray-100 rounded hover:bg-gray-200 transition"
              title="10秒進む"
            >
              <SkipForward className="w-5 h-5" />
            </button>

            {/* プログレスバー */}
            <div className="flex-1 bg-gray-200 rounded-full h-2 relative">
              <div
                className="absolute h-full bg-purple-500 rounded-full transition-all"
                style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
              />
            </div>

            {/* 時間表示 */}
            <span className="text-sm text-gray-600 font-mono">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

// 時間フォーマット用ヘルパー関数
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}