'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, AlertCircle, Lightbulb, PlayCircle } from 'lucide-react';

interface AIFeedbackProps {
  comparisonId: string | null;
  onSeek: (time: number) => void;
}

interface TimeRangeIssue {
  timeRange: string;
  startTime: number;
  endTime: number;
  description: string;
  severity: 'high' | 'medium' | 'low';
  metric: string;
}

const AIFeedback: React.FC<AIFeedbackProps> = ({ comparisonId, onSeek }) => {
  const goodPoints = [
    '手の動きが全体的に滑らか',
    '基本姿勢が安定している',
    '器具の持ち方が適切',
    '仕上げ段階の精度が高い'
  ];

  const improvements = [
    { time: '1:45-2:00', description: '速度が不安定' },
    { description: '左手の協調性が基準より低い' },
    { description: '器具切替時に無駄な動きがある' },
    { description: '手首の回転角度が大きすぎる' }
  ];

  const suggestions = [
    '基礎動作を毎日10分反復練習',
    '左手単独での器具操作訓練',
    '0.5倍速でのスローモーション練習',
    'Phase 2の区間を重点的に練習'
  ];

  const timeRangeIssues: TimeRangeIssue[] = [
    {
      timeRange: '1:45-2:00',
      startTime: 105,
      endTime: 120,
      description: '速度の変動が大きい（基準との差: 25mm/s）',
      severity: 'high',
      metric: '速度'
    },
    {
      timeRange: '2:30-2:45',
      startTime: 150,
      endTime: 165,
      description: '左右の手の正確性低下（正確率: 65%）',
      severity: 'medium',
      metric: '正確性'
    }
  ];

  const handleTimeRangeClick = (issue: TimeRangeIssue) => {
    onSeek(issue.startTime);
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="bg-white rounded-lg shadow-sm p-6"
    >
      <h3 className="font-semibold mb-4">🤖 AI分析による詳細フィードバック</h3>

      {/* フィードバックカード */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {/* 良い点 */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
          className="bg-green-50 rounded-lg p-4 border border-green-200"
        >
          <h4 className="font-medium text-green-800 mb-3 flex items-center">
            <CheckCircle size={18} className="mr-2" />
            良い点
          </h4>
          <ul className="space-y-2 text-sm text-green-700">
            {goodPoints.map((point, index) => (
              <motion.li
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + index * 0.1 }}
                className="flex items-start"
              >
                <span className="mr-2">•</span>
                <span>{point}</span>
              </motion.li>
            ))}
          </ul>
        </motion.div>

        {/* 改善点 */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.6 }}
          className="bg-yellow-50 rounded-lg p-4 border border-yellow-200"
        >
          <h4 className="font-medium text-yellow-800 mb-3 flex items-center">
            <AlertCircle size={18} className="mr-2" />
            改善点
          </h4>
          <ul className="space-y-2 text-sm text-yellow-700">
            {improvements.map((item, index) => (
              <motion.li
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.7 + index * 0.1 }}
                className="flex items-start"
              >
                <span className="mr-2">•</span>
                <span>
                  {item.time && <strong>{item.time}</strong>} {item.description}
                </span>
              </motion.li>
            ))}
          </ul>
        </motion.div>

        {/* 練習提案 */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.7 }}
          className="bg-blue-50 rounded-lg p-4 border border-blue-200"
        >
          <h4 className="font-medium text-blue-800 mb-3 flex items-center">
            <Lightbulb size={18} className="mr-2" />
            練習提案
          </h4>
          <ul className="space-y-2 text-sm text-blue-700">
            {suggestions.map((suggestion, index) => (
              <motion.li
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.8 + index * 0.1 }}
                className="flex items-start"
              >
                <span className="mr-2">{index + 1}.</span>
                <span>{suggestion}</span>
              </motion.li>
            ))}
          </ul>
        </motion.div>
      </div>

      {/* 具体的な改善箇所 */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h4 className="font-medium text-gray-800 mb-3">🎯 特に注意すべき時間帯</h4>
        <div className="space-y-2">
          {timeRangeIssues.map((issue, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.9 + index * 0.1 }}
              className={`flex items-center justify-between p-2 bg-white rounded border-l-4 ${
                issue.severity === 'high' ? 'border-red-500' :
                issue.severity === 'medium' ? 'border-yellow-500' :
                'border-blue-500'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-mono">{issue.timeRange}</span>
                <span className="text-sm">{issue.description}</span>
              </div>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => handleTimeRangeClick(issue)}
                className={`text-sm px-2 py-1 rounded hover:opacity-80 transition flex items-center gap-1 ${
                  issue.severity === 'high' ? 'bg-red-100 text-red-700' :
                  issue.severity === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-blue-100 text-blue-700'
                }`}
              >
                <PlayCircle size={14} />
                この区間を再生
              </motion.button>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.section>
  );
};

export default AIFeedback;