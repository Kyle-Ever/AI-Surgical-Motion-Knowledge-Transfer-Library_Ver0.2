'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, Download, Play, Pause, SkipForward, Repeat, Settings } from 'lucide-react';
import Link from 'next/link';
import DualVideoSection from '@/components/scoring/DualVideoSection';
import SyncControlBar from '@/components/scoring/SyncControlBar';
import ScoreComparison from '@/components/scoring/ScoreComparison';
import DetailedAnalysis from '@/components/scoring/DetailedAnalysis';
import AIFeedback from '@/components/scoring/AIFeedback';
import Trajectory3D from '@/components/scoring/Trajectory3D';

export default function ComparisonDashboard() {
  const searchParams = useSearchParams();
  const comparisonId = searchParams.get('id');

  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showSkeleton, setShowSkeleton] = useState(true);
  const [showTrajectory, setShowTrajectory] = useState(true);
  const [useDTW, setUseDTW] = useState(true);

  // モックデータ（後でAPIから取得）
  const comparisonData = {
    reference: {
      title: '基準動作（指導医）',
      performer: 'Dr. 田中太郎',
      procedure: '腹腔鏡下胆嚢摘出術',
      date: '2024/12/01',
      videoUrl: '/api/v1/videos/reference/1',
      detectionRate: 98.5,
      fps: 30
    },
    evaluation: {
      title: '評価動作（学習者）',
      performer: '研修医 山田花子',
      procedure: '腹腔鏡下胆嚢摘出術',
      date: '2024/12/27',
      videoUrl: '/api/v1/videos/evaluation/2',
      detectionRate: 95.2,
      fps: 30
    },
    scores: {
      total: { value: 85.3, reference: 92.0, diff: -6.7 },
      speed: { value: 78.5, reference: 90.0, diff: -11.5 },
      smoothness: { value: 92.1, reference: 94.0, diff: -1.9 },
      stability: { value: 85.7, reference: 93.0, diff: -7.3 }
    }
  };

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
  };

  const handleExportPDF = async () => {
    // PDF出力機能の実装
    console.log('Exporting PDF...');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ヘッダー */}
      <header className="bg-white shadow-sm border-b px-6 py-4">
        <div className="max-w-[1920px] mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">採点比較ダッシュボード</h1>
            <p className="text-sm text-gray-600 mt-1">基準動作との詳細比較</p>
          </div>
          <div className="flex gap-3">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleExportPDF}
              className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition flex items-center gap-2"
            >
              <Download size={16} />
              レポート出力
            </motion.button>
            <Link href="/scoring">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition flex items-center gap-2"
              >
                <ArrowLeft size={16} />
                採点モードへ戻る
              </motion.button>
            </Link>
          </div>
        </div>
      </header>

      {/* メインコンテンツ */}
      <main className="max-w-[1920px] mx-auto p-6 space-y-6">
        {/* デュアルビデオセクション */}
        <DualVideoSection
          referenceData={comparisonData.reference}
          evaluationData={comparisonData.evaluation}
          isPlaying={isPlaying}
          currentTime={currentTime}
          duration={duration}
          showSkeleton={showSkeleton}
          showTrajectory={showTrajectory}
          onTimeUpdate={setCurrentTime}
          onDurationChange={setDuration}
        />

        {/* 同期コントロールバー */}
        <SyncControlBar
          isPlaying={isPlaying}
          playbackSpeed={playbackSpeed}
          useDTW={useDTW}
          onPlayPause={handlePlayPause}
          onSpeedChange={handleSpeedChange}
          onDTWToggle={() => setUseDTW(!useDTW)}
          onSkeletonToggle={() => setShowSkeleton(!showSkeleton)}
          onTrajectoryToggle={() => setShowTrajectory(!showTrajectory)}
        />

        {/* スコア比較セクション */}
        <ScoreComparison scores={comparisonData.scores} />

        {/* 詳細分析セクション */}
        <DetailedAnalysis
          comparisonId={comparisonId}
          currentTime={currentTime}
          onSeek={setCurrentTime}
        />

        {/* AIフィードバックセクション */}
        <AIFeedback
          comparisonId={comparisonId}
          onSeek={setCurrentTime}
        />

        {/* 3D軌跡比較 */}
        <Trajectory3D
          comparisonId={comparisonId}
          showReference={true}
          showEvaluation={true}
        />
      </main>

      {/* フッター */}
      <footer className="bg-white border-t mt-12 py-4">
        <div className="max-w-[1920px] mx-auto px-6 text-center text-sm text-gray-600">
          AI Surgical Motion Knowledge Transfer Library - 採点比較モード v0.2
        </div>
      </footer>
    </div>
  );
}