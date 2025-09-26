'use client'

import { useEffect, useState, useMemo } from 'react'

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

interface HandMetricsTableProps {
  skeletonData: SkeletonFrame[]
  currentTime: number
}

// MediaPipeの手のランドマーク定義
const HAND_LANDMARKS = {
  // 手首と手のひら
  WRIST: 0,

  // 親指
  THUMB_CMC: 1,
  THUMB_MCP: 2,
  THUMB_IP: 3,
  THUMB_TIP: 4,

  // 人差し指
  INDEX_MCP: 5,
  INDEX_PIP: 6,
  INDEX_DIP: 7,
  INDEX_TIP: 8,

  // 中指
  MIDDLE_MCP: 9,
  MIDDLE_PIP: 10,
  MIDDLE_DIP: 11,
  MIDDLE_TIP: 12,

  // 薬指
  RING_MCP: 13,
  RING_PIP: 14,
  RING_DIP: 15,
  RING_TIP: 16,

  // 小指
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

  // ベクトルの大きさ
  const mag1 = Math.sqrt(v1.x * v1.x + v1.y * v1.y + v1.z * v1.z)
  const mag2 = Math.sqrt(v2.x * v2.x + v2.y * v2.y + v2.z * v2.z)

  if (mag1 === 0 || mag2 === 0) return 0

  // 内積
  const dot = v1.x * v2.x + v1.y * v2.y + v1.z * v2.z

  // 角度（ラジアン）
  const cosAngle = dot / (mag1 * mag2)
  const angleRad = Math.acos(Math.max(-1, Math.min(1, cosAngle)))

  // 度数に変換
  return (angleRad * 180) / Math.PI
}

// ランドマークを取得するヘルパー関数
function getLandmark(landmarks: any, index: number): HandLandmark | null {
  const key = `point_${index}`
  return landmarks[key] || null
}

export default function HandMetricsTable({ skeletonData, currentTime }: HandMetricsTableProps) {
  const [currentFrame, setCurrentFrame] = useState<SkeletonFrame | null>(null)

  // 現在の時間に最も近いフレームを取得
  useEffect(() => {
    if (!skeletonData || skeletonData.length === 0) {
      setCurrentFrame(null)
      return
    }

    // 現在時間に最も近いフレームを見つける
    let closestFrame = skeletonData[0]
    let minDiff = Math.abs(skeletonData[0].timestamp - currentTime)

    for (const frame of skeletonData) {
      const diff = Math.abs(frame.timestamp - currentTime)
      if (diff < minDiff) {
        minDiff = diff
        closestFrame = frame
      }
    }

    setCurrentFrame(closestFrame)
  }, [skeletonData, currentTime])

  // 各関節の角度を計算
  const jointAngles = useMemo(() => {
    if (!currentFrame) return null

    const landmarks = currentFrame.landmarks
    const angles: { [key: string]: number | null } = {}

    // 親指の角度
    const thumbCMC = getLandmark(landmarks, HAND_LANDMARKS.THUMB_CMC)
    const thumbMCP = getLandmark(landmarks, HAND_LANDMARKS.THUMB_MCP)
    const thumbIP = getLandmark(landmarks, HAND_LANDMARKS.THUMB_IP)
    const thumbTIP = getLandmark(landmarks, HAND_LANDMARKS.THUMB_TIP)

    if (thumbCMC && thumbMCP && thumbIP) {
      angles.thumbMCP = calculateAngle(thumbCMC, thumbMCP, thumbIP)
    }
    if (thumbMCP && thumbIP && thumbTIP) {
      angles.thumbIP = calculateAngle(thumbMCP, thumbIP, thumbTIP)
    }

    // 人差し指の角度
    const wrist = getLandmark(landmarks, HAND_LANDMARKS.WRIST)
    const indexMCP = getLandmark(landmarks, HAND_LANDMARKS.INDEX_MCP)
    const indexPIP = getLandmark(landmarks, HAND_LANDMARKS.INDEX_PIP)
    const indexDIP = getLandmark(landmarks, HAND_LANDMARKS.INDEX_DIP)
    const indexTIP = getLandmark(landmarks, HAND_LANDMARKS.INDEX_TIP)

    if (wrist && indexMCP && indexPIP) {
      angles.indexMCP = calculateAngle(wrist, indexMCP, indexPIP)
    }
    if (indexMCP && indexPIP && indexDIP) {
      angles.indexPIP = calculateAngle(indexMCP, indexPIP, indexDIP)
    }
    if (indexPIP && indexDIP && indexTIP) {
      angles.indexDIP = calculateAngle(indexPIP, indexDIP, indexTIP)
    }

    // 中指の角度
    const middleMCP = getLandmark(landmarks, HAND_LANDMARKS.MIDDLE_MCP)
    const middlePIP = getLandmark(landmarks, HAND_LANDMARKS.MIDDLE_PIP)
    const middleDIP = getLandmark(landmarks, HAND_LANDMARKS.MIDDLE_DIP)
    const middleTIP = getLandmark(landmarks, HAND_LANDMARKS.MIDDLE_TIP)

    if (wrist && middleMCP && middlePIP) {
      angles.middleMCP = calculateAngle(wrist, middleMCP, middlePIP)
    }
    if (middleMCP && middlePIP && middleDIP) {
      angles.middlePIP = calculateAngle(middleMCP, middlePIP, middleDIP)
    }
    if (middlePIP && middleDIP && middleTIP) {
      angles.middleDIP = calculateAngle(middlePIP, middleDIP, middleTIP)
    }

    // 薬指の角度
    const ringMCP = getLandmark(landmarks, HAND_LANDMARKS.RING_MCP)
    const ringPIP = getLandmark(landmarks, HAND_LANDMARKS.RING_PIP)
    const ringDIP = getLandmark(landmarks, HAND_LANDMARKS.RING_DIP)
    const ringTIP = getLandmark(landmarks, HAND_LANDMARKS.RING_TIP)

    if (wrist && ringMCP && ringPIP) {
      angles.ringMCP = calculateAngle(wrist, ringMCP, ringPIP)
    }
    if (ringMCP && ringPIP && ringDIP) {
      angles.ringPIP = calculateAngle(ringMCP, ringPIP, ringDIP)
    }
    if (ringPIP && ringDIP && ringTIP) {
      angles.ringDIP = calculateAngle(ringPIP, ringDIP, ringTIP)
    }

    // 小指の角度
    const pinkyMCP = getLandmark(landmarks, HAND_LANDMARKS.PINKY_MCP)
    const pinkyPIP = getLandmark(landmarks, HAND_LANDMARKS.PINKY_PIP)
    const pinkyDIP = getLandmark(landmarks, HAND_LANDMARKS.PINKY_DIP)
    const pinkyTIP = getLandmark(landmarks, HAND_LANDMARKS.PINKY_TIP)

    if (wrist && pinkyMCP && pinkyPIP) {
      angles.pinkyMCP = calculateAngle(wrist, pinkyMCP, pinkyPIP)
    }
    if (pinkyMCP && pinkyPIP && pinkyDIP) {
      angles.pinkyPIP = calculateAngle(pinkyMCP, pinkyPIP, pinkyDIP)
    }
    if (pinkyPIP && pinkyDIP && pinkyTIP) {
      angles.pinkyDIP = calculateAngle(pinkyPIP, pinkyDIP, pinkyTIP)
    }

    return angles
  }, [currentFrame])

  // 手の重心座標を計算
  const handCentroid = useMemo(() => {
    if (!currentFrame) return null

    const landmarks = currentFrame.landmarks
    const points = Object.keys(landmarks).map(key => landmarks[key])

    if (points.length === 0) return null

    const sum = points.reduce(
      (acc, point) => ({
        x: acc.x + point.x,
        y: acc.y + point.y,
        z: acc.z + point.z,
      }),
      { x: 0, y: 0, z: 0 }
    )

    return {
      x: sum.x / points.length,
      y: sum.y / points.length,
      z: sum.z / points.length,
    }
  }, [currentFrame])

  if (!currentFrame || !jointAngles) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-lg font-semibold mb-4">手の詳細メトリクス</h2>
        <p className="text-gray-500">データがありません</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold mb-4">
        手の詳細メトリクス - {currentFrame.hand_type}手
      </h2>

      {/* 現在のフレーム情報 */}
      <div className="mb-4 p-3 bg-gray-50 rounded">
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <span className="text-gray-600">フレーム:</span>
            <span className="ml-2 font-medium">{currentFrame.frame_number}</span>
          </div>
          <div>
            <span className="text-gray-600">時間:</span>
            <span className="ml-2 font-medium">{currentFrame.timestamp.toFixed(3)}秒</span>
          </div>
          <div>
            <span className="text-gray-600">手:</span>
            <span className="ml-2 font-medium">{currentFrame.hand_type}</span>
          </div>
        </div>
      </div>

      {/* 手の重心座標 */}
      {handCentroid && (
        <div className="mb-4 p-3 bg-blue-50 rounded">
          <h3 className="text-sm font-semibold mb-2">手の重心座標</h3>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div>
              <span className="text-gray-600">X:</span>
              <span className="ml-2 font-medium">{handCentroid.x.toFixed(4)}</span>
            </div>
            <div>
              <span className="text-gray-600">Y:</span>
              <span className="ml-2 font-medium">{handCentroid.y.toFixed(4)}</span>
            </div>
            <div>
              <span className="text-gray-600">Z:</span>
              <span className="ml-2 font-medium">{handCentroid.z.toFixed(4)}</span>
            </div>
          </div>
        </div>
      )}

      {/* 関節角度テーブル */}
      <div className="overflow-x-auto">
        <table className="min-w-full table-auto">
          <thead>
            <tr className="bg-gray-50">
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                指
              </th>
              <th className="px-4 py-2 text-center text-xs font-medium text-gray-600 uppercase tracking-wider">
                MCP関節
              </th>
              <th className="px-4 py-2 text-center text-xs font-medium text-gray-600 uppercase tracking-wider">
                PIP/IP関節
              </th>
              <th className="px-4 py-2 text-center text-xs font-medium text-gray-600 uppercase tracking-wider">
                DIP関節
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {/* 親指 */}
            <tr>
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                親指
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.thumbMCP ? `${jointAngles.thumbMCP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.thumbIP ? `${jointAngles.thumbIP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                -
              </td>
            </tr>

            {/* 人差し指 */}
            <tr>
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                人差し指
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.indexMCP ? `${jointAngles.indexMCP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.indexPIP ? `${jointAngles.indexPIP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.indexDIP ? `${jointAngles.indexDIP.toFixed(1)}°` : '-'}
              </td>
            </tr>

            {/* 中指 */}
            <tr>
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                中指
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.middleMCP ? `${jointAngles.middleMCP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.middlePIP ? `${jointAngles.middlePIP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.middleDIP ? `${jointAngles.middleDIP.toFixed(1)}°` : '-'}
              </td>
            </tr>

            {/* 薬指 */}
            <tr>
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                薬指
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.ringMCP ? `${jointAngles.ringMCP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.ringPIP ? `${jointAngles.ringPIP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.ringDIP ? `${jointAngles.ringDIP.toFixed(1)}°` : '-'}
              </td>
            </tr>

            {/* 小指 */}
            <tr>
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                小指
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.pinkyMCP ? `${jointAngles.pinkyMCP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.pinkyPIP ? `${jointAngles.pinkyPIP.toFixed(1)}°` : '-'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-center text-gray-500">
                {jointAngles.pinkyDIP ? `${jointAngles.pinkyDIP.toFixed(1)}°` : '-'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}