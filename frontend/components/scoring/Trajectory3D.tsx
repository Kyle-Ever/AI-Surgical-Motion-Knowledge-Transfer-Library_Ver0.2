'use client';

import React, { useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Line, Grid, Box, Text } from '@react-three/drei';
import { motion } from 'framer-motion';
import * as THREE from 'three';

interface Trajectory3DProps {
  comparisonId: string | null;
  showReference: boolean;
  showEvaluation: boolean;
}

// 3Dシーン内の軌跡ライン
const TrajectoryLine: React.FC<{
  points: THREE.Vector3[];
  color: string;
  opacity?: number;
}> = ({ points, color, opacity = 1 }) => {
  return (
    <Line
      points={points}
      color={color}
      lineWidth={2}
      opacity={opacity}
      transparent
    />
  );
};

// 3Dシーンコンポーネント
const Scene3D: React.FC<{
  showReference: boolean;
  showEvaluation: boolean;
}> = ({ showReference, showEvaluation }) => {
  // サンプル軌跡データ（実際はAPIから取得）
  const referencePoints = [
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(1, 0.5, 0.2),
    new THREE.Vector3(2, 1, 0.3),
    new THREE.Vector3(3, 0.8, 0.5),
    new THREE.Vector3(4, 0.3, 0.7),
  ];

  const evaluationPoints = [
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0.9, 0.6, 0.1),
    new THREE.Vector3(2.1, 1.1, 0.4),
    new THREE.Vector3(2.9, 0.9, 0.6),
    new THREE.Vector3(4, 0.4, 0.8),
  ];

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />

      {/* グリッド */}
      <Grid
        args={[10, 10]}
        cellSize={0.5}
        cellThickness={1}
        cellColor="#6b7280"
        sectionSize={1}
        sectionThickness={1.5}
        sectionColor="#374151"
        fadeDistance={30}
        fadeStrength={1}
      />

      {/* 基準軌跡（緑） */}
      {showReference && (
        <TrajectoryLine
          points={referencePoints}
          color="#22c55e"
          opacity={0.8}
        />
      )}

      {/* 評価軌跡（青） */}
      {showEvaluation && (
        <TrajectoryLine
          points={evaluationPoints}
          color="#3b82f6"
          opacity={0.8}
        />
      )}

      {/* 座標軸ラベル */}
      <Text position={[5, 0, 0]} fontSize={0.2} color="#666">
        X
      </Text>
      <Text position={[0, 2, 0]} fontSize={0.2} color="#666">
        Y
      </Text>
      <Text position={[0, 0, 2]} fontSize={0.2} color="#666">
        Z
      </Text>

      <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} />
    </>
  );
};

const Trajectory3D: React.FC<Trajectory3DProps> = ({
  comparisonId,
  showReference,
  showEvaluation
}) => {
  const [view, setView] = useState<'front' | 'side' | 'top'>('front');

  const handleViewChange = (newView: 'front' | 'side' | 'top') => {
    setView(newView);
    // カメラ位置の変更ロジックを実装
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5 }}
      className="bg-white rounded-lg shadow-sm p-6"
    >
      <h3 className="font-semibold mb-4">🎮 3D軌跡比較</h3>

      {/* 3Dビューア */}
      <div className="bg-gray-100 rounded-lg overflow-hidden" style={{ height: '400px' }}>
        <Canvas camera={{ position: [5, 5, 5], fov: 50 }}>
          <Scene3D
            showReference={showReference}
            showEvaluation={showEvaluation}
          />
        </Canvas>
      </div>

      {/* ビューコントロール */}
      <div className="flex justify-center gap-2 mt-4">
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => handleViewChange('front')}
          className={`px-3 py-1 rounded text-sm ${
            view === 'front' ? 'bg-purple-600 text-white' : 'bg-gray-200'
          }`}
        >
          正面
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => handleViewChange('side')}
          className={`px-3 py-1 rounded text-sm ${
            view === 'side' ? 'bg-purple-600 text-white' : 'bg-gray-200'
          }`}
        >
          側面
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => handleViewChange('top')}
          className={`px-3 py-1 rounded text-sm ${
            view === 'top' ? 'bg-purple-600 text-white' : 'bg-gray-200'
          }`}
        >
          上面
        </motion.button>
      </div>

      {/* 凡例 */}
      <div className="flex justify-center gap-4 mt-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded-full"></div>
          <span>基準動作</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
          <span>評価動作</span>
        </div>
      </div>
    </motion.section>
  );
};

export default Trajectory3D;