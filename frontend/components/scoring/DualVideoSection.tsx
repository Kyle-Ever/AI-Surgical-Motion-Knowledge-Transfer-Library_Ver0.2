'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';
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
  console.log(`[VideoPlayer ${isReference ? 'REF' : 'EVAL'}] Component rendering with videoUrl:`, data.videoUrl);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [localTime, setLocalTime] = useState(0);
  const [localDuration, setLocalDuration] = useState(0);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [videoError, setVideoError] = useState<string | null>(null);

  // RVFC/RAF用のRef
  const rvfcHandleRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastDrawnFrameRef = useRef<number>(-1);

  // 現在のタイムスタンプに最も近い骨格データを取得
  const getCurrentData = useCallback((timestamp: number) => {
    const tolerance = 0.016; // 16ms = 約半フレーム

    if (!data.skeletonData || data.skeletonData.length === 0) {
      return null;
    }

    // 最も近いフレームを探す
    let closestFrame = data.skeletonData.find(
      frame => Math.abs(frame.timestamp - timestamp) < tolerance
    );

    // 見つからない場合は最近傍
    if (!closestFrame) {
      closestFrame = data.skeletonData.reduce((prev, curr) => {
        const prevDiff = Math.abs(prev.timestamp - timestamp);
        const currDiff = Math.abs(curr.timestamp - timestamp);
        return currDiff < prevDiff ? curr : prev;
      });
    }

    return closestFrame;
  }, [data.skeletonData]);

  // 指定されたタイムスタンプで骨格を描画
  const drawOverlayAtTime = useCallback((timestamp: number) => {
    console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Called at timestamp:`, timestamp);

    if (!videoRef.current || !canvasRef.current) {
      console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Missing refs`);
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] No context`);
      return;
    }

    const video = videoRef.current;

    // フレームスキップ最適化
    const fps = data.fps || 30;
    const currentFrameNum = Math.floor(timestamp * fps);
    if (currentFrameNum === lastDrawnFrameRef.current && !isPlaying) {
      console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Frame skip - already drawn frame ${currentFrameNum}`);
      return;
    }
    lastDrawnFrameRef.current = currentFrameNum;

    // Canvasサイズをビデオサイズに合わせる
    if (video.videoWidth && video.videoHeight) {
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Resized canvas to ${canvas.width}x${canvas.height}`);
      }
    }

    // クリア
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] showSkeleton=${showSkeleton}, skeletonData.length=${data.skeletonData?.length || 0}`);

    if (!showSkeleton || !data.skeletonData || data.skeletonData.length === 0) {
      console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Early return - conditions not met`);
      return;
    }

    // 現在のタイムスタンプに最も近い骨格フレームを取得
    const skeletonFrame = getCurrentData(timestamp);
    console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Got skeleton frame:`, !!skeletonFrame);
    if (!skeletonFrame) return;

    // 新形式: frame.hands配列（複数手対応）
    const hands = skeletonFrame.hands || [skeletonFrame]; // 旧形式との互換性
    console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Processing ${hands.length} hands`);

    hands.forEach((hand: any, handIndex: number) => {
      console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Hand ${handIndex}:`, hand);
      console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Hand landmarks type:`, typeof hand?.landmarks, 'isArray:', Array.isArray(hand?.landmarks));

      if (!hand?.landmarks) {
        console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Hand ${handIndex} has no landmarks`);
        return;
      }

      // landmarksの形式を統一（配列形式に変換）
      const landmarks = Array.isArray(hand.landmarks)
        ? hand.landmarks
        : Object.values(hand.landmarks);

      if (landmarks.length === 0) {
        console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Hand ${handIndex} has empty landmarks`);
        return;
      }

      console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Hand ${handIndex} drawing ${landmarks.length} landmarks`);

      // 座標が正規化されているか確認（0-1の範囲か、それともピクセル値か）
      const firstLandmark = landmarks[0];
      const isNormalized = firstLandmark.x <= 1.0 && firstLandmark.y <= 1.0;

      // 正規化されていない場合（ピクセル座標）、動画サイズで正規化
      const normalizeCoord = (x: number, y: number) => {
        if (isNormalized) {
          return { x, y };
        } else {
          // ピクセル座標を0-1の範囲に正規化
          return {
            x: x / video.videoWidth,
            y: y / video.videoHeight
          };
        }
      };

      console.log(`[drawOverlay ${isReference ? 'REF' : 'EVAL'}] Coordinates ${isNormalized ? 'normalized' : 'pixel-based'}, first point: (${firstLandmark.x}, ${firstLandmark.y})`);

      const isLeftHand = hand.hand_type === 'Left';
      const handColor = isLeftHand ? (isReference ? '#10b981' : '#3b82f6') : (isReference ? '#059669' : '#1e40af');
      const pointColor = isLeftHand ? (isReference ? '#10b981' : '#3b82f6') : (isReference ? '#ff0000' : '#1e40af');

      // 線を描画
      ctx.strokeStyle = handColor;
      ctx.lineWidth = 2;

      const connections = [
        [0, 1], [1, 2], [2, 3], [3, 4],  // 親指
        [0, 5], [5, 6], [6, 7], [7, 8],  // 人差し指
        [0, 9], [9, 10], [10, 11], [11, 12],  // 中指
        [0, 13], [13, 14], [14, 15], [15, 16],  // 薬指
        [0, 17], [17, 18], [18, 19], [19, 20],  // 小指
        [5, 9], [9, 13], [13, 17]  // 手のひら
      ];

      connections.forEach(([startIdx, endIdx]) => {
        const startPoint = landmarks[startIdx];
        const endPoint = landmarks[endIdx];

        if (startPoint && endPoint && startPoint.x !== undefined && endPoint.x !== undefined) {
          const startNorm = normalizeCoord(startPoint.x, startPoint.y);
          const endNorm = normalizeCoord(endPoint.x, endPoint.y);

          ctx.beginPath();
          ctx.moveTo(startNorm.x * canvas.width, startNorm.y * canvas.height);
          ctx.lineTo(endNorm.x * canvas.width, endNorm.y * canvas.height);
          ctx.stroke();
        }
      });

      // 点を描画
      ctx.fillStyle = pointColor;
      landmarks.forEach((point: any) => {
        if (point && typeof point === 'object' && point.x !== undefined && point.y !== undefined) {
          const normalized = normalizeCoord(point.x, point.y);

          ctx.beginPath();
          ctx.arc(normalized.x * canvas.width, normalized.y * canvas.height, 3, 0, 2 * Math.PI);
          ctx.fill();
        }
      });

      // 手のタイプラベル表示
      const wrist = landmarks[0];
      if (wrist) {
        const wristNorm = normalizeCoord(wrist.x, wrist.y);
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.font = '12px Arial';
        ctx.fillText(hand.hand_type || 'Unknown', wristNorm.x * canvas.width, wristNorm.y * canvas.height - 10);
      }
    });
  }, [showSkeleton, data.skeletonData, data.fps, isReference, isPlaying, getCurrentData]);

  // 次のフレーム描画をスケジュール（RVFC優先、フォールバックRAF）
  const scheduleNextFrame = useCallback(() => {
    if (!videoRef.current || !isPlaying) return;

    const video = videoRef.current;

    // RVFC対応ブラウザ: ビデオフレームと完全同期
    if ('requestVideoFrameCallback' in video) {
      rvfcHandleRef.current = (video as any).requestVideoFrameCallback((now: number, metadata: any) => {
        drawOverlayAtTime(metadata.mediaTime);

        // 再生中なら次のフレームをスケジュール
        if (isPlaying) {
          scheduleNextFrame();
        }
      });
    }
    // フォールバック: RAF（Firefox等、RVFC非対応ブラウザ）
    else {
      animationFrameRef.current = requestAnimationFrame(() => {
        if (videoRef.current) {
          drawOverlayAtTime(videoRef.current.currentTime);

          if (isPlaying) {
            scheduleNextFrame();
          }
        }
      });
    }
  }, [isPlaying, drawOverlayAtTime]);

  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current) return;
    const time = videoRef.current.currentTime;
    setLocalTime(time);

    // 外部にも通知
    if (isReference && onTimeUpdate) {
      onTimeUpdate(time);
    }

    // フレーム番号を更新
    const fps = data.fps || 30;
    const frameNumber = Math.floor(time * fps);
    setCurrentFrame(frameNumber);

    // 一時停止中のみ描画（再生中はRVFC/RAFで自動描画）
    if (!isPlaying) {
      drawOverlayAtTime(time);
    }
  }, [isPlaying, drawOverlayAtTime, isReference, onTimeUpdate, data.fps]);

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const duration = videoRef.current.duration;
      setLocalDuration(duration);
      if (isReference && onDurationChange) {
        onDurationChange(duration);
      }
    }
  };

  // useEffects - 関数定義の後に配置
  // videoUrl変更時にエラーをリセット
  useEffect(() => {
    console.log(`[DualVideoSection ${isReference ? 'REF' : 'EVAL'}] Resetting videoError for URL:`, data.videoUrl);
    setVideoError(null);
  }, [data.videoUrl, isReference]);

  // Canvas初期化: videoのメタデータ読み込み後にCanvasサイズを設定
  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas) return;

    const handleLoadedMetadata = () => {
      if (video.videoWidth && video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        console.log(`[Canvas ${isReference ? 'REF' : 'EVAL'}] Initialized to ${canvas.width}x${canvas.height}`);
      }
    };

    // すでにメタデータが読み込まれている場合
    if (video.readyState >= 1) {
      handleLoadedMetadata();
    }

    // メタデータ読み込みイベントをリスン
    video.addEventListener('loadedmetadata', handleLoadedMetadata);

    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, [data.videoUrl, isReference]);

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

  // skeletonData変更時に再描画
  useEffect(() => {
    if (data.skeletonData && canvasRef.current && videoRef.current) {
      drawOverlayAtTime(videoRef.current.currentTime);
    }
  }, [data.skeletonData, drawOverlayAtTime]);

  // 再生/停止時のRVFC/RAFスケジュール管理
  useEffect(() => {
    if (isPlaying) {
      // 再生開始 - フレーム描画をスケジュール
      scheduleNextFrame();
    }

    // クリーンアップ: コンポーネントアンマウント時やisPlaying変化時
    return () => {
      if (rvfcHandleRef.current && videoRef.current && 'cancelVideoFrameCallback' in videoRef.current) {
        (videoRef.current as any).cancelVideoFrameCallback(rvfcHandleRef.current);
        rvfcHandleRef.current = null;
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [isPlaying, scheduleNextFrame]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progressPercentage = localDuration > 0 ? (localTime / localDuration) * 100 : 0;

  // videoUrlが空の場合のエラーチェック
  if (!data.videoUrl) {
    return (
      <div className="bg-white rounded-lg shadow-sm">
        <div className={`px-4 py-3 border-b ${isReference ? 'bg-green-50' : 'bg-blue-50'}`}>
          <h2 className={`font-semibold ${isReference ? 'text-green-800' : 'text-blue-800'} flex items-center`}>
            <span className={`w-2 h-2 ${isReference ? 'bg-green-500' : 'bg-blue-500'} rounded-full mr-2`}></span>
            {data.title}
          </h2>
        </div>
        <div className="p-4">
          <div className="relative aspect-video rounded-lg overflow-hidden bg-gray-900 flex items-center justify-center text-white">
            <div className="text-center p-8">
              <div className="text-6xl mb-4">⚠️</div>
              <h3 className="text-xl font-semibold mb-2">動画URLが見つかりません</h3>
              <p className="text-sm text-gray-400">動画データの読み込みに失敗しました</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

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
              key={data.videoUrl}
              ref={videoRef}
              className="w-full h-full object-cover"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onError={(e) => {
                const target = e.target as HTMLVideoElement;
                console.error(`[VideoPlayer ${isReference ? 'REF' : 'EVAL'}] Video load error:`, {
                  videoUrl: data.videoUrl,
                  error: e,
                  networkState: target.networkState,
                  readyState: target.readyState,
                  currentSrc: target.currentSrc
                });
                setVideoError(`動画の読み込みに失敗しました (${isReference ? '基準' : '評価'}動画): ${data.videoUrl}`);
              }}
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