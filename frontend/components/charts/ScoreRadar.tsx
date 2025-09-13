'use client'

import { Radar } from 'react-chartjs-2'
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

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
)

interface ScoreData {
  labels: string[]
  scores: number[]
  maxScore?: number
}

interface ScoreRadarProps {
  scoreData?: ScoreData
  mockData?: boolean
  compareData?: number[] // 比較用データ（熟練医の平均など）
}

export function ScoreRadar({ scoreData, mockData = false, compareData }: ScoreRadarProps) {
  // デフォルトまたはモックデータ
  const defaultData: ScoreData = mockData || !scoreData
    ? {
        labels: ['速度', '精度', '安定性', '効率性', '滑らかさ'],
        scores: [85, 92, 78, 88, 81],
        maxScore: 100,
      }
    : scoreData

  const datasets = [
    {
      label: '今回のスコア',
      data: defaultData.scores,
      backgroundColor: 'rgba(59, 130, 246, 0.2)',
      borderColor: 'rgb(59, 130, 246)',
      borderWidth: 2,
      pointBackgroundColor: 'rgb(59, 130, 246)',
      pointBorderColor: '#fff',
      pointHoverBackgroundColor: '#fff',
      pointHoverBorderColor: 'rgb(59, 130, 246)',
    },
  ]

  // 比較データがある場合は追加
  if (compareData && compareData.length === defaultData.labels.length) {
    datasets.push({
      label: '熟練医平均',
      data: compareData,
      backgroundColor: 'rgba(34, 197, 94, 0.1)',
      borderColor: 'rgb(34, 197, 94)',
      borderWidth: 2,
      pointBackgroundColor: 'rgb(34, 197, 94)',
      pointBorderColor: '#fff',
      pointHoverBackgroundColor: '#fff',
      pointHoverBorderColor: 'rgb(34, 197, 94)',
    })
  }

  const data = {
    labels: defaultData.labels,
    datasets,
  }

  const options: ChartOptions<'radar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'スキル評価レーダーチャート',
        font: {
          size: 16,
        },
      },
    },
    scales: {
      r: {
        angleLines: {
          display: true,
        },
        suggestedMin: 0,
        suggestedMax: defaultData.maxScore || 100,
        ticks: {
          stepSize: 20,
        },
      },
    },
  }

  // 総合スコア計算
  const totalScore = defaultData.scores.reduce((a, b) => a + b, 0) / defaultData.scores.length

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div style={{ height: 350 }}>
        <Radar data={data} options={options} />
      </div>

      <div className="mt-6">
        <div className="text-center mb-4">
          <div className="text-sm text-gray-600">総合スコア</div>
          <div className="text-3xl font-bold text-blue-600">
            {totalScore.toFixed(1)}
            <span className="text-lg text-gray-500">/100</span>
          </div>
        </div>

        <div className="grid grid-cols-5 gap-2">
          {defaultData.labels.map((label, index) => (
            <div key={label} className="text-center p-2 bg-gray-50 rounded-lg">
              <div className="text-xs text-gray-600">{label}</div>
              <div className={`text-lg font-bold ${
                defaultData.scores[index] >= 90
                  ? 'text-green-600'
                  : defaultData.scores[index] >= 80
                  ? 'text-blue-600'
                  : defaultData.scores[index] >= 70
                  ? 'text-yellow-600'
                  : 'text-red-600'
              }`}>
                {defaultData.scores[index]}
              </div>
            </div>
          ))}
        </div>

        {compareData && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg">
            <div className="text-sm text-blue-800">
              <span className="font-semibold">比較結果:</span>
              {totalScore >= compareData.reduce((a, b) => a + b, 0) / compareData.length
                ? ' 熟練医平均を上回っています！'
                : ' もう少しで熟練医レベルです。継続して練習しましょう。'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}