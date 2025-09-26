'use client'

import { useEffect, useRef } from 'react'
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js'
import { Radar } from 'react-chartjs-2'

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
)

interface ScoreRadarChartProps {
  learnerScores: {
    speed: number
    smoothness: number
    stability: number
    efficiency: number
  }
  referenceScores?: {
    speed: number
    smoothness: number
    stability: number
    efficiency: number
  }
  className?: string
}

export default function ScoreRadarChart({
  learnerScores,
  referenceScores,
  className = ''
}: ScoreRadarChartProps) {
  const chartRef = useRef<any>(null)

  const data = {
    labels: ['速度', '滑らかさ', '安定性', '効率性'],
    datasets: [
      {
        label: 'あなたのスコア',
        data: [
          learnerScores.speed || 0,
          learnerScores.smoothness || 0,
          learnerScores.stability || 0,
          learnerScores.efficiency || 0,
        ],
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        borderWidth: 2,
        pointBackgroundColor: 'rgb(59, 130, 246)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgb(59, 130, 246)',
      },
    ],
  }

  // 基準スコアがある場合は追加
  if (referenceScores) {
    data.datasets.push({
      label: '基準スコア',
      data: [
        referenceScores.speed || 0,
        referenceScores.smoothness || 0,
        referenceScores.stability || 0,
        referenceScores.efficiency || 0,
      ],
      borderColor: 'rgb(156, 163, 175)',
      backgroundColor: 'rgba(156, 163, 175, 0.1)',
      borderWidth: 2,
      borderDash: [5, 5],
      pointBackgroundColor: 'rgb(156, 163, 175)',
      pointBorderColor: '#fff',
      pointHoverBackgroundColor: '#fff',
      pointHoverBorderColor: 'rgb(156, 163, 175)',
    })
  }

  const options: ChartOptions<'radar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          font: {
            size: 11,
          },
        },
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            return context.dataset.label + ': ' + context.raw + '点'
          },
        },
      },
    },
    scales: {
      r: {
        beginAtZero: true,
        max: 100,
        ticks: {
          stepSize: 20,
          font: {
            size: 10,
          },
        },
        pointLabels: {
          font: {
            size: 12,
          },
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
      },
    },
  }

  return (
    <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
      <h3 className="text-lg font-semibold mb-4">スコア分布</h3>
      <div style={{ height: '300px' }}>
        <Radar ref={chartRef} data={data} options={options} />
      </div>

      {/* スコアレジェンド */}
      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="flex items-center mb-1">
            <div className="w-3 h-3 bg-blue-500 rounded-full mr-2"></div>
            <span className="font-medium">速度</span>
          </div>
          <div className="text-gray-600 ml-5">
            {learnerScores.speed || 0}点
          </div>
        </div>
        <div>
          <div className="flex items-center mb-1">
            <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
            <span className="font-medium">滑らかさ</span>
          </div>
          <div className="text-gray-600 ml-5">
            {learnerScores.smoothness || 0}点
          </div>
        </div>
        <div>
          <div className="flex items-center mb-1">
            <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div>
            <span className="font-medium">安定性</span>
          </div>
          <div className="text-gray-600 ml-5">
            {learnerScores.stability || 0}点
          </div>
        </div>
        <div>
          <div className="flex items-center mb-1">
            <div className="w-3 h-3 bg-purple-500 rounded-full mr-2"></div>
            <span className="font-medium">効率性</span>
          </div>
          <div className="text-gray-600 ml-5">
            {learnerScores.efficiency || 0}点
          </div>
        </div>
      </div>
    </div>
  )
}