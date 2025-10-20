"""
Frame Extraction Service

フレーム抽出の専用サービス。以下の問題を解決:
1. int()切り捨てによるframe_skip計算の問題 → round()使用
2. cv2.read()失敗時のリトライ機構がない → 最大3回リトライ
3. 連続失敗時の早期停止がない → 10回連続失敗で停止
4. 抽出成功率の検証がない → 50%未満でエラー
"""

import cv2
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """動画のメタデータ"""
    width: int
    height: int
    fps: float
    total_frames: int
    duration: float
    codec: str

    def __str__(self) -> str:
        return (f"VideoMetadata(size={self.width}x{self.height}, "
                f"fps={self.fps:.2f}, frames={self.total_frames}, "
                f"duration={self.duration:.2f}s, codec={self.codec})")


@dataclass
class ExtractionConfig:
    """フレーム抽出の設定"""
    target_fps: float = 15.0
    max_retries: int = 3
    retry_delay_ms: int = 10
    max_consecutive_failures: int = 10
    use_round: bool = True  # True: round()使用, False: int()使用（後方互換性）

    def calculate_frame_skip(self, video_fps: float) -> int:
        """
        frame_skipを計算

        重要: int()ではなくround()を使用
        - int(25/15) = int(1.666) = 1 → 全フレーム抽出（25fps）
        - round(25/15) = round(1.666) = 2 → 2フレームごと（12.5fps）
        """
        if self.use_round:
            skip = max(1, round(video_fps / self.target_fps))
        else:
            skip = max(1, int(video_fps / self.target_fps))

        logger.info(f"[FRAME_EXTRACTION] frame_skip calculation: "
                   f"video_fps={video_fps:.2f}, target_fps={self.target_fps:.2f}, "
                   f"method={'round' if self.use_round else 'int'}, skip={skip}")
        return skip


@dataclass
class ExtractionResult:
    """フレーム抽出の結果"""
    frames: List[np.ndarray]
    frame_indices: List[int]  # 動画内の実際のフレーム番号
    timestamps: List[float]
    failed_indices: List[int]
    metadata: VideoMetadata
    effective_fps: float
    frame_skip: int

    @property
    def success_rate(self) -> float:
        """抽出成功率を計算"""
        total = len(self.frames) + len(self.failed_indices)
        return len(self.frames) / total if total > 0 else 0.0

    @property
    def total_attempted(self) -> int:
        """試行したフレーム数"""
        return len(self.frames) + len(self.failed_indices)

    def __str__(self) -> str:
        return (f"ExtractionResult(frames={len(self.frames)}, "
                f"failed={len(self.failed_indices)}, "
                f"success_rate={self.success_rate*100:.1f}%, "
                f"effective_fps={self.effective_fps:.2f})")


class FrameExtractionService:
    """
    ロバストなフレーム抽出サービス

    特徴:
    - リトライ機構（フレームごとに最大3回）
    - 連続失敗による早期停止（10回連続失敗で停止）
    - round()によるframe_skip計算（int()の切り捨て問題を解決）
    - 詳細なログ出力
    - 抽出成功率の検証
    """

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        logger.info(f"[FRAME_EXTRACTION] Service initialized with config: "
                   f"target_fps={self.config.target_fps}, "
                   f"max_retries={self.config.max_retries}, "
                   f"use_round={self.config.use_round}")

    def extract_frames(
        self,
        video_path: str,
        target_fps: Optional[float] = None
    ) -> ExtractionResult:
        """
        動画からフレームを抽出

        Args:
            video_path: 動画ファイルのパス
            target_fps: 目標FPS（Noneの場合はconfig.target_fpsを使用）

        Returns:
            ExtractionResult: 抽出結果

        Raises:
            FileNotFoundError: 動画ファイルが存在しない
            ValueError: 動画が開けない、または抽出成功率が50%未満
        """
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        logger.info(f"[FRAME_EXTRACTION] Starting extraction: {video_path}")

        # メタデータ取得
        metadata = self._get_video_metadata(video_path)
        logger.info(f"[FRAME_EXTRACTION] {metadata}")

        # target_fpsの決定
        fps_to_use = target_fps if target_fps is not None else self.config.target_fps

        # frame_skip計算
        frame_skip = self.config.calculate_frame_skip(metadata.fps)

        # 抽出対象フレーム番号を計算
        frame_indices = list(range(0, metadata.total_frames, frame_skip))
        logger.info(f"[FRAME_EXTRACTION] Extraction plan: "
                   f"{len(frame_indices)} frames to extract "
                   f"(skip={frame_skip}, total={metadata.total_frames})")

        # フレーム抽出実行
        frames, timestamps, failed_indices = self._extract_frames_with_retry(
            video_path, frame_indices, metadata.fps
        )

        # effective_fps計算
        if len(frames) >= 2:
            time_span = timestamps[-1] - timestamps[0]
            effective_fps = (len(frames) - 1) / time_span if time_span > 0 else 0
        else:
            effective_fps = 0

        # 結果作成
        result = ExtractionResult(
            frames=frames,
            frame_indices=[frame_indices[i] for i in range(len(frames))],
            timestamps=timestamps,
            failed_indices=failed_indices,
            metadata=metadata,
            effective_fps=effective_fps,
            frame_skip=frame_skip
        )

        logger.info(f"[FRAME_EXTRACTION] {result}")

        # 成功率検証
        if result.success_rate < 0.5:
            raise ValueError(
                f"Frame extraction failed: success rate {result.success_rate*100:.1f}% "
                f"(extracted {len(frames)}/{result.total_attempted} frames)"
            )

        return result

    def _get_video_metadata(self, video_path: str) -> VideoMetadata:
        """動画のメタデータを取得"""
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            # コーデック情報（4文字のFourCC）
            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)])

            return VideoMetadata(
                width=width,
                height=height,
                fps=fps,
                total_frames=total_frames,
                duration=duration,
                codec=codec
            )
        finally:
            cap.release()

    def _extract_frames_with_retry(
        self,
        video_path: str,
        frame_indices: List[int],
        video_fps: float
    ) -> Tuple[List[np.ndarray], List[float], List[int]]:
        """
        リトライ機構付きでフレームを抽出

        Returns:
            (frames, timestamps, failed_indices)
        """
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        frames: List[np.ndarray] = []
        timestamps: List[float] = []
        failed_indices: List[int] = []
        consecutive_failures = 0

        try:
            for idx, frame_idx in enumerate(frame_indices):
                frame_extracted = False

                # リトライループ
                for retry in range(self.config.max_retries):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()

                    if ret and frame is not None:
                        frames.append(frame)
                        timestamp = frame_idx / video_fps
                        timestamps.append(timestamp)
                        consecutive_failures = 0
                        frame_extracted = True

                        if idx % 50 == 0:  # 50フレームごとにログ
                            logger.debug(f"[FRAME_EXTRACTION] Progress: {idx}/{len(frame_indices)} "
                                       f"(frame_idx={frame_idx}, timestamp={timestamp:.2f}s)")
                        break
                    else:
                        if retry < self.config.max_retries - 1:
                            logger.warning(f"[FRAME_EXTRACTION] Frame {frame_idx} failed, "
                                         f"retry {retry + 1}/{self.config.max_retries}")
                            time.sleep(self.config.retry_delay_ms / 1000.0)

                # リトライ後も失敗
                if not frame_extracted:
                    failed_indices.append(frame_idx)
                    consecutive_failures += 1
                    logger.error(f"[FRAME_EXTRACTION] Frame {frame_idx} failed after "
                               f"{self.config.max_retries} retries "
                               f"(consecutive_failures={consecutive_failures})")

                    # 連続失敗が多すぎる場合は早期停止
                    if consecutive_failures >= self.config.max_consecutive_failures:
                        logger.error(f"[FRAME_EXTRACTION] Too many consecutive failures "
                                   f"({consecutive_failures}), stopping extraction at frame {frame_idx}")
                        break

        finally:
            cap.release()

        logger.info(f"[FRAME_EXTRACTION] Extraction complete: "
                   f"extracted={len(frames)}, failed={len(failed_indices)}, "
                   f"success_rate={len(frames)/(len(frames)+len(failed_indices))*100:.1f}%")

        return frames, timestamps, failed_indices
