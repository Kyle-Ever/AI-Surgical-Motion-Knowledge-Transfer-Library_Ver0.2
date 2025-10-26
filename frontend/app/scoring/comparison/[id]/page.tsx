'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, Download, Play, Pause, SkipForward, Repeat, Settings } from 'lucide-react';
import Link from 'next/link';
import DualVideoSection from '@/components/scoring/DualVideoSection';
import SyncControlBar from '@/components/scoring/SyncControlBar';
import ScoreComparison from '@/components/scoring/ScoreComparison';
import DetailedAnalysis from '@/components/scoring/DetailedAnalysis';
import AIFeedback from '@/components/scoring/AIFeedback';
import { useComparisonResult } from '@/hooks/useScoring';

export default function ComparisonDashboard() {
  const params = useParams();
  const comparisonId = params.id as string;

  // APIから比較結果を取得
  const { result, isLoading, error } = useComparisonResult(comparisonId);

  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showSkeleton, setShowSkeleton] = useState(true);
  const [useDTW, setUseDTW] = useState(true);

  // comparisonData を useMemo でメモ化（result が変更されたときのみ再計算）
  // IMPORTANT: React Hooks のルールにより、フックは条件分岐の前に呼び出す必要がある
  const comparisonData = React.useMemo(() => {
    if (!result) return null;

    const referenceVideoId = result.reference_video_id || result.reference_analysis?.video_id || result.reference_model?.analysis_result?.video_id;
    const evaluationVideoId = result.learner_video_id || result.learner_analysis?.video_id || result.evaluation_video_id;
    const referenceAnalysis = result.reference_analysis || null;
    const evaluationAnalysis = result.learner_analysis || null;

    console.log('[comparisonData MEMO] Recalculating with result:', !!result);
    console.log('[comparisonData MEMO] referenceVideoId:', referenceVideoId);
    console.log('[comparisonData MEMO] evaluationVideoId:', evaluationVideoId);

    return {
      reference: {
        title: '基準動作（指導医）',
        performer: result.reference_video?.performer_name || result.reference_model?.surgeon_name || 'Dr. 田中太郎',
        procedure: result.reference_video?.procedure_name || result.reference_model?.surgery_type || '腹腔鏡下胆嚢摘出術',
        date: result.reference_video?.created_at ? new Date(result.reference_video.created_at).toLocaleDateString('ja-JP') : '2024/12/01',
        videoUrl: referenceVideoId ? `/api/v1/videos/${referenceVideoId}/stream` : '',
        detectionRate: 98.5,
        fps: 30,
        skeletonData: referenceAnalysis?.skeleton_data || result.reference_analysis?.skeleton_data || []
      },
      evaluation: {
        title: '評価動作（学習者）',
        performer: result.evaluation_video?.performer_name || result.learner_analysis?.surgeon_name || '研修医 山田花子',
        procedure: result.evaluation_video?.procedure_name || result.learner_analysis?.surgery_type || '腹腔鏡下胆嚢摘出術',
        date: result.evaluation_video?.created_at ? new Date(result.evaluation_video.created_at).toLocaleDateString('ja-JP') : '2024/12/27',
        videoUrl: evaluationVideoId ? `/api/v1/videos/${evaluationVideoId}/stream` : '',
        detectionRate: 95.2,
        fps: 30,
        skeletonData: evaluationAnalysis?.skeleton_data || result.learner_analysis?.skeleton_data || []
      },
      scores: {
        total: {
          value: result.overall_score || 85.3,
          reference: 92.0,
          diff: (result.overall_score || 85.3) - 92.0
        },
        speed: {
          value: result.speed_score || 78.5,
          reference: 90.0,
          diff: (result.speed_score || 78.5) - 90.0
        },
        smoothness: {
          value: result.smoothness_score || 92.1,
          reference: 94.0,
          diff: (result.smoothness_score || 92.1) - 94.0
        },
        stability: {
          value: result.stability_score || 85.7,
          reference: 93.0,
          diff: (result.stability_score || 85.7) - 93.0
        }
      },
      // DetailedAnalysis コンポーネント用に analysis データも含める
      referenceAnalysis,
      evaluationAnalysis
    };
  }, [result]);

  // 早期リターン: データ読み込み中またはデータなし
  if (isLoading || !result || !comparisonData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">比較データを読み込み中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md p-8 bg-white rounded-lg shadow">
          <div className="text-6xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">エラーが発生しました</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <Link href="/scoring" className="inline-block px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors">
            スコアリング画面に戻る
          </Link>
        </div>
      </div>
    );
  }

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
  };

  const handleExportPDF = async () => {
    // PDF出力機能の実装
    console.log('Exporting PDF...');
    // 将来的にはreact-pdfを使用して実装
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
            <Link href={`/scoring/result/${comparisonId}`}>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition flex items-center gap-2"
              >
                <ArrowLeft size={16} />
                結果ページへ戻る
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
        />

        {/* スコア比較セクション */}
        <ScoreComparison scores={comparisonData.scores} />

        {/* 詳細分析セクション */}
        <DetailedAnalysis
          comparisonId={comparisonId}
          currentTime={currentTime}
          onSeek={setCurrentTime}
          referenceAnalysis={comparisonData.referenceAnalysis}
          evaluationAnalysis={comparisonData.evaluationAnalysis}
          isAnalyzing={false}
        />

        {/* AIフィードバックセクション */}
        <AIFeedback
          comparisonId={comparisonId}
          onSeek={setCurrentTime}
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