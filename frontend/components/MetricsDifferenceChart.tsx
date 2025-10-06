'use client'

import { useEffect, useRef, useState } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

interface MetricsDifferenceChartProps {
  comparisonData?: any
  currentTime?: number
}

export default function MetricsDifferenceChart({
  comparisonData,
  currentTime = 0
}: MetricsDifferenceChartProps) {
  const [chartData, setChartData] = useState<any>(null)
  const [currentMetrics, setCurrentMetrics] = useState({
    speedDiff: 0,
    smoothnessDiff: 0,
    stabilityDiff: 0,
    trajectoryDeviation: 0
  })

  // チャートデータの準備
  useEffect(() => {
    if (!comparisonData) {
      // モックデータを使用
      setChartData({
        labels: ['0:00', '0:30', '1:00', '1:30', '2:00', '2:30', '3:00', '3:30', '4:00'],
        datasets: [
          {
            label: '速度差',
            data: [0, -5, -8, -15, -12, -8, -3, 2, 0],
            borderColor: 'rgb(59, 130, 246)',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.4,
            fill: true
          },
          {
            label: '滑らかさ差',
            data: [0, 2, -1, -5, -8, -3, 1, 3, 2],
            borderColor: 'rgb(34, 197, 94)',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            tension: 0.4,
            fill: true
          },
          {
            label: '安定性差',
            data: [0, -3, -7, -10, -6, -4, -2, 0, 1],
            borderColor: 'rgb(234, 179, 8)',
            backgroundColor: 'rgba(234, 179, 8, 0.1)',
            tension: 0.4,
            fill: true
          }
        ]
      })
    } else {
      // 実際のデータから変換
      processComparisonData(comparisonData)
    }
  }, [comparisonData])

  // 現在時刻のメトリクスを更新
  useEffect(() => {
    if (currentTime !== undefined) {
      updateCurrentMetrics(currentTime)
    }
  }, [currentTime])

  const processComparisonData = (data: any) => {
    // APIから取得したデータを処理してグラフ用データに変換
    // TODO: 実際のデータ構造に合わせて実装
    const mockProcessedData = {
      labels: generateTimeLabels(300), // 5分間のラベル
      datasets: [
        {
          label: '速度差',
          data: generateMockDifferences(9),
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          tension: 0.4,
          fill: true
        },
        {
          label: '滑らかさ差',
          data: generateMockDifferences(9),
          borderColor: 'rgb(34, 197, 94)',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          tension: 0.4,
          fill: true
        }
      ]
    }
    setChartData(mockProcessedData)
  }

  const generateTimeLabels = (seconds: number): string[] => {
    const labels = []
    for (let i = 0; i <= seconds; i += 30) {
      const mins = Math.floor(i / 60)
      const secs = i % 60
      labels.push(`${mins}:${secs.toString().padStart(2, '0')}`)
    }
    return labels
  }

  const generateMockDifferences = (count: number): number[] => {
    const data = []
    for (let i = 0; i < count; i++) {
      data.push(Math.sin(i * 0.5) * 10 + Math.random() * 5 - 2.5)
    }
    return data
  }

  const updateCurrentMetrics = (time: number) => {
    // 現在時刻に基づいてメトリクスを更新
    setCurrentMetrics({
      speedDiff: Math.sin(time * 0.1) * 15,
      smoothnessDiff: Math.cos(time * 0.08) * 10,
      stabilityDiff: Math.sin(time * 0.12) * 8,
      trajectoryDeviation: Math.abs(Math.sin(time * 0.05)) * 12
    })
  }

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          boxWidth: 15,
          padding: 10,
          font: {
            size: 11
          }
        }
      },
      tooltip: {
        mode: 'index' as const,
        intersect: false,
      }
    },
    scales: {
      y: {
        beginAtZero: false,
        grid: {
          color: 'rgba(0, 0, 0, 0.05)'
        },
        title: {
          display: true,
          text: '基準との差',
          font: {
            size: 11
          }
        }
      },
      x: {
        grid: {
          color: 'rgba(0, 0, 0, 0.05)'
        }
      }
    },
    interaction: {
      intersect: false,
      mode: 'index' as const
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h3 className="font-semibold mb-4 flex items-center">
        リアルタイム差分メトリクス
        <span className="ml-2 text-xs bg-green-100 text-green-800 px-2 py-1 rounded">LIVE</span>
      </h3>

      {/* グラフとメトリクスを横並びに配置 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* グラフエリア（2/3幅） */}
        <div className="lg:col-span-2">
          <div style={{ height: '250px' }}>
            {chartData && <Line data={chartData} options={chartOptions} />}
          </div>
        </div>

        {/* 現在値表示エリア（1/3幅） */}
        <div className="space-y-3">
          <div className="bg-gray-50 p-3 rounded">
            <div className="text-xs text-gray-600 mb-1">速度差</div>
            <div className="font-semibold text-xl">
              {currentMetrics.speedDiff.toFixed(1)} mm/s
            </div>
            <div className={`text-xs mt-1 ${currentMetrics.speedDiff < 0 ? 'text-red-600' : 'text-green-600'}`}>
              {currentMetrics.speedDiff < 0 ? '基準より遅い' : '基準より速い'}
            </div>
          </div>

          <div className="bg-gray-50 p-3 rounded">
            <div className="text-xs text-gray-600 mb-1">軌跡のズレ</div>
            <div className="font-semibold text-xl">
              {currentMetrics.trajectoryDeviation.toFixed(1)} mm
            </div>
            <div className={`text-xs mt-1 ${currentMetrics.trajectoryDeviation > 10 ? 'text-red-600' : 'text-green-600'}`}>
              {currentMetrics.trajectoryDeviation > 10 ? '要改善' : '良好'}
            </div>
          </div>

          <div className="bg-gray-50 p-3 rounded">
            <div className="text-xs text-gray-600 mb-1">滑らかさ差</div>
            <div className="font-semibold text-xl">
              {Math.abs(currentMetrics.smoothnessDiff).toFixed(1)}%
            </div>
            <div className={`text-xs mt-1 ${Math.abs(currentMetrics.smoothnessDiff) > 15 ? 'text-yellow-600' : 'text-green-600'}`}>
              {Math.abs(currentMetrics.smoothnessDiff) > 15 ? '差が大きい' : '適切'}
            </div>
          </div>
        </div>
      </div>

      {/* タイムライン上の重要ポイント */}
      <div className="mt-4 pt-4 border-t">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-600">解析時間: {formatTime(currentTime)}</span>
          <div className="flex gap-4">
            <span className="flex items-center">
              <span className="w-2 h-2 bg-red-500 rounded-full mr-1"></span>
              要改善区間
            </span>
            <span className="flex items-center">
              <span className="w-2 h-2 bg-yellow-500 rounded-full mr-1"></span>
              注意区間
            </span>
            <span className="flex items-center">
              <span className="w-2 h-2 bg-green-500 rounded-full mr-1"></span>
              良好区間
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}