"""手が握っている器具のみを検出 - 改善版"""

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GripInstrumentDetector:
    """手が握っている器具を検出"""

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
        self.instrument_tracks = {}  # hand_id -> deque of positions

        self.stats = {
            'total_frames': 0,
            'hands_detected': 0,
            'grips_detected': 0,
            'instruments_detected': 0
        }

    def is_gripping(self, hand_landmarks):
        """手が何かを握っているか判定"""
        # 指先と手のひらの距離で握り判定
        wrist = hand_landmarks.landmark[0]
        thumb_tip = hand_landmarks.landmark[4]
        index_tip = hand_landmarks.landmark[8]
        middle_tip = hand_landmarks.landmark[12]
        ring_tip = hand_landmarks.landmark[16]
        pinky_tip = hand_landmarks.landmark[20]

        # 手のひらの中心（簡易的に手首と中指の付け根の中間）
        palm_center_x = (wrist.x + hand_landmarks.landmark[9].x) / 2
        palm_center_y = (wrist.y + hand_landmarks.landmark[9].y) / 2
        palm_center_z = (wrist.z + hand_landmarks.landmark[9].z) / 2

        # 各指先と手のひら中心の距離
        distances = []
        for tip in [index_tip, middle_tip, ring_tip, pinky_tip]:
            dist = math.sqrt(
                (tip.x - palm_center_x) ** 2 +
                (tip.y - palm_center_y) ** 2 +
                (tip.z - palm_center_z) ** 2
            )
            distances.append(dist)

        # 平均距離が小さい = 握っている
        avg_distance = sum(distances) / len(distances)

        # 親指と人差し指の距離も確認
        thumb_index_dist = math.sqrt(
            (thumb_tip.x - index_tip.x) ** 2 +
            (thumb_tip.y - index_tip.y) ** 2 +
            (thumb_tip.z - index_tip.z) ** 2
        )

        # 握り判定の閾値
        is_closed = avg_distance < 0.15  # 指が曲がっている
        thumb_close = thumb_index_dist < 0.1  # 親指と人差し指が近い

        return is_closed or thumb_close

    def get_grip_direction(self, hand_landmarks, frame_shape):
        """握りの方向を推定"""
        h, w = frame_shape[:2]

        # 手首と中指の付け根を結ぶベクトル（手の向き）
        wrist = hand_landmarks.landmark[0]
        middle_base = hand_landmarks.landmark[9]

        # 画像座標に変換
        wrist_x, wrist_y = int(wrist.x * w), int(wrist.y * h)
        middle_x, middle_y = int(middle_base.x * w), int(middle_base.y * h)

        # 方向ベクトル
        direction_x = middle_x - wrist_x
        direction_y = middle_y - wrist_y

        # 正規化
        length = math.sqrt(direction_x ** 2 + direction_y ** 2)
        if length > 0:
            direction_x /= length
            direction_y /= length

        return (wrist_x, wrist_y), (direction_x, direction_y)

    def detect_instrument_along_grip(self, frame, grip_point, direction):
        """握り点から方向に沿って器具を検出"""
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 握り点から両方向に探索
        instrument_points = []

        # 探索パラメータ
        max_length = 300  # 最大探索距離
        step_size = 5     # ステップサイズ

        for sign in [1, -1]:  # 両方向
            for distance in range(0, max_length, step_size):
                # 探索点
                x = int(grip_point[0] + sign * direction[0] * distance)
                y = int(grip_point[1] + sign * direction[1] * distance)

                # 画像範囲チェック
                if not (0 <= x < w and 0 <= y < h):
                    break

                # 周囲の領域を取得（5x5ピクセル）
                x1, y1 = max(0, x - 2), max(0, y - 2)
                x2, y2 = min(w, x + 3), min(h, y + 3)
                roi = gray[y1:y2, x1:x2]

                if roi.size == 0:
                    break

                # エッジ強度チェック
                edge_strength = cv2.Laplacian(roi, cv2.CV_64F).var()

                # 金属的な光沢をHSVで検出
                roi_color = frame[y1:y2, x1:x2]
                hsv = cv2.cvtColor(roi_color, cv2.COLOR_BGR2HSV)

                # 低彩度（グレー系）かつ明るさが中間〜高い
                saturation = np.mean(hsv[:, :, 1])
                value = np.mean(hsv[:, :, 2])

                is_metallic = saturation < 50 and value > 100
                has_edge = edge_strength > 100

                if is_metallic or has_edge:
                    instrument_points.append((x, y))
                else:
                    # 連続性が途切れたら終了
                    if len(instrument_points) > 10:
                        break

        return instrument_points

    def process_frame(self, frame):
        """フレーム処理"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 手を検出
        hands_result = self.mp_hands.process(rgb_frame)

        grip_instruments = []

        if hands_result.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(hands_result.multi_hand_landmarks):
                # 握り判定
                is_gripping = self.is_gripping(hand_landmarks)

                if is_gripping:
                    self.stats['grips_detected'] += 1

                    # 握りの方向を取得
                    grip_point, direction = self.get_grip_direction(hand_landmarks, frame.shape)

                    # 器具を検出
                    instrument_points = self.detect_instrument_along_grip(frame, grip_point, direction)

                    if len(instrument_points) > 20:  # 最小長さ
                        grip_instruments.append({
                            'hand_idx': hand_idx,
                            'grip_point': grip_point,
                            'direction': direction,
                            'points': instrument_points,
                            'is_gripping': True
                        })

                        # トラッキング履歴更新
                        if hand_idx not in self.instrument_tracks:
                            self.instrument_tracks[hand_idx] = deque(maxlen=10)
                        self.instrument_tracks[hand_idx].append(instrument_points)

        return hands_result, grip_instruments

    def visualize(self, frame, hands_result, grip_instruments, frame_num, total_frames):
        """可視化"""
        vis_frame = frame.copy()

        # 手を描画
        if hands_result.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(hands_result.multi_hand_landmarks):
                # 握っている手は赤、そうでない手は緑
                is_gripping_hand = any(
                    inst['hand_idx'] == hand_idx and inst['is_gripping']
                    for inst in grip_instruments
                )

                if is_gripping_hand:
                    # 握っている手は赤で描画
                    self.mp_drawing.draw_landmarks(
                        vis_frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=3),
                        self.mp_drawing.DrawingSpec(color=(0, 100, 255), thickness=2)
                    )
                else:
                    # 通常の手は緑で描画
                    self.mp_drawing.draw_landmarks(
                        vis_frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                        self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2)
                    )

        # 器具を描画
        for inst in grip_instruments:
            # 握り点
            cv2.circle(vis_frame, inst['grip_point'], 8, (0, 0, 255), -1)

            # 器具の線
            if len(inst['points']) > 1:
                points = np.array(inst['points'], np.int32)

                # 太い黄色の線で器具を描画
                for i in range(len(points) - 1):
                    cv2.line(vis_frame, tuple(points[i]), tuple(points[i + 1]),
                            (0, 255, 255), 4)

                # 器具の先端に印
                cv2.circle(vis_frame, tuple(points[-1]), 5, (255, 0, 255), -1)
                cv2.circle(vis_frame, tuple(points[0]), 5, (255, 0, 255), -1)

            # 方向ベクトルを表示
            end_point = (
                int(inst['grip_point'][0] + inst['direction'][0] * 100),
                int(inst['grip_point'][1] + inst['direction'][1] * 100)
            )
            cv2.arrowedLine(vis_frame, inst['grip_point'], end_point,
                          (255, 100, 0), 2, tipLength=0.3)

        # 情報パネル
        progress = (frame_num / total_frames * 100) if total_frames > 0 else 0

        # 背景ボックス
        cv2.rectangle(vis_frame, (10, 10), (450, 120), (0, 0, 0), -1)
        cv2.rectangle(vis_frame, (10, 10), (450, 120), (255, 255, 255), 2)

        cv2.putText(vis_frame, f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        hands_text = "Hands: " + ("Detected" if hands_result.multi_hand_landmarks else "Not detected")
        color = (0, 255, 0) if hands_result.multi_hand_landmarks else (100, 100, 100)
        cv2.putText(vis_frame, hands_text,
                   (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        grip_text = f"Gripping: {len(grip_instruments)} hand(s)"
        color = (0, 0, 255) if grip_instruments else (100, 100, 100)
        cv2.putText(vis_frame, grip_text,
                   (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        inst_text = f"Instruments: {len(grip_instruments)}"
        color = (0, 255, 255) if grip_instruments else (100, 100, 100)
        cv2.putText(vis_frame, inst_text,
                   (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return vis_frame

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"GRIP-BASED INSTRUMENT DETECTION")

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
            hands_result, grip_instruments = self.process_frame(frame)

            # 統計更新
            if hands_result.multi_hand_landmarks:
                self.stats['hands_detected'] += 1
            if grip_instruments:
                self.stats['instruments_detected'] += 1

            # 可視化
            vis_frame = self.visualize(frame, hands_result, grip_instruments, frame_count, total_frames)
            out.write(vis_frame)

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示（10%ごと）
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames * 100)
                hands_rate = (self.stats['hands_detected'] / frame_count * 100)
                grip_rate = (self.stats['grips_detected'] / frame_count * 100) if frame_count > 0 else 0
                inst_rate = (self.stats['instruments_detected'] / frame_count * 100)
                logger.info(f"Progress: {progress:.1f}% | Hands: {hands_rate:.1f}% | Grips: {grip_rate:.1f}% | Instruments: {inst_rate:.1f}%")

        cap.release()
        out.release()

        self._print_stats()

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("GRIP ANALYSIS COMPLETE")
        print("=" * 80)

        total = self.stats['total_frames']
        hands = self.stats['hands_detected']
        grips = self.stats['grips_detected']
        instruments = self.stats['instruments_detected']

        print(f"Total frames: {total}")
        print(f"Hands detected: {hands} ({hands/total*100:.1f}%)")
        print(f"Grips detected: {grips} ({grips/total*100:.1f}% of frames with hands)")
        print(f"Instruments detected: {instruments} ({instruments/total*100:.1f}%)")
        print(f"Output saved to: {self.output_path}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/grip_instrument_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    # 出力ディレクトリ作成
    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("GRIP-BASED INSTRUMENT DETECTION")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    detector = GripInstrumentDetector(str(input_video), str(output_video))
    detector.generate_video()


if __name__ == "__main__":
    main()