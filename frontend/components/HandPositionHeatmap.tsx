'use client'

import { useMemo, useRef, useEffect } from 'react'

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

interface HandPositionHeatmapProps {
  skeletonData: SkeletonFrame[]
  gridSize?: number // グリッドの解像度
  selectedLandmark?: number // どのランドマークを表示するか
}

export default function HandPositionHeatmap({ 
  skeletonData,
  gridSize = 50,
  selectedLandmark = 0
}: HandPositionHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const leftCanvasRef = useRef<HTMLCanvasElement>(null)
  const rightCanvasRef = useRef<HTMLCanvasElement>(null)
  
  // ヒートマップデータを計算
  const heatmapData = useMemo(() => {
    const leftHeatmap = Array(gridSize).fill(null).map(() => Array(gridSize).fill(0))
    const rightHeatmap = Array(gridSize).fill(null).map(() => Array(gridSize).fill(0))
    
    // 各フレームを処理
    skeletonData.forEach(frame => {
      const landmark = frame.landmarks[`point_${selectedLandmark}`]
      if (landmark) {
        // 座標をグリッドインデックスに変換 (0-1 → 0-gridSize)
        const x = Math.floor(landmark.x * (gridSize - 1))
        const y = Math.floor(landmark.y * (gridSize - 1))
        
        if (x >= 0 && x < gridSize && y >= 0 && y < gridSize) {
          if (frame.hand_type === 'left') {
            leftHeatmap[y][x] += 1
            // 周囲にも影響を与える（ガウシアンフィルタ風）
            for (let dx = -2; dx <= 2; dx++) {
              for (let dy = -2; dy <= 2; dy++) {
                const nx = x + dx
                const ny = y + dy
                if (nx >= 0 && nx < gridSize && ny >= 0 && ny < gridSize) {
                  const distance = Math.sqrt(dx * dx + dy * dy)
                  const weight = Math.exp(-distance * distance / 2) // ガウシアン
                  leftHeatmap[ny][nx] += weight * 0.5
                }
              }
            }
          } else if (frame.hand_type === 'right') {
            rightHeatmap[y][x] += 1
            // 周囲にも影響を与える
            for (let dx = -2; dx <= 2; dx++) {
              for (let dy = -2; dy <= 2; dy++) {
                const nx = x + dx
                const ny = y + dy
                if (nx >= 0 && nx < gridSize && ny >= 0 && ny < gridSize) {
                  const distance = Math.sqrt(dx * dx + dy * dy)
                  const weight = Math.exp(-distance * distance / 2)
                  rightHeatmap[ny][nx] += weight * 0.5
                }
              }
            }
          }
        }
      }
    })
    
    // 正規化
    const normalizeHeatmap = (heatmap: number[][]) => {
      let maxValue = 0
      heatmap.forEach(row => {
        row.forEach(val => {
          maxValue = Math.max(maxValue, val)
        })
      })
      
      if (maxValue > 0) {
        heatmap.forEach((row, y) => {
          row.forEach((val, x) => {
            heatmap[y][x] = val / maxValue
          })
        })
      }
      
      return heatmap
    }
    
    return {
      left: normalizeHeatmap(leftHeatmap),
      right: normalizeHeatmap(rightHeatmap)
    }
  }, [skeletonData, gridSize, selectedLandmark])
  
  // ヒートマップを描画
  useEffect(() => {
    const drawHeatmap = (canvas: HTMLCanvasElement | null, data: number[][]) => {
      if (!canvas) return
      
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      
      const cellWidth = canvas.width / gridSize
      const cellHeight = canvas.height / gridSize
      
      // クリア
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      
      // 背景
      ctx.fillStyle = '#f3f4f6'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      
      // ヒートマップを描画
      data.forEach((row, y) => {
        row.forEach((value, x) => {
          if (value > 0) {
            // 値に応じて色を変える（青→赤）
            const intensity = Math.floor(value * 255)
            const r = intensity
            const g = Math.floor(intensity * 0.3)
            const b = 255 - intensity
            
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${value * 0.8})`
            ctx.fillRect(x * cellWidth, y * cellHeight, cellWidth, cellHeight)
          }
        })
      })
      
      // グリッド線
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.05)'
      ctx.lineWidth = 0.5
      for (let i = 0; i <= gridSize; i++) {
        // 垂直線
        ctx.beginPath()
        ctx.moveTo(i * cellWidth, 0)
        ctx.lineTo(i * cellWidth, canvas.height)
        ctx.stroke()
        // 水平線
        ctx.beginPath()
        ctx.moveTo(0, i * cellHeight)
        ctx.lineTo(canvas.width, i * cellHeight)
        ctx.stroke()
      }
    }
    
    drawHeatmap(leftCanvasRef.current, heatmapData.left)
    drawHeatmap(rightCanvasRef.current, heatmapData.right)
  }, [heatmapData, gridSize])
  
  // 統計情報を計算
  const statistics = useMemo(() => {
    const calculateStats = (heatmap: number[][]) => {
      let hotspotX = 0
      let hotspotY = 0
      let maxValue = 0
      let coverage = 0
      let totalWeight = 0
      let centroidX = 0
      let centroidY = 0
      
      heatmap.forEach((row, y) => {
        row.forEach((value, x) => {
          if (value > maxValue) {
            maxValue = value
            hotspotX = x
            hotspotY = y
          }
          if (value > 0.1) { // 闾値以上はカバレッジに含める
            coverage++
          }
          totalWeight += value
          centroidX += x * value
          centroidY += y * value
        })
      })
      
      if (totalWeight > 0) {
        centroidX /= totalWeight
        centroidY /= totalWeight
      }
      
      return {
        hotspot: { x: hotspotX / gridSize, y: hotspotY / gridSize },
        coverage: (coverage / (gridSize * gridSize)) * 100,
        centroid: { x: centroidX / gridSize, y: centroidY / gridSize }
      }
    }
    
    return {
      left: calculateStats(heatmapData.left),
      right: calculateStats(heatmapData.right)
    }
  }, [heatmapData, gridSize])
  
  const landmarkNames: { [key: number]: string } = {
    0: '手首',
    4: '親指先端',
    8: '人差し指先端',
    12: '中指先端',
    16: '薬指先端',
    20: '小指先端',
  }
  
  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">手の位置ヒートマップ</h2>
        <select
          value={selectedLandmark}
          onChange={() => {}}
          disabled
          className="px-3 py-1 border border-gray-300 rounded-md text-sm"
        >
          {Object.entries(landmarkNames).map(([index, name]) => (
            <option key={index} value={index}>
              {name}
            </option>
          ))}
        </select>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左手ヒートマップ */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">左手</h3>
          <div className="relative bg-gray-100 rounded">
            <canvas
              ref={leftCanvasRef}
              width={400}
              height={400}
              className="w-full h-auto rounded"
              style={{ imageRendering: 'pixelated' }}
            />
            {/* ホットスポットマーカー */}
            <div
              className="absolute w-3 h-3 bg-yellow-400 border-2 border-yellow-600 rounded-full"
              style={{
                left: `${statistics.left.hotspot.x * 100}%`,
                top: `${statistics.left.hotspot.y * 100}%`,
                transform: 'translate(-50%, -50%)'
              }}
              title="ホットスポット"
            />
            {/* 重心マーカー */}
            <div
              className="absolute w-2 h-2 bg-green-400 border border-green-600 rounded-full"
              style={{
                left: `${statistics.left.centroid.x * 100}%`,
                top: `${statistics.left.centroid.y * 100}%`,
                transform: 'translate(-50%, -50%)'
              }}
              title="重心"
            />
          </div>
          <div className="mt-2 text-sm text-gray-600">
            <p>カバレッジ: {statistics.left.coverage.toFixed(1)}%</p>
            <p>ホットスポット: ({(statistics.left.hotspot.x * 100).toFixed(0)}, {(statistics.left.hotspot.y * 100).toFixed(0)})</p>
            <p>重心: ({(statistics.left.centroid.x * 100).toFixed(0)}, {(statistics.left.centroid.y * 100).toFixed(0)})</p>
          </div>
        </div>
        
        {/* 右手ヒートマップ */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">右手</h3>
          <div className="relative bg-gray-100 rounded">
            <canvas
              ref={rightCanvasRef}
              width={400}
              height={400}
              className="w-full h-auto rounded"
              style={{ imageRendering: 'pixelated' }}
            />
            {/* ホットスポットマーカー */}
            <div
              className="absolute w-3 h-3 bg-yellow-400 border-2 border-yellow-600 rounded-full"
              style={{
                left: `${statistics.right.hotspot.x * 100}%`,
                top: `${statistics.right.hotspot.y * 100}%`,
                transform: 'translate(-50%, -50%)'
              }}
              title="ホットスポット"
            />
            {/* 重心マーカー */}
            <div
              className="absolute w-2 h-2 bg-green-400 border border-green-600 rounded-full"
              style={{
                left: `${statistics.right.centroid.x * 100}%`,
                top: `${statistics.right.centroid.y * 100}%`,
                transform: 'translate(-50%, -50%)'
              }}
              title="重心"
            />
          </div>
          <div className="mt-2 text-sm text-gray-600">
            <p>カバレッジ: {statistics.right.coverage.toFixed(1)}%</p>
            <p>ホットスポット: ({(statistics.right.hotspot.x * 100).toFixed(0)}, {(statistics.right.hotspot.y * 100).toFixed(0)})</p>
            <p>重心: ({(statistics.right.centroid.x * 100).toFixed(0)}, {(statistics.right.centroid.y * 100).toFixed(0)})</p>
          </div>
        </div>
      </div>
      
      {/* 凡例 */}
      <div className="mt-4 flex items-center space-x-4 text-xs text-gray-500">
        <div className="flex items-center">
          <div className="w-3 h-3 bg-yellow-400 border border-yellow-600 rounded-full mr-1" />
          <span>ホットスポット: 最も頻繁に存在した位置</span>
        </div>
        <div className="flex items-center">
          <div className="w-2 h-2 bg-green-400 border border-green-600 rounded-full mr-1" />
          <span>重心: 全体の動きの中心点</span>
        </div>
      </div>
      <div className="mt-2 text-xs text-gray-500">
        <p>※ 色が濃い箇所ほど、その位置に手が存在した時間が長いことを示します</p>
        <p>※ カバレッジは作業範囲の広さを示す指標です</p>
      </div>
    </div>
  )
}