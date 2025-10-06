'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Play, Pause, SkipForward, Repeat, RotateCcw } from 'lucide-react';

interface SyncControlBarProps {
  isPlaying: boolean;
  playbackSpeed: number;
  useDTW: boolean;
  onPlayPause: () => void;
  onSpeedChange: (speed: number) => void;
  onDTWToggle: () => void;
  onSkeletonToggle: () => void;
  onTrajectoryToggle: () => void;
}

const SyncControlBar: React.FC<SyncControlBarProps> = ({
  isPlaying,
  playbackSpeed,
  useDTW,
  onPlayPause,
  onSpeedChange,
  onDTWToggle,
  onSkeletonToggle,
  onTrajectoryToggle
}) => {
  const speeds = [0.5, 1, 2];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="bg-white rounded-lg shadow-sm p-4"
    >
      <div className="flex items-center justify-center gap-4 flex-wrap">
        {/* 同期再生ボタン */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onPlayPause}
          className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition flex items-center gap-2"
        >
          {isPlaying ? <Pause size={18} /> : <Play size={18} />}
          {isPlaying ? '一時停止' : '同期再生'}
        </motion.button>

        {/* 再生速度コントロール */}
        <div className="flex gap-2">
          {speeds.map(speed => (
            <motion.button
              key={speed}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => onSpeedChange(speed)}
              className={`px-3 py-2 rounded-md transition ${
                playbackSpeed === speed
                  ? 'bg-purple-100 border-2 border-purple-500'
                  : 'bg-gray-200 hover:bg-gray-300'
              }`}
            >
              {speed === 1 ? '標準速度' : `${speed}x`}
            </motion.button>
          ))}
        </div>

        <div className="border-l h-6" />

        {/* 追加コントロール */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="px-3 py-2 bg-gray-200 rounded-md hover:bg-gray-300 transition flex items-center gap-2"
        >
          <SkipForward size={16} />
          コマ送り
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="px-3 py-2 bg-gray-200 rounded-md hover:bg-gray-300 transition flex items-center gap-2"
        >
          <Repeat size={16} />
          区間リピート
        </motion.button>

        <div className="border-l h-6" />

        {/* DTWトグル */}
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={useDTW}
            onChange={onDTWToggle}
            className="rounded text-purple-600 focus:ring-purple-500"
          />
          <span className="text-sm">DTW時間軸調整</span>
        </label>

        {/* 表示オプション */}
        <div className="flex gap-2">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onSkeletonToggle}
            className="px-3 py-2 bg-gray-200 rounded-md hover:bg-gray-300 transition text-sm"
          >
            ✋ 手技検出
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onTrajectoryToggle}
            className="px-3 py-2 bg-gray-200 rounded-md hover:bg-gray-300 transition text-sm"
          >
            〰️ 軌跡
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
};

export default SyncControlBar;