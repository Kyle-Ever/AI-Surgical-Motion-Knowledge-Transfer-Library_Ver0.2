'use client'

import { useEffect, useState } from 'react'
import { MotionChart } from './MotionChart'

interface VelocityData {
  frames: number[]
  velocities: number[]
  avgVelocity: number
  maxVelocity: number
}

interface VelocityChartProps {
  analysisData?: any
  mockData?: boolean
}

export function VelocityChart({ analysisData, mockData = false }: VelocityChartProps) {
  const [velocityData, setVelocityData] = useState<VelocityData | null>(null)

  useEffect(() => {
    if (mockData || !analysisData) {
      // モックデータ生成
      const frames = Array.from({ length: 100 }, (_, i) => i)
      const velocities = frames.map(f => {
        const base = 10
        const noise = Math.sin(f * 0.1) * 3
        const spike = f % 20 === 0 ? Math.random() * 10 : 0
        return Math.max(0, base + noise + spike + Math.random() * 2)
      })

      setVelocityData({
        frames,
        velocities,
        avgVelocity: velocities.reduce((a, b) => a + b, 0) / velocities.length,
        maxVelocity: Math.max(...velocities),
      })
    } else if (analysisData?.motion_analysis) {
      // 実データから速度データを抽出
      const velocityInfo = analysisData.motion_analysis['速度解析'] || {}
      const frames = analysisData.coordinate_data?.map((_, i: number) => i) || []

      // 座標データから速度を計算
      let velocities: number[] = []
      if (analysisData.coordinate_data && analysisData.coordinate_data.length > 1) {
        for (let i = 1; i < analysisData.coordinate_data.length; i++) {
          const prev = analysisData.coordinate_data[i - 1]
          const curr = analysisData.coordinate_data[i]
          const dx = curr.x - prev.x
          const dy = curr.y - prev.y
          const velocity = Math.sqrt(dx * dx + dy * dy)
          velocities.push(velocity)
        }
      } else {
        // データがない場合はモック
        velocities = frames.map(() => Math.random() * 20)
      }

      setVelocityData({
        frames,
        velocities,
        avgVelocity: velocityInfo.avg_velocity || 10,
        maxVelocity: velocityInfo.max_velocity || 25,
      })
    }
  }, [analysisData, mockData])

  if (!velocityData) {
    return <div className="p-4 text-gray-500">データ読み込み中...</div>
  }

  const chartData = {
    labels: velocityData.frames.map(f => f.toString()),
    datasets: [
      {
        label: '速度',
        data: velocityData.velocities,
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.3,
      },
      {
        label: '平均速度',
        data: velocityData.frames.map(() => velocityData.avgVelocity),
        borderColor: 'rgb(34, 197, 94)',
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        borderDash: [5, 5],
      },
      {
        label: '最大速度',
        data: velocityData.frames.map(() => velocityData.maxVelocity),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderDash: [10, 5],
      },
    ],
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <MotionChart
        data={chartData}
        title="動作速度の推移"
        yAxisLabel="速度 (px/frame)"
        height={300}
      />

      <div className="mt-4 grid grid-cols-3 gap-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">平均速度</div>
          <div className="text-xl font-bold text-green-600">
            {velocityData.avgVelocity.toFixed(1)} px/f
          </div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">最大速度</div>
          <div className="text-xl font-bold text-red-600">
            {velocityData.maxVelocity.toFixed(1)} px/f
          </div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">変動係数</div>
          <div className="text-xl font-bold text-blue-600">
            {((Math.sqrt(velocityData.velocities.reduce((sum, v) =>
              sum + Math.pow(v - velocityData.avgVelocity, 2), 0
            ) / velocityData.velocities.length) / velocityData.avgVelocity) * 100).toFixed(1)}%
          </div>
        </div>
      </div>
    </div>
  )
}