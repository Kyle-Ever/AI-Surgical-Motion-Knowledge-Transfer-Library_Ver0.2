"""
手の骨格検出モジュール

MediaPipeを使用して手の21個のランドマークを検出し、
指の角度や動きを解析する
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class HandSkeletonDetector:
    """手の骨格検出クラス"""
    
    FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']
    
    FINGER_LANDMARK_IDS = {
        'thumb': [1, 2, 3, 4],
        'index': [5, 6, 7, 8],
        'middle': [9, 10, 11, 12],
        'ring': [13, 14, 15, 16],
        'pinky': [17, 18, 19, 20]
    }
    
    def __init__(self, 
                 static_image_mode: bool = False,
                 max_num_hands: int = 2,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        """
        初期化
        
        Args:
            static_image_mode: 静止画モード
            max_num_hands: 検出する最大手数
            min_detection_confidence: 検出の最小信頼度
            min_tracking_confidence: トラッキングの最小信頼度
        """
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        logger.info("HandSkeletonDetector initialized with MediaPipe")
    
    def detect_from_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        フレームから手の骨格を検出
        
        Args:
            frame: 入力画像フレーム (BGR)
        
        Returns:
            検出結果の辞書
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        results = self.hands.process(rgb_frame)
        
        detection_result = {
            "hands": [],
            "frame_shape": frame.shape[:2]
        }
        
        if results.multi_hand_landmarks:
            for hand_idx, (hand_landmarks, hand_info) in enumerate(
                zip(results.multi_hand_landmarks, results.multi_handedness)
            ):
                hand_data = self._process_hand_landmarks(
                    hand_landmarks, 
                    hand_info,
                    frame.shape
                )
                detection_result["hands"].append(hand_data)
        
        return detection_result
    
    def _process_hand_landmarks(self, 
                                hand_landmarks,
                                hand_info,
                                frame_shape: Tuple[int, int, int]) -> Dict[str, Any]:
        """
        手のランドマークを処理
        
        Args:
            hand_landmarks: MediaPipeのランドマーク
            hand_info: 手の情報（左右など）
            frame_shape: フレームの形状
        
        Returns:
            処理された手のデータ
        """
        height, width = frame_shape[:2]
        
        landmarks_list = []
        for landmark in hand_landmarks.landmark:
            landmarks_list.append({
                "x": landmark.x * width,
                "y": landmark.y * height,
                "z": landmark.z,
                "visibility": landmark.visibility
            })
        
        finger_angles = self._calculate_finger_angles(landmarks_list)
        
        palm_center = self._calculate_palm_center(landmarks_list)
        
        hand_openness = self._calculate_hand_openness(finger_angles)
        
        return {
            "label": hand_info.classification[0].label,
            "confidence": hand_info.classification[0].score,
            "landmarks": landmarks_list,
            "finger_angles": finger_angles,
            "palm_center": palm_center,
            "hand_openness": hand_openness,
            "bbox": self._calculate_bbox(landmarks_list)
        }
    
    def _calculate_finger_angles(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """
        各指の曲がり角度を計算
        
        Args:
            landmarks: ランドマークのリスト
        
        Returns:
            各指の角度（度数）
        """
        angles = {}
        
        for finger_name in self.FINGER_NAMES:
            landmark_ids = self.FINGER_LANDMARK_IDS[finger_name]
            
            if finger_name == 'thumb':
                p1 = np.array([landmarks[0]["x"], landmarks[0]["y"]])
                p2 = np.array([landmarks[landmark_ids[1]]["x"], 
                             landmarks[landmark_ids[1]]["y"]])
                p3 = np.array([landmarks[landmark_ids[2]]["x"], 
                             landmarks[landmark_ids[2]]["y"]])
            else:
                p1 = np.array([landmarks[landmark_ids[0]]["x"], 
                             landmarks[landmark_ids[0]]["y"]])
                p2 = np.array([landmarks[landmark_ids[1]]["x"], 
                             landmarks[landmark_ids[1]]["y"]])
                p3 = np.array([landmarks[landmark_ids[2]]["x"], 
                             landmarks[landmark_ids[2]]["y"]])
            
            angle = self._calculate_angle(p1, p2, p3)
            angles[finger_name] = angle
        
        return angles
    
    def _calculate_angle(self, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
        """
        3点間の角度を計算
        
        Args:
            p1, p2, p3: 3つの点の座標
        
        Returns:
            角度（度数）
        """
        v1 = p1 - p2
        v2 = p3 - p2
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        
        angle = np.degrees(np.arccos(cos_angle))
        
        return float(angle)
    
    def _calculate_palm_center(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """
        手のひらの中心座標を計算
        
        Args:
            landmarks: ランドマークのリスト
        
        Returns:
            中心座標
        """
        palm_landmarks = [0, 1, 5, 9, 13, 17]
        
        x_coords = [landmarks[i]["x"] for i in palm_landmarks]
        y_coords = [landmarks[i]["y"] for i in palm_landmarks]
        
        return {
            "x": float(np.mean(x_coords)),
            "y": float(np.mean(y_coords))
        }
    
    def _calculate_hand_openness(self, finger_angles: Dict[str, float]) -> float:
        """
        手の開き具合を計算（0-100%）
        
        Args:
            finger_angles: 各指の角度
        
        Returns:
            開き具合のパーセンテージ
        """
        max_angle = 180.0
        
        total_openness = 0
        for finger, angle in finger_angles.items():
            openness = (max_angle - angle) / max_angle
            total_openness += openness
        
        average_openness = (total_openness / len(finger_angles)) * 100
        
        return float(np.clip(average_openness, 0, 100))
    
    def _calculate_bbox(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """
        手の境界ボックスを計算
        
        Args:
            landmarks: ランドマークのリスト
        
        Returns:
            境界ボックス座標
        """
        x_coords = [lm["x"] for lm in landmarks]
        y_coords = [lm["y"] for lm in landmarks]
        
        margin = 20
        
        return {
            "x_min": float(max(0, min(x_coords) - margin)),
            "y_min": float(max(0, min(y_coords) - margin)),
            "x_max": float(max(x_coords) + margin),
            "y_max": float(max(y_coords) + margin)
        }
    
    def draw_landmarks(self, frame: np.ndarray, detection_result: Dict[str, Any]) -> np.ndarray:
        """
        検出結果を画像に描画
        
        Args:
            frame: 入力画像
            detection_result: 検出結果
        
        Returns:
            描画された画像
        """
        annotated_frame = frame.copy()
        
        for hand_data in detection_result.get("hands", []):
            landmarks = hand_data["landmarks"]
            
            for i, landmark in enumerate(landmarks):
                x = int(landmark["x"])
                y = int(landmark["y"])
                cv2.circle(annotated_frame, (x, y), 5, (0, 255, 0), -1)
                
                if i > 0:
                    if i in [1, 5, 9, 13, 17]:
                        prev_idx = 0
                    elif i in [2, 6, 10, 14, 18]:
                        prev_idx = i - 1
                    elif i in [3, 7, 11, 15, 19]:
                        prev_idx = i - 1
                    elif i in [4, 8, 12, 16, 20]:
                        prev_idx = i - 1
                    else:
                        prev_idx = i - 1
                    
                    prev_x = int(landmarks[prev_idx]["x"])
                    prev_y = int(landmarks[prev_idx]["y"])
                    cv2.line(annotated_frame, (prev_x, prev_y), (x, y), (0, 255, 0), 2)
            
            label = f"{hand_data['label']} ({hand_data['confidence']:.2f})"
            bbox = hand_data["bbox"]
            cv2.putText(annotated_frame, label,
                       (int(bbox["x_min"]), int(bbox["y_min"]) - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            cv2.rectangle(annotated_frame,
                         (int(bbox["x_min"]), int(bbox["y_min"])),
                         (int(bbox["x_max"]), int(bbox["y_max"])),
                         (0, 255, 0), 2)
        
        return annotated_frame
    
    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, 'hands'):
            self.hands.close()