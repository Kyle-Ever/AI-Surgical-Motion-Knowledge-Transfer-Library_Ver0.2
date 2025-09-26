'use client'

import { useMemo } from 'react'
import { TrendingUp, TrendingDown, Activity, Target, Move, Clock } from 'lucide-react'

interface HandLandmark {
  x: number
  y: number
  z: number
}

interface SkeletonFrame {
  frame_number: number
  timestamp: number
  hand_type: string
  landmarks: {
    [key: string]: HandLandmark
  }
}

interface DetailedMetricsTableProps {
  skeletonData: SkeletonFrame[]
}

interface MetricStats {
  mean: number
  std: number
  min: number
  max: number
  range: number
}

interface HandMetrics {
  detectionRate: number
  avgSpeed: MetricStats
  avgAcceleration: MetricStats
  movementRange: {
    x: MetricStats
    y: MetricStats
    z: MetricStats
  }
  jerkiness: number
  pathLength: number
  movementEfficiency: number
  avgFingerFlexion: MetricStats
  tremor: number
  coordinationScore: number
}

// 統計値を計算
function calculateStats(values: number[]): MetricStats {
  if (values.length === 0) {
    return { mean: 0, std: 0, min: 0, max: 0, range: 0 }
  }
  
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length
  const std = Math.sqrt(variance)
  const min = Math.min(...values)
  const max = Math.max(...values)
  
  return {
    mean,
    std,
    min,
    max,
    range: max - min
  }
}

// 両手間の距離を計算
function calculateHandDistance(left: HandLandmark, right: HandLandmark): number {
  return Math.sqrt(
    Math.pow(left.x - right.x, 2) +
    Math.pow(left.y - right.y, 2) +
    Math.pow(left.z - right.z, 2)
  )
}

// 速度を計算
function calculateVelocity(p1: HandLandmark, p2: HandLandmark, dt: number): number {
  if (dt === 0) return 0
  const distance = Math.sqrt(
    Math.pow(p2.x - p1.x, 2) +
    Math.pow(p2.y - p1.y, 2) +
    Math.pow(p2.z - p1.z, 2)
  )
  return distance / dt
}

export default function DetailedMetricsTable({ skeletonData }: DetailedMetricsTableProps) {
  
  // メトリクスの計算
  const metrics = useMemo(() => {
    const leftFrames = skeletonData.filter(f => f.hand_type === 'left')
    const rightFrames = skeletonData.filter(f => f.hand_type === 'right')
    
    const calculateHandMetrics = (frames: SkeletonFrame[]): HandMetrics => {
      // 検出率
      const detectionRate = frames.length > 0 ? frames.length / Math.max(skeletonData.length, 1) : 0
      
      // 手首の位置を取得
      const wristPositions = frames
        .map(f => f.landmarks['point_0'])
        .filter(p => p !== undefined)
      
      // 移動範囲
      const xPositions = wristPositions.map(p => p.x)
      const yPositions = wristPositions.map(p => p.y)
      const zPositions = wristPositions.map(p => p.z)
      
      // 速度計算
      const velocities: number[] = []
      const accelerations: number[] = []
      let pathLength = 0
      
      for (let i = 1; i < frames.length; i++) {
        const dt = frames[i].timestamp - frames[i - 1].timestamp
        const p1 = frames[i - 1].landmarks['point_0']
        const p2 = frames[i].landmarks['point_0']
        
        if (p1 && p2 && dt > 0) {
          const velocity = calculateVelocity(p1, p2, dt)
          velocities.push(velocity)
          
          // 経路長
          pathLength += Math.sqrt(
            Math.pow(p2.x - p1.x, 2) +
            Math.pow(p2.y - p1.y, 2) +
            Math.pow(p2.z - p1.z, 2)
          )
          
          // 加速度
          if (i > 1 && velocities.length >= 2) {
            const acc = Math.abs(velocities[velocities.length - 1] - velocities[velocities.length - 2]) / dt
            accelerations.push(acc)
          }
        }
      }
      
      // ジャーク（加速度の変化率）
      const jerkiness = accelerations.length > 0 
        ? calculateStats(accelerations).std
        : 0
      
      // 効率性（直線距離vs実際の経路）
      let efficiency = 0
      if (frames.length >= 2) {
        const start = frames[0].landmarks['point_0']
        const end = frames[frames.length - 1].landmarks['point_0']
        if (start && end) {
          const directDistance = Math.sqrt(
            Math.pow(end.x - start.x, 2) +
            Math.pow(end.y - start.y, 2) +
            Math.pow(end.z - start.z, 2)
          )
          efficiency = pathLength > 0 ? directDistance / pathLength : 0
        }
      }
      
      // 指の曲げ角度（全指のMCP, PIP, DIP関節）
      const fingerAngles: number[] = []
      frames.forEach(frame => {
        // 人差し指MCP角度の例
        const wrist = frame.landmarks['point_0']
        const indexMCP = frame.landmarks['point_5']
        const indexPIP = frame.landmarks['point_6']
        
        if (wrist && indexMCP && indexPIP) {
          const v1 = {
            x: wrist.x - indexMCP.x,
            y: wrist.y - indexMCP.y,
            z: wrist.z - indexMCP.z,
          }
          const v2 = {
            x: indexPIP.x - indexMCP.x,
            y: indexPIP.y - indexMCP.y,
            z: indexPIP.z - indexMCP.z,
          }
          
          const mag1 = Math.sqrt(v1.x * v1.x + v1.y * v1.y + v1.z * v1.z)
          const mag2 = Math.sqrt(v2.x * v2.x + v2.y * v2.y + v2.z * v2.z)
          
          if (mag1 > 0 && mag2 > 0) {
            const dot = v1.x * v2.x + v1.y * v2.y + v1.z * v2.z
            const angle = Math.acos(Math.max(-1, Math.min(1, dot / (mag1 * mag2))))
            fingerAngles.push((angle * 180) / Math.PI)
          }
        }
      })
      
      // 震え（高周波成分）
      const tremor = velocities.length > 10 
        ? calculateStats(velocities.slice(-10)).std 
        : 0
      
      // 協調性スコア（速度の安定性）
      const coordinationScore = velocities.length > 0
        ? 1 / (1 + calculateStats(velocities).std)
        : 0
      
      return {
        detectionRate,
        avgSpeed: calculateStats(velocities),
        avgAcceleration: calculateStats(accelerations),
        movementRange: {
          x: calculateStats(xPositions),
          y: calculateStats(yPositions),
          z: calculateStats(zPositions),
        },
        jerkiness,
        pathLength,
        movementEfficiency: efficiency,
        avgFingerFlexion: calculateStats(fingerAngles),
        tremor,
        coordinationScore,
      }
    }
    
    const leftMetrics = calculateHandMetrics(leftFrames)
    const rightMetrics = calculateHandMetrics(rightFrames)
    
    // 両手の協調性
    const handDistances: number[] = []
    const syncFrames = leftFrames.filter(lf => 
      rightFrames.some(rf => Math.abs(rf.timestamp - lf.timestamp) < 0.01)
    )
    
    syncFrames.forEach(leftFrame => {
      const rightFrame = rightFrames.find(rf => 
        Math.abs(rf.timestamp - leftFrame.timestamp) < 0.01
      )
      if (rightFrame) {
        const leftWrist = leftFrame.landmarks['point_0']
        const rightWrist = rightFrame.landmarks['point_0']
        if (leftWrist && rightWrist) {
          handDistances.push(calculateHandDistance(leftWrist, rightWrist))
        }
      }
    })
    
    const bimanualCoordination = handDistances.length > 0
      ? calculateStats(handDistances).std
      : 0
    
    return {
      left: leftMetrics,
      right: rightMetrics,
      bimanualCoordination,
      totalFrames: skeletonData.length,
    }
  }, [skeletonData])
  
  const formatValue = (value: number, decimals: number = 2) => {
    return value.toFixed(decimals)
  }
  
  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(1)}%`
  }
  
  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">詳細メトリクス統計</h2>
      
      {/* サマリーカード */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-blue-50 rounded-lg p-3">
          <div className="flex items-center mb-2">
            <Target className="w-4 h-4 text-blue-600 mr-2" />
            <span className="text-sm font-medium text-blue-900">検出率</span>
          </div>
          <div className="text-2xl font-bold text-blue-600">
            L: {formatPercentage(metrics.left.detectionRate)}
          </div>
          <div className="text-xl font-bold text-blue-600">
            R: {formatPercentage(metrics.right.detectionRate)}
          </div>
        </div>
        
        <div className="bg-green-50 rounded-lg p-3">
          <div className="flex items-center mb-2">
            <Activity className="w-4 h-4 text-green-600 mr-2" />
            <span className="text-sm font-medium text-green-900">平均速度</span>
          </div>
          <div className="text-2xl font-bold text-green-600">
            L: {formatValue(metrics.left.avgSpeed.mean, 3)}
          </div>
          <div className="text-xl font-bold text-green-600">
            R: {formatValue(metrics.right.avgSpeed.mean, 3)}
          </div>
        </div>
        
        <div className="bg-purple-50 rounded-lg p-3">
          <div className="flex items-center mb-2">
            <Move className="w-4 h-4 text-purple-600 mr-2" />
            <span className="text-sm font-medium text-purple-900">効率性</span>
          </div>
          <div className="text-2xl font-bold text-purple-600">
            L: {formatPercentage(metrics.left.movementEfficiency)}
          </div>
          <div className="text-xl font-bold text-purple-600">
            R: {formatPercentage(metrics.right.movementEfficiency)}
          </div>
        </div>
        
        <div className="bg-orange-50 rounded-lg p-3">
          <div className="flex items-center mb-2">
            <Clock className="w-4 h-4 text-orange-600 mr-2" />
            <span className="text-sm font-medium text-orange-900">両手協調</span>
          </div>
          <div className="text-2xl font-bold text-orange-600">
            {formatValue(metrics.bimanualCoordination, 3)}
          </div>
          <div className="text-sm text-orange-700">
            （低いほど良い）
          </div>
        </div>
      </div>
      
      {/* 詳細テーブル */}
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="bg-gray-50">
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                メトリクス
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase tracking-wider">
                左手
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase tracking-wider">
                右手
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase tracking-wider">
                差異
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {/* 速度統計 */}
            <tr>
              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                速度 (平均 ± 標準偏差)
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.left.avgSpeed.mean, 3)} ± {formatValue(metrics.left.avgSpeed.std, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.right.avgSpeed.mean, 3)} ± {formatValue(metrics.right.avgSpeed.std, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center">
                <span className={`inline-flex items-center ${
                  Math.abs(metrics.left.avgSpeed.mean - metrics.right.avgSpeed.mean) > 0.05
                    ? 'text-red-600' : 'text-green-600'
                }`}>
                  {Math.abs(metrics.left.avgSpeed.mean - metrics.right.avgSpeed.mean) > 0.05
                    ? <TrendingUp className="w-4 h-4 mr-1" />
                    : <TrendingDown className="w-4 h-4 mr-1" />
                  }
                  {formatValue(Math.abs(metrics.left.avgSpeed.mean - metrics.right.avgSpeed.mean), 3)}
                </span>
              </td>
            </tr>
            
            {/* 加速度 */}
            <tr>
              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                加速度 (平均)
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.left.avgAcceleration.mean, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.right.avgAcceleration.mean, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(Math.abs(metrics.left.avgAcceleration.mean - metrics.right.avgAcceleration.mean), 3)}
              </td>
            </tr>
            
            {/* ジャーク */}
            <tr>
              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                ジャークネス (低いほど滑らか)
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.left.jerkiness, 4)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.right.jerkiness, 4)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(Math.abs(metrics.left.jerkiness - metrics.right.jerkiness), 4)}
              </td>
            </tr>
            
            {/* 移動範囲 X */}
            <tr>
              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                X軸移動範囲
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.left.movementRange.x.range, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.right.movementRange.x.range, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(Math.abs(metrics.left.movementRange.x.range - metrics.right.movementRange.x.range), 3)}
              </td>
            </tr>
            
            {/* 移動範囲 Y */}
            <tr>
              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                Y軸移動範囲
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.left.movementRange.y.range, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.right.movementRange.y.range, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(Math.abs(metrics.left.movementRange.y.range - metrics.right.movementRange.y.range), 3)}
              </td>
            </tr>
            
            {/* 経路長 */}
            <tr>
              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                総移動距離
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.left.pathLength, 2)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.right.pathLength, 2)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(Math.abs(metrics.left.pathLength - metrics.right.pathLength), 2)}
              </td>
            </tr>
            
            {/* 震え */}
            <tr>
              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                震え指标
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.left.tremor, 4)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.right.tremor, 4)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(Math.abs(metrics.left.tremor - metrics.right.tremor), 4)}
              </td>
            </tr>
            
            {/* 協調性 */}
            <tr>
              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                協調性スコア
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.left.coordinationScore, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(metrics.right.coordinationScore, 3)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-sm text-center text-gray-700">
                {formatValue(Math.abs(metrics.left.coordinationScore - metrics.right.coordinationScore), 3)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      {/* 凡例 */}
      <div className="mt-4 text-xs text-gray-500">
        <p>※ 値は正規化された座標系で計算されています</p>
        <p>※ ジャークネスと震え指標は低いほど滑らかな動きを示します</p>
        <p>※ 効率性は直線距離/実際の経路長で、100%に近いほど効率的な動きです</p>
      </div>
    </div>
  )
}