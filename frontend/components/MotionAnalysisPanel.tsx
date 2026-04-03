'use client'

import React, { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'

// 動的インポート（Chart.jsのSSR対策）
const AngleTimelineChart = dynamic(() => import('./AngleTimelineChart'), { ssr: false })

console.log('🔴🔴🔴 MOTION ANALYSIS PANEL LOADED - WITH REALTIME BARS 🔴🔴🔴')
console.log('=== MOTION ANALYSIS PANEL DEBUG ===')
console.log('File: MotionAnalysisPanel.tsx')
console.log('Timestamp:', new Date().toISOString())
console.log('Version: 3-PARAMETER-REALTIME-BARS')
console.log('===================================')

interface MotionAnalysisPanelProps {
  analysisData: any
  videoType: string
  currentVideoTime: number
}

interface HandMetrics {
  total_distance: number
  average_speed: number
  max_speed: number
  acceleration: number
  direction_changes: number
  smoothness: number
  path_efficiency: number
}

interface InstrumentMetrics {
  total_distance: number
  average_speed: number
  max_speed: number
  smoothness: number
}

interface Metrics {
  handTechnique: HandMetrics
  instrumentMotion: InstrumentMetrics
}

interface RealtimeMetrics {
  speed: number
  smoothness: number
  accuracy: number
}

const MotionAnalysisPanel: React.FC<MotionAnalysisPanelProps> = ({
  analysisData,
  videoType,
  currentVideoTime
}) => {
  const [metrics, setMetrics] = useState<Metrics>({
    handTechnique: {
      total_distance: 0,
      average_speed: 0,
      max_speed: 0,
      acceleration: 0,
      direction_changes: 0,
      smoothness: 0,
      path_efficiency: 0
    },
    instrumentMotion: {
      total_distance: 0,
      average_speed: 0,
      max_speed: 0,
      smoothness: 0
    }
  })

  const [realtimeMetrics, setRealtimeMetrics] = useState<RealtimeMetrics>({
    speed: 0,
    smoothness: 0,
    accuracy: 0
  })

  const [instrumentRealtimeMetrics, setInstrumentRealtimeMetrics] = useState<RealtimeMetrics>({
    speed: 0,
    smoothness: 0,
    accuracy: 0
  })

  useEffect(() => {
    console.log('[MotionAnalysisPanel] Component mounted', { videoType, showInstrumentMetrics: videoType === 'external_with_instruments' })
  }, [videoType])

  useEffect(() => {
    console.log('[MotionAnalysisPanel] Updating metrics', { currentVideoTime })

    if (analysisData?.skeleton_data) {
      const skeletonData = analysisData.skeleton_data

      // Hand technique metrics calculation
      const handMetrics: HandMetrics = {
        total_distance: skeletonData.total_distance || 0,
        average_speed: skeletonData.average_speed || 0,
        max_speed: skeletonData.max_speed || 0,
        acceleration: skeletonData.average_acceleration || 0,
        direction_changes: skeletonData.direction_changes || 0,
        smoothness: skeletonData.smoothness || 0,
        path_efficiency: skeletonData.path_efficiency || 0
      }

      // Instrument metrics calculation
      let instrumentMetrics: InstrumentMetrics = {
        total_distance: 0,
        average_speed: 0,
        max_speed: 0,
        smoothness: 0
      }

      if (videoType === 'external_with_instruments' && analysisData.instruments_data) {
        instrumentMetrics = {
          total_distance: analysisData.instruments_data.total_distance || 0,
          average_speed: analysisData.instruments_data.average_speed || 0,
          max_speed: analysisData.instruments_data.max_speed || 0,
          smoothness: analysisData.instruments_data.smoothness || 0
        }
      }

      console.log('[MotionAnalysisPanel] New metrics:', { handTechnique: handMetrics, instrumentMotion: instrumentMetrics })
      setMetrics({ handTechnique: handMetrics, instrumentMotion: instrumentMetrics })

      // リアルタイムメトリクス計算（現在のビデオ時間まで）
      calculateRealtimeMetrics(analysisData.skeleton_data, currentVideoTime)

      // 器具のリアルタイムメトリクス計算（器具ありモードのみ）
      if (videoType === 'external_with_instruments' && analysisData.instrument_data) {
        calculateInstrumentRealtimeMetrics(analysisData.instrument_data, currentVideoTime)
      }
    }
  }, [analysisData, currentVideoTime, videoType])

  const calculateRealtimeMetrics = (skeletonData: any[], currentTime: number) => {
    if (!skeletonData || skeletonData.length === 0) return

    // 現在時刻までのデータをフィルタ
    const currentFrameData = skeletonData.filter((frame: any) => {
      const frameTime = frame.timestamp || 0
      return frameTime <= currentTime
    })

    if (currentFrameData.length < 2) {
      setRealtimeMetrics({ speed: 0, smoothness: 0, accuracy: 0 })
      return
    }

    // 手首位置を抽出
    const positions: Array<{ x: number; y: number; timestamp: number } | null> = []
    currentFrameData.forEach((frame: any) => {
      if (frame.hands && frame.hands.length > 0 && frame.hands[0].landmarks && frame.hands[0].landmarks.length > 0) {
        positions.push({
          x: frame.hands[0].landmarks[0].x,
          y: frame.hands[0].landmarks[0].y,
          timestamp: frame.timestamp || 0
        })
      } else {
        positions.push(null)
      }
    })

    const validPositionCount = positions.filter(p => p !== null).length
    console.log('[REALTIME] Valid positions:', validPositionCount, '/', currentFrameData.length)

    if (validPositionCount < 2) {
      setRealtimeMetrics({ speed: 0, smoothness: 0, accuracy: 0 })
      return
    }

    // 速度計算（ピクセル/秒）
    const velocities: number[] = []
    for (let i = 1; i < positions.length; i++) {
      if (positions[i] && positions[i - 1]) {
        const dx = positions[i]!.x - positions[i - 1]!.x
        const dy = positions[i]!.y - positions[i - 1]!.y
        const distance = Math.sqrt(dx * dx + dy * dy)
        const dt = positions[i]!.timestamp - positions[i - 1]!.timestamp
        const velocity = dt > 0 ? distance / dt : 0
        velocities.push(velocity)
      }
    }

    const avgVelocity = velocities.length > 0
      ? velocities.reduce((a, b) => a + b, 0) / velocities.length
      : 0

    // 滑らかさ計算（速度の安定性）
    // 方法: 速度の変動係数 (CV = stdDev / mean) を使用
    const velocityMean = velocities.length > 0
      ? velocities.reduce((a, b) => a + b, 0) / velocities.length
      : 0

    const velocityStdDev = velocities.length > 0
      ? Math.sqrt(velocities.reduce((sum, v) => sum + ((v - velocityMean) ** 2), 0) / velocities.length)
      : 0

    // 変動係数が小さいほど滑らか (CV: 0-10の範囲を想定)
    const velocityCV = velocityMean > 0 ? velocityStdDev / velocityMean : 0

    // CVを0-100スケールに変換（対数スケール）
    // CV=0で100点、CV=1で約69点、CV=5で約38点、CV=10で約10点
    const smoothness = velocityCV > 0
      ? Math.max(0, Math.min(100, 100 * Math.exp(-velocityCV / 3)))
      : 100

    console.log('[REALTIME DEBUG] velocities:', velocities.length, 'velocityMean:', velocityMean.toFixed(2), 'velocityStdDev:', velocityStdDev.toFixed(2), 'velocityCV:', velocityCV.toFixed(4), 'smoothness:', smoothness.toFixed(2))

    // 正確性計算（経路の直線性と無駄のなさ）
    // 方法: 全体の経路効率を使用し、より広い範囲で評価
    const validPositions = positions.filter(p => p !== null) as Array<{ x: number; y: number }>
    let pathEfficiency = 0

    if (validPositions.length >= 2) {
      // 全体の始点から終点までの直線距離
      const start = validPositions[0]
      const end = validPositions[validPositions.length - 1]
      const straightDistance = Math.sqrt(
        (end.x - start.x) ** 2 + (end.y - start.y) ** 2
      )

      // 実際の経路距離
      let actualDistance = 0
      for (let i = 1; i < validPositions.length; i++) {
        const dx = validPositions[i].x - validPositions[i - 1].x
        const dy = validPositions[i].y - validPositions[i - 1].y
        actualDistance += Math.sqrt(dx * dx + dy * dy)
      }

      if (actualDistance > 0.001 && straightDistance > 0.001) {
        // 経路効率（0-1の範囲、1が完全に直線）
        const efficiency = straightDistance / actualDistance

        // スコアリング: 効率をより穏やかに変換（さらに甘く）
        // 効率0.8で100点、0.6で87点、0.4で75点、0.2で63点
        pathEfficiency = Math.max(0, Math.min(100,
          Math.pow(efficiency, 0.3) * 100
        ))

        console.log('[ACCURACY DEBUG] straightDist:', straightDistance.toFixed(2), 'actualDist:', actualDistance.toFixed(2), 'efficiency:', efficiency.toFixed(4), 'score:', pathEfficiency.toFixed(2))
      }
    }

    // スコアに変換（ピクセル/秒を0-100スケールに正規化）
    // 典型的な手技の速度: 100-2000 px/s と仮定
    const speedScore = Math.min(Math.max((avgVelocity / 20), 0), 100)

    console.log('[REALTIME] rawSpeed:', avgVelocity.toFixed(2), 'speed:', speedScore.toFixed(2), 'smoothness:', smoothness.toFixed(2), 'accuracy:', pathEfficiency.toFixed(2))

    setRealtimeMetrics({
      speed: speedScore,
      smoothness: smoothness,
      accuracy: pathEfficiency
    })
  }

  const calculateInstrumentRealtimeMetrics = (instrumentData: any[], currentTime: number) => {
    // instrument_dataは直接フレーム配列
    if (!instrumentData || instrumentData.length === 0) {
      setInstrumentRealtimeMetrics({ speed: 0, smoothness: 0, accuracy: 0 })
      return
    }

    // 現在時刻までのデータをフィルタ
    const currentFrameData = instrumentData.filter((frame: any) => {
      const frameTime = frame.timestamp || 0
      return frameTime <= currentTime
    })

    if (currentFrameData.length < 2) {
      setInstrumentRealtimeMetrics({ speed: 0, smoothness: 0, accuracy: 0 })
      return
    }

    // 器具の中心位置を抽出（複数器具がある場合は最初の器具を使用）
    const positions: Array<{ x: number; y: number; timestamp: number } | null> = []
    currentFrameData.forEach((frame: any) => {
      if (frame.detections && frame.detections.length > 0) {
        const detection = frame.detections[0]
        // centerフィールドを直接使用 [x, y]
        const centerX = detection.center[0]
        const centerY = detection.center[1]
        positions.push({
          x: centerX,
          y: centerY,
          timestamp: frame.timestamp || 0
        })
      } else {
        positions.push(null)
      }
    })

    const validPositionCount = positions.filter(p => p !== null).length

    if (validPositionCount < 2) {
      setInstrumentRealtimeMetrics({ speed: 0, smoothness: 0, accuracy: 0 })
      return
    }

    // 速度計算（ピクセル/秒）
    const velocities: number[] = []
    for (let i = 1; i < positions.length; i++) {
      if (positions[i] && positions[i - 1]) {
        const dx = positions[i]!.x - positions[i - 1]!.x
        const dy = positions[i]!.y - positions[i - 1]!.y
        const distance = Math.sqrt(dx * dx + dy * dy)
        const dt = positions[i]!.timestamp - positions[i - 1]!.timestamp
        const velocity = dt > 0 ? distance / dt : 0
        velocities.push(velocity)
      }
    }

    const avgVelocity = velocities.length > 0
      ? velocities.reduce((a, b) => a + b, 0) / velocities.length
      : 0

    // 滑らかさ計算
    const velocityMean = velocities.length > 0
      ? velocities.reduce((a, b) => a + b, 0) / velocities.length
      : 0

    const velocityStdDev = velocities.length > 0
      ? Math.sqrt(velocities.reduce((sum, v) => sum + ((v - velocityMean) ** 2), 0) / velocities.length)
      : 0

    const velocityCV = velocityMean > 0 ? velocityStdDev / velocityMean : 0
    const smoothness = velocityCV > 0
      ? Math.max(0, Math.min(100, 100 * Math.exp(-velocityCV / 3)))
      : 100

    // 正確性計算（経路効率）
    const validPositions = positions.filter(p => p !== null) as Array<{ x: number; y: number }>
    let pathEfficiency = 0

    if (validPositions.length >= 2) {
      const start = validPositions[0]
      const end = validPositions[validPositions.length - 1]
      const straightDistance = Math.sqrt(
        (end.x - start.x) ** 2 + (end.y - start.y) ** 2
      )

      let actualDistance = 0
      for (let i = 1; i < validPositions.length; i++) {
        const dx = validPositions[i].x - validPositions[i - 1].x
        const dy = validPositions[i].y - validPositions[i - 1].y
        actualDistance += Math.sqrt(dx * dx + dy * dy)
      }

      if (actualDistance > 0.001 && straightDistance > 0.001) {
        const efficiency = straightDistance / actualDistance
        pathEfficiency = Math.max(0, Math.min(100,
          Math.pow(efficiency, 0.3) * 100
        ))
      }
    }

    // 速度スコアを調整：除数を5に減らして感度を上げる
    const speedScore = Math.min(Math.max((avgVelocity / 5), 0), 100)

    console.log('[INSTRUMENT REALTIME] speed:', speedScore.toFixed(2), 'smoothness:', smoothness.toFixed(2), 'accuracy:', pathEfficiency.toFixed(2))

    setInstrumentRealtimeMetrics({
      speed: speedScore,
      smoothness: smoothness,
      accuracy: pathEfficiency
    })
  }

  const showInstrumentMetrics = videoType === 'external_with_instruments'

  // プログレスバーコンポーネント
  const ProgressBar: React.FC<{ value: number; color: string; label: string }> = ({ value, color, label }) => {
    const percentage = Math.min(Math.max(value, 0), 100)

    return (
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-gray-700">{label}</span>
          <span className={`text-lg font-bold ${color}`}>{percentage.toFixed(1)}</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${color.replace('text-', 'bg-')}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    )
  }

  console.log('[MotionAnalysisPanel] Rendering hand technique section')

  return (
    <div className="space-y-4">
      {/* 手技の動き - 3パラメータ（リアルタイムバー表示） */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-4 rounded-lg border border-blue-200">
        <h3 className="text-lg font-bold text-gray-800 mb-3 flex items-center">
          <span className="mr-2">✋</span>
          手技の動き
        </h3>

        <div className="space-y-2">
          <ProgressBar value={realtimeMetrics.speed} color="text-blue-600" label="速度" />
          <ProgressBar value={realtimeMetrics.smoothness} color="text-green-600" label="滑らかさ" />
          <ProgressBar value={realtimeMetrics.accuracy} color="text-purple-600" label="正確性" />
        </div>
      </div>

      {/* 器具の動き - 3パラメータ（リアルタイムバー表示） */}
      {showInstrumentMetrics && (
        <div className="bg-gradient-to-r from-orange-50 to-red-50 p-4 rounded-lg border border-orange-200">
          <h3 className="text-lg font-bold text-gray-800 mb-3 flex items-center">
            <span className="mr-2">🔧</span>
            器具の動き
          </h3>

          <div className="space-y-2">
            <ProgressBar value={instrumentRealtimeMetrics.speed} color="text-orange-600" label="速度" />
            <ProgressBar value={instrumentRealtimeMetrics.smoothness} color="text-green-600" label="滑らかさ" />
            <ProgressBar value={instrumentRealtimeMetrics.accuracy} color="text-purple-600" label="正確性" />
          </div>
        </div>
      )}

      {/* 角度の推移グラフ - 最下部に配置 */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <AngleTimelineChart
          skeletonData={analysisData?.skeleton_data || []}
          instrumentData={analysisData?.instrument_data || []}
          currentVideoTime={currentVideoTime}
          videoType={videoType}
          height={250}
        />
      </div>
    </div>
  )
}

export default MotionAnalysisPanel
