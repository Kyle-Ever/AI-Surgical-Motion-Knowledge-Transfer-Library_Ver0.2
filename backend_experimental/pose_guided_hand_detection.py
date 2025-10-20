"""MediaPipe Poseで手首位置を特定してから手検出"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
import mediapipe as mp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PoseGuidedHandDetector:
    """Poseで手首位置を特定してから手を検出"""

    def __init__(self):
        # Pose検出（手首位置の特定用）
        self.mp_pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Hand検出
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3,
            model_complexity=1
        )
        
        self.mp_drawing = mp.solutions.drawing_utils

    def process_frame(self, frame):
        """フレームを処理"""
        h, w = frame.shape[:2]
        
        # 1. Poseで手首位置を検出
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pose_result = self.mp_pose.process(rgb_frame)
        
        hand_regions = []
        if pose_result.pose_landmarks:
            # 左右の手首位置を取得
            left_wrist = pose_result.pose_landmarks.landmark[15]  # 左手首
            right_wrist = pose_result.pose_landmarks.landmark[16]  # 右手首
            
            # 手首周辺の領域を定義（画面の20%の正方形）
            region_size = int(min(w, h) * 0.2)
            
            for wrist, name in [(left_wrist, "Left"), (right_wrist, "Right")]:
                if wrist.visibility > 0.5:  # 手首が見える場合
                    cx = int(wrist.x * w)
                    cy = int(wrist.y * h)
                    
                    # 顔領域を除外（Y座標が上20%以内なら無視）
                    if cy > h * 0.2:
                        x1 = max(0, cx - region_size)
                        y1 = max(0, cy - region_size)
                        x2 = min(w, cx + region_size)
                        y2 = min(h, cy + region_size)
                        
                        hand_regions.append({
                            'name': name,
                            'bbox': (x1, y1, x2, y2),
                            'center': (cx, cy)
                        })
        
        # 2. 手領域を前処理
        processed_frame = self.preprocess_hand_regions(frame, hand_regions)
        
        # 3. MediaPipe Handsで手を検出
        rgb_processed = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
        hands_result = self.mp_hands.process(rgb_processed)
        
        return hands_result, hand_regions, processed_frame

    def preprocess_hand_regions(self, frame, hand_regions):
        """手領域のみを前処理"""
        processed = frame.copy()
        
        for region in hand_regions:
            x1, y1, x2, y2 = region['bbox']
            roi = processed[y1:y2, x1:x2]
            
            if roi.size > 0:
                # 青い手袋を肌色に変換
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                
                # 青色の範囲
                lower_blue = np.array([70, 30, 30])
                upper_blue = np.array([140, 255, 255])
                blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
                
                # 青を肌色に変換
                hsv[blue_mask > 0, 0] = 20  # 肌色
                hsv[blue_mask > 0, 1] = hsv[blue_mask > 0, 1] * 0.3
                
                # コントラスト強調
                converted = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
                processed[y1:y2, x1:x2] = converted
        
        return processed


def main():
    """テスト実行"""
    print("=" * 80)
    print("POSE-GUIDED HAND DETECTION TEST")
    print("=" * 80)
    
    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")
    
    if not video_path.exists():
        print(f"Error: Video not found")
        return
    
    detector = PoseGuidedHandDetector()
    cap = cv2.VideoCapture(str(video_path))
    
    # 最初の30フレームをテスト
    frame_count = 0
    detected_count = 0
    
    while frame_count < 30:
        ret, frame = cap.read()
        if not ret:
            break
        
        hands_result, hand_regions, processed = detector.process_frame(frame)
        
        if hands_result.multi_hand_landmarks:
            detected_count += 1
            print(f"Frame {frame_count}: Detected {len(hands_result.multi_hand_landmarks)} hand(s)")
            
            # 手領域の情報
            for region in hand_regions:
                print(f"  - {region['name']} wrist region at {region['center']}")
        
        frame_count += 1
    
    cap.release()
    
    detection_rate = (detected_count / frame_count * 100) if frame_count > 0 else 0
    print(f"\nResults: {detected_count}/{frame_count} frames ({detection_rate:.1f}%)")


if __name__ == "__main__":
    main()
