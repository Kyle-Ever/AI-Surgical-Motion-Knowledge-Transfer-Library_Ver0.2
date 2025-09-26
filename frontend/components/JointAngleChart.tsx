'use client'

import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Brush } from 'recharts'

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

interface JointAngleChartProps {
  skeletonData: SkeletonFrame[]
  selectedFinger?: 'thumb' | 'index' | 'middle' | 'ring' | 'pinky'
  currentTime?: number
}

// MediaPipeランドマークインデックス
const LANDMARKS = {
  WRIST: 0,
  THUMB_CMC: 1,
  THUMB_MCP: 2,
  THUMB_IP: 3,
  THUMB_TIP: 4,
  INDEX_MCP: 5,
  INDEX_PIP: 6,
  INDEX_DIP: 7,
  INDEX_TIP: 8,
  MIDDLE_MCP: 9,
  MIDDLE_PIP: 10,
  MIDDLE_DIP: 11,
  MIDDLE_TIP: 12,
  RING_MCP: 13,
  RING_PIP: 14,
  RING_DIP: 15,
  RING_TIP: 16,
  PINKY_MCP: 17,
  PINKY_PIP: 18,
  PINKY_DIP: 19,
  PINKY_TIP: 20,
}

// 3点から角度を計算（度数）
function calculateAngle(p1: HandLandmark, p2: HandLandmark, p3: HandLandmark): number {
  const v1 = {
    x: p1.x - p2.x,
    y: p1.y - p2.y,
    z: p1.z - p2.z,
  }
  const v2 = {
    x: p3.x - p2.x,
    y: p3.y - p2.y,
    z: p3.z - p2.z,
  }

  const mag1 = Math.sqrt(v1.x * v1.x + v1.y * v1.y + v1.z * v1.z)
  const mag2 = Math.sqrt(v2.x * v2.x + v2.y * v2.y + v2.z * v2.z)

  if (mag1 === 0 || mag2 === 0) return 0

  const dot = v1.x * v2.x + v1.y * v2.y + v1.z * v2.z
  const cosAngle = dot / (mag1 * mag2)
  const angleRad = Math.acos(Math.max(-1, Math.min(1, cosAngle)))

  return (angleRad * 180) / Math.PI
}

// ランドマークを取得
function getLandmark(landmarks: any, index: number): HandLandmark | null {
  return landmarks[`point_${index}`] || null
}

export default function JointAngleChart({ 
  skeletonData, 
  selectedFinger = 'index',
  currentTime = 0
}: JointAngleChartProps) {
  
  // 指のランドマークインデックスを取得
  const fingerLandmarks = useMemo(() => {
    switch (selectedFinger) {
      case 'thumb':
        return {
          base: LANDMARKS.THUMB_CMC,
          mcp: LANDMARKS.THUMB_MCP,
          pip: LANDMARKS.THUMB_IP,
          tip: LANDMARKS.THUMB_TIP,
          hasDIP: false
        }
      case 'index':
        return {
          base: LANDMARKS.WRIST,
          mcp: LANDMARKS.INDEX_MCP,
          pip: LANDMARKS.INDEX_PIP,
          dip: LANDMARKS.INDEX_DIP,
          tip: LANDMARKS.INDEX_TIP,
          hasDIP: true
        }
      case 'middle':
        return {
          base: LANDMARKS.WRIST,
          mcp: LANDMARKS.MIDDLE_MCP,
          pip: LANDMARKS.MIDDLE_PIP,
          dip: LANDMARKS.MIDDLE_DIP,
          tip: LANDMARKS.MIDDLE_TIP,
          hasDIP: true
        }
      case 'ring':
        return {
          base: LANDMARKS.WRIST,
          mcp: LANDMARKS.RING_MCP,
          pip: LANDMARKS.RING_PIP,
          dip: LANDMARKS.RING_DIP,
          tip: LANDMARKS.RING_TIP,
          hasDIP: true
        }
      case 'pinky':
        return {
          base: LANDMARKS.WRIST,
          mcp: LANDMARKS.PINKY_MCP,
          pip: LANDMARKS.PINKY_PIP,
          dip: LANDMARKS.PINKY_DIP,
          tip: LANDMARKS.PINKY_TIP,
          hasDIP: true
        }
      default:
        return null
    }
  }, [selectedFinger])
  
  // 時系列角度データを計算
  const chartData = useMemo(() => {
    if (!fingerLandmarks) return []
    
    const leftData = skeletonData.filter(f => f.hand_type === 'left')
    const rightData = skeletonData.filter(f => f.hand_type === 'right')
    
    // タイムスタンプのユニークリストを作成
    const uniqueTimestamps = new Set<number>()
    skeletonData.forEach(frame => uniqueTimestamps.add(frame.timestamp))
    const timestamps = Array.from(uniqueTimestamps).sort((a, b) => a - b)
    
    return timestamps.map(timestamp => {
      const leftFrame = leftData.find(f => Math.abs(f.timestamp - timestamp) < 0.01)
      const rightFrame = rightData.find(f => Math.abs(f.timestamp - timestamp) < 0.01)
      
      const dataPoint: any = {
        time: timestamp.toFixed(2),
        timestamp,
      }
      
      // 左手の角度を計算
      if (leftFrame) {
        const base = fingerLandmarks.base !== undefined ? getLandmark(leftFrame.landmarks, fingerLandmarks.base) : null
        const mcp = getLandmark(leftFrame.landmarks, fingerLandmarks.mcp)
        const pip = getLandmark(leftFrame.landmarks, fingerLandmarks.pip)
        const tip = getLandmark(leftFrame.landmarks, fingerLandmarks.tip)
        const dip = fingerLandmarks.hasDIP && fingerLandmarks.dip !== undefined
          ? getLandmark(leftFrame.landmarks, fingerLandmarks.dip)
          : null
        
        // MCP関節角度
        if (base && mcp && pip) {
          dataPoint.leftMCP = calculateAngle(base, mcp, pip)
        }
        
        // PIP/IP関節角度
        if (fingerLandmarks.hasDIP && mcp && pip && dip) {
          dataPoint.leftPIP = calculateAngle(mcp, pip, dip)
        } else if (!fingerLandmarks.hasDIP && mcp && pip && tip) {
          dataPoint.leftPIP = calculateAngle(mcp, pip, tip) // 親指のIP関節
        }
        
        // DIP関節角度
        if (fingerLandmarks.hasDIP && pip && dip && tip) {
          dataPoint.leftDIP = calculateAngle(pip, dip, tip)
        }
      }
      
      // 右手の角度を計算
      if (rightFrame) {
        const base = fingerLandmarks.base !== undefined ? getLandmark(rightFrame.landmarks, fingerLandmarks.base) : null
        const mcp = getLandmark(rightFrame.landmarks, fingerLandmarks.mcp)
        const pip = getLandmark(rightFrame.landmarks, fingerLandmarks.pip)
        const tip = getLandmark(rightFrame.landmarks, fingerLandmarks.tip)
        const dip = fingerLandmarks.hasDIP && fingerLandmarks.dip !== undefined
          ? getLandmark(rightFrame.landmarks, fingerLandmarks.dip)
          : null
        
        // MCP関節角度
        if (base && mcp && pip) {
          dataPoint.rightMCP = calculateAngle(base, mcp, pip)
        }
        
        // PIP/IP関節角度
        if (fingerLandmarks.hasDIP && mcp && pip && dip) {
          dataPoint.rightPIP = calculateAngle(mcp, pip, dip)
        } else if (!fingerLandmarks.hasDIP && mcp && pip && tip) {
          dataPoint.rightPIP = calculateAngle(mcp, pip, tip) // 親指のIP関節
        }
        
        // DIP関節角度
        if (fingerLandmarks.hasDIP && pip && dip && tip) {
          dataPoint.rightDIP = calculateAngle(pip, dip, tip)
        }
      }
      
      return dataPoint
    })
  }, [skeletonData, fingerLandmarks])
  
  // 現在時間のインデックスを取得
  const currentIndex = useMemo(() => {
    let minDiff = Infinity
    let index = 0
    chartData.forEach((data, i) => {
      const diff = Math.abs(data.timestamp - currentTime)
      if (diff < minDiff) {
        minDiff = diff
        index = i
      }
    })
    return index
  }, [chartData, currentTime])
  
  const fingerNames = {
    thumb: '親指',
    index: '人差し指',
    middle: '中指',
    ring: '薬指',
    pinky: '小指'
  }
  
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-2 border border-gray-200 rounded shadow-md">
          <p className="font-semibold">{`時間: ${label}秒`}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ color: entry.color }}>
              {`${entry.name}: ${entry.value?.toFixed(1)}°`}
            </p>
          ))}
        </div>
      )
    }
    return null
  }
  
  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">
          {fingerNames[selectedFinger]}の関節角度変化
        </h2>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-600">指選択:</label>
          <select
            value={selectedFinger}
            onChange={() => {}}
            disabled
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
          >
            {Object.entries(fingerNames).map(([key, name]) => (
              <option key={key} value={key}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>
      
      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart
            data={chartData}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              label={{ value: '時間 (秒)', position: 'insideBottom', offset: -5 }}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              label={{ value: '角度 (°)', angle: -90, position: 'insideLeft' }}
              tick={{ fontSize: 12 }}
              domain={[0, 180]}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="line"
              wrapperStyle={{ fontSize: 12 }}
            />
            
            {/* 左手の角度 */}
            <Line
              type="monotone"
              dataKey="leftMCP"
              stroke="#3b82f6"
              strokeWidth={2}
              name="左手 MCP"
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="leftPIP"
              stroke="#60a5fa"
              strokeWidth={2}
              name={fingerLandmarks?.hasDIP ? "左手 PIP" : "左手 IP"}
              dot={false}
              connectNulls
            />
            {fingerLandmarks?.hasDIP && (
              <Line
                type="monotone"
                dataKey="leftDIP"
                stroke="#93c5fd"
                strokeWidth={2}
                name="左手 DIP"
                dot={false}
                connectNulls
              />
            )}
            
            {/* 右手の角度 */}
            <Line
              type="monotone"
              dataKey="rightMCP"
              stroke="#ef4444"
              strokeWidth={2}
              name="右手 MCP"
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="rightPIP"
              stroke="#f87171"
              strokeWidth={2}
              name={fingerLandmarks?.hasDIP ? "右手 PIP" : "右手 IP"}
              dot={false}
              connectNulls
            />
            {fingerLandmarks?.hasDIP && (
              <Line
                type="monotone"
                dataKey="rightDIP"
                stroke="#fca5a5"
                strokeWidth={2}
                name="右手 DIP"
                dot={false}
                connectNulls
              />
            )}
            
            {/* ブラシコンポーネント（ズーム機能） */}
            <Brush
              dataKey="time"
              height={30}
              stroke="#8884d8"
              startIndex={Math.max(0, currentIndex - 50)}
              endIndex={Math.min(chartData.length - 1, currentIndex + 50)}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex items-center justify-center h-96 text-gray-500">
          データがありません
        </div>
      )}
      
      {/* 統計情報 */}
      {chartData.length > 0 && (
        <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-blue-50 rounded p-3">
            <h4 className="text-sm font-medium text-blue-900">左手MCP平均</h4>
            <p className="text-xl font-bold text-blue-600">
              {chartData
                .map(d => d.leftMCP)
                .filter(v => v !== undefined)
                .reduce((sum, val, _, arr) => sum + val / arr.length, 0)
                .toFixed(1)}°
            </p>
          </div>
          <div className="bg-red-50 rounded p-3">
            <h4 className="text-sm font-medium text-red-900">右手MCP平均</h4>
            <p className="text-xl font-bold text-red-600">
              {chartData
                .map(d => d.rightMCP)
                .filter(v => v !== undefined)
                .reduce((sum, val, _, arr) => sum + val / arr.length, 0)
                .toFixed(1)}°
            </p>
          </div>
          <div className="bg-green-50 rounded p-3">
            <h4 className="text-sm font-medium text-green-900">最大曲げ角度</h4>
            <p className="text-xl font-bold text-green-600">
              {Math.max(
                ...chartData.map(d => d.leftMCP || 0),
                ...chartData.map(d => d.rightMCP || 0)
              ).toFixed(1)}°
            </p>
          </div>
          <div className="bg-purple-50 rounded p-3">
            <h4 className="text-sm font-medium text-purple-900">最小曲げ角度</h4>
            <p className="text-xl font-bold text-purple-600">
              {Math.min(
                ...chartData.map(d => d.leftMCP || 180).filter(v => v > 0),
                ...chartData.map(d => d.rightMCP || 180).filter(v => v > 0)
              ).toFixed(1)}°
            </p>
          </div>
        </div>
      )}
      
      <div className="mt-4 text-xs text-gray-500">
        <p>※ MCP: 中手指節骨関節、PIP: 近位指節間関節、DIP: 遠位指節間関節、IP: 指節間関節（親指）</p>
        <p>※ グラフ下部のブラシをドラッグしてズームできます</p>
      </div>
    </div>
  )
}