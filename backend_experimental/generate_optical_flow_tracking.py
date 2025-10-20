"""Optical Flowを使った高精度器具トラッキングシステム"""

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
from scipy.interpolate import splprep, splev
from skimage.morphology import skeletonize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpticalFlowInstrumentTracker:
    """Optical Flowで器具を継続的に追跡"""

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

        # ランドマーク数
        self.num_landmarks = 15

        # 接続情報
        self.landmark_connections = [(i, i+1) for i in range(self.num_landmarks - 1)]

        # Optical Flow用
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )

        # トラッキング状態
        self.tracking_state = {
            'left': {
                'active': False,
                'points': None,
                'confidence': 0,
                'lost_frames': 0,
                'initial_detection': False
            },
            'right': {
                'active': False,
                'points': None,
                'confidence': 0,
                'lost_frames': 0,
                'initial_detection': False
            }
        }

        # 前フレーム（Optical Flow用）
        self.prev_gray = None

        # 統計
        self.stats = {
            'total_frames': 0,
            'initial_detections': {'left': 0, 'right': 0},
            'tracking_frames': {'left': 0, 'right': 0},
            'total_tracked': {'left': 0, 'right': 0},
            'tracking_quality': []
        }

        # 検出履歴（スムージング用）
        self.detection_history = {
            'left': deque(maxlen=3),
            'right': deque(maxlen=3)
        }

    def detect_initial_landmarks(self, frame, hand_landmarks):
        """初期ランドマークを検出"""
        h, w = frame.shape[:2]

        # 手の領域を取得
        hand_points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

        x_coords = [p[0] for p in hand_points]
        y_coords = [p[1] for p in hand_points]

        # 拡張領域で器具を探す
        padding = 200
        x1 = max(0, min(x_coords) - padding)
        y1 = max(0, min(y_coords) - padding)
        x2 = min(w, max(x_coords) + padding)
        y2 = min(h, max(y_coords) + padding)

        roi = frame[y1:y2, x1:x2]

        # 器具マスクを生成
        mask = self.extract_instrument_mask(roi)

        if mask is None or np.sum(mask) < 500:
            return None

        # スケルトン化
        skeleton = skeletonize(mask // 255).astype(np.uint8) * 255

        # スケルトン点を取得
        skeleton_points = np.column_stack(np.where(skeleton > 0))

        if len(skeleton_points) < 10:
            return None

        # 手の中心に近い点から順序付け
        hand_center_x = sum(x_coords) // len(x_coords) - x1
        hand_center_y = sum(y_coords) // len(y_coords) - y1

        ordered_points = self.order_points(skeleton_points, (hand_center_x, hand_center_y))

        if ordered_points is None or len(ordered_points) < 10:
            return None

        # ランドマークを生成（スプライン補間）
        try:
            points = np.array(ordered_points)
            x = points[:, 1]
            y = points[:, 0]

            if len(x) > 3:
                tck, u = splprep([x, y], s=len(x)*2, k=min(3, len(x)-1))
                u_new = np.linspace(0, 1, self.num_landmarks)
                landmarks_x, landmarks_y = splev(u_new, tck)

                # グローバル座標に変換
                landmarks = []
                for i in range(self.num_landmarks):
                    lm_x = int(landmarks_x[i] + x1)
                    lm_y = int(landmarks_y[i] + y1)
                    landmarks.append([lm_x, lm_y])

                return np.array(landmarks, dtype=np.float32).reshape(-1, 1, 2)
        except:
            pass

        # フォールバック：等間隔サンプリング
        step = max(1, len(ordered_points) // self.num_landmarks)
        landmarks = []

        for i in range(0, len(ordered_points), step):
            if len(landmarks) >= self.num_landmarks:
                break
            point = ordered_points[i]
            lm_x = point[1] + x1
            lm_y = point[0] + y1
            landmarks.append([lm_x, lm_y])

        # パディング
        while len(landmarks) < self.num_landmarks:
            landmarks.append(landmarks[-1])

        return np.array(landmarks[:self.num_landmarks], dtype=np.float32).reshape(-1, 1, 2)

    def extract_instrument_mask(self, roi):
        """器具マスクを抽出"""
        if roi.size == 0:
            return None

        # HSVで金属検出
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower = np.array([0, 0, 100])
        upper = np.array([180, 60, 255])
        metal_mask = cv2.inRange(hsv, lower, upper)

        # エッジ検出
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 30, 100)

        # 結合
        combined = cv2.bitwise_or(metal_mask, edges)

        # ノイズ除去
        kernel = np.ones((3, 3), np.uint8)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)

        # 最大連結成分
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(combined)

        if num_labels <= 1:
            return None

        # 細長い形状を選択
        valid_mask = np.zeros_like(combined)

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            width = stats[i, cv2.CC_STAT_WIDTH]
            height = stats[i, cv2.CC_STAT_HEIGHT]

            if area > 300 and width > 0 and height > 0:
                aspect_ratio = max(width, height) / min(width, height)
                if aspect_ratio > 2.0:
                    valid_mask[labels == i] = 255

        return valid_mask

    def order_points(self, points, hand_center):
        """点を順序付け"""
        if len(points) == 0:
            return None

        # 手の中心に最も近い点を開始点
        distances = [np.sqrt((p[0] - hand_center[1])**2 + (p[1] - hand_center[0])**2) for p in points]
        start_idx = np.argmin(distances)

        ordered = [points[start_idx]]
        remaining = list(points)
        remaining.pop(start_idx)

        # 最近傍法で順序付け
        while remaining and len(ordered) < 200:
            current = ordered[-1]
            min_dist = float('inf')
            next_idx = -1

            for i, point in enumerate(remaining):
                dist = np.sqrt((point[0] - current[0])**2 + (point[1] - current[1])**2)
                if dist < min_dist:
                    min_dist = dist
                    next_idx = i

            if next_idx >= 0 and min_dist < 10:
                ordered.append(remaining[next_idx])
                remaining.pop(next_idx)
            else:
                break

        return ordered if len(ordered) > 10 else None

    def track_with_optical_flow(self, prev_gray, curr_gray, prev_points):
        """Optical Flowで点を追跡"""
        if prev_points is None or len(prev_points) == 0:
            return None, None

        # Lucas-Kanade Optical Flow
        next_points, status, error = cv2.calcOpticalFlowPyrLK(
            prev_gray, curr_gray, prev_points, None, **self.lk_params
        )

        if next_points is None:
            return None, None

        # 有効な点のみ保持
        good_points = next_points[status == 1]

        if len(good_points) < self.num_landmarks * 0.5:  # 半分以上失った場合
            return None, None

        # 失った点を補間
        if len(good_points) < self.num_landmarks:
            next_points = self.interpolate_lost_points(next_points, status)

        # トラッキング品質を計算
        if error is not None:
            avg_error = np.mean(error[status == 1]) if np.any(status == 1) else float('inf')
            confidence = 1.0 / (1.0 + avg_error)
        else:
            confidence = 0.5

        return next_points, confidence

    def interpolate_lost_points(self, points, status):
        """失った点を補間"""
        if points is None:
            return None

        valid_indices = np.where(status == 1)[0]

        if len(valid_indices) == 0:
            return None

        # 全点の配列を作成
        interpolated = np.zeros_like(points)

        # 有効な点をコピー
        for idx in valid_indices:
            interpolated[idx] = points[idx]

        # 無効な点を補間
        for i in range(len(points)):
            if status[i] == 0:
                # 最も近い有効な点から補間
                if len(valid_indices) > 0:
                    # 前後の有効な点を探す
                    before = [idx for idx in valid_indices if idx < i]
                    after = [idx for idx in valid_indices if idx > i]

                    if before and after:
                        # 線形補間
                        b_idx = before[-1]
                        a_idx = after[0]
                        alpha = (i - b_idx) / (a_idx - b_idx)
                        interpolated[i] = (1 - alpha) * points[b_idx] + alpha * points[a_idx]
                    elif before:
                        # 前の点から外挿
                        interpolated[i] = points[before[-1]]
                    elif after:
                        # 後の点から外挿
                        interpolated[i] = points[after[0]]

        return interpolated

    def refine_tracking(self, frame, points, hand_label):
        """トラッキング結果を改善"""
        if points is None:
            return points

        # 点の連続性をチェック
        refined = points.copy()

        for i in range(1, len(points) - 1):
            if points[i] is not None and points[i-1] is not None and points[i+1] is not None:
                # 3点の関係から外れ値を検出
                p1 = points[i-1].flatten()
                p2 = points[i].flatten()
                p3 = points[i+1].flatten()

                # 中点との距離
                expected = (p1 + p3) / 2
                dist = np.linalg.norm(p2 - expected)

                if dist > 30:  # 外れ値
                    refined[i] = expected.reshape(1, 1, 2)

        return refined

    def visualize(self, frame, tracking_state):
        """トラッキング結果を可視化"""
        vis_frame = frame.copy()

        for hand_label, state in tracking_state.items():
            if not state['active'] or state['points'] is None:
                continue

            points = state['points'].reshape(-1, 2)
            color = (0, 255, 0) if hand_label == 'left' else (255, 0, 0)

            # 信頼度によって線の太さを変える
            line_thickness = int(2 + state['confidence'] * 3)

            # 接続線を描画
            for i in range(len(points) - 1):
                pt1 = tuple(points[i].astype(int))
                pt2 = tuple(points[i+1].astype(int))
                cv2.line(vis_frame, pt1, pt2, color, line_thickness)

            # ランドマーク点
            for i, point in enumerate(points):
                pt = tuple(point.astype(int))

                if i == 0:  # 握り部
                    cv2.circle(vis_frame, pt, 6, (0, 255, 255), -1)
                    cv2.circle(vis_frame, pt, 8, color, 2)
                elif i == len(points) - 1:  # 先端
                    cv2.circle(vis_frame, pt, 6, (255, 0, 255), -1)
                    cv2.circle(vis_frame, pt, 8, color, 2)
                else:  # 中間点
                    cv2.circle(vis_frame, pt, 4, color, -1)
                    cv2.circle(vis_frame, pt, 5, (255, 255, 255), 1)

            # 状態表示
            if state['initial_detection']:
                status_text = f"{hand_label.upper()}: DETECTED"
                status_color = (0, 255, 0)
            else:
                status_text = f"{hand_label.upper()}: TRACKING (conf: {state['confidence']:.2f})"
                status_color = (0, 200, 200)

            y_pos = 60 if hand_label == 'left' else 90
            cv2.putText(vis_frame, status_text,
                       (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

        return vis_frame

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"OPTICAL FLOW INSTRUMENT TRACKING")

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

            # グレースケール変換
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 手を検出
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands_result = self.mp_hands.process(rgb_frame)

            # 各手の処理
            if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
                for hand_landmarks, handedness in zip(
                    hands_result.multi_hand_landmarks,
                    hands_result.multi_handedness
                ):
                    hand_label = 'left' if handedness.classification[0].label == 'Right' else 'right'
                    state = self.tracking_state[hand_label]

                    # トラッキングがアクティブでない場合、初期検出を試みる
                    if not state['active'] or state['lost_frames'] > 30:
                        landmarks = self.detect_initial_landmarks(frame, hand_landmarks)

                        if landmarks is not None:
                            state['points'] = landmarks
                            state['active'] = True
                            state['confidence'] = 1.0
                            state['lost_frames'] = 0
                            state['initial_detection'] = True
                            self.stats['initial_detections'][hand_label] += 1
                            logger.info(f"Initial detection for {hand_label} hand at frame {frame_count}")

                    # 手を薄く描画（参考用）
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(240, 240, 240), thickness=1, circle_radius=1),
                        self.mp_drawing.DrawingSpec(color=(240, 240, 240), thickness=1)
                    )

            # Optical Flowでトラッキング
            if self.prev_gray is not None:
                for hand_label in ['left', 'right']:
                    state = self.tracking_state[hand_label]

                    if state['active'] and state['points'] is not None:
                        # Optical Flow実行
                        new_points, confidence = self.track_with_optical_flow(
                            self.prev_gray, gray, state['points']
                        )

                        if new_points is not None and confidence > 0.3:
                            # 改善
                            new_points = self.refine_tracking(frame, new_points, hand_label)

                            state['points'] = new_points
                            state['confidence'] = confidence
                            state['lost_frames'] = 0
                            state['initial_detection'] = False
                            self.stats['tracking_frames'][hand_label] += 1
                        else:
                            state['lost_frames'] += 1
                            state['confidence'] *= 0.9

                            if state['lost_frames'] > 30:
                                state['active'] = False
                                logger.info(f"Lost tracking for {hand_label} hand at frame {frame_count}")

            # トラッキング中の手をカウント
            for hand_label in ['left', 'right']:
                if self.tracking_state[hand_label]['active']:
                    self.stats['total_tracked'][hand_label] += 1

            # 可視化
            vis_frame = self.visualize(frame, self.tracking_state)

            # 情報パネル
            self.add_info_panel(vis_frame, frame_count, total_frames)

            out.write(vis_frame)

            # 次フレーム用に保存
            self.prev_gray = gray.copy()

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames * 100)
                left_rate = (self.stats['total_tracked']['left'] / frame_count * 100)
                right_rate = (self.stats['total_tracked']['right'] / frame_count * 100)
                logger.info(f"Progress: {progress:.1f}% | Left tracking: {left_rate:.1f}% | Right tracking: {right_rate:.1f}%")

        cap.release()
        out.release()
        self.mp_hands.close()

        # 統計を保存
        self.save_metrics()
        self._print_stats()

    def add_info_panel(self, frame, frame_num, total_frames):
        """情報パネルを追加"""
        h, w = frame.shape[:2]

        # 上部パネル
        panel_height = 40
        cv2.rectangle(frame, (0, 0), (w, panel_height), (0, 0, 0), -1)
        cv2.rectangle(frame, (0, 0), (w, panel_height), (255, 255, 255), 1)

        progress = (frame_num / total_frames * 100) if total_frames > 0 else 0
        active_count = sum(1 for s in self.tracking_state.values() if s['active'])

        text = f"Frame: {frame_num}/{total_frames} ({progress:.1f}%) | "
        text += f"Active tracking: {active_count}/2 instruments"

        cv2.putText(frame, text,
                   (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    def save_metrics(self):
        """メトリクスを保存"""
        metrics_file = self.output_path.with_suffix('.json')

        save_data = {
            'total_frames': self.stats['total_frames'],
            'initial_detections': self.stats['initial_detections'],
            'tracking_statistics': {
                'left': {
                    'initial_detections': self.stats['initial_detections']['left'],
                    'optical_flow_frames': self.stats['tracking_frames']['left'],
                    'total_tracked': self.stats['total_tracked']['left'],
                    'tracking_rate': self.stats['total_tracked']['left'] / max(1, self.stats['total_frames'])
                },
                'right': {
                    'initial_detections': self.stats['initial_detections']['right'],
                    'optical_flow_frames': self.stats['tracking_frames']['right'],
                    'total_tracked': self.stats['total_tracked']['right'],
                    'tracking_rate': self.stats['total_tracked']['right'] / max(1, self.stats['total_frames'])
                }
            }
        }

        with open(metrics_file, 'w') as f:
            json.dump(save_data, f, indent=2, default=float)

        logger.info(f"Metrics saved to: {metrics_file}")

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("OPTICAL FLOW TRACKING COMPLETE")
        print("=" * 80)

        print(f"\nTotal frames: {self.stats['total_frames']}")

        for hand in ['left', 'right']:
            tracked = self.stats['total_tracked'][hand]
            rate = tracked / max(1, self.stats['total_frames']) * 100

            print(f"\n{hand.capitalize()} hand:")
            print(f"  - Initial detections: {self.stats['initial_detections'][hand]}")
            print(f"  - Optical flow frames: {self.stats['tracking_frames'][hand]}")
            print(f"  - Total tracked: {tracked} frames")
            print(f"  - Tracking rate: {rate:.1f}%")

        # 全体の成功率
        total_tracked = self.stats['total_tracked']['left'] + self.stats['total_tracked']['right']
        total_possible = self.stats['total_frames'] * 2
        overall_rate = (total_tracked / max(1, total_possible)) * 100

        print(f"\nOverall tracking rate: {overall_rate:.1f}%")
        print(f"\nOutput video: {self.output_path}")
        print(f"Metrics JSON: {self.output_path.with_suffix('.json')}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/optical_flow_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("OPTICAL FLOW INSTRUMENT TRACKING")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    tracker = OpticalFlowInstrumentTracker(str(input_video), str(output_video))
    tracker.generate_video()


if __name__ == "__main__":
    main()