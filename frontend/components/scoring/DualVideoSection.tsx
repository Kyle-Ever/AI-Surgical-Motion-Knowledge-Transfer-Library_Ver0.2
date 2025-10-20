'use client';

import React, { useRef, useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface VideoData {
  title: string;
  performer: string;
  procedure: string;
  date: string;
  videoUrl: string;
  detectionRate: number;
  fps: number;
  skeletonData?: any[];
}

interface DualVideoSectionProps {
  referenceData: VideoData;
  evaluationData: VideoData;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  showSkeleton: boolean;
  onTimeUpdate: (time: number) => void;
  onDurationChange: (duration: number) => void;
}

const VideoPlayer: React.FC<{
  data: VideoData;
  isReference: boolean;
  isPlaying: boolean;
  currentTime: number;
  showSkeleton: boolean;
  onTimeUpdate?: (time: number) => void;
  onDurationChange?: (duration: number) => void;
}> = ({ data, isReference, isPlaying, currentTime, showSkeleton, onTimeUpdate, onDurationChange }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [localTime, setLocalTime] = useState(0);
  const [localDuration, setLocalDuration] = useState(0);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [videoError, setVideoError] = useState<string | null>(null);

  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play();
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);

  useEffect(() => {
    if (videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 0.1) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const time = videoRef.current.currentTime;
      setLocalTime(time);
      if (isReference && onTimeUpdate) {
        onTimeUpdate(time);
      }
      // フレーム番号を計算
      const fps = data.fps || 30;
      const frameNumber = Math.floor(time * fps);
      setCurrentFrame(frameNumber);

      // 骨格データを描画
      if (showSkeleton && data.skeletonData && canvasRef.current) {
        drawSkeleton(frameNumber);
      }
    }
  };

  const drawSkeleton = (frameNumber: number) => {
    const canvas = canvasRef.current;
    if (!canvas || !videoRef.current) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Canvasサイズをビデオサイズに合わせる
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;

    // クリア
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!data.skeletonData || data.skeletonData.length === 0) return;

    // 現在のフレームの骨格データを取得（最近傍探索・複数手対応）
    // バックエンドは5fps、フロントは30fpsなので、最も近いフレームを探す
    const currentTime = frameNumber / (data.fps || 30); // 現在の時刻を秒で計算
    let matchedFrames: any[] = [];

    // タイムスタンプベースで同時刻の全フレームを収集（両手対応）
    if (data.skeletonData && data.skeletonData.length > 0) {
      // 0.2秒以内（5fpsの1フレーム分）のすべてのデータを収集
      const timeWindow = 0.2;

      // 手のタイプごとに最も近いフレームを1つだけ選択（重複除去）
      const handTypeFrames: { [key: string]: any } = {};

      for (const frame of data.skeletonData) {
        const diff = Math.abs(frame.timestamp - currentTime);
        if (diff <= timeWindow) {
          const handType = frame.hand_type || 'Unknown';

          // この手のタイプの既存フレームがない、またはより近いフレームの場合のみ保存
          if (!handTypeFrames[handType] ||
              Math.abs(frame.timestamp - currentTime) < Math.abs(handTypeFrames[handType].timestamp - currentTime)) {
            handTypeFrames[handType] = frame;
          }
        }
      }

      // オブジェクトから配列に変換
      matchedFrames = Object.values(handTypeFrames);

      if (matchedFrames.length === 0) {
        console.log(`[DualVideoSection] No frames within ${timeWindow}s for ${isReference ? 'reference' : 'evaluation'} at time ${currentTime}`);
        return;
      } else {
        console.log(`[DualVideoSection] Found ${matchedFrames.length} unique hand(s) for time ${currentTime}`);
      }
    }

    if (matchedFrames.length === 0) return;

    // すべての手のランドマークを描画（両手対応）
    matchedFrames.forEach((frameData, index) => {
      if (frameData.landmarks) {
        const landmarks = frameData.landmarks;
        const handType = frameData.hand_type || 'Unknown';

        // 手ごとに色を変える（左手: 緑系、右手: 青系）
        if (handType === 'Left') {
          ctx.fillStyle = isReference ? '#10b981' : '#3b82f6';
        } else if (handType === 'Right') {
          ctx.fillStyle = isReference ? '#059669' : '#1e40af';
        } else {
          ctx.fillStyle = isReference ? '#10b981' : '#3b82f6';
        }

        // ポイントを描画
        Object.values(landmarks).forEach((point: any) => {
          if (point && typeof point === 'object' && 'x' in point && 'y' in point) {
            const x = point.x * canvas.width;
            const y = point.y * canvas.height;
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, 2 * Math.PI);
            ctx.fill();
          }
        });

        // デバッグ: 手のタイプを表示
        if (frameData.landmarks.point_0) {
          const wrist = frameData.landmarks.point_0;
          ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
          ctx.font = '12px Arial';
          ctx.fillText(handType, wrist.x * canvas.width, wrist.y * canvas.height - 10);
        }
      }

    });

      // 手のコネクション（線の描画）
      matchedFrames.forEach((frameData) => {
        if (frameData.landmarks) {
          const landmarks = frameData.landmarks;
          const handType = frameData.hand_type || 'Unknown';

          // 手ごとに線の色を設定
          if (handType === 'Left') {
            ctx.strokeStyle = isReference ? '#10b981' : '#3b82f6';
          } else if (handType === 'Right') {
            ctx.strokeStyle = isReference ? '#059669' : '#1e40af';
          } else {
            ctx.strokeStyle = isReference ? '#10b981' : '#3b82f6';
          }
          ctx.lineWidth = 2;

          const connections = [
            [0, 1], [1, 2], [2, 3], [3, 4],  // 親指
            [0, 5], [5, 6], [6, 7], [7, 8],  // 人差し指
            [0, 9], [9, 10], [10, 11], [11, 12],  // 中指
            [0, 13], [13, 14], [14, 15], [15, 16],  // 薬指
            [0, 17], [17, 18], [18, 19], [19, 20],  // 小指
            [5, 9], [9, 13], [13, 17]  // 手のひら
          ];

          connections.forEach(([start, end]) => {
            const startPoint = landmarks[`point_${start}`];
            const endPoint = landmarks[`point_${end}`];
            if (startPoint && endPoint) {
              ctx.beginPath();
              ctx.moveTo(startPoint.x * canvas.width, startPoint.y * canvas.height);
              ctx.lineTo(endPoint.x * canvas.width, endPoint.y * canvas.height);
              ctx.stroke();
            }
          });
        }
      });
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const duration = videoRef.current.duration;
      setLocalDuration(duration);
      if (isReference && onDurationChange) {
        onDurationChange(duration);
      }
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progressPercentage = localDuration > 0 ? (localTime / localDuration) * 100 : 0;

  return (
    <div className="bg-white rounded-lg shadow-sm">
      <div className={`px-4 py-3 border-b ${isReference ? 'bg-green-50' : 'bg-blue-50'}`}>
        <h2 className={`font-semibold ${isReference ? 'text-green-800' : 'text-blue-800'} flex items-center`}>
          <span className={`w-2 h-2 ${isReference ? 'bg-green-500' : 'bg-blue-500'} rounded-full mr-2 animate-pulse`}></span>
          {data.title}
        </h2>
        <p className="text-sm text-gray-600">
          {data.performer} - {data.procedure} - {data.date}
        </p>
      </div>
      <div className="p-4">
        {/* ビデオプレーヤー */}
        <div className="relative aspect-video rounded-lg overflow-hidden bg-black mb-3">
          {videoError ? (
            <div className="w-full h-full flex items-center justify-center bg-gray-900 text-white">
              <div className="text-center p-8">
                <div className="text-6xl mb-4">⚠️</div>
                <h3 className="text-xl font-semibold mb-2">動画ファイルが見つかりません</h3>
                <p className="text-sm text-gray-400 mb-4">{videoError}</p>
                <p className="text-xs text-gray-500">
                  この動画ファイルはデータベースに登録されていますが、<br />
                  サーバー上に実際のファイルが存在しません。
                </p>
              </div>
            </div>
          ) : (
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onError={(e) => {
                console.error('[VideoPlayer] Video load error:', e);
                setVideoError(`動画の読み込みに失敗しました (${isReference ? '基準' : '評価'}動画)`);
              }}
              poster={`https://via.placeholder.com/640x360/${isReference ? '22c55e' : '3b82f6'}/ffffff?text=${isReference ? '基準動画' : '評価動画'}`}
            >
              <source src={data.videoUrl} type="video/mp4" />
            </video>
          )}

          {/* オーバーレイCanvas（手技検出/軌跡表示用） */}
          {showSkeleton && <canvas ref={canvasRef} className="absolute top-0 left-0 w-full h-full pointer-events-none" />}

          {/* オーバーレイコントロール */}
          <div className="absolute top-2 right-2 flex gap-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`px-2 py-1 ${showSkeleton ? 'bg-green-600' : 'bg-black/70'} text-white text-xs rounded hover:bg-opacity-90 transition`}
            >
              ✋ 手技検出 {showSkeleton ? 'ON' : 'OFF'}
            </motion.button>
          </div>

          {/* 検出情報オーバーレイ */}
          <div className="absolute bottom-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
            手の検出: {data.detectionRate}% | FPS: {data.fps}
          </div>
        </div>

        {/* 再生コントロール */}
        <div className="flex items-center gap-3">
          <button className="p-2 bg-gray-100 rounded hover:bg-gray-200 transition">
            {isPlaying ? '⏸️' : '▶️'}
          </button>
          <div className="flex-1 bg-gray-200 rounded-full h-2 relative">
            <div
              className={`absolute h-full ${isReference ? 'bg-green-500' : 'bg-blue-500'} rounded-full transition-all`}
              style={{ width: `${progressPercentage}%` }}
            />
            <div
              className={`absolute w-3 h-3 bg-white border-2 ${isReference ? 'border-green-500' : 'border-blue-500'} rounded-full`}
              style={{ left: `${progressPercentage}%`, top: '-2px', transform: 'translateX(-50%)' }}
            />
          </div>
          <span className="text-sm text-gray-600 font-mono">
            {formatTime(localTime)} / {formatTime(localDuration)}
          </span>
        </div>
      </div>
    </div>
  );
};

const DualVideoSection: React.FC<DualVideoSectionProps> = ({
  referenceData,
  evaluationData,
  isPlaying,
  currentTime,
  duration,
  showSkeleton,
  onTimeUpdate,
  onDurationChange
}) => {
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid grid-cols-1 lg:grid-cols-2 gap-4"
    >
      {/* 左側：基準動画 */}
      <VideoPlayer
        data={referenceData}
        isReference={true}
        isPlaying={isPlaying}
        currentTime={currentTime}
        showSkeleton={showSkeleton}
        onTimeUpdate={onTimeUpdate}
        onDurationChange={onDurationChange}
      />

      {/* 右側：評価動画 */}
      <VideoPlayer
        data={evaluationData}
        isReference={false}
        isPlaying={isPlaying}
        currentTime={currentTime}
        showSkeleton={showSkeleton}
      />
    </motion.section>
  );
};

export default DualVideoSection;