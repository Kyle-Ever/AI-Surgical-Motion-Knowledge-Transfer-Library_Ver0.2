"""器具検出のシンプルバージョン - エッジ検出ベース"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
import mediapipe as mp
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleInstrumentDetector:
    """エッジ検出による器具検出"""

    def __init__(self, input_video: str, output_video: str):
        self.input_path = Path(input_video)
        self.output_path = Path(output_video)

        # MediaPipe手検出
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.5,
            model_complexity=1
        )

        self.mp_drawing = mp.solutions.drawing_utils

        # 器具の追跡履歴
        self.instrument_history = deque(maxlen=10)

        self.stats = {
            'total_frames': 0,
            'hands_detected': 0,
            'instruments_detected': 0
        }

    def detect_instruments_edge(self, frame, hand_regions):
        """エッジ検出で器具を検出"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 手領域の周辺で器具を探す
        instrument_masks = []

        for region in hand_regions:
            x, y, w, h = region

            # 手領域を拡張（器具は手の延長にある）
            pad = 50
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(frame.shape[1], x + w + pad)
            y2 = min(frame.shape[0], y + h + pad)

            roi = gray[y1:y2, x1:x2]

            # エッジ検出
            edges = cv2.Canny(roi, 50, 150)

            # 膨張処理で繋げる
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=2)

            # 細長い形状（器具の特徴）を検出
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 100:  # 小さすぎる領域は無視
                    continue

                # アスペクト比チェック（細長い形状）
                rect = cv2.minAreaRect(cnt)
                box = cv2.boxPoints(rect)
                box = np.int0(box)

                width = rect[1][0]
                height = rect[1][1]

                if width > 0 and height > 0:
                    aspect_ratio = max(width, height) / min(width, height)

                    # 細長い形状（器具の可能性）
                    if aspect_ratio > 2.5:
                        # 元画像座標に変換
                        box[:, 0] += x1
                        box[:, 1] += y1
                        instrument_masks.append(box)

        return instrument_masks

    def process_frame(self, frame):
        """フレーム処理"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 手を検出
        hands_result = self.mp_hands.process(rgb_frame)

        hand_regions = []
        if hands_result.multi_hand_landmarks:
            for hand_landmarks in hands_result.multi_hand_landmarks:
                # 手の境界ボックスを計算
                h, w = frame.shape[:2]
                x_coords = [int(lm.x * w) for lm in hand_landmarks.landmark]
                y_coords = [int(lm.y * h) for lm in hand_landmarks.landmark]

                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)

                hand_regions.append((x_min, y_min, x_max - x_min, y_max - y_min))

        # 器具を検出
        instruments = []
        if hand_regions:
            instruments = self.detect_instruments_edge(frame, hand_regions)

        return hands_result, instruments

    def visualize(self, frame, hands_result, instruments, frame_num, total_frames):
        """可視化"""
        vis_frame = frame.copy()

        # 手を描画（緑）
        if hands_result.multi_hand_landmarks:
            for hand_landmarks in hands_result.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    vis_frame, hand_landmarks,
                    mp.solutions.hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                    self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2)
                )

        # 器具を描画（青）
        for instrument in instruments:
            cv2.drawContours(vis_frame, [instrument], 0, (255, 100, 0), 2)

            # 器具領域を半透明で塗りつぶし
            overlay = vis_frame.copy()
            cv2.fillPoly(overlay, [instrument], (255, 150, 0))
            vis_frame = cv2.addWeighted(vis_frame, 0.7, overlay, 0.3, 0)

        # 情報パネル
        progress = (frame_num / total_frames * 100) if total_frames > 0 else 0

        # 背景ボックス
        cv2.rectangle(vis_frame, (10, 10), (400, 100), (0, 0, 0), -1)
        cv2.rectangle(vis_frame, (10, 10), (400, 100), (255, 255, 255), 2)

        cv2.putText(vis_frame, f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        hands_text = "Hands: " + ("Detected" if hands_result.multi_hand_landmarks else "Not detected")
        color = (0, 255, 0) if hands_result.multi_hand_landmarks else (100, 100, 100)
        cv2.putText(vis_frame, hands_text,
                   (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        inst_text = f"Instruments: {len(instruments)}"
        color = (255, 150, 0) if instruments else (100, 100, 100)
        cv2.putText(vis_frame, inst_text,
                   (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return vis_frame

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"Simple INSTRUMENT DETECTION using edge detection")

        cap = cv2.VideoCapture(str(self.input_path))

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video: {width}x{height} @ {fps}fps, {total_frames} frames")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(self.output_path), fourcc, fps, (width, height))

        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 処理
            hands_result, instruments = self.process_frame(frame)

            # 統計更新
            if hands_result.multi_hand_landmarks:
                self.stats['hands_detected'] += 1
            if instruments:
                self.stats['instruments_detected'] += 1

            # 可視化
            vis_frame = self.visualize(frame, hands_result, instruments, frame_count, total_frames)
            out.write(vis_frame)

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示（10%ごと）
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames * 100)
                hands_rate = (self.stats['hands_detected'] / frame_count * 100)
                inst_rate = (self.stats['instruments_detected'] / frame_count * 100)
                logger.info(f"Progress: {progress:.1f}% | Hands: {hands_rate:.1f}% | Instruments: {inst_rate:.1f}%")

        cap.release()
        out.release()

        self._print_stats()

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)

        total = self.stats['total_frames']
        hands = self.stats['hands_detected']
        instruments = self.stats['instruments_detected']

        print(f"Total frames: {total}")
        print(f"Hands detected: {hands} ({hands/total*100:.1f}%)")
        print(f"Instruments detected: {instruments} ({instruments/total*100:.1f}%)")
        print(f"Output saved to: {self.output_path}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/instrument_simple_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    # 出力ディレクトリ作成
    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("SIMPLE INSTRUMENT DETECTION")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    detector = SimpleInstrumentDetector(str(input_video), str(output_video))
    detector.generate_video()


if __name__ == "__main__":
    main()