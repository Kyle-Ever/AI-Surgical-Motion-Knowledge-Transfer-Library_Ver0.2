'use client'

import { useMemo } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartOptions,
} from 'chart.js'
import { Line } from 'react-chartjs-2'

// Chart.jsの登録
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

interface AngleTimelineChartProps {
  skeletonData: any[]
  instrumentData?: any[]
  currentVideoTime: number
  videoType?: string
  className?: string
  height?: number
}

// MediaPipeランドマークインデックス
const LANDMARKS = {
  WRIST: 0,
  MIDDLE_MCP: 9,  // 中指の付け根
}

/**
 * 手の角度を計算（手首から中指MCPへのベクトルの角度）
 * @returns 0-360度の角度
 */
function calculateHandAngle(landmarks: any[]): number | null {
  if (!landmarks || landmarks.length < 10) return null

  const wrist = landmarks[LANDMARKS.WRIST]
  const middleMcp = landmarks[LANDMARKS.MIDDLE_MCP]

  if (!wrist || !middleMcp) return null

  const dx = middleMcp.x - wrist.x
  const dy = middleMcp.y - wrist.y

  // atan2で角度計算 (-180 ~ 180度)
  let angle = Math.atan2(dy, dx) * (180 / Math.PI)

  // 0-360度に正規化
  if (angle < 0) angle += 360

  return angle
}

/**
 * 器具の角度を計算（バウンディングボックスの対角線の傾き）
 * @returns 0-180度の角度
 */
function calculateInstrumentAngle(bbox: number[]): number | null {
  if (!bbox || bbox.length < 4) return null

  const [x1, y1, x2, y2] = bbox
  const dx = x2 - x1
  const dy = y2 - y1

  // 対角線の角度を計算
  let angle = Math.atan2(dy, dx) * (180 / Math.PI)

  // 0-180度に正規化
  if (angle < 0) angle += 180

  return angle
}

export default function AngleTimelineChart({
  skeletonData,
  instrumentData,
  currentVideoTime,
  videoType,
  className = '',
  height = 250
}: AngleTimelineChartProps) {

  // 器具を表示するかどうか
  const showInstrument = videoType === 'external_with_instruments' || videoType === 'internal'

  // 角度データを計算
  const angleData = useMemo(() => {
    if (!skeletonData || skeletonData.length === 0) {
      return { timestamps: [], leftHand: [], rightHand: [], instrument: [] }
    }

    const timestamps: number[] = []
    const leftHand: (number | null)[] = []
    const rightHand: (number | null)[] = []
    const instrument: (number | null)[] = []

    // 骨格データから角度を計算
    skeletonData.forEach((frame) => {
      const timestamp = frame.timestamp || frame.frame_number / 30 // フレーム番号から秒数を推定

      timestamps.push(timestamp)

      // 左手と右手の角度を計算
      let leftAngle: number | null = null
      let rightAngle: number | null = null

      if (frame.hands && Array.isArray(frame.hands)) {
        frame.hands.forEach((hand: any) => {
          if (hand.hand_type === 'Left' && hand.landmarks) {
            leftAngle = calculateHandAngle(hand.landmarks)
          } else if (hand.hand_type === 'Right' && hand.landmarks) {
            rightAngle = calculateHandAngle(hand.landmarks)
          }
        })
      }

      leftHand.push(leftAngle)
      rightHand.push(rightAngle)

      // 器具の角度を計算（該当フレームのデータがあれば）
      if (showInstrument && instrumentData) {
        const instrumentFrame = instrumentData.find(
          (inst: any) => inst.frame_number === frame.frame_number
        )

        if (instrumentFrame && instrumentFrame.detections && instrumentFrame.detections.length > 0) {
          // 最初の器具の角度を使用
          const firstInstrument = instrumentFrame.detections[0]
          instrument.push(calculateInstrumentAngle(firstInstrument.bbox))
        } else {
          instrument.push(null)
        }
      }
    })

    console.log('[AngleTimelineChart] Calculated angles:', {
      totalFrames: timestamps.length,
      leftHandPoints: leftHand.filter(v => v !== null).length,
      rightHandPoints: rightHand.filter(v => v !== null).length,
      instrumentPoints: instrument.filter(v => v !== null).length
    })

    return { timestamps, leftHand, rightHand, instrument }
  }, [skeletonData, instrumentData, showInstrument])

  // 現在時刻のインデックスを計算
  const currentIndex = useMemo(() => {
    if (angleData.timestamps.length === 0) return -1

    let closestIndex = 0
    let minDiff = Math.abs(angleData.timestamps[0] - currentVideoTime)

    for (let i = 1; i < angleData.timestamps.length; i++) {
      const diff = Math.abs(angleData.timestamps[i] - currentVideoTime)
      if (diff < minDiff) {
        minDiff = diff
        closestIndex = i
      }
    }

    return closestIndex
  }, [angleData.timestamps, currentVideoTime])

  // Chart.jsのデータセット（現在時刻までのデータのみ表示）
  const chartData = useMemo(() => {
    // 現在時刻までのデータをフィルタリング
    const currentDataIndex = currentIndex >= 0 ? currentIndex : 0

    // 現在時刻までのデータを抽出
    const visibleLeftHand = angleData.leftHand.slice(0, currentDataIndex + 1)
    const visibleRightHand = angleData.rightHand.slice(0, currentDataIndex + 1)
    const visibleInstrument = angleData.instrument.slice(0, currentDataIndex + 1)

    // 残りの部分はnullで埋める（グラフの幅を保つため）
    const remainingCount = angleData.timestamps.length - (currentDataIndex + 1)
    const nullArray = new Array(remainingCount).fill(null)

    const datasets: any[] = [
      {
        label: '左手',
        data: [...visibleLeftHand, ...nullArray],
        borderColor: 'rgb(59, 130, 246)', // blue-500
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.3,
        spanGaps: false,  // 現在位置以降は描画しない
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
      },
      {
        label: '右手',
        data: [...visibleRightHand, ...nullArray],
        borderColor: 'rgb(34, 197, 94)', // green-500
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        tension: 0.3,
        spanGaps: false,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
      },
    ]

    // 器具データを追加（条件付き）
    if (showInstrument && angleData.instrument.some(v => v !== null)) {
      datasets.push({
        label: '器具',
        data: [...visibleInstrument, ...nullArray],
        borderColor: 'rgb(239, 68, 68)', // red-500
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        tension: 0.3,
        spanGaps: false,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
      })
    }

    return {
      labels: angleData.timestamps.map(t => t.toFixed(1)),
      datasets
    }
  }, [angleData, showInstrument, currentIndex])

  // Chart.jsのオプション
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
        labels: {
          usePointStyle: true,
          padding: 10,
          font: {
            size: 11
          }
        }
      },
      title: {
        display: false  // 外側にタイトルを配置するため無効化
      },
      tooltip: {
        callbacks: {
          title: (context) => {
            const index = context[0]?.dataIndex
            if (index !== undefined && angleData.timestamps[index]) {
              return `時刻: ${angleData.timestamps[index].toFixed(2)}秒`
            }
            return ''
          },
          label: (context) => {
            const label = context.dataset.label || ''
            const value = context.parsed.y
            return value !== null ? `${label}: ${value.toFixed(1)}°` : `${label}: -`
          }
        }
      }
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
        grid: {
          display: true,
          color: 'rgba(0, 0, 0, 0.05)'
        }
      },
      y: {
        display: true,
        title: {
          display: true,
          text: '角度 (度)',
        },
        min: 0,
        max: 360,
        ticks: {
          stepSize: 60,
        },
        grid: {
          display: true,
          color: 'rgba(0, 0, 0, 0.05)'
        }
      },
    },
    animation: {
      duration: 0, // リアルタイム更新のためアニメーション無効
    },
  }

  // データがない場合の表示
  if (!skeletonData || skeletonData.length === 0) {
    return (
      <div className={className}>
        <h4 className="text-xs font-semibold text-gray-600 uppercase mb-3">角度の推移</h4>
        <div className="bg-gray-50 rounded-lg p-6">
          <div className="text-center text-gray-500 text-sm">
            角度データがありません
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={className}>
      {/* タイトル - 手技の動き分析と同じスタイル */}
      <h4 className="text-xs font-semibold text-gray-600 uppercase mb-3">角度の推移</h4>

      <div className="bg-white rounded-lg border border-gray-200" style={{ height: `${height}px`, padding: '16px' }}>
        <Line data={chartData} options={options} />
      </div>
    </div>
  )
}
