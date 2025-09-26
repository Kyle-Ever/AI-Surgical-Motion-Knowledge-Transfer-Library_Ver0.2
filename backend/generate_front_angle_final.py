"""Front_Angle.mp4 - 上部除外で手術手技のみを検出"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from collections import deque
import mediapipe as mp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FrontAngleFinalDetector:
    """上部30%を除外して手術手技のみ検出"""

    def __init__(self, input_video_path: str, output_video_path: str):
        self.input_path = Path(input_video_path)
        self.output_path = Path(output_video_path)
        
        # 上部30%を除外
        self.exclude_top_ratio = 0.30
        
        # MediaPipe手検出（青い手袋用に低閾値）
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.01,
            min_tracking_confidence=0.01,
            model_complexity=1
        )
        
        self.mp_drawing = mp.solutions.drawing_utils
        self.detection_history = deque(maxlen=100)
        
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'excluded_detections': 0,
            'total_hands': 0
        }

    def generate_video(self):
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"TOP 30% EXCLUDED - Surgical hands only")
        
        cap = cv2.VideoCapture(str(self.input_path))
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        self.exclude_y_line = int(height * self.exclude_top_ratio)
        
        logger.info(f"Video: {width}x{height}, Excluding Y < {self.exclude_y_line}")
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(self.output_path), fourcc, fps, (width, height))
        
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 青い手袋用の前処理
            preprocessed = self.preprocess_blue_glove(frame)
            
            # 手を検出
            rgb_frame = cv2.cvtColor(preprocessed, cv2.COLOR_BGR2RGB)
            result = self.mp_hands.process(rgb_frame)
            
            # 上部を除外してフィルタリング
            valid_hands = []
            if result.multi_hand_landmarks:
                for hand_landmarks in result.multi_hand_landmarks:
                    center_y = sum([lm.y for lm in hand_landmarks.landmark]) / 21 * height
                    
                    if center_y >= self.exclude_y_line:
                        valid_hands.append(hand_landmarks)
                        self.stats['total_hands'] += 1
                    else:
                        self.stats['excluded_detections'] += 1
            
            if valid_hands:
                self.stats['detected_frames'] += 1
            
            self.detection_history.append(1 if valid_hands else 0)
            
            # 可視化
            vis_frame = self.visualize(frame, valid_hands, frame_count, total_frames)
            out.write(vis_frame)
            
            frame_count += 1
            self.stats['total_frames'] = frame_count
            
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                detection_rate = (self.stats['detected_frames'] / frame_count) * 100
                logger.info(f"Progress: {progress:.1f}% | Detection: {detection_rate:.1f}%")
        
        cap.release()
        out.release()
        
        self._print_stats()

    def preprocess_blue_glove(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 青色範囲
        lower_blue = np.array([60, 10, 10])
        upper_blue = np.array([150, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # 青を肌色に変換
        hsv_copy = hsv.copy()
        hsv_copy[blue_mask > 0, 0] = 18  # 肌色
        hsv_copy[blue_mask > 0, 1] = hsv_copy[blue_mask > 0, 1] * 0.3
        
        result = cv2.cvtColor(hsv_copy, cv2.COLOR_HSV2BGR)
        return cv2.addWeighted(frame, 0.2, result, 0.8, 0)

    def visualize(self, frame, valid_hands, frame_num, total_frames):
        vis_frame = frame.copy()
        
        # 除外領域を暗く
        overlay = vis_frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], self.exclude_y_line), (0, 0, 0), -1)
        vis_frame[:self.exclude_y_line] = cv2.addWeighted(
            vis_frame[:self.exclude_y_line], 0.3,
            overlay[:self.exclude_y_line], 0.7, 0
        )
        
        # 境界線
        cv2.line(vis_frame, (0, self.exclude_y_line), (frame.shape[1], self.exclude_y_line), (0, 255, 255), 2)
        cv2.putText(vis_frame, "SURGICAL AREA", (10, self.exclude_y_line + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # 手を描画
        for hand_landmarks in valid_hands:
            self.mp_drawing.draw_landmarks(
                vis_frame, hand_landmarks,
                mp.solutions.hands.HAND_CONNECTIONS,
                self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                self.mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)
            )
        
        # 情報パネル
        progress = (frame_num / total_frames) * 100
        detection_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100 if frame_num > 0 else 0
        
        cv2.putText(vis_frame, f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(vis_frame, f"Detection: {detection_rate:.1f}%",
                   (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return vis_frame

    def _print_stats(self):
        print("\n" + "=" * 80)
        print("ANALYSIS RESULTS")
        print("=" * 80)
        
        total = self.stats['total_frames']
        detected = self.stats['detected_frames']
        detection_rate = (detected / total * 100) if total > 0 else 0
        
        print(f"Total frames: {total}")
        print(f"Detected frames: {detected} ({detection_rate:.1f}%)")
        print(f"Total hands: {self.stats['total_hands']}")
        print(f"Excluded (face area): {self.stats['excluded_detections']}")
        print(f"Output saved to: {self.output_path}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/Front_Angle_final_{timestamp}.mp4")
    
    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return
    
    print("\n" + "=" * 80)
    print("FRONT ANGLE FINAL ANALYSIS")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")
    
    generator = FrontAngleFinalDetector(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()
