"""実用的な器具トラッキング - 初回SAM + 継続的Optical Flow"""

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PracticalInstrumentTracker:
    """実用的な器具トラッキング - 高速かつ高精度"""

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

        # ランドマーク設定
        self.num_landmarks = 15

        # Optical Flow設定（より堅牢に）
        self.lk_params = dict(
            winSize=(25, 25),  # 大きめのウィンドウ
            maxLevel=4,  # より多くのピラミッドレベル
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

        # 特徴点検出器
        self.feature_params = dict(
            maxCorners=100,
            qualityLevel=0.01,
            minDistance=7,
            blockSize=7
        )

        # トラッキング状態
        self.tracking_state = {
            'left': {
                'active': False,
                'points': None,
                'confidence': 0,
                'lost_frames': 0,
                'initial_frame': -1
            },
            'right': {
                'active': False,
                'points': None,
                'confidence': 0,
                'lost_frames': 0,
                'initial_frame': -1
            }
        }

        # 前フレーム
        self.prev_gray = None

        # 統計
        self.stats = {
            'total_frames': 0,
            'initial_detections': {'left': 0, 'right': 0},
            'optical_flow_success': {'left': 0, 'right': 0},
            'redetections': {'left': 0, 'right': 0},
            'total_tracked': {'left': 0, 'right': 0}
        }

    def detect_instrument_advanced(self, frame, hand_landmarks):
        """高度な器具検出（初回検出用）"""
        h, w = frame.shape[:2]

        # 手の位置情報
        hand_points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

        # 親指と人差し指の中点（握り位置）
        thumb = hand_points[4]
        index = hand_points[8]
        grip_point = ((thumb[0] + index[0]) // 2, (thumb[1] + index[1]) // 2)

        # 手首から中指への方向（器具の方向）
        wrist = hand_points[0]
        middle = hand_points[12]
        direction = np.array([middle[0] - wrist[0], middle[1] - wrist[1]], dtype=np.float32)
        norm = np.linalg.norm(direction)
        if norm > 0:
            direction /= norm

        # 手の領域を除外するマスク
        hand_mask = np.zeros((h, w), dtype=np.uint8)
        hand_contour = np.array(hand_points, np.int32)
        cv2.fillPoly(hand_mask, [hand_contour], 255)
        hand_mask = cv2.dilate(hand_mask, np.ones((15, 15), np.uint8))

        # 器具検出用の前処理
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # CLAHE（コントラスト強調）
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # エッジ検出（複数の手法を組み合わせ）
        edges1 = cv2.Canny(enhanced, 30, 100)
        edges2 = cv2.Canny(gray, 50, 150)
        combined_edges = cv2.bitwise_or(edges1, edges2)

        # 手の領域を除外
        combined_edges = cv2.bitwise_and(combined_edges, cv2.bitwise_not(hand_mask))

        # 器具の候補領域を探索
        instrument_points = []

        # 握り点から方向ベクトルに沿って探索
        search_length = 400
        search_width = 60

        for dist in range(20, search_length, 5):
            # 探索点
            search_x = int(grip_point[0] + direction[0] * dist)
            search_y = int(grip_point[1] + direction[1] * dist)

            # 探索範囲（幅を持たせる）
            perp_direction = np.array([-direction[1], direction[0]])

            for offset in range(-search_width//2, search_width//2 + 1, 10):
                px = int(search_x + perp_direction[0] * offset)
                py = int(search_y + perp_direction[1] * offset)

                if 0 <= px < w and 0 <= py < h:
                    # エッジ強度をチェック
                    if combined_edges[py, px] > 0:
                        # 周囲のエッジ密度も確認
                        roi = combined_edges[max(0, py-5):min(h, py+6),
                                            max(0, px-5):min(w, px+6)]
                        edge_density = np.sum(roi > 0) / (roi.size + 1)

                        if edge_density > 0.1:  # 十分なエッジがある
                            instrument_points.append([px, py])
                            break

        if len(instrument_points) < 10:
            # フォールバック：Harris コーナー検出
            corners = cv2.goodFeaturesToTrack(
                enhanced, maxCorners=50, qualityLevel=0.01,
                minDistance=10, mask=cv2.bitwise_not(hand_mask)
            )

            if corners is not None:
                for corner in corners:
                    x, y = corner[0]
                    # 握り点からの距離と方向を確認
                    vec_to_corner = np.array([x - grip_point[0], y - grip_point[1]])
                    dist = np.linalg.norm(vec_to_corner)

                    if 50 < dist < 300:  # 適切な距離範囲
                        # 方向が概ね一致するか
                        vec_normalized = vec_to_corner / (dist + 1e-6)
                        dot_product = np.dot(direction, vec_normalized)

                        if dot_product > 0.5:  # 方向が概ね一致
                            instrument_points.append([int(x), int(y)])

        if len(instrument_points) < 5:
            return None

        # 点を整理してランドマークに変換
        instrument_points = np.array(instrument_points)

        # 点を握り点からの距離でソート
        distances = [np.linalg.norm(p - np.array(grip_point)) for p in instrument_points]
        sorted_indices = np.argsort(distances)
        sorted_points = instrument_points[sorted_indices]

        # スプライン補間で滑らかな曲線を作成
        if len(sorted_points) > 3:
            try:
                # 重複を除去
                unique_points = []
                for p in sorted_points:
                    if not unique_points or np.linalg.norm(p - unique_points[-1]) > 5:
                        unique_points.append(p)

                if len(unique_points) > 3:
                    points = np.array(unique_points)
                    tck, u = splprep([points[:, 0], points[:, 1]],
                                    s=len(points) * 10, k=min(3, len(points) - 1))

                    # 等間隔でランドマークを配置
                    u_new = np.linspace(0, 1, self.num_landmarks)
                    x_new, y_new = splev(u_new, tck)

                    landmarks = np.array([[x, y] for x, y in zip(x_new, y_new)],
                                        dtype=np.float32).reshape(-1, 1, 2)

                    return landmarks
            except:
                pass

        # フォールバック：等間隔でサンプリング
        if len(sorted_points) >= self.num_landmarks:
            step = len(sorted_points) // self.num_landmarks
            landmarks = sorted_points[::step][:self.num_landmarks]
        else:
            # 不足分は最後の点で埋める
            landmarks = sorted_points.tolist()
            while len(landmarks) < self.num_landmarks:
                landmarks.append(landmarks[-1])
            landmarks = np.array(landmarks[:self.num_landmarks])

        return np.array(landmarks, dtype=np.float32).reshape(-1, 1, 2)

    def track_with_optical_flow(self, prev_gray, curr_gray, prev_points):
        """Optical Flowで追跡（改善版）"""
        if prev_points is None or len(prev_points) == 0:
            return None, 0

        # Lucas-Kanade Optical Flow
        next_points, status, error = cv2.calcOpticalFlowPyrLK(
            prev_gray, curr_gray, prev_points, None, **self.lk_params
        )

        if next_points is None:
            return None, 0

        # バックワードフローで検証（より正確）
        prev_points_back, status_back, _ = cv2.calcOpticalFlowPyrLK(
            curr_gray, prev_gray, next_points, None, **self.lk_params
        )

        if prev_points_back is None:
            return next_points, 0.3  # 低信頼度で継続

        # フォワード・バックワードエラーを計算
        fb_error = np.linalg.norm(prev_points - prev_points_back, axis=2).reshape(-1)

        # 良好な点を選択（FB誤差が小さい）
        good_points = fb_error < 2.0

        # 有効な点の割合で信頼度を計算
        valid_ratio = np.sum(good_points) / len(good_points)

        if valid_ratio < 0.3:
            return None, 0

        # エラーから信頼度を計算
        if error is not None and np.any(status == 1):
            avg_error = np.mean(error[status == 1])
            confidence = min(1.0, 10.0 / (avg_error + 1)) * valid_ratio
        else:
            confidence = valid_ratio

        # 失われた点を補間
        if valid_ratio < 1.0:
            next_points = self.interpolate_lost_points(next_points, good_points)

        return next_points, confidence

    def interpolate_lost_points(self, points, valid_mask):
        """失われた点を補間"""
        if points is None:
            return None

        interpolated = points.copy()
        valid_indices = np.where(valid_mask)[0]

        if len(valid_indices) < 3:
            return points  # 補間不可

        # 無効な点を補間
        for i in range(len(points)):
            if not valid_mask[i]:
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
                    if len(before) >= 2:
                        p1 = points[before[-2]].flatten()
                        p2 = points[before[-1]].flatten()
                        direction = p2 - p1
                        interpolated[i] = (p2 + direction).reshape(1, 2)
                    else:
                        interpolated[i] = points[before[-1]]
                elif after:
                    # 後の点から外挿
                    interpolated[i] = points[after[0]]

        return interpolated

    def visualize(self, frame, tracking_state):
        """可視化（MediaPipe風）"""
        vis_frame = frame.copy()

        for hand_label, state in tracking_state.items():
            if not state['active'] or state['points'] is None:
                continue

            points = state['points'].reshape(-1, 2)
            color = (0, 255, 0) if hand_label == 'left' else (0, 0, 255)

            # 信頼度で線の太さを調整
            thickness = 3 if state['confidence'] > 0.7 else 2

            # ランドマーク間を線で接続
            for i in range(len(points) - 1):
                pt1 = tuple(points[i].astype(int))
                pt2 = tuple(points[i+1].astype(int))
                cv2.line(vis_frame, pt1, pt2, color, thickness)

            # ランドマーク点を描画
            for i, pt in enumerate(points):
                point = tuple(pt.astype(int))

                if i == 0:  # 握り部（黄色）
                    cv2.circle(vis_frame, point, 6, (0, 255, 255), -1)
                    cv2.circle(vis_frame, point, 8, color, 2)
                elif i == len(points) - 1:  # 先端（ピンク）
                    cv2.circle(vis_frame, point, 6, (255, 0, 255), -1)
                    cv2.circle(vis_frame, point, 8, color, 2)
                else:  # 中間点
                    cv2.circle(vis_frame, point, 4, color, -1)
                    cv2.circle(vis_frame, point, 5, (255, 255, 255), 1)

            # 状態表示
            status_text = f"{hand_label.upper()}: "
            if state['lost_frames'] == 0:
                status_text += f"TRACKING ({state['confidence']:.2f})"
                status_color = color
            else:
                status_text += f"SEARCHING ({state['lost_frames']})"
                status_color = (100, 100, 100)

            y_pos = 60 if hand_label == 'left' else 90
            cv2.putText(vis_frame, status_text,
                       (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

        return vis_frame

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"PRACTICAL INSTRUMENT TRACKING (Efficient)")

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

            # 手を検出
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands_result = self.mp_hands.process(rgb_frame)

            if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
                for hand_landmarks, handedness in zip(
                    hands_result.multi_hand_landmarks,
                    hands_result.multi_handedness
                ):
                    hand_label = 'left' if handedness.classification[0].label == 'Right' else 'right'
                    state = self.tracking_state[hand_label]

                    # 追跡中の場合
                    if state['active'] and self.prev_gray is not None and state['points'] is not None:
                        # Optical Flowで追跡
                        new_points, confidence = self.track_with_optical_flow(
                            self.prev_gray, gray, state['points']
                        )

                        if new_points is not None and confidence > 0.2:
                            state['points'] = new_points
                            state['confidence'] = confidence
                            state['lost_frames'] = 0
                            self.stats['optical_flow_success'][hand_label] += 1
                        else:
                            state['lost_frames'] += 1

                            # 長時間失った場合は非アクティブに
                            if state['lost_frames'] > 30:
                                state['active'] = False
                                logger.info(f"Lost tracking for {hand_label} at frame {frame_count}")

                    # 初期検出または再検出が必要な場合
                    if not state['active'] or state['lost_frames'] > 15:
                        landmarks = self.detect_instrument_advanced(frame, hand_landmarks)

                        if landmarks is not None:
                            state['points'] = landmarks
                            state['active'] = True
                            state['confidence'] = 1.0
                            state['lost_frames'] = 0

                            if state['initial_frame'] < 0:
                                state['initial_frame'] = frame_count
                                self.stats['initial_detections'][hand_label] += 1
                                logger.info(f"Initial detection for {hand_label} at frame {frame_count}")
                            else:
                                self.stats['redetections'][hand_label] += 1
                                logger.info(f"Re-detection for {hand_label} at frame {frame_count}")

                    # トラッキング成功をカウント
                    if state['active'] and state['lost_frames'] == 0:
                        self.stats['total_tracked'][hand_label] += 1

                    # 手を薄く表示（参考用）
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(245, 245, 245), thickness=1, circle_radius=1),
                        self.mp_drawing.DrawingSpec(color=(245, 245, 245), thickness=1)
                    )

            # 可視化
            vis_frame = self.visualize(frame, self.tracking_state)

            # フレーム情報
            progress = (frame_count / total_frames * 100) if total_frames > 0 else 0
            info_text = f"Frame: {frame_count}/{total_frames} ({progress:.1f}%)"

            active_count = sum(1 for s in self.tracking_state.values()
                             if s['active'] and s['lost_frames'] == 0)
            info_text += f" | Active: {active_count}/2"

            cv2.putText(vis_frame, info_text,
                       (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            out.write(vis_frame)

            # 次フレーム用に保存
            self.prev_gray = gray.copy()

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示
            if frame_count % max(1, total_frames // 10) == 0:
                left_rate = self.stats['total_tracked']['left'] / frame_count * 100
                right_rate = self.stats['total_tracked']['right'] / frame_count * 100
                logger.info(f"Progress: {progress:.1f}% | Left: {left_rate:.1f}% | Right: {right_rate:.1f}%")

        cap.release()
        out.release()
        self.mp_hands.close()

        self._save_metrics()
        self._print_stats()

    def _save_metrics(self):
        """メトリクスを保存"""
        metrics_file = self.output_path.with_suffix('.json')

        save_data = {
            'total_frames': self.stats['total_frames'],
            'tracking_performance': {
                'left': {
                    'initial_detections': self.stats['initial_detections']['left'],
                    'redetections': self.stats['redetections']['left'],
                    'optical_flow_success': self.stats['optical_flow_success']['left'],
                    'total_tracked': self.stats['total_tracked']['left'],
                    'tracking_rate': self.stats['total_tracked']['left'] / max(1, self.stats['total_frames'])
                },
                'right': {
                    'initial_detections': self.stats['initial_detections']['right'],
                    'redetections': self.stats['redetections']['right'],
                    'optical_flow_success': self.stats['optical_flow_success']['right'],
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
        print("PRACTICAL TRACKING COMPLETE")
        print("=" * 80)

        print(f"\nTotal frames: {self.stats['total_frames']}")

        for hand in ['left', 'right']:
            tracked = self.stats['total_tracked'][hand]
            rate = tracked / max(1, self.stats['total_frames']) * 100

            print(f"\n{hand.capitalize()} hand:")
            print(f"  - Initial detections: {self.stats['initial_detections'][hand]}")
            print(f"  - Re-detections: {self.stats['redetections'][hand]}")
            print(f"  - Optical flow frames: {self.stats['optical_flow_success'][hand]}")
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
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/practical_tracking_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("PRACTICAL INSTRUMENT TRACKING")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    tracker = PracticalInstrumentTracker(str(input_video), str(output_video))
    tracker.generate_video()


if __name__ == "__main__":
    main()