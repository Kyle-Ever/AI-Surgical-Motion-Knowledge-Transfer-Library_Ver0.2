"""
動画フレーム抽出モジュール

動画ファイルから指定されたFPSでフレームを抽出し、
メモリ効率的に処理するためのユーティリティ
"""

import cv2
import numpy as np
from typing import Generator, Tuple, Optional, List
from pathlib import Path
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """動画情報"""
    width: int
    height: int
    fps: float
    total_frames: int
    duration: float  # seconds

    def __str__(self):
        return (f"Video: {self.width}x{self.height}, "
                f"{self.fps:.2f}fps, {self.total_frames} frames, "
                f"{self.duration:.2f}s")


class FrameExtractor:
    """動画フレーム抽出クラス"""

    def __init__(self, video_path: str, target_fps: int = 5):
        """
        初期化

        Args:
            video_path: 動画ファイルパス
            target_fps: 抽出するフレームレート（デフォルト5fps）
        """
        self.video_path = Path(video_path)
        self.target_fps = target_fps
        self.cap = None
        self.video_info = None

        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # 動画情報を取得
        self._initialize_capture()

    def _initialize_capture(self):
        """動画キャプチャを初期化"""
        self.cap = cv2.VideoCapture(str(self.video_path))

        if not self.cap.isOpened():
            raise ValueError(f"Cannot open video file: {self.video_path}")

        # 動画情報を取得
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        self.video_info = VideoInfo(
            width=width,
            height=height,
            fps=fps,
            total_frames=total_frames,
            duration=duration
        )

        logger.info(f"Video loaded: {self.video_info}")

    def get_info(self) -> VideoInfo:
        """動画情報を取得"""
        return self.video_info

    def extract_frames_generator(self) -> Generator[Tuple[int, np.ndarray], None, None]:
        """
        フレームを順次抽出するジェネレータ

        Yields:
            (frame_number, frame): フレーム番号とフレーム画像
        """
        if not self.cap or not self.cap.isOpened():
            self._initialize_capture()

        # フレームスキップ数を計算
        frame_skip = int(self.video_info.fps / self.target_fps)
        if frame_skip < 1:
            frame_skip = 1

        frame_count = 0
        extracted_count = 0

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 最初に戻る

        while True:
            ret, frame = self.cap.read()

            if not ret:
                break

            # 指定のフレームレートに合わせてフレームを抽出
            if frame_count % frame_skip == 0:
                yield (frame_count, frame)
                extracted_count += 1

            frame_count += 1

        logger.info(f"Extracted {extracted_count} frames from {frame_count} total frames")

    def extract_all_frames(self, max_frames: Optional[int] = None) -> List[Tuple[int, np.ndarray]]:
        """
        全フレームを抽出してリストで返す

        Args:
            max_frames: 最大フレーム数（メモリ制限用）

        Returns:
            [(frame_number, frame), ...]: フレームのリスト
        """
        frames = []

        for i, (frame_num, frame) in enumerate(self.extract_frames_generator()):
            frames.append((frame_num, frame))

            if max_frames and i >= max_frames - 1:
                logger.warning(f"Reached max_frames limit: {max_frames}")
                break

        return frames

    def extract_frame_at_time(self, time_seconds: float) -> Optional[np.ndarray]:
        """
        指定時刻のフレームを抽出

        Args:
            time_seconds: 時刻（秒）

        Returns:
            フレーム画像またはNone
        """
        if not self.cap or not self.cap.isOpened():
            self._initialize_capture()

        # フレーム番号を計算
        frame_number = int(time_seconds * self.video_info.fps)

        if frame_number >= self.video_info.total_frames:
            logger.warning(f"Time {time_seconds}s exceeds video duration")
            return None

        # 指定フレームに移動
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()

        return frame if ret else None

    def extract_keyframes(self, interval_seconds: float = 1.0) -> List[Tuple[float, np.ndarray]]:
        """
        キーフレームを定期間隔で抽出

        Args:
            interval_seconds: 抽出間隔（秒）

        Returns:
            [(time, frame), ...]: 時刻とフレームのリスト
        """
        keyframes = []
        time = 0.0

        while time < self.video_info.duration:
            frame = self.extract_frame_at_time(time)
            if frame is not None:
                keyframes.append((time, frame))
            time += interval_seconds

        logger.info(f"Extracted {len(keyframes)} keyframes")
        return keyframes

    def save_frames(self, output_dir: Path, prefix: str = "frame"):
        """
        抽出したフレームを画像ファイルとして保存

        Args:
            output_dir: 出力ディレクトリ
            prefix: ファイル名プレフィックス
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        for frame_num, frame in self.extract_frames_generator():
            filename = output_dir / f"{prefix}_{frame_num:06d}.jpg"
            cv2.imwrite(str(filename), frame)

        logger.info(f"Frames saved to {output_dir}")

    def release(self):
        """リソースを解放"""
        if self.cap:
            self.cap.release()
            self.cap = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def extract_frames_from_video(
    video_path: str,
    target_fps: int = 5,
    max_frames: Optional[int] = None
) -> Tuple[VideoInfo, List[Tuple[int, np.ndarray]]]:
    """
    動画からフレームを抽出する便利関数

    Args:
        video_path: 動画ファイルパス
        target_fps: 抽出FPS
        max_frames: 最大フレーム数

    Returns:
        (video_info, frames): 動画情報とフレームリスト
    """
    with FrameExtractor(video_path, target_fps) as extractor:
        info = extractor.get_info()
        frames = extractor.extract_all_frames(max_frames)
        return info, frames


def get_video_info(video_path: str) -> VideoInfo:
    """
    動画情報を取得する便利関数

    Args:
        video_path: 動画ファイルパス

    Returns:
        VideoInfo: 動画情報
    """
    with FrameExtractor(video_path) as extractor:
        return extractor.get_info()