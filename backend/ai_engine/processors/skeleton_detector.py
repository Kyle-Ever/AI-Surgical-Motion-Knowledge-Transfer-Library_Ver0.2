import mediapipe as mp
import cv2
import numpy as np
from typing import List, Dict, Any, Optional

class HandSkeletonDetector:
    """MediaPipeを使用した手の骨格検出"""
    
    def __init__(self, min_detection_confidence: float = 0.8, min_tracking_confidence: float = 0.8):
        """
        骨格検出器の初期化
        
        Args:
            min_detection_confidence: 検出の最小信頼度
            min_tracking_confidence: トラッキングの最小信頼度
        """
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
    def detect_from_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        単一フレームから手の骨格を検出
        
        Args:
            frame: 画像フレーム（BGR）
        
        Returns:
            検出結果の辞書
        """
        # BGRからRGBに変換（MediaPipeはRGBを期待）
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        frame_data = {
            'hands': []
        }
        
        if results.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # 左右の判定
                handedness = 'unknown'
                if results.multi_handedness:
                    handedness = results.multi_handedness[hand_idx].classification[0].label
                
                # 21個のランドマーク座標を取得
                landmarks = []
                for landmark in hand_landmarks.landmark:
                    landmarks.append({
                        'x': landmark.x * 2 - 1,  # -1～1に正規化
                        'y': landmark.y * 2 - 1,  # -1～1に正規化
                        'z': landmark.z,
                        'visibility': landmark.visibility if hasattr(landmark, 'visibility') else 1.0
                    })
                
                # 手首の角度を計算
                wrist_angle = self._calculate_wrist_angle(landmarks)
                
                # 指の曲がり具合を計算
                finger_angles = self._calculate_finger_angles(landmarks)
                
                frame_data['hands'].append({
                    'hand_type': handedness,
                    'landmarks': landmarks,
                    'wrist_angle': wrist_angle,
                    'finger_angles': finger_angles,
                    'confidence': results.multi_handedness[hand_idx].classification[0].score if results.multi_handedness else 1.0
                })
        
        return frame_data
    
    def detect_from_frames(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        複数フレームから手の骨格を検出
        
        Args:
            frames: フレームのリスト（各要素は'image'キーを持つ辞書）
        
        Returns:
            検出結果のリスト
        """
        skeleton_data = []
        
        for frame in frames:
            frame_result = self.detect_from_frame(frame['image'])
            frame_result['frame_number'] = frame.get('frame_number', 0)
            frame_result['timestamp'] = frame.get('timestamp', 0.0)
            
            # 検出失敗時の補間
            if len(frame_result['hands']) == 0 and len(skeleton_data) > 0:
                # 前のフレームのデータを使用（簡易的な補間）
                frame_result = self._interpolate_skeleton(skeleton_data[-1], frame_result)
            
            skeleton_data.append(frame_result)
        
        return skeleton_data
    
    def _calculate_wrist_angle(self, landmarks: List[Dict]) -> float:
        """
        手首の角度を計算
        
        Args:
            landmarks: ランドマークのリスト
        
        Returns:
            手首の角度（度）
        """
        # MediaPipeの手のランドマーク定義に基づく
        # 0: 手首, 5: 人差し指の根本, 17: 小指の根本
        if len(landmarks) < 18:
            return 0.0
            
        wrist = landmarks[0]
        index_base = landmarks[5]
        pinky_base = landmarks[17]
        
        # ベクトル計算
        v1 = np.array([index_base['x'] - wrist['x'], 
                      index_base['y'] - wrist['y']])
        v2 = np.array([pinky_base['x'] - wrist['x'], 
                      pinky_base['y'] - wrist['y']])
        
        # ゼロベクトルの場合
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        
        # 角度計算
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値誤差対策
        angle = np.arccos(cos_angle)
        return np.degrees(angle)
    
    def _calculate_finger_angles(self, landmarks: List[Dict]) -> Dict[str, float]:
        """
        各指の曲がり具合を計算
        
        Args:
            landmarks: ランドマークのリスト
        
        Returns:
            各指の角度の辞書
        """
        finger_angles = {}
        
        if len(landmarks) < 21:
            return finger_angles
        
        # 各指のランドマークインデックス
        fingers = {
            'thumb': [1, 2, 3, 4],
            'index': [5, 6, 7, 8],
            'middle': [9, 10, 11, 12],
            'ring': [13, 14, 15, 16],
            'pinky': [17, 18, 19, 20]
        }
        
        for finger_name, indices in fingers.items():
            if indices[0] < len(landmarks):
                # 各指の根本から先端までのベクトルで角度を計算
                base = landmarks[indices[0]]
                tip = landmarks[indices[-1]]
                
                # 簡易的に屈曲度を計算（Y座標の差）
                bend_angle = abs(tip['y'] - base['y']) * 90  # 0-90度にマッピング
                finger_angles[finger_name] = min(bend_angle, 90.0)
        
        return finger_angles
    
    def _interpolate_skeleton(self, prev_frame: Dict, curr_frame: Dict) -> Dict:
        """
        欠損フレームの補間（簡易版）
        
        Args:
            prev_frame: 前のフレームデータ
            curr_frame: 現在のフレームデータ（空）
        
        Returns:
            補間されたフレームデータ
        """
        # 前のフレームのデータをコピー
        interpolated = curr_frame.copy()
        interpolated['hands'] = prev_frame['hands'].copy()
        interpolated['interpolated'] = True
        
        return interpolated
    
    def draw_landmarks(self, image: np.ndarray, detection_result: Dict) -> np.ndarray:
        """
        画像上にランドマークを描画
        
        Args:
            image: 描画対象の画像
            detection_result: 検出結果
        
        Returns:
            ランドマークが描画された画像
        """
        annotated_image = image.copy()
        h, w = image.shape[:2]
        
        for hand in detection_result.get('hands', []):
            # ランドマークを描画用の形式に変換
            landmarks = hand['landmarks']
            
            # 各ランドマークを描画
            for i, landmark in enumerate(landmarks):
                # 正規化座標から画像座標に変換
                x = int((landmark['x'] + 1) * w / 2)
                y = int((landmark['y'] + 1) * h / 2)
                
                # 左右で色分け
                color = (0, 255, 0) if hand['hand_type'] == 'Left' else (255, 0, 0)
                cv2.circle(annotated_image, (x, y), 5, color, -1)
                
                # ランドマーク番号を表示
                cv2.putText(annotated_image, str(i), (x + 5, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
            
            # 手の接続線を描画
            connections = self.mp_hands.HAND_CONNECTIONS
            for connection in connections:
                start_idx, end_idx = connection
                if start_idx < len(landmarks) and end_idx < len(landmarks):
                    start = landmarks[start_idx]
                    end = landmarks[end_idx]
                    
                    x1 = int((start['x'] + 1) * w / 2)
                    y1 = int((start['y'] + 1) * h / 2)
                    x2 = int((end['x'] + 1) * w / 2)
                    y2 = int((end['y'] + 1) * h / 2)
                    
                    cv2.line(annotated_image, (x1, y1), (x2, y2), color, 2)
        
        return annotated_image
    
    def close(self):
        """リソースを解放"""
        self.hands.close()