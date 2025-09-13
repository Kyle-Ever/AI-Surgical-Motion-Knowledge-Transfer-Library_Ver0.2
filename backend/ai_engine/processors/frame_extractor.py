"""フレーム抽出モジュール - 動画からフレームを効率的に抽出"""

import cv2
import numpy as np
from typing import Iterator, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FrameExtractor:
    """動画からフレームを抽出するクラス"""
    
    def __init__(self, video_path: str, sampling_rate: int = 5):
        """
        Args:
            video_path: 動画ファイルのパス
            sampling_rate: サンプリングレート（fps）
        """
        self.video_path = Path(video_path)
        self.sampling_rate = sampling_rate
        
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # OpenCVでビデオを開く
        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")
        
        # ビデオ情報を取得
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # サンプリング間隔を計算
        self.frame_interval = max(1, int(self.fps / self.sampling_rate))
        
        logger.info(f"Video loaded: {self.width}x{self.height}, {self.fps}fps, {self.total_frames} frames")
        logger.info(f"Sampling every {self.frame_interval} frames ({self.sampling_rate}fps)")
    
    def extract_frames(self) -> Iterator[Tuple[int, float, np.ndarray]]:
        """
        フレームを抽出してイテレータとして返す
        
        Yields:
            (frame_number, timestamp, frame): フレーム番号、タイムスタンプ、フレーム画像
        """
        frame_count = 0
        extracted_count = 0
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                # 指定間隔でフレームを抽出
                if frame_count % self.frame_interval == 0:
                    timestamp = frame_count / self.fps
                    yield frame_count, timestamp, frame
                    extracted_count += 1
                
                frame_count += 1
                
        finally:
            logger.info(f"Extracted {extracted_count} frames from {frame_count} total frames")
    
    def get_frame_at(self, frame_number: int) -> Optional[np.ndarray]:
        """
        特定のフレーム番号の画像を取得
        
        Args:
            frame_number: フレーム番号
            
        Returns:
            フレーム画像（存在しない場合はNone）
        """
        if frame_number < 0 or frame_number >= self.total_frames:
            return None
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        
        return frame if ret else None
    
    def get_metadata(self) -> dict:
        """
        ビデオのメタデータを取得
        
        Returns:
            メタデータ辞書
        """
        return {
            "fps": self.fps,
            "total_frames": self.total_frames,
            "width": self.width,
            "height": self.height,
            "duration": self.total_frames / self.fps if self.fps > 0 else 0,
            "sampling_rate": self.sampling_rate,
            "frame_interval": self.frame_interval
        }
    
    def close(self):
        """リソースを解放"""
        if hasattr(self, 'cap') and self.cap is not None:
            self.cap.release()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __del__(self):
        self.close()