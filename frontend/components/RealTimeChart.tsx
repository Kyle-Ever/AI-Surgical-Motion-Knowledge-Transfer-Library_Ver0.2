'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js'
import { Line } from 'react-chartjs-2'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

interface RealTimeChartProps {
  title: string
  data: {
    timestamps: number[]
    left_hand?: (number | null)[]
    right_hand?: (number | null)[]
  }
  currentTime?: number
  yAxisLabel?: string
  height?: number
}

export default function RealTimeChart({
  title,
  data,
  currentTime = 0,
  yAxisLabel = '値',
  height = 300,
}: RealTimeChartProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const chartRef = useRef<any>(null)

  // 現在時刻に基づいてインデックスを更新
  useEffect(() => {
    if (!data.timestamps || data.timestamps.length === 0) return

    // 現在時刻に最も近いインデックスを見つける
    let closestIndex = 0
    let minDiff = Math.abs(data.timestamps[0] - currentTime)

    for (let i = 1; i < data.timestamps.length; i++) {
      const diff = Math.abs(data.timestamps[i] - currentTime)
      if (diff < minDiff) {
        minDiff = diff
        closestIndex = i
      }
    }

    setCurrentIndex(closestIndex)
  }, [currentTime, data.timestamps])

  // グラフデータの準備
  const chartData = {
    labels: data.timestamps.map(t => t.toFixed(2)),
    datasets: [
      {
        label: '左手',
        data: data.left_hand || [],
        borderColor: 'rgb(0, 170, 255)',
        backgroundColor: 'rgba(0, 170, 255, 0.1)',
        tension: 0.1,
        spanGaps: true,
      },
      {
        label: '右手',
        data: data.right_hand || [],
        borderColor: 'rgb(0, 255, 0)',
        backgroundColor: 'rgba(0, 255, 0, 0.1)',
        tension: 0.1,
        spanGaps: true,
      },
    ],
  }

  // 現在位置にマーカーを追加
  if (currentIndex >= 0 && currentIndex < data.timestamps.length) {
    // 現在位置の縦線
    chartData.datasets.push({
      label: '現在位置',
      data: data.timestamps.map((_, i) => i === currentIndex ? 100000 : null),
      borderColor: 'rgba(255, 0, 0, 0.5)',
      backgroundColor: 'rgba(255, 0, 0, 0.1)',
      pointRadius: 0,
      borderWidth: 2,
      type: 'line' as any,
      yAxisID: 'y1',
    } as any)
  }

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: title,
      },
      tooltip: {
        callbacks: {
          title: (context) => {
            const index = context[0]?.dataIndex
            if (index !== undefined && data.timestamps[index]) {
              return `時刻: ${data.timestamps[index].toFixed(2)}秒`
            }
            return ''
          },
        },
      },
    },
    scales: {
      x: {
        display: true,
        title: {
          display: true,
          text: '時間 (秒)',
        },
        ticks: {
          maxTicksLimit: 10,
        },
      },
      y: {
        display: true,
        title: {
          display: true,
          text: yAxisLabel,
        },
      },
      y1: {
        display: false,
        position: 'right',
        grid: {
          drawOnChartArea: false,
        },
      },
    },
    animation: {
      duration: 0, // アニメーションを無効化（リアルタイム更新のため）
    },
  }

  return (
    <div style={{ height: `${height}px` }}>
      <Line ref={chartRef} data={chartData} options={options} />
    </div>
  )
}