"""手術器具検出モジュール - YOLOv8ベースの器具検出と追跡"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """検出結果を表すデータクラス"""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    class_name: str
    track_id: Optional[int] = None


class ToolDetector:
    """手術器具検出クラス（現在はモック実装）"""
    
    # 手術器具のクラス定義
    TOOL_CLASSES = [
        "forceps",      # 鉗子
        "scissors",     # ハサミ
        "needle_holder", # 持針器
        "scalpel",      # メス
        "suction",      # 吸引管
        "retractor",    # 開創器
    ]
    
    def __init__(self, model_path: Optional[str] = None, confidence_threshold: float = 0.5):
        """
        Args:
            model_path: YOLOv8モデルのパス（Noneの場合はモック動作）
            confidence_threshold: 検出の信頼度閾値
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model = None
        
        # 実際の実装ではYOLOv8モデルをロード
        if model_path:
            try:
                # from ultralytics import YOLO
                # self.model = YOLO(model_path)
                logger.warning("YOLOv8 model loading not implemented, using mock detector")
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
        else:
            logger.info("Using mock tool detector")
        
        # 追跡用の状態
        self.next_track_id = 1
        self.track_history = {}
    
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        フレームから手術器具を検出
        
        Args:
            frame: 入力画像
            
        Returns:
            検出結果のリスト
        """
        if self.model:
            # 実際のYOLOv8検出
            # results = self.model(frame, conf=self.confidence_threshold)
            # detections = self._parse_yolo_results(results)
            pass
        else:
            # モック検出（デモ用）
            detections = self._mock_detect(frame)
        
        return detections
    
    def detect_and_track(self, frame: np.ndarray) -> List[Detection]:
        """
        検出と追跡を行う
        
        Args:
            frame: 入力画像
            
        Returns:
            追跡ID付きの検出結果
        """
        detections = self.detect(frame)
        
        # 簡易的な追跡（実際にはDeepSORTやByteTrackを使用）
        for detection in detections:
            detection.track_id = self._assign_track_id(detection)
        
        return detections
    
    def _mock_detect(self, frame: np.ndarray) -> List[Detection]:
        """
        モック検出（テスト・デモ用）
        
        Args:
            frame: 入力画像
            
        Returns:
            ダミーの検出結果
        """
        h, w = frame.shape[:2]
        detections = []
        
        # ランダムな位置に器具を配置（実際の動作をシミュレート）
        import random
        
        # 1-3個の器具を検出
        num_tools = random.randint(1, 3)
        for i in range(num_tools):
            # ランダムなバウンディングボックス
            x1 = random.randint(int(w * 0.1), int(w * 0.7))
            y1 = random.randint(int(h * 0.1), int(h * 0.7))
            x2 = x1 + random.randint(50, 150)
            y2 = y1 + random.randint(30, 100)
            
            # 画像範囲内にクリップ
            x2 = min(x2, w - 1)
            y2 = min(y2, h - 1)
            
            detection = Detection(
                bbox=(x1, y1, x2, y2),
                confidence=random.uniform(0.6, 0.95),
                class_name=random.choice(self.TOOL_CLASSES)
            )
            detections.append(detection)
        
        return detections
    
    def _assign_track_id(self, detection: Detection) -> int:
        """
        検出結果に追跡IDを割り当て（簡易版）
        
        Args:
            detection: 検出結果
            
        Returns:
            追跡ID
        """
        # 実際にはIoUベースのマッチングを行う
        # ここでは単純に新しいIDを割り当て
        track_id = self.next_track_id
        self.next_track_id += 1
        
        # 履歴に追加
        if track_id not in self.track_history:
            self.track_history[track_id] = []
        self.track_history[track_id].append(detection.bbox)
        
        # 履歴が長すぎる場合は古いものを削除
        if len(self.track_history[track_id]) > 30:
            self.track_history[track_id].pop(0)
        
        return track_id
    
    def draw_detections(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """
        検出結果を画像に描画
        
        Args:
            frame: 入力画像
            detections: 検出結果
            
        Returns:
            描画済み画像
        """
        result = frame.copy()
        
        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            
            # 色を決定（クラスごとに異なる色）
            color_idx = self.TOOL_CLASSES.index(detection.class_name) if detection.class_name in self.TOOL_CLASSES else 0
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
            color = colors[color_idx % len(colors)]
            
            # バウンディングボックスを描画
            cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)
            
            # ラベルを描画
            label = f"{detection.class_name}"
            if detection.track_id:
                label += f" #{detection.track_id}"
            label += f" ({detection.confidence:.2f})"
            
            # テキスト背景
            (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(result, (x1, y1 - text_height - 4), (x1 + text_width, y1), color, -1)
            
            # テキスト
            cv2.putText(result, label, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return result
    
    def get_trajectory(self, track_id: int) -> List[Tuple[int, int]]:
        """
        特定の追跡IDの軌跡を取得
        
        Args:
            track_id: 追跡ID
            
        Returns:
            中心座標のリスト
        """
        if track_id not in self.track_history:
            return []
        
        trajectory = []
        for bbox in self.track_history[track_id]:
            x1, y1, x2, y2 = bbox
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            trajectory.append((center_x, center_y))
        
        return trajectory