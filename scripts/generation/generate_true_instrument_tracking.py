"""器具を正確に検出・追跡するシステム（手ではなく器具そのもの）"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
import mediapipe as mp
from collections import deque
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrueInstrumentTracker:
    """器具そのものを正確に追跡"""

    def __init__(self, input_video: str, output_video: str):
        self.input_path = Path(input_video)
        self.output_path = Path(output_video)

        # MediaPipe手検出（手の位置参照用）
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.5,
            model_complexity=1
        )

        self.mp_drawing = mp.solutions.drawing_utils

        # ランドマーク数
        self.num_landmarks = 10  # 器具用に減らす

        # Optical Flow設定
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

        # トラッキング状態
        self.tracking_state = {
            'left': {'active': False, 'points': None, 'confidence': 0},
            'right': {'active': False, 'points': None, 'confidence': 0}
        }

        # 前フレーム
        self.prev_gray = None

        # 統計
        self.stats = {
            'total_frames': 0,
            'detection_success': {'left': 0, 'right': 0},
            'tracking_success': {'left': 0, 'right': 0}
        }

    def detect_instrument_directly(self, frame, hand_bbox=None):
        """器具を直接検出（手の領域は除外）"""
        h, w = frame.shape[:2]

        # グレースケール変換
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. 金属器具の特徴を強調
        # CLAHE（コントラスト強調）
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)

        # 2. エッジ検出（器具は強いエッジを持つ）
        edges = cv2.Canny(enhanced, 50, 150)

        # 3. 直線検出（器具は直線的）
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                                minLineLength=100, maxLineGap=10)

        if lines is None:
            return None

        # 4. 手の領域を除外
        mask = np.ones((h, w), dtype=np.uint8) * 255

        if hand_bbox:
            x, y, hw, hh = hand_bbox
            # 手の領域を少し拡張してマスク
            padding = 20
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(w, x + hw + padding)
            y2 = min(h, y + hh + padding)
            cv2.rectangle(mask, (x1, y1), (x2, y2), 0, -1)

        # 5. 器具らしい直線を選択
        instrument_points = []

        for line in lines:
            x1, y1, x2, y2 = line[0]

            # 手の領域外かチェック
            if mask[y1, x1] > 0 and mask[y2, x2] > 0:
                # 線の長さ
                length = np.sqrt((x2-x1)**2 + (y2-y1)**2)

                if length > 80:  # 十分長い
                    # 線上に等間隔で点を配置
                    num_points = self.num_landmarks
                    for i in range(num_points):
                        t = i / (num_points - 1)
                        px = int(x1 + t * (x2 - x1))
                        py = int(y1 + t * (y2 - y1))
                        instrument_points.append([px, py])

                    if len(instrument_points) >= self.num_landmarks:
                        break

        if len(instrument_points) < self.num_landmarks:
            return None

        # 最初のnum_landmarks個の点を返す
        return np.array(instrument_points[:self.num_landmarks], dtype=np.float32).reshape(-1, 1, 2)

    def detect_by_color_and_shape(self, frame):
        """色と形状で器具を検出"""
        h, w = frame.shape[:2]

        # HSVに変換
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 金属器具の色範囲（グレー系）
        lower_gray = np.array([0, 0, 120])
        upper_gray = np.array([180, 30, 255])
        gray_mask = cv2.inRange(hsv, lower_gray, upper_gray)

        # 光沢のある部分（高輝度）
        _, bright_mask = cv2.threshold(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                                      180, 255, cv2.THRESH_BINARY)

        # マスクを結合
        instrument_mask = cv2.bitwise_and(gray_mask, bright_mask)

        # ノイズ除去
        kernel = np.ones((3, 3), np.uint8)
        instrument_mask = cv2.morphologyEx(instrument_mask, cv2.MORPH_OPEN, kernel)
        instrument_mask = cv2.morphologyEx(instrument_mask, cv2.MORPH_CLOSE, kernel)

        # 輪郭検出
        contours, _ = cv2.findContours(instrument_mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # 最も細長い輪郭を選択
        best_contour = None
        best_ratio = 0

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 500:
                continue

            rect = cv2.minAreaRect(cnt)
            width, height = rect[1]

            if width > 0 and height > 0:
                ratio = max(width, height) / min(width, height)
                if ratio > best_ratio and ratio > 3:  # 細長い
                    best_ratio = ratio
                    best_contour = cnt

        if best_contour is None:
            return None

        # 輪郭を近似して主軸を取得
        epsilon = 0.02 * cv2.arcLength(best_contour, True)
        approx = cv2.approxPolyDP(best_contour, epsilon, True)

        if len(approx) < 2:
            return None

        # 最も離れた2点を端点とする
        max_dist = 0
        p1, p2 = None, None

        for i in range(len(approx)):
            for j in range(i+1, len(approx)):
                dist = np.linalg.norm(approx[i] - approx[j])
                if dist > max_dist:
                    max_dist = dist
                    p1 = approx[i][0]
                    p2 = approx[j][0]

        if p1 is None or p2 is None:
            return None

        # 線上に点を配置
        points = []
        for i in range(self.num_landmarks):
            t = i / (self.num_landmarks - 1)
            px = int(p1[0] + t * (p2[0] - p1[0]))
            py = int(p1[1] + t * (p2[1] - p1[1]))
            points.append([px, py])

        return np.array(points, dtype=np.float32).reshape(-1, 1, 2)

    def track_with_optical_flow(self, prev_gray, curr_gray, prev_points):
        """Optical Flowで追跡"""
        if prev_points is None:
            return None, 0

        # Lucas-Kanade
        next_points, status, error = cv2.calcOpticalFlowPyrLK(
            prev_gray, curr_gray, prev_points, None, **self.lk_params
        )

        if next_points is None:
            return None, 0

        # 有効な点を確認
        valid_count = np.sum(status == 1)

        if valid_count < self.num_landmarks * 0.3:
            return None, 0

        # エラーから信頼度を計算
        if error is not None and np.any(status == 1):
            avg_error = np.mean(error[status == 1])
            confidence = min(1.0, 10.0 / (avg_error + 1))
        else:
            confidence = 0.5

        return next_points, confidence

    def get_hand_bbox(self, hand_landmarks, w, h):
        """手のバウンディングボックスを取得"""
        x_coords = [int(lm.x * w) for lm in hand_landmarks.landmark]
        y_coords = [int(lm.y * h) for lm in hand_landmarks.landmark]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        return (x_min, y_min, x_max - x_min, y_max - y_min)

    def visualize(self, frame, tracking_state):
        """可視化"""
        vis_frame = frame.copy()

        for hand_label, state in tracking_state.items():
            if not state['active'] or state['points'] is None:
                continue

            points = state['points'].reshape(-1, 2)
            color = (0, 255, 0) if hand_label == 'left' else (0, 0, 255)

            # 器具を線で描画
            for i in range(len(points) - 1):
                pt1 = tuple(points[i].astype(int))
                pt2 = tuple(points[i+1].astype(int))
                thickness = 3 if state['confidence'] > 0.5 else 2
                cv2.line(vis_frame, pt1, pt2, color, thickness)

            # 端点を強調
            if len(points) > 0:
                # 始点
                cv2.circle(vis_frame, tuple(points[0].astype(int)), 8, (0, 255, 255), -1)
                # 終点
                cv2.circle(vis_frame, tuple(points[-1].astype(int)), 8, (255, 0, 255), -1)

            # 信頼度表示
            conf_text = f"{hand_label.upper()}: {state['confidence']:.2f}"
            y_pos = 60 if hand_label == 'left' else 90
            cv2.putText(vis_frame, conf_text,
                       (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return vis_frame

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"TRUE INSTRUMENT TRACKING (not hands)")

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

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 手を検出（参照用）
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands_result = self.mp_hands.process(rgb_frame)

            hand_bboxes = {}
            if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
                for hand_landmarks, handedness in zip(
                    hands_result.multi_hand_landmarks,
                    hands_result.multi_handedness
                ):
                    hand_label = 'left' if handedness.classification[0].label == 'Right' else 'right'
                    hand_bboxes[hand_label] = self.get_hand_bbox(hand_landmarks, width, height)

                    # 手を薄く表示
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(250, 250, 250), thickness=1, circle_radius=1),
                        self.mp_drawing.DrawingSpec(color=(250, 250, 250), thickness=1)
                    )

            # 各手に対応する器具を検出/追跡
            for hand_label in ['left', 'right']:
                state = self.tracking_state[hand_label]

                # 追跡中の場合
                if state['active'] and self.prev_gray is not None:
                    new_points, confidence = self.track_with_optical_flow(
                        self.prev_gray, gray, state['points']
                    )

                    if new_points is not None and confidence > 0.2:
                        state['points'] = new_points
                        state['confidence'] = confidence
                        self.stats['tracking_success'][hand_label] += 1
                        continue

                # 新規検出または再検出
                if hand_label in hand_bboxes:
                    # 手の近くで器具を探す
                    instrument_points = self.detect_instrument_directly(
                        frame, hand_bboxes[hand_label]
                    )

                    if instrument_points is None:
                        # 色と形状で再試行
                        instrument_points = self.detect_by_color_and_shape(frame)

                    if instrument_points is not None:
                        state['points'] = instrument_points
                        state['active'] = True
                        state['confidence'] = 1.0
                        self.stats['detection_success'][hand_label] += 1
                        logger.info(f"Detected instrument for {hand_label} at frame {frame_count}")
                    else:
                        state['active'] = False

            # 可視化
            vis_frame = self.visualize(frame, self.tracking_state)

            # フレーム情報
            info_text = f"Frame: {frame_count}/{total_frames}"
            cv2.putText(vis_frame, info_text,
                       (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            out.write(vis_frame)

            # 次フレーム用
            self.prev_gray = gray.copy()

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames * 100)
                logger.info(f"Progress: {progress:.1f}%")

        cap.release()
        out.release()
        self.mp_hands.close()

        self._print_stats()

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("TRUE INSTRUMENT TRACKING COMPLETE")
        print("=" * 80)

        print(f"\nTotal frames: {self.stats['total_frames']}")

        for hand in ['left', 'right']:
            detections = self.stats['detection_success'][hand]
            tracking = self.stats['tracking_success'][hand]
            total = detections + tracking

            print(f"\n{hand.capitalize()} hand:")
            print(f"  - New detections: {detections}")
            print(f"  - Optical flow tracking: {tracking}")
            print(f"  - Total success: {total} frames ({total/self.stats['total_frames']*100:.1f}%)")

        print(f"\nOutput: {self.output_path}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/true_instrument_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("TRUE INSTRUMENT TRACKING")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    tracker = TrueInstrumentTracker(str(input_video), str(output_video))
    tracker.generate_video()


if __name__ == "__main__":
    main()