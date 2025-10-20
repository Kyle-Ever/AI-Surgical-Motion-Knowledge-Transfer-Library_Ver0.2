'use client'

import { useState, useEffect } from 'react'
import { Activity, TrendingUp, Target, Timer } from 'lucide-react'
import dynamic from 'next/dynamic'

// 動的インポート（Chart.jsのSSR対策）
const AngleTimelineChart = dynamic(() => import('./AngleTimelineChart'), { ssr: false })

interface MotionAnalysisPanelProps {
  analysisData: any
  currentVideoTime: number
  videoType?: string  // 'external_no_instruments' | 'external_with_instruments' | 'internal'
  className?: string
}

interface MotionMetrics {
  handTechnique: {
    speed: number
    smoothness: number
    precision: number
    coordination: number
  }
  instrumentMotion: {
    stability: number
    efficiency: number
    accuracy: number
    control: number
  }
}

export default function MotionAnalysisPanel({
  analysisData,
  currentVideoTime,
  videoType,
  className = ''
}: MotionAnalysisPanelProps) {
  const [currentMetrics, setCurrentMetrics] = useState<MotionMetrics>({
    handTechnique: {
      speed: 15,
      smoothness: 80,
      precision: 85,
      coordination: 82
    },
    instrumentMotion: {
      stability: 88,
      efficiency: 78,
      accuracy: 90,
      control: 85
    }
  })

  // 器具の動きセクションを表示するかどうか
  const showInstrumentMetrics =
    videoType === 'external_with_instruments' ||
    videoType === 'internal'

  // 🔍 デバッグ: コンポーネント初期化
  useEffect(() => {
    console.log('[MotionAnalysisPanel] Component mounted', {
      videoType,
      showInstrumentMetrics
    })
  }, [videoType, showInstrumentMetrics])

  // 🔍 デバッグ: メトリクス更新（モックデータ使用）
  useEffect(() => {
    console.log('[MotionAnalysisPanel] Updating metrics', { currentVideoTime })

    // 🎨 モックデータ生成: より大きな変動でリアルな動きを再現
    // TODO: 実データ対応時は skeleton_data から計算
    const time = currentVideoTime

    // ランダム要素を追加（より自然な変動）
    const randomFactor1 = Math.sin(time * 1.7) * Math.cos(time * 0.9)
    const randomFactor2 = Math.cos(time * 2.3) * Math.sin(time * 1.1)
    const randomFactor3 = Math.sin(time * 1.5) * Math.cos(time * 1.9)

    const newMetrics: MotionMetrics = {
      handTechnique: {
        // 速度: 5-35 cm/s (大きな振幅)
        speed: 20 + Math.sin(time * 0.8) * 12 + randomFactor1 * 3,
        // 滑らかさ: 60-95% (中程度の変動)
        smoothness: 77.5 + Math.cos(time * 0.6) * 15 + randomFactor2 * 2.5,
        // 精密度: 65-98% (大きな変動)
        precision: 81.5 + Math.sin(time * 0.9) * 16.5 + randomFactor3 * 3,
        // 協調性: 55-95% (非常に大きな変動)
        coordination: 75 + Math.cos(time * 0.7) * 18 + randomFactor1 * 2
      },
      instrumentMotion: {
        // 安定性: 70-100% (中程度の変動)
        stability: 85 + Math.sin(time * 0.5) * 13 + randomFactor2 * 2,
        // 効率性: 50-95% (大きな変動)
        efficiency: 72.5 + Math.cos(time * 0.85) * 20 + randomFactor3 * 2.5,
        // 正確性: 75-100% (中程度の変動)
        accuracy: 87.5 + Math.sin(time * 0.65) * 11 + randomFactor1 * 1.5,
        // 制御性: 60-100% (大きな変動)
        control: 80 + Math.cos(time * 0.75) * 18 + randomFactor2 * 2
      }
    }

    console.log('[MotionAnalysisPanel] New metrics:', newMetrics)
    setCurrentMetrics(newMetrics)
  }, [currentVideoTime])

  // メトリクスバーコンポーネント
  const MetricBar = ({ label, value, unit, icon: Icon, color }: any) => (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1 text-gray-600">
          <Icon className="w-3 h-3" />
          {label}
        </span>
        <span className="font-medium text-gray-900">
          {value.toFixed(1)} {unit}
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`${color} h-2 rounded-full transition-all duration-300`}
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  )

  return (
    <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-500" />
          手技の動き分析
        </h2>
      </div>

      <div className={`grid ${showInstrumentMetrics ? 'grid-cols-2' : 'grid-cols-1'} gap-4`}>
        {/* 手技の動き */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-gray-600 uppercase">手技の動き</h4>
          <MetricBar
            label="速度"
            value={currentMetrics.handTechnique.speed}
            unit="cm/s"
            icon={TrendingUp}
            color="bg-blue-500"
          />
          <MetricBar
            label="滑らかさ"
            value={currentMetrics.handTechnique.smoothness}
            unit="%"
            icon={Activity}
            color="bg-green-500"
          />
          <MetricBar
            label="精密度"
            value={currentMetrics.handTechnique.precision}
            unit="%"
            icon={Target}
            color="bg-purple-500"
          />
          <MetricBar
            label="協調性"
            value={currentMetrics.handTechnique.coordination}
            unit="%"
            icon={Timer}
            color="bg-orange-500"
          />
        </div>

        {/* 器具の動き - 条件付き表示 */}
        {showInstrumentMetrics && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-gray-600 uppercase">器具の動き</h4>
            <MetricBar
              label="安定性"
              value={currentMetrics.instrumentMotion.stability}
              unit="%"
              icon={Target}
              color="bg-indigo-500"
            />
            <MetricBar
              label="効率性"
              value={currentMetrics.instrumentMotion.efficiency}
              unit="%"
              icon={TrendingUp}
              color="bg-cyan-500"
            />
            <MetricBar
              label="正確性"
              value={currentMetrics.instrumentMotion.accuracy}
              unit="%"
              icon={Activity}
              color="bg-pink-500"
            />
            <MetricBar
              label="制御性"
              value={currentMetrics.instrumentMotion.control}
              unit="%"
              icon={Timer}
              color="bg-amber-500"
            />
          </div>
        )}
      </div>

      {/* 角度の推移グラフ */}
      <div className="mt-6 space-y-2">
        <AngleTimelineChart
          skeletonData={analysisData?.skeleton_data || []}
          instrumentData={analysisData?.instrument_data}
          currentVideoTime={currentVideoTime}
          videoType={videoType}
        />
      </div>

      {/* デバッグ情報 */}
      <div className="mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
        現在時刻: {currentVideoTime.toFixed(2)}s
      </div>
    </div>
  )
}
