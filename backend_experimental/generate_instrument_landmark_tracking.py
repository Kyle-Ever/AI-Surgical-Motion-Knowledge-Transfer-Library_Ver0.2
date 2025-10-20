"""器具をMediaPipeのようにランドマークでトラッキングするシステム"""

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
from scipy import ndimage
from skimage.morphology import skeletonize
from scipy.interpolate import splprep, splev

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InstrumentLandmarkTracker:
    """器具をランドマーク点で表現してMediaPipe風にトラッキング"""

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

        # 器具のランドマーク数（MediaPipeの手は21点、器具は15点）
        self.num_landmarks = 15

        # ランドマークの連結情報（どの点とどの点を線でつなぐか）
        self.landmark_connections = [
            (i, i+1) for i in range(self.num_landmarks - 1)
        ]

        # トラッキングデータ
        self.instrument_landmarks = {
            'left': deque(maxlen=5),   # スムージング用
            'right': deque(maxlen=5)
        }

        # カルマンフィルタ（各ランドマーク用）
        self.kalman_filters = {
            'left': {},
            'right': {}
        }

        # 統計
        self.stats = {
            'total_frames': 0,
            'detection_success': {'left': 0, 'right': 0},
            'landmark_stability': {'left': [], 'right': []},
            'tracking_quality': []
        }

    def init_kalman(self):
        """カルマンフィルタを初期化"""
        kf = cv2.KalmanFilter(4, 2)
        kf.measurementMatrix = np.array([[1, 0, 0, 0],
                                         [0, 1, 0, 0]], np.float32)
        kf.transitionMatrix = np.array([[1, 0, 1, 0],
                                        [0, 1, 0, 1],
                                        [0, 0, 1, 0],
                                        [0, 0, 0, 1]], np.float32)
        kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.01
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.1
        return kf

    def detect_instrument_region(self, frame, hand_landmarks):
        """手の周辺から器具領域を検出"""
        h, w = frame.shape[:2]

        # 手のバウンディングボックスを取得
        hand_points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

        x_coords = [p[0] for p in hand_points]
        y_coords = [p[1] for p in hand_points]

        hand_center_x = sum(x_coords) // len(x_coords)
        hand_center_y = sum(y_coords) // len(y_coords)

        # 器具は手の延長にあるので、手の周囲を拡張
        padding = 200
        x1 = max(0, min(x_coords) - padding)
        y1 = max(0, min(y_coords) - padding)
        x2 = min(w, max(x_coords) + padding)
        y2 = min(h, max(y_coords) + padding)

        roi = frame[y1:y2, x1:x2]

        # 器具の特徴を抽出
        mask = self.extract_instrument(roi, frame[y1:y2, x1:x2])

        if mask is None:
            return None

        # グローバル座標系での器具情報
        return {
            'mask': mask,
            'offset': (x1, y1),
            'hand_center': (hand_center_x, hand_center_y)
        }

    def extract_instrument(self, roi, original_roi):
        """器具を抽出"""
        if roi.size == 0:
            return None

        # HSVで金属的な特徴を検出
        hsv = cv2.cvtColor(original_roi, cv2.COLOR_BGR2HSV)

        # 金属器具の特徴（低彩度、高明度）
        lower = np.array([0, 0, 100])
        upper = np.array([180, 60, 255])
        metal_mask = cv2.inRange(hsv, lower, upper)

        # エッジ検出
        gray = cv2.cvtColor(original_roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 30, 100)

        # ラプラシアンで細かいエッジも検出
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_mask = (np.abs(laplacian) > 20).astype(np.uint8) * 255

        # マスクを結合
        combined = cv2.bitwise_or(metal_mask, edges)
        combined = cv2.bitwise_or(combined, laplacian_mask)

        # モルフォロジー処理
        kernel = np.ones((3, 3), np.uint8)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)

        # 最大の連結成分を器具とする
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(combined)

        if num_labels <= 1:
            return None

        # 細長い形状を選択
        valid_mask = np.zeros_like(combined)

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < 300:
                continue

            # バウンディングボックスのアスペクト比
            width = stats[i, cv2.CC_STAT_WIDTH]
            height = stats[i, cv2.CC_STAT_HEIGHT]

            if width > 0 and height > 0:
                aspect_ratio = max(width, height) / min(width, height)

                # 細長い形状（器具の特徴）
                if aspect_ratio > 2.0:
                    valid_mask[labels == i] = 255

        if np.sum(valid_mask) < 500:
            return None

        return valid_mask

    def extract_landmarks(self, mask, hand_center, offset):
        """器具のマスクからランドマークを抽出"""
        if mask is None or np.sum(mask) < 100:
            return None

        # スケルトン化で中心線を取得
        skeleton = skeletonize(mask // 255).astype(np.uint8) * 255

        # スケルトン上の点を取得
        skeleton_points = np.column_stack(np.where(skeleton > 0))

        if len(skeleton_points) < 10:
            return None

        # 点を並び替え（一筆書きになるように）
        ordered_points = self.order_skeleton_points(skeleton_points, hand_center, offset)

        if ordered_points is None or len(ordered_points) < 10:
            return None

        # スプライン補間で滑らかな曲線を作成
        try:
            # 点をxy座標に変換
            points = np.array(ordered_points)
            x = points[:, 1]  # column
            y = points[:, 0]  # row

            # パラメトリックスプライン
            if len(x) > 3:
                tck, u = splprep([x, y], s=len(x)*2, k=min(3, len(x)-1))

                # 等間隔でランドマークを配置
                u_new = np.linspace(0, 1, self.num_landmarks)
                landmarks_x, landmarks_y = splev(u_new, tck)

                # グローバル座標に変換
                landmarks = []
                for i in range(self.num_landmarks):
                    lm_x = int(landmarks_x[i] + offset[0])
                    lm_y = int(landmarks_y[i] + offset[1])
                    landmarks.append((lm_x, lm_y))

                return landmarks

        except:
            pass

        # スプライン失敗時は等間隔でサンプリング
        step = max(1, len(ordered_points) // self.num_landmarks)
        landmarks = []

        for i in range(0, len(ordered_points), step):
            if len(landmarks) >= self.num_landmarks:
                break
            point = ordered_points[i]
            lm_x = point[1] + offset[0]
            lm_y = point[0] + offset[1]
            landmarks.append((lm_x, lm_y))

        # 不足分は最後の点で埋める
        while len(landmarks) < self.num_landmarks:
            landmarks.append(landmarks[-1])

        return landmarks[:self.num_landmarks]

    def order_skeleton_points(self, skeleton_points, hand_center, offset):
        """スケルトン点を順序付け（握り部から先端へ）"""
        if len(skeleton_points) == 0:
            return None

        # 手の中心に最も近い点を始点とする
        hand_x = hand_center[0] - offset[0]
        hand_y = hand_center[1] - offset[1]

        distances = []
        for point in skeleton_points:
            dist = np.sqrt((point[0] - hand_y)**2 + (point[1] - hand_x)**2)
            distances.append(dist)

        start_idx = np.argmin(distances)
        start_point = skeleton_points[start_idx]

        # 最近傍法で点を順序付け
        ordered = [start_point]
        remaining = list(skeleton_points)
        remaining.pop(start_idx)

        while remaining:
            if len(ordered) > 200:  # 無限ループ防止
                break

            current = ordered[-1]

            # 最も近い次の点を探す
            min_dist = float('inf')
            next_idx = -1

            for i, point in enumerate(remaining):
                dist = np.sqrt((point[0] - current[0])**2 + (point[1] - current[1])**2)
                if dist < min_dist:
                    min_dist = dist
                    next_idx = i

            if next_idx >= 0 and min_dist < 10:  # 距離閾値
                ordered.append(remaining[next_idx])
                remaining.pop(next_idx)
            else:
                break

        return ordered if len(ordered) > 10 else None

    def smooth_landmarks(self, landmarks, hand_label):
        """カルマンフィルタでランドマークを平滑化"""
        if landmarks is None:
            return None

        smoothed = []

        for i, (x, y) in enumerate(landmarks):
            # 各ランドマーク用のカルマンフィルタ
            if i not in self.kalman_filters[hand_label]:
                kf = self.init_kalman()
                kf.statePre = np.array([x, y, 0, 0], dtype=np.float32)
                kf.statePost = kf.statePre.copy()
                self.kalman_filters[hand_label][i] = kf

            kf = self.kalman_filters[hand_label][i]

            # 予測
            prediction = kf.predict()

            # 測定値で更新
            measurement = np.array([[x], [y]], dtype=np.float32)
            kf.correct(measurement)

            # 平滑化された位置
            smoothed_x = int(kf.statePost[0])
            smoothed_y = int(kf.statePost[1])
            smoothed.append((smoothed_x, smoothed_y))

        return smoothed

    def visualize_landmarks(self, frame, landmarks_dict):
        """MediaPipe風にランドマークを可視化"""
        vis_frame = frame.copy()

        for hand_label, landmarks in landmarks_dict.items():
            if landmarks is None:
                continue

            # 左手は緑、右手は赤
            color = (0, 255, 0) if hand_label == 'left' else (255, 0, 0)
            connection_color = (0, 200, 0) if hand_label == 'left' else (200, 0, 0)

            # 接続線を描画
            for connection in self.landmark_connections:
                start_idx, end_idx = connection
                if start_idx < len(landmarks) and end_idx < len(landmarks):
                    cv2.line(vis_frame,
                            landmarks[start_idx],
                            landmarks[end_idx],
                            connection_color, 2)

            # ランドマーク点を描画
            for i, landmark in enumerate(landmarks):
                # 始点（握り部）は大きく
                if i == 0:
                    cv2.circle(vis_frame, landmark, 6, (0, 255, 255), -1)
                    cv2.circle(vis_frame, landmark, 8, color, 2)
                # 終点（先端）も大きく
                elif i == self.num_landmarks - 1:
                    cv2.circle(vis_frame, landmark, 6, (255, 0, 255), -1)
                    cv2.circle(vis_frame, landmark, 8, color, 2)
                # 中間点
                else:
                    cv2.circle(vis_frame, landmark, 4, color, -1)
                    cv2.circle(vis_frame, landmark, 5, (255, 255, 255), 1)

                # ランドマーク番号を表示（デバッグ用、必要に応じてコメントアウト）
                # cv2.putText(vis_frame, str(i),
                #            (landmark[0] + 5, landmark[1] - 5),
                #            cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)

        return vis_frame

    def calculate_metrics(self, landmarks):
        """ランドマークからメトリクスを計算"""
        if landmarks is None or len(landmarks) < 2:
            return None

        # 全体の長さ
        total_length = 0
        for i in range(len(landmarks) - 1):
            dist = np.linalg.norm(
                np.array(landmarks[i+1]) - np.array(landmarks[i])
            )
            total_length += dist

        # 直線性（始点と終点の距離 vs 経路長）
        direct_dist = np.linalg.norm(
            np.array(landmarks[-1]) - np.array(landmarks[0])
        )
        linearity = direct_dist / (total_length + 0.001)

        # 曲率（隣接ベクトルの角度変化）
        curvatures = []
        for i in range(1, len(landmarks) - 1):
            v1 = np.array(landmarks[i]) - np.array(landmarks[i-1])
            v2 = np.array(landmarks[i+1]) - np.array(landmarks[i])

            if np.linalg.norm(v1) > 0 and np.linalg.norm(v2) > 0:
                v1_norm = v1 / np.linalg.norm(v1)
                v2_norm = v2 / np.linalg.norm(v2)
                angle = np.arccos(np.clip(np.dot(v1_norm, v2_norm), -1, 1))
                curvatures.append(angle)

        avg_curvature = np.mean(curvatures) if curvatures else 0

        return {
            'length': total_length,
            'linearity': linearity,
            'curvature': avg_curvature
        }

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"INSTRUMENT LANDMARK TRACKING (MediaPipe-style)")

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

            # 手を検出
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands_result = self.mp_hands.process(rgb_frame)

            current_landmarks = {}

            if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
                for hand_landmarks, handedness in zip(
                    hands_result.multi_hand_landmarks,
                    hands_result.multi_handedness
                ):
                    # 左右判定
                    hand_label = 'left' if handedness.classification[0].label == 'Right' else 'right'

                    # 器具領域を検出
                    instrument_region = self.detect_instrument_region(frame, hand_landmarks)

                    if instrument_region:
                        # ランドマークを抽出
                        landmarks = self.extract_landmarks(
                            instrument_region['mask'],
                            instrument_region['hand_center'],
                            instrument_region['offset']
                        )

                        # スムージング
                        if landmarks:
                            landmarks = self.smooth_landmarks(landmarks, hand_label)
                            current_landmarks[hand_label] = landmarks
                            self.stats['detection_success'][hand_label] += 1

                            # メトリクス計算
                            metrics = self.calculate_metrics(landmarks)
                            if metrics:
                                self.stats['tracking_quality'].append(metrics['linearity'])

                    # 手を薄く描画（参考用）
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(230, 230, 230), thickness=1, circle_radius=1),
                        self.mp_drawing.DrawingSpec(color=(230, 230, 230), thickness=1)
                    )

            # ランドマークを可視化
            vis_frame = self.visualize_landmarks(frame, current_landmarks)

            # 情報パネル
            self.add_info_panel(vis_frame, frame_count, total_frames, current_landmarks)

            out.write(vis_frame)

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames * 100)
                left_rate = (self.stats['detection_success']['left'] / frame_count * 100)
                right_rate = (self.stats['detection_success']['right'] / frame_count * 100)
                logger.info(f"Progress: {progress:.1f}% | Left: {left_rate:.1f}% | Right: {right_rate:.1f}%")

        cap.release()
        out.release()
        self.mp_hands.close()

        # メトリクスを保存
        self.save_metrics()
        self._print_stats()

    def add_info_panel(self, frame, frame_num, total_frames, landmarks):
        """情報パネルを追加"""
        h, w = frame.shape[:2]

        # 上部に小さなパネル
        panel_height = 40
        cv2.rectangle(frame, (0, 0), (w, panel_height), (0, 0, 0), -1)
        cv2.rectangle(frame, (0, 0), (w, panel_height), (255, 255, 255), 1)

        # 進捗
        progress = (frame_num / total_frames * 100) if total_frames > 0 else 0

        # テキスト
        text = f"Frame: {frame_num}/{total_frames} ({progress:.1f}%) | "
        text += f"Tracking: {len(landmarks)} instruments"

        cv2.putText(frame, text,
                   (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    def save_metrics(self):
        """メトリクスを保存"""
        metrics_file = self.output_path.with_suffix('.json')

        save_data = {
            'stats': {
                'total_frames': self.stats['total_frames'],
                'left_detection_rate': self.stats['detection_success']['left'] / max(1, self.stats['total_frames']),
                'right_detection_rate': self.stats['detection_success']['right'] / max(1, self.stats['total_frames']),
                'avg_tracking_quality': np.mean(self.stats['tracking_quality']) if self.stats['tracking_quality'] else 0
            },
            'num_landmarks': self.num_landmarks
        }

        with open(metrics_file, 'w') as f:
            json.dump(save_data, f, indent=2, default=float)

        logger.info(f"Metrics saved to: {metrics_file}")

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("INSTRUMENT LANDMARK TRACKING COMPLETE")
        print("=" * 80)

        print(f"\nTotal frames: {self.stats['total_frames']}")
        print(f"Landmarks per instrument: {self.num_landmarks}")

        for hand in ['left', 'right']:
            success = self.stats['detection_success'][hand]
            rate = success / max(1, self.stats['total_frames']) * 100
            print(f"\n{hand.capitalize()} hand:")
            print(f"  - Detection rate: {rate:.1f}% ({success} frames)")

        if self.stats['tracking_quality']:
            avg_quality = np.mean(self.stats['tracking_quality'])
            print(f"\nAverage tracking quality: {avg_quality:.3f}")

        print(f"\nOutput video: {self.output_path}")
        print(f"Metrics JSON: {self.output_path.with_suffix('.json')}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/landmark_tracking_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("INSTRUMENT LANDMARK TRACKING (MediaPipe-style)")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    tracker = InstrumentLandmarkTracker(str(input_video), str(output_video))
    tracker.generate_video()


if __name__ == "__main__":
    main()