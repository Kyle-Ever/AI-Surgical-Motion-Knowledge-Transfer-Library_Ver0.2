'use client'

import { useRef, useMemo, useEffect, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Line, Text, Grid } from '@react-three/drei'
import * as THREE from 'three'

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

interface HandTrajectory3DProps {
  skeletonData: SkeletonFrame[]
  currentTime: number
  selectedLandmark?: number // Which landmark to track (default: wrist = 0)
  showBothHands?: boolean
}

// MediaPipe手のランドマークインデックス
const LANDMARK_NAMES: { [key: number]: string } = {
  0: '手首',
  4: '親指先端',
  8: '人差し指先端',
  12: '中指先端',
  16: '薬指先端',
  20: '小指先端',
}

function TrajectoryLine({ points, color, lineWidth = 2 }: { points: THREE.Vector3[], color: string, lineWidth?: number }) {
  const lineRef = useRef<THREE.Line>(null)
  
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry()
    if (points.length > 0) {
      const positions = new Float32Array(points.length * 3)
      points.forEach((p, i) => {
        positions[i * 3] = p.x
        positions[i * 3 + 1] = p.y
        positions[i * 3 + 2] = p.z
      })
      geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    }
    return geo
  }, [points])

  return (
    <line ref={lineRef}>
      <bufferGeometry attach="geometry" {...geometry} />
      <lineBasicMaterial attach="material" color={color} linewidth={lineWidth} />
    </line>
  )
}

function CurrentPositionMarker({ position, color }: { position: THREE.Vector3, color: string }) {
  const meshRef = useRef<THREE.Mesh>(null)
  
  useFrame((state) => {
    if (meshRef.current) {
      // アニメーション：軽く上下に動かす
      meshRef.current.position.y = position.y + Math.sin(state.clock.elapsedTime * 2) * 0.01
    }
  })

  return (
    <mesh ref={meshRef} position={[position.x, position.y, position.z]}>
      <sphereGeometry args={[0.015, 16, 16]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.5} />
    </mesh>
  )
}

function Scene({ 
  leftTrajectory, 
  rightTrajectory,
  currentLeftPos,
  currentRightPos,
  showBothHands
}: {
  leftTrajectory: THREE.Vector3[]
  rightTrajectory: THREE.Vector3[]
  currentLeftPos: THREE.Vector3 | null
  currentRightPos: THREE.Vector3 | null
  showBothHands: boolean
}) {
  const { camera } = useThree()
  
  useEffect(() => {
    // カメラの初期位置を設定
    camera.position.set(0.3, 0.3, 0.5)
    camera.lookAt(0, 0, 0)
  }, [])

  return (
    <>
      {/* ライト */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      
      {/* グリッド */}
      <Grid
        args={[1, 1]}
        cellSize={0.1}
        cellThickness={0.5}
        cellColor="#6e6e6e"
        sectionSize={0.3}
        sectionThickness={1}
        sectionColor="#9d4b4b"
        fadeDistance={1}
        fadeStrength={1}
        followCamera={false}
        infiniteGrid
      />
      
      {/* 軸の表示 */}
      <axesHelper args={[0.3]} />
      
      {/* 左手の軌跡 */}
      {leftTrajectory.length > 0 && (
        <>
          <TrajectoryLine points={leftTrajectory} color="#3b82f6" lineWidth={3} />
          {currentLeftPos && (
            <CurrentPositionMarker position={currentLeftPos} color="#3b82f6" />
          )}
        </>
      )}
      
      {/* 右手の軌跡 */}
      {showBothHands && rightTrajectory.length > 0 && (
        <>
          <TrajectoryLine points={rightTrajectory} color="#ef4444" lineWidth={3} />
          {currentRightPos && (
            <CurrentPositionMarker position={currentRightPos} color="#ef4444" />
          )}
        </>
      )}
      
      {/* ラベル */}
      <Text
        position={[0, -0.3, 0]}
        fontSize={0.03}
        color="white"
        anchorX="center"
        anchorY="middle"
      >
        3D手の軌跡
      </Text>
      
      {/* OrbitControls for camera interaction */}
      <OrbitControls 
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={0.2}
        maxDistance={2}
      />
    </>
  )
}

export default function HandTrajectory3D({ 
  skeletonData, 
  currentTime,
  selectedLandmark = 0,
  showBothHands = true
}: HandTrajectory3DProps) {
  const [selectedPoint, setSelectedPoint] = useState(selectedLandmark)
  
  // 左手と右手のデータを分離
  const { leftHandData, rightHandData } = useMemo(() => {
    const left = skeletonData.filter(frame => frame.hand_type === 'left')
    const right = skeletonData.filter(frame => frame.hand_type === 'right')
    return { leftHandData: left, rightHandData: right }
  }, [skeletonData])
  
  // 軌跡データを生成（選択したランドマークポイントの3D座標）
  const { leftTrajectory, rightTrajectory } = useMemo(() => {
    const getLandmarkTrajectory = (data: SkeletonFrame[]) => {
      return data
        .map(frame => {
          const landmark = frame.landmarks[`point_${selectedPoint}`]
          if (landmark) {
            // MediaPipeの座標系を3D空間に変換
            // x: 左右 (0-1を-0.5～0.5に)
            // y: 上下 (0-1を-0.5～0.5に、上下反転)
            // z: 奥行き (正規化)
            return new THREE.Vector3(
              landmark.x - 0.5,
              -(landmark.y - 0.5),
              landmark.z * 0.5
            )
          }
          return null
        })
        .filter((point): point is THREE.Vector3 => point !== null)
    }
    
    return {
      leftTrajectory: getLandmarkTrajectory(leftHandData),
      rightTrajectory: getLandmarkTrajectory(rightHandData)
    }
  }, [leftHandData, rightHandData, selectedPoint])
  
  // 現在時間における位置を取得
  const { currentLeftPos, currentRightPos } = useMemo(() => {
    const getCurrentPosition = (data: SkeletonFrame[]) => {
      if (data.length === 0) return null
      
      // 現在時間に最も近いフレームを見つける
      let closestFrame = data[0]
      let minDiff = Math.abs(data[0].timestamp - currentTime)
      
      for (const frame of data) {
        const diff = Math.abs(frame.timestamp - currentTime)
        if (diff < minDiff) {
          minDiff = diff
          closestFrame = frame
        }
      }
      
      const landmark = closestFrame.landmarks[`point_${selectedPoint}`]
      if (landmark) {
        return new THREE.Vector3(
          landmark.x - 0.5,
          -(landmark.y - 0.5),
          landmark.z * 0.5
        )
      }
      return null
    }
    
    return {
      currentLeftPos: getCurrentPosition(leftHandData),
      currentRightPos: getCurrentPosition(rightHandData)
    }
  }, [leftHandData, rightHandData, currentTime, selectedPoint])
  
  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">3D軌跡ビュー</h2>
        <select
          value={selectedPoint}
          onChange={(e) => setSelectedPoint(Number(e.target.value))}
          className="px-3 py-1 border border-gray-300 rounded-md text-sm"
        >
          {Object.entries(LANDMARK_NAMES).map(([index, name]) => (
            <option key={index} value={index}>
              {name}
            </option>
          ))}
        </select>
      </div>
      
      <div className="relative w-full" style={{ height: '400px' }}>
        <Canvas>
          <Scene
            leftTrajectory={leftTrajectory}
            rightTrajectory={rightTrajectory}
            currentLeftPos={currentLeftPos}
            currentRightPos={currentRightPos}
            showBothHands={showBothHands}
          />
        </Canvas>
      </div>
      
      <div className="mt-4 flex items-center space-x-4 text-sm">
        <div className="flex items-center">
          <div className="w-4 h-4 bg-blue-500 rounded-full mr-2" />
          <span>左手</span>
        </div>
        {showBothHands && (
          <div className="flex items-center">
            <div className="w-4 h-4 bg-red-500 rounded-full mr-2" />
            <span>右手</span>
          </div>
        )}
        <div className="text-gray-500 ml-auto">
          マウスでドラッグして回転、スクロールで拡大縮小
        </div>
      </div>
    </div>
  )
}