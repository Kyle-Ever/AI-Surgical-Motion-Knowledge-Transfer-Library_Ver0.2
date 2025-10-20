"""白い手袋の検出（顔・耳の誤検出を除外）"""

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


class FilteredWhiteGloveDetector:
    """顔・耳の誤検出を除外する白い手袋検出器"""

    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),  # 親指
        (0, 5), (5, 6), (6, 7), (7, 8),  # 人差し指
        (5, 9), (9, 10), (10, 11), (11, 12),  # 中指
        (9, 13), (13, 14), (14, 15), (15, 16),  # 薬指
        (13, 17), (17, 18), (18, 19), (19, 20),  # 小指
        (0, 17)  # 手のひら
    ]

    def __init__(self, input_video_path: str, output_video_path: str):
        """初期化"""
        self.input_path = Path(input_video_path)
        self.output_path = Path(output_video_path)

        # MediaPipe Hand Detector
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,  # 閾値を上げて誤検出を減らす
            min_tracking_confidence=0.5,
            model_complexity=1
        )

        # MediaPipe Pose Detector（顔の位置を特定）
        self.mp_pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # 描画用
        self.mp_drawing = mp.solutions.drawing_utils

        # トラッキング履歴
        self.detection_history = deque(maxlen=100)
        self.valid_detections = deque(maxlen=10)
        self.face_regions = []  # 顔の領域を記録

        # 統計情報
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'filtered_out': 0,
            'total_hands': 0,
            'left_hands': 0,
            'right_hands': 0,
            'rejection_reasons': {
                'face_area': 0,
                'large_size': 0,
                'invalid_shape': 0,
                'near_face': 0
            }
        }

    def generate_video(self):
        """検出結果を可視化した動画を生成（フィルタリング付き）"""

        logger.info(f"Processing: {self.input_path}")
        logger.info("FILTERED DETECTION MODE: Excluding face/ear misdetections")

        # 入力動画を開く
        cap = cv2.VideoCapture(str(self.input_path))

        # 動画情報を取得
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video info: {width}x{height} @ {fps}fps, {total_frames} frames")

        # 出力動画の設定
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(self.output_path),
            fourcc,
            fps,
            (width, height)
        )

        frame_count = 0
        logger.info("Starting filtered detection...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 顔の位置を検出
            face_region = self.detect_face_region(frame)

            # 手の検出（フィルタリング付き）
            valid_hands, filtered_hands = self.detect_and_filter_hands(frame, face_region)

            # 統計更新
            if valid_hands:
                self.stats['detected_frames'] += 1
                self.stats['total_hands'] += len(valid_hands)
                self.valid_detections.append(valid_hands)

            if filtered_hands:
                self.stats['filtered_out'] += len(filtered_hands)

            # 検出履歴
            self.detection_history.append(1 if valid_hands else 0)

            # 可視化
            vis_frame = self._create_visualization(
                frame, valid_hands, filtered_hands, face_region,
                frame_count, total_frames
            )

            # 動画に書き込み
            out.write(vis_frame)

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                detection_rate = (self.stats['detected_frames'] / frame_count) * 100
                logger.info(f"Progress: {progress:.1f}% | Detection: {detection_rate:.1f}% | Filtered: {self.stats['filtered_out']}")

        # クリーンアップ
        cap.release()
        out.release()
        cv2.destroyAllWindows()

        logger.info("Video generation completed!")
        self._print_final_stats()

    def detect_face_region(self, frame):
        """顔の領域を検出"""

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pose_result = self.mp_pose.process(rgb_frame)

        face_region = None

        if pose_result.pose_landmarks:
            h, w = frame.shape[:2]

            # 顔のランドマーク（鼻、左目、右目、左耳、右耳）
            nose = pose_result.pose_landmarks.landmark[0]
            left_eye = pose_result.pose_landmarks.landmark[2]
            right_eye = pose_result.pose_landmarks.landmark[5]
            left_ear = pose_result.pose_landmarks.landmark[7]
            right_ear = pose_result.pose_landmarks.landmark[8]

            # 顔の中心と範囲を計算
            face_x = int(nose.x * w)
            face_y = int(nose.y * h)

            # 顔の幅（耳から耳まで）
            face_width = abs(int(left_ear.x * w) - int(right_ear.x * w))
            if face_width < 50:  # 最小幅
                face_width = 150

            # 顔の領域（余裕を持たせる）
            margin = 1.5
            face_region = {
                'center': (face_x, face_y),
                'left': max(0, face_x - int(face_width * margin)),
                'right': min(w, face_x + int(face_width * margin)),
                'top': max(0, face_y - int(face_width * margin)),
                'bottom': min(h, face_y + int(face_width * margin))
            }

        return face_region

    def detect_and_filter_hands(self, frame, face_region):
        """手を検出し、誤検出をフィルタリング"""

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hand_result = self.mp_hands.process(rgb_frame)

        valid_hands = []
        filtered_hands = []

        if hand_result.multi_hand_landmarks:
            h, w = frame.shape[:2]

            for hand_landmarks in hand_result.multi_hand_landmarks:
                # 手の妥当性チェック
                is_valid, reason = self.validate_hand(hand_landmarks, w, h, face_region)

                if is_valid:
                    valid_hands.append(hand_landmarks)
                else:
                    filtered_hands.append((hand_landmarks, reason))
                    if reason in self.stats['rejection_reasons']:
                        self.stats['rejection_reasons'][reason] += 1

        return valid_hands, filtered_hands

    def validate_hand(self, hand_landmarks, width, height, face_region):
        """手の妥当性を検証"""

        # 手の中心位置を計算
        landmarks_x = [lm.x for lm in hand_landmarks.landmark]
        landmarks_y = [lm.y for lm in hand_landmarks.landmark]

        center_x = sum(landmarks_x) / len(landmarks_x) * width
        center_y = sum(landmarks_y) / len(landmarks_y) * height

        # 1. 顔の領域内かチェック
        if face_region:
            if (face_region['left'] <= center_x <= face_region['right'] and
                face_region['top'] <= center_y <= face_region['bottom']):
                return False, 'near_face'

        # 2. 画面上部1/3にあるかチェック（顔の可能性）
        if center_y < height * 0.33:
            # ただし、手が前に出ている場合は除外しない
            # 手のサイズで判断
            hand_width = (max(landmarks_x) - min(landmarks_x)) * width
            hand_height = (max(landmarks_y) - min(landmarks_y)) * height
            hand_size = max(hand_width, hand_height)

            # 顔より小さければOK（手は顔より小さい）
            if hand_size > min(width, height) * 0.2:
                return False, 'face_area'

        # 3. 手の形状チェック
        # 手首から中指MCPまでの距離
        wrist = hand_landmarks.landmark[0]
        middle_mcp = hand_landmarks.landmark[9]

        wrist_to_mcp = np.sqrt(
            ((wrist.x - middle_mcp.x) * width) ** 2 +
            ((wrist.y - middle_mcp.y) * height) ** 2
        )

        # 異常に大きい場合は除外
        if wrist_to_mcp > min(width, height) * 0.2:
            return False, 'large_size'

        # 4. 手の縦横比チェック
        hand_width = (max(landmarks_x) - min(landmarks_x)) * width
        hand_height = (max(landmarks_y) - min(landmarks_y)) * height

        if hand_width > 0:
            aspect_ratio = hand_height / hand_width
            # 通常の手の縦横比は0.7～1.5程度
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                return False, 'invalid_shape'

        # 5. 指の配置の妥当性チェック
        # 親指と小指の相対位置
        thumb_tip = hand_landmarks.landmark[4]
        pinky_tip = hand_landmarks.landmark[20]

        # 両方が同じ側にある場合は不自然
        thumb_x = thumb_tip.x * width
        pinky_x = pinky_tip.x * width
        wrist_x = wrist.x * width

        thumb_side = thumb_x > wrist_x
        pinky_side = pinky_x > wrist_x

        # 親指と小指が完全に同じ側にあり、距離が近い場合は怪しい
        if thumb_side == pinky_side:
            distance = abs(thumb_x - pinky_x)
            if distance < width * 0.02:  # 非常に近い
                return False, 'invalid_shape'

        return True, None

    def _create_visualization(self, frame, valid_hands, filtered_hands, face_region, frame_num, total_frames):
        """フィルタリング結果を可視化"""

        vis_frame = frame.copy()

        # 顔の領域を表示（デバッグ用）
        if face_region:
            cv2.rectangle(vis_frame,
                         (face_region['left'], face_region['top']),
                         (face_region['right'], face_region['bottom']),
                         (255, 200, 200), 1)
            cv2.putText(vis_frame, "FACE AREA",
                       (face_region['left'], face_region['top'] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 200, 200), 1)

        # 有効な手の検出を描画
        if valid_hands:
            for hand_landmarks in valid_hands:
                self._draw_valid_hand(vis_frame, hand_landmarks)

        # フィルタリングされた検出を表示（薄く）
        if filtered_hands:
            for hand_landmarks, reason in filtered_hands:
                self._draw_filtered_hand(vis_frame, hand_landmarks, reason)

        # 情報パネル
        self._add_info_panel(vis_frame, frame_num, total_frames, valid_hands, filtered_hands)

        # タイムライン
        self._add_timeline(vis_frame)

        return vis_frame

    def _draw_valid_hand(self, frame, hand_landmarks):
        """有効な手を描画"""

        h, w = frame.shape[:2]

        # 接続線
        for connection in self.HAND_CONNECTIONS:
            start_idx, end_idx = connection
            start = hand_landmarks.landmark[start_idx]
            end = hand_landmarks.landmark[end_idx]

            x1, y1 = int(start.x * w), int(start.y * h)
            x2, y2 = int(end.x * w), int(end.y * h)

            cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # ランドマーク
        for landmark in hand_landmarks.landmark:
            x, y = int(landmark.x * w), int(landmark.y * h)
            cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)
            cv2.circle(frame, (x, y), 5, (0, 0, 0), 1)

    def _draw_filtered_hand(self, frame, hand_landmarks, reason):
        """フィルタリングされた手を描画（薄く）"""

        h, w = frame.shape[:2]

        # 中心位置
        center_x = sum([lm.x for lm in hand_landmarks.landmark]) / 21 * w
        center_y = sum([lm.y for lm in hand_landmarks.landmark]) / 21 * h

        # 薄い赤で描画
        for connection in self.HAND_CONNECTIONS:
            start_idx, end_idx = connection
            start = hand_landmarks.landmark[start_idx]
            end = hand_landmarks.landmark[end_idx]

            x1, y1 = int(start.x * w), int(start.y * h)
            x2, y2 = int(end.x * w), int(end.y * h)

            cv2.line(frame, (x1, y1), (x2, y2), (100, 100, 255), 1)

        # フィルタリング理由を表示
        cv2.putText(frame, f"FILTERED: {reason}",
                   (int(center_x) - 50, int(center_y) - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 255), 1)

    def _add_info_panel(self, frame, frame_num, total_frames, valid_hands, filtered_hands):
        """情報パネル"""

        # パネル背景
        panel_height = 120
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
        frame[:panel_height] = cv2.addWeighted(overlay[:panel_height], 0.7, frame[:panel_height], 0.3, 0)

        # 基本情報
        progress = (frame_num / total_frames) * 100
        cv2.putText(frame, f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出状態
        valid_count = len(valid_hands) if valid_hands else 0
        filtered_count = len(filtered_hands) if filtered_hands else 0

        cv2.putText(frame, f"Valid Hands: {valid_count}",
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.putText(frame, f"Filtered: {filtered_count}",
                   (200, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 1)

        # 検出率
        if self.stats['total_frames'] > 0:
            detection_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100 if frame_num > 0 else 0
            cv2.putText(frame, f"Detection Rate: {detection_rate:.1f}%",
                       (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            total_filtered = self.stats['filtered_out']
            cv2.putText(frame, f"Total Filtered: {total_filtered}",
                       (250, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 1)

        # モード表示
        cv2.putText(frame, "[FILTERED DETECTION MODE]",
                   (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    def _add_timeline(self, frame):
        """検出タイムライン"""

        if len(self.detection_history) < 2:
            return

        # グラフ領域
        graph_x = frame.shape[1] - 220
        graph_y = frame.shape[0] - 70
        graph_width = 200
        graph_height = 50

        # 背景
        overlay = frame.copy()
        cv2.rectangle(overlay,
                     (graph_x - 5, graph_y - 5),
                     (graph_x + graph_width + 5, graph_y + graph_height + 5),
                     (0, 0, 0), -1)
        frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5] = \
            cv2.addWeighted(overlay[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5],
                          0.7,
                          frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5],
                          0.3, 0)

        # グラフ
        for i, detected in enumerate(self.detection_history):
            x = graph_x + int(i * graph_width / len(self.detection_history))
            if detected:
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y), (0, 255, 0), 1)

        cv2.putText(frame, "Valid Detections (100 frames)",
                   (graph_x, graph_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

    def _print_final_stats(self):
        """最終統計"""

        print("\n" + "=" * 80)
        print("FILTERED DETECTION STATISTICS")
        print("=" * 80)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']
        filtered = self.stats['filtered_out']

        detection_rate = (detected / total * 100) if total > 0 else 0

        print(f"Total frames: {total}")
        print(f"Frames with valid detection: {detected} ({detection_rate:.1f}%)")
        print(f"Total hands detected: {self.stats['total_hands']}")
        print(f"Total detections filtered: {filtered}")

        print("\nFiltering reasons:")
        for reason, count in self.stats['rejection_reasons'].items():
            print(f"  - {reason}: {count}")

        print(f"\nOutput saved to: {self.output_path}")


def main():
    """メイン処理"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/White_Glove.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/White_Glove_filtered_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 80)
    print("FILTERED WHITE GLOVE DETECTION")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    generator = FilteredWhiteGloveDetector(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()