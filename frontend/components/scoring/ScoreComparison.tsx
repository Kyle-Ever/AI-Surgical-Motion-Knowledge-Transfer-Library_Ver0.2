'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Zap, Activity, Scale, TrendingUp } from 'lucide-react';

interface ScoreData {
  value: number;
  reference: number;
  diff: number;
}

interface ScoreComparisonProps {
  scores: {
    total: ScoreData;
    speed: ScoreData;
    smoothness: ScoreData;
    stability: ScoreData;
  };
}

const ScoreCard: React.FC<{
  title: string;
  icon: React.ReactNode;
  score: ScoreData;
  color: string;
  delay?: number;
}> = ({ title, icon, score, color, delay = 0 }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay }}
      whileHover={{ scale: 1.02, boxShadow: '0 10px 30px rgba(0,0,0,0.1)' }}
      className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition cursor-pointer"
    >
      <h3 className="text-sm font-medium text-gray-600 mb-2 flex items-center gap-2">
        {icon}
        {title}
      </h3>
      <div className={`text-3xl font-bold ${color}`}>{score.value.toFixed(1)}</div>
      <div className="text-xs text-gray-500 mt-1">
        基準: {score.reference.toFixed(1)} (差: {score.diff > 0 ? '+' : ''}{score.diff.toFixed(1)})
      </div>
      <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score.value}%` }}
          transition={{ duration: 1, delay: delay + 0.3 }}
          className={`h-full bg-gradient-to-r ${
            title === '総合スコア' ? 'from-purple-400 to-purple-600' :
            title === '速度' ? 'from-blue-400 to-blue-600' :
            title === '滑らかさ' ? 'from-green-400 to-green-600' :
            'from-yellow-400 to-yellow-600'
          }`}
        />
      </div>
    </motion.div>
  );
};

const ScoreComparison: React.FC<ScoreComparisonProps> = ({ scores }) => {
  return (
    <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <ScoreCard
        title="総合スコア"
        icon={<TrendingUp size={16} />}
        score={scores.total}
        color="text-purple-600"
        delay={0}
      />
      <ScoreCard
        title="速度"
        icon={<Zap size={16} />}
        score={scores.speed}
        color="text-blue-600"
        delay={0.1}
      />
      <ScoreCard
        title="滑らかさ"
        icon={<Activity size={16} />}
        score={scores.smoothness}
        color="text-green-600"
        delay={0.2}
      />
      <ScoreCard
        title="安定性"
        icon={<Scale size={16} />}
        score={scores.stability}
        color="text-yellow-600"
        delay={0.3}
      />
    </section>
  );
};

export default ScoreComparison;