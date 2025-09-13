import cv2
from pathlib import Path
from typing import Optional, Dict, Any

class VideoService:
    """動画処理サービス"""
    
    @staticmethod
    def extract_metadata(video_path: str) -> Dict[str, Any]:
        """動画のメタデータを抽出"""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            duration_seconds = frame_count / fps if fps > 0 else 0
            duration = VideoService.format_duration(duration_seconds)
            
            return {
                "fps": fps,
                "frame_count": frame_count,
                "width": width,
                "height": height,
                "duration": duration,
                "duration_seconds": duration_seconds
            }
        finally:
            cap.release()
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """秒数を MM:SS 形式に変換"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    @staticmethod
    def extract_frames(video_path: str, target_fps: int = 5) -> list:
        """動画からフレームを抽出"""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        frames = []
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(original_fps / target_fps) if original_fps > target_fps else 1
        
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                frames.append({
                    "frame_number": frame_count,
                    "timestamp": frame_count / original_fps,
                    "image": frame
                })
            
            frame_count += 1
        
        cap.release()
        return frames