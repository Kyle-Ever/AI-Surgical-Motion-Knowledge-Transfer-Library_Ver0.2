"""器具の形状を直接認識して追跡するシステム"""

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


class ShapeRecognitionTracker:
    """器具の形状を認識して追跡"""

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

        # 器具のテンプレート（初回検出時に保存）
        self.instrument_templates = {'left': None, 'right': None}

        # トラッキング履歴
        self.tracking_history = {
            'left': deque(maxlen=30),
            'right': deque(maxlen=30)
        }

        # 統計
        self.stats = {
            'total_frames': 0,
            'hands_detected': 0,
            'instruments_detected': 0,
            'tracking_quality': []
        }

    def detect_instrument_shape(self, frame, hand_landmarks):
        """器具の形状を検出"""
        h, w = frame.shape[:2]

        # 手の領域を取得
        hand_bbox = self.get_hand_bbox(hand_landmarks, w, h)

        if hand_bbox is None:
            return None

        # 手の周囲を拡張して器具を含める
        x, y, hw, hh = hand_bbox
        padding = 150
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(w, x + hw + padding)
        y2 = min(h, y + hh + padding)

        # 対象領域を切り出し
        roi = frame[y1:y2, x1:x2]

        # 器具の特徴を抽出
        instrument_mask = self.extract_instrument_features(roi)

        if instrument_mask is None:
            return None

        # 器具の形状を検出
        shape_info = self.analyze_shape(instrument_mask, (x1, y1))

        if shape_info:
            shape_info['roi'] = (x1, y1, x2, y2)

        return shape_info

    def get_hand_bbox(self, hand_landmarks, w, h):
        """手のバウンディングボックスを取得"""
        x_coords = [int(lm.x * w) for lm in hand_landmarks.landmark]
        y_coords = [int(lm.y * h) for lm in hand_landmarks.landmark]

        if not x_coords or not y_coords:
            return None

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        return (x_min, y_min, x_max - x_min, y_max - y_min)

    def extract_instrument_features(self, roi):
        """器具の特徴を抽出"""
        if roi.size == 0:
            return None

        # 複数の特徴を組み合わせる
        h, w = roi.shape[:2]

        # 1. 色による検出（金属的な特徴）
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # 金属的な色（低彩度）
        lower_metal = np.array([0, 0, 50])
        upper_metal = np.array([180, 80, 255])
        metal_mask = cv2.inRange(hsv, lower_metal, upper_metal)

        # 2. エッジ検出
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 適応的エッジ検出
        edges = cv2.adaptiveThreshold(blurred, 255,
                                     cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)

        # エッジを反転（白が物体）
        edges = 255 - edges

        # 3. 輝度による検出（器具は明るい）
        _, bright_mask = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)

        # マスクを結合
        combined = cv2.bitwise_or(metal_mask, edges)
        combined = cv2.bitwise_and(combined, bright_mask)

        # ノイズ除去
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)

        # 小さい領域を除去
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(combined, connectivity=8)

        min_area = 200
        filtered_mask = np.zeros_like(combined)

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area >= min_area:
                filtered_mask[labels == i] = 255

        return filtered_mask

    def analyze_shape(self, mask, offset):
        """器具の形状を分析"""
        if mask is None or np.sum(mask) < 100:
            return None

        # 輪郭を検出
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # 細長い形状を選択（器具の特徴）
        instrument_contours = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 100:
                continue

            # 最小外接矩形
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (width, height), angle = rect

            if width > 0 and height > 0:
                aspect_ratio = max(width, height) / min(width, height)

                # 細長い形状（器具らしい）
                if aspect_ratio > 2.5:
                    # グローバル座標に変換
                    cnt_global = cnt.copy()
                    cnt_global[:, 0, 0] += offset[0]
                    cnt_global[:, 0, 1] += offset[1]

                    instrument_contours.append({
                        'contour': cnt_global,
                        'center': (int(cx + offset[0]), int(cy + offset[1])),
                        'size': (width, height),
                        'angle': angle,
                        'aspect_ratio': aspect_ratio,
                        'area': area
                    })

        if not instrument_contours:
            return None

        # 最も器具らしい形状を選択（アスペクト比が大きい）
        best_instrument = max(instrument_contours, key=lambda x: x['aspect_ratio'])

        # 器具の端点を計算
        endpoints = self.find_endpoints(best_instrument['contour'])

        best_instrument['endpoints'] = endpoints

        return best_instrument

    def find_endpoints(self, contour):
        """輪郭の端点を見つける"""
        if len(contour) < 10:
            return None

        # 輪郭点の重心を計算
        M = cv2.moments(contour)
        if M["m00"] == 0:
            return None

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        center = np.array([cx, cy])

        # 重心から最も遠い2点を端点とする
        points = contour.reshape(-1, 2)
        distances = np.linalg.norm(points - center, axis=1)

        # 最遠点
        max_idx = np.argmax(distances)
        endpoint1 = points[max_idx]

        # 反対側の最遠点を探す
        # endpoint1から最も遠い点
        distances_from_ep1 = np.linalg.norm(points - endpoint1, axis=1)
        max_idx2 = np.argmax(distances_from_ep1)
        endpoint2 = points[max_idx2]

        return (tuple(endpoint1), tuple(endpoint2))

    def track_shape(self, frame, prev_shape, search_region=None):
        """前フレームの形状を追跡"""
        if prev_shape is None:
            return None

        # 探索領域を設定
        if search_region:
            x1, y1, x2, y2 = search_region
            roi = frame[y1:y2, x1:x2]
        else:
            # 前回の位置周辺を探索
            cx, cy = prev_shape['center']
            search_size = 200
            x1 = max(0, cx - search_size)
            y1 = max(0, cy - search_size)
            x2 = min(frame.shape[1], cx + search_size)
            y2 = min(frame.shape[0], cy + search_size)
            roi = frame[y1:y2, x1:x2]

        # 器具特徴を抽出
        instrument_mask = self.extract_instrument_features(roi)

        if instrument_mask is None:
            return None

        # 形状を分析
        shape_info = self.analyze_shape(instrument_mask, (x1, y1))

        return shape_info

    def visualize(self, frame, shapes, frame_num, total_frames):
        """検出結果を可視化"""
        vis_frame = frame.copy()

        # 各手の器具を描画
        for hand_label, shape in shapes.items():
            if shape is None:
                continue

            color = (0, 255, 0) if hand_label == 'left' else (0, 0, 255)

            # 輪郭を描画
            if 'contour' in shape:
                # 輪郭を太く描画
                cv2.drawContours(vis_frame, [shape['contour']], -1, color, 3)

                # 輪郭を塗りつぶし（半透明効果）
                overlay = vis_frame.copy()
                cv2.fillPoly(overlay, [shape['contour']], color)
                vis_frame = cv2.addWeighted(vis_frame, 0.7, overlay, 0.3, 0)

            # 端点を描画
            if 'endpoints' in shape and shape['endpoints']:
                ep1, ep2 = shape['endpoints']

                # 端点を強調
                cv2.circle(vis_frame, ep1, 10, (0, 255, 255), -1)
                cv2.circle(vis_frame, ep2, 10, (255, 0, 255), -1)

                # 中心線
                cv2.line(vis_frame, ep1, ep2, (255, 255, 0), 2)

                # 長さを表示
                length = np.linalg.norm(np.array(ep2) - np.array(ep1))
                mid_point = ((ep1[0] + ep2[0]) // 2, (ep1[1] + ep2[1]) // 2)
                cv2.putText(vis_frame, f"{length:.0f}px",
                           mid_point,
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # 中心点
            if 'center' in shape:
                cv2.circle(vis_frame, shape['center'], 5, (255, 255, 255), -1)

            # 情報表示
            if 'aspect_ratio' in shape:
                info_text = f"AR: {shape['aspect_ratio']:.1f}"
                cv2.putText(vis_frame, info_text,
                           (shape['center'][0] - 30, shape['center'][1] + 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # 軌跡表示は削除（動画が見にくくなるため）

        # 情報パネル
        h = vis_frame.shape[0]
        panel_y = h - 80

        # 背景
        cv2.rectangle(vis_frame, (0, panel_y), (vis_frame.shape[1], h), (0, 0, 0), -1)
        cv2.rectangle(vis_frame, (0, panel_y), (vis_frame.shape[1], h), (255, 255, 255), 2)

        # 進捗
        progress = (frame_num / total_frames * 100) if total_frames > 0 else 0
        cv2.putText(vis_frame,
                   f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (10, panel_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出状態
        detected = sum(1 for s in shapes.values() if s is not None)
        cv2.putText(vis_frame,
                   f"Tracking: {detected} instruments",
                   (10, panel_y + 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if detected else (100, 100, 100), 2)

        return vis_frame

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"SHAPE RECOGNITION TRACKING")

        cap = cv2.VideoCapture(str(self.input_path))

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video: {width}x{height} @ {fps}fps, {total_frames} frames")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(self.output_path), fourcc, fps, (width, height))

        frame_count = 0
        prev_shapes = {'left': None, 'right': None}

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 手を検出
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands_result = self.mp_hands.process(rgb_frame)

            current_shapes = {'left': None, 'right': None}

            if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
                self.stats['hands_detected'] += 1

                for hand_landmarks, handedness in zip(
                    hands_result.multi_hand_landmarks,
                    hands_result.multi_handedness
                ):
                    # 左右判定
                    hand_label = 'left' if handedness.classification[0].label == 'Right' else 'right'

                    # 器具形状を検出
                    shape = self.detect_instrument_shape(frame, hand_landmarks)

                    # 検出失敗時は前フレームから追跡
                    if shape is None and prev_shapes[hand_label] is not None:
                        shape = self.track_shape(frame, prev_shapes[hand_label])

                    if shape:
                        current_shapes[hand_label] = shape
                        self.tracking_history[hand_label].append(shape)
                        self.stats['instruments_detected'] += 1

                    # 手を薄く描画
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(200, 200, 200), thickness=1, circle_radius=1),
                        self.mp_drawing.DrawingSpec(color=(200, 200, 200), thickness=1)
                    )

            # 可視化
            vis_frame = self.visualize(frame, current_shapes, frame_count, total_frames)
            out.write(vis_frame)

            # 次フレーム用に保存
            prev_shapes = current_shapes.copy()

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames * 100)
                detection_rate = (self.stats['instruments_detected'] /
                                (self.stats['hands_detected'] * 2) * 100) if self.stats['hands_detected'] else 0
                logger.info(f"Progress: {progress:.1f}% | Detection rate: {detection_rate:.1f}%")

        cap.release()
        out.release()
        self.mp_hands.close()

        self._print_stats()

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("SHAPE RECOGNITION TRACKING COMPLETE")
        print("=" * 80)

        print(f"\nTotal frames: {self.stats['total_frames']}")
        print(f"Hands detected: {self.stats['hands_detected']}")
        print(f"Instruments detected: {self.stats['instruments_detected']}")

        if self.stats['hands_detected'] > 0:
            detection_rate = (self.stats['instruments_detected'] /
                            (self.stats['hands_detected'] * 2) * 100)
            print(f"Detection rate: {detection_rate:.1f}%")

        print(f"\nOutput video: {self.output_path}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/shape_tracking_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("SHAPE RECOGNITION TRACKING")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    tracker = ShapeRecognitionTracker(str(input_video), str(output_video))
    tracker.generate_video()


if __name__ == "__main__":
    main()