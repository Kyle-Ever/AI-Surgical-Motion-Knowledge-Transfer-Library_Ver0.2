"""器具の動きを正確にトレース・評価するシステム"""

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InstrumentMotionTracker:
    """器具の動きを追跡し評価メトリクスを生成"""

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

        # トラッキング用データ構造
        self.instrument_tracks = {
            'left': {
                'positions': [],  # (x, y, frame_num)
                'velocities': [],  # pixels/frame
                'accelerations': [],  # pixels/frame^2
                'angles': [],  # degrees
                'grip_strength': [],  # 0-1
                'stability': []  # 振れの少なさ
            },
            'right': {
                'positions': [],
                'velocities': [],
                'accelerations': [],
                'angles': [],
                'grip_strength': [],
                'stability': []
            }
        }

        # 前フレームの器具位置（トラッキング用）
        self.prev_instruments = {}

        # カルマンフィルタ（スムーズなトラッキング）
        self.kalman_filters = {}

        # 評価メトリクス
        self.metrics = {
            'total_frames': 0,
            'detection_rate': 0,
            'avg_speed': 0,
            'max_speed': 0,
            'smoothness': 0,  # 動きの滑らかさ
            'precision': 0,  # 動きの精密さ
            'consistency': 0,  # 左右の協調性
            'path_length': {'left': 0, 'right': 0},
            'jerk': {'left': 0, 'right': 0}  # ジャーク（急激な動き）
        }

    def init_kalman_filter(self):
        """カルマンフィルタの初期化"""
        kf = cv2.KalmanFilter(4, 2)
        kf.measurementMatrix = np.array([[1, 0, 0, 0],
                                         [0, 1, 0, 0]], np.float32)
        kf.transitionMatrix = np.array([[1, 0, 1, 0],
                                        [0, 1, 0, 1],
                                        [0, 0, 1, 0],
                                        [0, 0, 0, 1]], np.float32)
        kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.1
        return kf

    def detect_instrument(self, frame, hand_landmarks, hand_label):
        """高精度な器具検出"""
        h, w = frame.shape[:2]

        # 手の重心を計算
        hand_center_x = np.mean([lm.x * w for lm in hand_landmarks.landmark])
        hand_center_y = np.mean([lm.y * h for lm in hand_landmarks.landmark])

        # 握り判定
        grip_strength = self.calculate_grip_strength(hand_landmarks)

        if grip_strength < 0.3:  # 握っていない
            return None

        # 手の向きベクトル（手首から中指方向）
        wrist = hand_landmarks.landmark[0]
        middle_tip = hand_landmarks.landmark[12]

        direction_x = (middle_tip.x - wrist.x) * w
        direction_y = (middle_tip.y - wrist.y) * h
        direction_length = math.sqrt(direction_x**2 + direction_y**2)

        if direction_length > 0:
            direction_x /= direction_length
            direction_y /= direction_length

        # 器具の先端位置を推定
        instrument_tip = self.find_instrument_tip(
            frame,
            (int(hand_center_x), int(hand_center_y)),
            (direction_x, direction_y)
        )

        if instrument_tip is None:
            return None

        return {
            'hand_center': (hand_center_x, hand_center_y),
            'tip': instrument_tip,
            'angle': math.degrees(math.atan2(direction_y, direction_x)),
            'grip_strength': grip_strength,
            'length': math.sqrt((instrument_tip[0] - hand_center_x)**2 +
                               (instrument_tip[1] - hand_center_y)**2)
        }

    def find_instrument_tip(self, frame, start_point, direction):
        """器具の先端を精密に検出"""
        h, w = frame.shape[:2]

        # HSV変換
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 金属器具の特徴（低彩度、中〜高輝度）
        lower_metal = np.array([0, 0, 100])
        upper_metal = np.array([180, 50, 255])
        metal_mask = cv2.inRange(hsv, lower_metal, upper_metal)

        # エッジ検出
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # 複合マスク
        combined_mask = cv2.bitwise_or(metal_mask, edges)

        # 方向に沿って探索
        max_dist = 400
        step = 5
        best_tip = None
        max_score = 0

        for dist in range(50, max_dist, step):
            x = int(start_point[0] + direction[0] * dist)
            y = int(start_point[1] + direction[1] * dist)

            if not (0 <= x < w and 0 <= y < h):
                break

            # 周囲のピクセルをチェック
            roi_size = 10
            x1, y1 = max(0, x - roi_size), max(0, y - roi_size)
            x2, y2 = min(w, x + roi_size), min(h, y + roi_size)

            roi = combined_mask[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            # スコア計算（エッジ強度 + 金属特徴）
            score = np.sum(roi) / (roi.size + 1)

            if score > max_score:
                max_score = score
                best_tip = (x, y)

        return best_tip

    def calculate_grip_strength(self, hand_landmarks):
        """握りの強さを計算（0-1）"""
        # 指先と手のひらの距離から握り強度を推定
        wrist = hand_landmarks.landmark[0]
        finger_tips = [
            hand_landmarks.landmark[8],   # 人差し指
            hand_landmarks.landmark[12],  # 中指
            hand_landmarks.landmark[16],  # 薬指
            hand_landmarks.landmark[20]   # 小指
        ]

        # 平均距離を計算
        distances = []
        for tip in finger_tips:
            dist = math.sqrt(
                (tip.x - wrist.x)**2 +
                (tip.y - wrist.y)**2 +
                (tip.z - wrist.z)**2
            )
            distances.append(dist)

        avg_dist = sum(distances) / len(distances)

        # 距離を握り強度に変換（距離が小さいほど強く握っている）
        grip_strength = max(0, min(1, 1 - (avg_dist - 0.1) / 0.3))

        return grip_strength

    def smooth_tracking(self, hand_label, current_pos):
        """カルマンフィルタでトラッキングを平滑化"""
        if hand_label not in self.kalman_filters:
            self.kalman_filters[hand_label] = self.init_kalman_filter()
            kf = self.kalman_filters[hand_label]
            kf.statePre = np.array([current_pos[0], current_pos[1], 0, 0], dtype=np.float32)
            kf.statePost = kf.statePre.copy()

        kf = self.kalman_filters[hand_label]

        # 予測
        prediction = kf.predict()

        # 測定値で更新
        measurement = np.array([[current_pos[0]], [current_pos[1]]], dtype=np.float32)
        kf.correct(measurement)

        # 平滑化された位置
        smoothed_pos = (int(kf.statePost[0]), int(kf.statePost[1]))

        return smoothed_pos

    def update_metrics(self, hand_label, instrument_data, frame_num):
        """メトリクスを更新"""
        if instrument_data is None:
            return

        track = self.instrument_tracks[hand_label]
        tip = instrument_data['tip']

        # 位置を記録
        smoothed_tip = self.smooth_tracking(hand_label, tip)
        track['positions'].append((smoothed_tip[0], smoothed_tip[1], frame_num))

        # 速度計算
        if len(track['positions']) >= 2:
            prev_pos = track['positions'][-2]
            velocity = math.sqrt(
                (smoothed_tip[0] - prev_pos[0])**2 +
                (smoothed_tip[1] - prev_pos[1])**2
            )
            track['velocities'].append(velocity)

            # 加速度計算
            if len(track['velocities']) >= 2:
                acceleration = track['velocities'][-1] - track['velocities'][-2]
                track['accelerations'].append(acceleration)

        # 角度、握り強度を記録
        track['angles'].append(instrument_data['angle'])
        track['grip_strength'].append(instrument_data['grip_strength'])

        # 安定性（位置の分散）
        if len(track['positions']) >= 10:
            recent_positions = track['positions'][-10:]
            x_coords = [p[0] for p in recent_positions]
            y_coords = [p[1] for p in recent_positions]
            stability = 1 / (1 + np.std(x_coords) + np.std(y_coords))
            track['stability'].append(stability)

    def calculate_final_metrics(self):
        """最終的な評価メトリクスを計算"""
        for hand_label in ['left', 'right']:
            track = self.instrument_tracks[hand_label]

            if len(track['positions']) > 1:
                # 総移動距離
                total_dist = 0
                for i in range(1, len(track['positions'])):
                    p1 = track['positions'][i-1]
                    p2 = track['positions'][i]
                    total_dist += math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                self.metrics['path_length'][hand_label] = total_dist

                # ジャーク（加速度の変化率）
                if len(track['accelerations']) > 0:
                    jerks = []
                    for i in range(1, len(track['accelerations'])):
                        jerk = abs(track['accelerations'][i] - track['accelerations'][i-1])
                        jerks.append(jerk)
                    if jerks:
                        self.metrics['jerk'][hand_label] = np.mean(jerks)

        # 全体メトリクス
        all_velocities = (self.instrument_tracks['left']['velocities'] +
                         self.instrument_tracks['right']['velocities'])

        if all_velocities:
            self.metrics['avg_speed'] = np.mean(all_velocities)
            self.metrics['max_speed'] = np.max(all_velocities)
            self.metrics['smoothness'] = 1 / (1 + np.std(all_velocities))

        # 精密さ（速度の一貫性）
        if len(all_velocities) > 10:
            self.metrics['precision'] = 1 / (1 + np.std(all_velocities) / (np.mean(all_velocities) + 1))

        # 左右の協調性
        left_angles = self.instrument_tracks['left']['angles']
        right_angles = self.instrument_tracks['right']['angles']

        if left_angles and right_angles:
            min_len = min(len(left_angles), len(right_angles))
            if min_len > 0:
                angle_diffs = [abs(left_angles[i] - right_angles[i])
                              for i in range(min_len)]
                self.metrics['consistency'] = 1 / (1 + np.mean(angle_diffs) / 180)

    def visualize(self, frame, instruments, frame_num, total_frames):
        """高度な可視化"""
        vis_frame = frame.copy()
        h, w = frame.shape[:2]

        # 器具を描画
        for hand_label, instrument in instruments.items():
            if instrument is None:
                continue

            color = (0, 255, 0) if hand_label == 'left' else (255, 0, 0)

            # 手の中心から先端まで線を描画
            cv2.line(vis_frame,
                    tuple(map(int, instrument['hand_center'])),
                    instrument['tip'],
                    color, 3)

            # 先端を強調
            cv2.circle(vis_frame, instrument['tip'], 8, color, -1)
            cv2.circle(vis_frame, instrument['tip'], 12, (255, 255, 255), 2)

            # 握り強度を表示
            grip_text = f"Grip: {instrument['grip_strength']:.2f}"
            cv2.putText(vis_frame, grip_text,
                       (int(instrument['hand_center'][0]) - 30,
                        int(instrument['hand_center'][1]) - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # 軌跡を描画（最近50フレーム）
        for hand_label, color in [('left', (100, 255, 100)), ('right', (255, 100, 100))]:
            positions = self.instrument_tracks[hand_label]['positions']
            if len(positions) > 1:
                recent = positions[-min(50, len(positions)):]
                for i in range(1, len(recent)):
                    cv2.line(vis_frame,
                            (recent[i-1][0], recent[i-1][1]),
                            (recent[i][0], recent[i][1]),
                            color, 2)

        # メトリクスパネル
        panel_height = 150
        panel = np.zeros((panel_height, w, 3), dtype=np.uint8)

        # 進捗バー
        progress = (frame_num / total_frames * 100) if total_frames > 0 else 0
        cv2.rectangle(panel, (10, 10), (w-10, 30), (100, 100, 100), 2)
        cv2.rectangle(panel, (10, 10),
                     (int(10 + (w-20) * progress / 100), 30),
                     (0, 255, 0), -1)

        # リアルタイムメトリクス
        y_offset = 50
        metrics_text = [
            f"Frame: {frame_num}/{total_frames}",
            f"Detection: {len([i for i in instruments.values() if i])} hands",
        ]

        # 速度情報
        for hand_label in ['left', 'right']:
            if self.instrument_tracks[hand_label]['velocities']:
                recent_vel = self.instrument_tracks[hand_label]['velocities'][-1]
                metrics_text.append(f"{hand_label.capitalize()} speed: {recent_vel:.1f} px/frame")

        for i, text in enumerate(metrics_text):
            cv2.putText(panel, text, (10, y_offset + i*25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # パネルを結合
        vis_frame = np.vstack([vis_frame, panel])

        return vis_frame

    def generate_video(self):
        """動画生成とメトリクス出力"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"ADVANCED INSTRUMENT MOTION TRACKING")

        cap = cv2.VideoCapture(str(self.input_path))

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 出力サイズ（パネル分追加）
        output_height = height + 150

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

            current_instruments = {'left': None, 'right': None}

            if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
                for hand_landmarks, handedness in zip(
                    hands_result.multi_hand_landmarks,
                    hands_result.multi_handedness
                ):
                    # 左右を判定
                    hand_label = 'left' if handedness.classification[0].label == 'Right' else 'right'

                    # 器具を検出
                    instrument = self.detect_instrument(frame, hand_landmarks, hand_label)
                    current_instruments[hand_label] = instrument

                    # メトリクスを更新
                    self.update_metrics(hand_label, instrument, frame_count)

                    # 手を描画
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS
                    )

            # 可視化
            vis_frame = self.visualize(frame, current_instruments, frame_count, total_frames)
            out.write(vis_frame)

            frame_count += 1
            self.metrics['total_frames'] = frame_count

            # 進捗表示
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames * 100)
                detected = sum(1 for v in current_instruments.values() if v is not None)
                logger.info(f"Progress: {progress:.1f}% | Tracking {detected} instruments")

        cap.release()
        out.release()
        self.mp_hands.close()

        # 最終メトリクスを計算
        self.calculate_final_metrics()

        # メトリクスを保存
        self.save_metrics()

        # 統計表示
        self._print_stats()

    def save_metrics(self):
        """メトリクスをJSONファイルに保存"""
        metrics_file = self.output_path.with_suffix('.json')

        # トラッキングデータを整理
        tracking_data = {
            'metrics': self.metrics,
            'left_hand': {
                'num_positions': len(self.instrument_tracks['left']['positions']),
                'avg_velocity': np.mean(self.instrument_tracks['left']['velocities'])
                               if self.instrument_tracks['left']['velocities'] else 0,
                'avg_grip': np.mean(self.instrument_tracks['left']['grip_strength'])
                           if self.instrument_tracks['left']['grip_strength'] else 0,
                'path_length': self.metrics['path_length']['left'],
                'jerk': self.metrics['jerk']['left']
            },
            'right_hand': {
                'num_positions': len(self.instrument_tracks['right']['positions']),
                'avg_velocity': np.mean(self.instrument_tracks['right']['velocities'])
                               if self.instrument_tracks['right']['velocities'] else 0,
                'avg_grip': np.mean(self.instrument_tracks['right']['grip_strength'])
                           if self.instrument_tracks['right']['grip_strength'] else 0,
                'path_length': self.metrics['path_length']['right'],
                'jerk': self.metrics['jerk']['right']
            }
        }

        with open(metrics_file, 'w') as f:
            json.dump(tracking_data, f, indent=2, default=float)

        logger.info(f"Metrics saved to: {metrics_file}")

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("INSTRUMENT MOTION ANALYSIS COMPLETE")
        print("=" * 80)

        print("\n[TRACKING STATISTICS]")
        print(f"Total frames: {self.metrics['total_frames']}")

        for hand in ['left', 'right']:
            positions = len(self.instrument_tracks[hand]['positions'])
            if positions > 0:
                print(f"\n{hand.capitalize()} hand:")
                print(f"  - Tracked positions: {positions}")
                print(f"  - Path length: {self.metrics['path_length'][hand]:.1f} pixels")
                print(f"  - Jerk (smoothness): {self.metrics['jerk'][hand]:.3f}")

        print("\n[MOTION METRICS]")
        print(f"Average speed: {self.metrics['avg_speed']:.2f} pixels/frame")
        print(f"Maximum speed: {self.metrics['max_speed']:.2f} pixels/frame")
        print(f"Smoothness score: {self.metrics['smoothness']:.3f}")
        print(f"Precision score: {self.metrics['precision']:.3f}")
        print(f"L/R Consistency: {self.metrics['consistency']:.3f}")

        print(f"\nOutput video: {self.output_path}")
        print(f"Metrics JSON: {self.output_path.with_suffix('.json')}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/instrument_motion_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    # 出力ディレクトリ作成
    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("ADVANCED INSTRUMENT MOTION TRACKING")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    tracker = InstrumentMotionTracker(str(input_video), str(output_video))
    tracker.generate_video()


if __name__ == "__main__":
    main()