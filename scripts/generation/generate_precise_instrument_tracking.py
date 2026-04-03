"""器具の実際の形状・ベクトルに正確に沿った高精度トラッキング"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
import mediapipe as mp
from collections import deque
import math
import json
from scipy import ndimage
from skimage.morphology import skeletonize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PreciseInstrumentTracker:
    """器具の実際の形状とベクトルを正確に追跡"""

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

        # トラッキングデータ
        self.instrument_data = {
            'left': {
                'contours': [],  # 器具の輪郭
                'vectors': [],   # 器具のベクトル (start, end)
                'lengths': [],   # 器具の長さ
                'angles': [],    # 器具の角度
                'centers': [],   # 器具の中心
                'trajectories': []  # 軌跡
            },
            'right': {
                'contours': [],
                'vectors': [],
                'lengths': [],
                'angles': [],
                'centers': [],
                'trajectories': []
            }
        }

        # 前フレームの検出結果（連続性のため）
        self.prev_detections = {'left': None, 'right': None}

        # メトリクス
        self.metrics = {
            'total_frames': 0,
            'detection_success': {'left': 0, 'right': 0},
            'avg_length': {'left': 0, 'right': 0},
            'stability': {'left': 0, 'right': 0}
        }

    def detect_instrument_precise(self, frame, hand_landmarks, hand_label):
        """器具を精密に検出し、実際の形状とベクトルを取得"""
        h, w = frame.shape[:2]

        # 手の位置を取得
        hand_points = []
        for lm in hand_landmarks.landmark:
            hand_points.append((int(lm.x * w), int(lm.y * h)))

        # 握り部分を特定（親指と人差し指の間）
        thumb_tip = hand_points[4]
        index_tip = hand_points[8]
        grip_center = ((thumb_tip[0] + index_tip[0]) // 2,
                      (thumb_tip[1] + index_tip[1]) // 2)

        # 器具領域を抽出
        instrument_mask = self.extract_instrument_region(frame, grip_center, hand_points)

        if instrument_mask is None:
            return None

        # 器具の主軸を検出
        instrument_vector = self.find_instrument_axis(instrument_mask, grip_center)

        if instrument_vector is None:
            return None

        # 器具の輪郭を取得
        contours, _ = cv2.findContours(instrument_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # 最大の輪郭を器具とする
        instrument_contour = max(contours, key=cv2.contourArea)

        # 器具のベクトルと長さを計算
        start_point, end_point, length, angle = instrument_vector

        return {
            'contour': instrument_contour,
            'mask': instrument_mask,
            'vector': (start_point, end_point),
            'length': length,
            'angle': angle,
            'grip_center': grip_center,
            'confidence': self.calculate_confidence(instrument_mask, instrument_contour)
        }

    def extract_instrument_region(self, frame, grip_center, hand_points):
        """器具領域を正確に抽出"""
        h, w = frame.shape[:2]

        # 複数の手法を組み合わせる

        # 1. 色ベースの検出（金属的な特徴）
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 金属的な色範囲（低彩度、中〜高明度）
        lower_metal = np.array([0, 0, 80])
        upper_metal = np.array([180, 60, 255])
        metal_mask = cv2.inRange(hsv, lower_metal, upper_metal)

        # 2. エッジベースの検出
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ガウシアンブラーでノイズ除去
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Cannyエッジ検出（適応的閾値）
        median_val = np.median(blurred)
        lower_thresh = int(max(0, 0.66 * median_val))
        upper_thresh = int(min(255, 1.33 * median_val))
        edges = cv2.Canny(blurred, lower_thresh, upper_thresh)

        # 3. 勾配ベースの検出
        grad_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(grad_x**2 + grad_y**2)
        grad_mask = (grad_mag > np.percentile(grad_mag, 80)).astype(np.uint8) * 255

        # マスクを統合
        combined_mask = cv2.bitwise_or(metal_mask, edges)
        combined_mask = cv2.bitwise_or(combined_mask, grad_mask)

        # 手の領域を除外
        hand_mask = np.zeros((h, w), dtype=np.uint8)
        hand_polygon = np.array(hand_points, np.int32)
        cv2.fillPoly(hand_mask, [hand_polygon], 255)

        # 手の領域を膨張させて少し広げる
        kernel = np.ones((15, 15), np.uint8)
        hand_mask_dilated = cv2.dilate(hand_mask, kernel, iterations=1)

        # 器具は手の延長にあるので、手の境界付近は残す
        instrument_mask = cv2.bitwise_and(combined_mask, cv2.bitwise_not(hand_mask))

        # 握り点から繋がっている領域のみを抽出
        # Flood fillで連結成分を抽出
        filled_mask = np.zeros((h+2, w+2), np.uint8)
        if 0 <= grip_center[0] < w and 0 <= grip_center[1] < h:
            cv2.floodFill(instrument_mask, filled_mask, grip_center, 255,
                         loDiff=50, upDiff=50, flags=4)

        # モルフォロジー処理でノイズ除去と形状整形
        kernel_close = np.ones((5, 5), np.uint8)
        instrument_mask = cv2.morphologyEx(instrument_mask, cv2.MORPH_CLOSE, kernel_close)

        kernel_open = np.ones((3, 3), np.uint8)
        instrument_mask = cv2.morphologyEx(instrument_mask, cv2.MORPH_OPEN, kernel_open)

        # 最小面積チェック
        if np.sum(instrument_mask) < 500:
            return None

        return instrument_mask

    def find_instrument_axis(self, mask, grip_center):
        """器具の主軸（ベクトル）を検出"""
        h, w = mask.shape

        # スケルトン化で中心線を抽出
        skeleton = skeletonize(mask // 255).astype(np.uint8) * 255

        # 輪郭点を取得
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        largest_contour = max(contours, key=cv2.contourArea)

        # PCAで主軸を計算
        points = largest_contour.reshape(-1, 2).astype(np.float32)

        if len(points) < 10:
            return None

        # 主成分分析
        mean = np.mean(points, axis=0)
        centered = points - mean

        # 共分散行列
        cov = np.cov(centered.T)

        # 固有値と固有ベクトル
        eigenvalues, eigenvectors = np.linalg.eig(cov)

        # 最大固有値の固有ベクトル（主軸方向）
        main_axis_idx = np.argmax(eigenvalues)
        main_axis = eigenvectors[:, main_axis_idx]

        # 器具の端点を見つける
        # 主軸に沿って点を投影
        projections = np.dot(centered, main_axis)

        # 最小と最大の投影点
        min_idx = np.argmin(projections)
        max_idx = np.argmax(projections)

        start_point = tuple(points[min_idx].astype(int))
        end_point = tuple(points[max_idx].astype(int))

        # 握り点に近い方を始点にする
        dist_to_start = np.linalg.norm(np.array(start_point) - np.array(grip_center))
        dist_to_end = np.linalg.norm(np.array(end_point) - np.array(grip_center))

        if dist_to_end < dist_to_start:
            start_point, end_point = end_point, start_point

        # 長さと角度を計算
        vector = np.array(end_point) - np.array(start_point)
        length = np.linalg.norm(vector)
        angle = np.degrees(np.arctan2(vector[1], vector[0]))

        # より正確な端点検出（輪郭に沿って）
        # 主軸方向に最も遠い点を探す
        refined_end = self.find_farthest_point_along_axis(
            largest_contour, start_point, main_axis
        )

        if refined_end is not None:
            end_point = refined_end
            vector = np.array(end_point) - np.array(start_point)
            length = np.linalg.norm(vector)
            angle = np.degrees(np.arctan2(vector[1], vector[0]))

        return (start_point, end_point, length, angle)

    def find_farthest_point_along_axis(self, contour, start_point, axis_vector):
        """輪郭に沿って軸方向の最遠点を見つける"""
        points = contour.reshape(-1, 2)
        start = np.array(start_point)

        # 各点の軸方向への投影距離
        max_dist = 0
        farthest_point = None

        for point in points:
            vec_to_point = point - start
            # 軸方向への投影
            projection = np.dot(vec_to_point, axis_vector)

            if projection > max_dist:
                max_dist = projection
                farthest_point = tuple(point)

        return farthest_point

    def calculate_confidence(self, mask, contour):
        """検出の信頼度を計算"""
        # 面積
        area = cv2.contourArea(contour)

        # アスペクト比（細長いほど器具らしい）
        rect = cv2.minAreaRect(contour)
        width = rect[1][0]
        height = rect[1][1]

        if width > 0 and height > 0:
            aspect_ratio = max(width, height) / min(width, height)
        else:
            aspect_ratio = 1

        # 信頼度スコア
        area_score = min(1.0, area / 10000)  # 面積スコア
        aspect_score = min(1.0, aspect_ratio / 5)  # アスペクト比スコア

        confidence = (area_score + aspect_score) / 2

        return confidence

    def track_with_smoothing(self, current_detection, prev_detection, hand_label):
        """前フレームの情報を使ってスムージング"""
        if prev_detection is None:
            return current_detection

        if current_detection is None:
            # 前フレームの情報を減衰させて使用
            decayed = prev_detection.copy()
            decayed['confidence'] *= 0.8
            return decayed if decayed['confidence'] > 0.3 else None

        # スムージング係数
        alpha = 0.7  # 現在フレームの重み

        # ベクトルのスムージング
        prev_start, prev_end = prev_detection['vector']
        curr_start, curr_end = current_detection['vector']

        smoothed_start = (
            int(alpha * curr_start[0] + (1-alpha) * prev_start[0]),
            int(alpha * curr_start[1] + (1-alpha) * prev_start[1])
        )

        smoothed_end = (
            int(alpha * curr_end[0] + (1-alpha) * prev_end[0]),
            int(alpha * curr_end[1] + (1-alpha) * prev_end[1])
        )

        current_detection['vector'] = (smoothed_start, smoothed_end)

        # 長さの再計算
        vector = np.array(smoothed_end) - np.array(smoothed_start)
        current_detection['length'] = np.linalg.norm(vector)
        current_detection['angle'] = np.degrees(np.arctan2(vector[1], vector[0]))

        return current_detection

    def visualize(self, frame, detections, frame_num, total_frames):
        """器具の形状とベクトルを正確に可視化"""
        vis_frame = frame.copy()
        h, w = frame.shape[:2]

        # 各手の器具を描画
        for hand_label, detection in detections.items():
            if detection is None:
                continue

            color = (0, 255, 0) if hand_label == 'left' else (0, 100, 255)

            # 器具の輪郭を描画（半透明）
            if 'contour' in detection:
                # 輪郭の塗りつぶし（半透明効果）
                overlay = vis_frame.copy()
                cv2.drawContours(overlay, [detection['contour']], -1, color, -1)
                vis_frame = cv2.addWeighted(vis_frame, 0.7, overlay, 0.3, 0)

                # 輪郭線
                cv2.drawContours(vis_frame, [detection['contour']], -1, color, 2)

            # 器具のベクトル（主軸）を太い線で描画
            if 'vector' in detection:
                start, end = detection['vector']

                # メインベクトル（太い線）
                cv2.line(vis_frame, start, end, (255, 255, 0), 4)

                # 始点（握り側）
                cv2.circle(vis_frame, start, 8, (0, 255, 255), -1)
                cv2.circle(vis_frame, start, 10, (255, 255, 255), 2)

                # 終点（先端）
                cv2.circle(vis_frame, end, 8, (255, 0, 255), -1)
                cv2.circle(vis_frame, end, 10, (255, 255, 255), 2)

                # ベクトル情報を表示
                mid_point = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
                length_text = f"{detection['length']:.0f}px"
                cv2.putText(vis_frame, length_text,
                           (mid_point[0] + 10, mid_point[1]),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

                # 角度表示
                angle_text = f"{detection['angle']:.0f}°"
                cv2.putText(vis_frame, angle_text,
                           (start[0] + 10, start[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # 信頼度表示
            if 'confidence' in detection:
                conf_text = f"Conf: {detection['confidence']:.2f}"
                grip_pos = detection.get('grip_center', (50, 50))
                cv2.putText(vis_frame, conf_text,
                           (grip_pos[0] - 30, grip_pos[1] + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # 軌跡を描画（最近30フレーム）
        for hand_label, color in [('left', (100, 255, 100)), ('right', (255, 100, 100))]:
            data = self.instrument_data[hand_label]
            if len(data['vectors']) > 1:
                recent = data['vectors'][-min(30, len(data['vectors'])):]

                # 先端の軌跡
                for i in range(1, len(recent)):
                    if recent[i-1] and recent[i]:
                        prev_end = recent[i-1][1]
                        curr_end = recent[i][1]
                        cv2.line(vis_frame, prev_end, curr_end, color, 2)

        # 情報パネル
        panel_height = 120
        panel = np.zeros((panel_height, w, 3), dtype=np.uint8)

        # 進捗バー
        progress = (frame_num / total_frames * 100) if total_frames > 0 else 0
        cv2.rectangle(panel, (10, 10), (w-10, 30), (100, 100, 100), 2)
        cv2.rectangle(panel, (10, 10),
                     (int(10 + (w-20) * progress / 100), 30),
                     (0, 255, 0), -1)

        # メトリクス表示
        y_offset = 45
        texts = [
            f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
            f"Tracking: {sum(1 for d in detections.values() if d)} instruments"
        ]

        for hand_label in ['left', 'right']:
            if detections.get(hand_label):
                length = detections[hand_label].get('length', 0)
                texts.append(f"{hand_label.capitalize()}: {length:.0f}px")

        for i, text in enumerate(texts):
            cv2.putText(panel, text, (10, y_offset + i*20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # パネルを結合
        vis_frame = np.vstack([vis_frame, panel])

        return vis_frame

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"PRECISE INSTRUMENT TRACKING with exact shape/vector")

        cap = cv2.VideoCapture(str(self.input_path))

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        output_height = height + 120  # パネル分

        logger.info(f"Video: {width}x{height} @ {fps}fps, {total_frames} frames")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(self.output_path), fourcc, fps, (width, output_height))

        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 手を検出
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands_result = self.mp_hands.process(rgb_frame)

            current_detections = {}

            if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
                for hand_landmarks, handedness in zip(
                    hands_result.multi_hand_landmarks,
                    hands_result.multi_handedness
                ):
                    # 左右判定（画面反転考慮）
                    hand_label = 'left' if handedness.classification[0].label == 'Right' else 'right'

                    # 器具を精密に検出
                    detection = self.detect_instrument_precise(frame, hand_landmarks, hand_label)

                    # スムージング
                    detection = self.track_with_smoothing(
                        detection,
                        self.prev_detections[hand_label],
                        hand_label
                    )

                    if detection:
                        current_detections[hand_label] = detection
                        self.metrics['detection_success'][hand_label] += 1

                        # データを記録
                        data = self.instrument_data[hand_label]
                        data['vectors'].append(detection['vector'])
                        data['lengths'].append(detection['length'])
                        data['angles'].append(detection['angle'])

                        # 前フレームとして保存
                        self.prev_detections[hand_label] = detection

                    # 手を描画（薄く）
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(200, 200, 200), thickness=1, circle_radius=2),
                        self.mp_drawing.DrawingSpec(color=(200, 200, 200), thickness=1)
                    )

            # 可視化
            vis_frame = self.visualize(frame, current_detections, frame_count, total_frames)
            out.write(vis_frame)

            frame_count += 1
            self.metrics['total_frames'] = frame_count

            # 進捗表示
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames * 100)
                tracked = sum(1 for d in current_detections.values() if d)
                logger.info(f"Progress: {progress:.1f}% | Tracking {tracked} instruments precisely")

        cap.release()
        out.release()
        self.mp_hands.close()

        # メトリクスを保存
        self.save_metrics()
        self._print_stats()

    def save_metrics(self):
        """メトリクスをJSON保存"""
        metrics_file = self.output_path.with_suffix('.json')

        # 統計を計算
        for hand_label in ['left', 'right']:
            data = self.instrument_data[hand_label]
            if data['lengths']:
                self.metrics['avg_length'][hand_label] = np.mean(data['lengths'])

                # 安定性（長さの変動係数）
                if len(data['lengths']) > 1:
                    std_dev = np.std(data['lengths'])
                    mean_len = np.mean(data['lengths'])
                    self.metrics['stability'][hand_label] = 1 - (std_dev / (mean_len + 1))

        save_data = {
            'metrics': self.metrics,
            'tracking_summary': {
                'left': {
                    'num_frames': len(self.instrument_data['left']['vectors']),
                    'avg_length': self.metrics['avg_length']['left'],
                    'stability': self.metrics['stability']['left'],
                    'success_rate': self.metrics['detection_success']['left'] / max(1, self.metrics['total_frames'])
                },
                'right': {
                    'num_frames': len(self.instrument_data['right']['vectors']),
                    'avg_length': self.metrics['avg_length']['right'],
                    'stability': self.metrics['stability']['right'],
                    'success_rate': self.metrics['detection_success']['right'] / max(1, self.metrics['total_frames'])
                }
            }
        }

        with open(metrics_file, 'w') as f:
            json.dump(save_data, f, indent=2, default=float)

        logger.info(f"Metrics saved to: {metrics_file}")

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("PRECISE INSTRUMENT TRACKING COMPLETE")
        print("=" * 80)

        print(f"\nTotal frames: {self.metrics['total_frames']}")

        for hand in ['left', 'right']:
            success = self.metrics['detection_success'][hand]
            rate = success / max(1, self.metrics['total_frames']) * 100

            print(f"\n{hand.capitalize()} hand:")
            print(f"  - Detection rate: {rate:.1f}% ({success} frames)")
            print(f"  - Avg length: {self.metrics['avg_length'][hand]:.1f} pixels")
            print(f"  - Stability: {self.metrics['stability'][hand]:.3f}")

        print(f"\nOutput video: {self.output_path}")
        print(f"Metrics JSON: {self.output_path.with_suffix('.json')}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/precise_tracking_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("PRECISE INSTRUMENT SHAPE & VECTOR TRACKING")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    tracker = PreciseInstrumentTracker(str(input_video), str(output_video))
    tracker.generate_video()


if __name__ == "__main__":
    main()