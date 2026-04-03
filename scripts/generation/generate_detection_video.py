"""青い手袋の手技検出結果を可視化した動画を生成"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DetectionVideoGenerator:
    """検出結果を可視化した動画生成クラス"""

    # 手のランドマーク接続情報（MediaPipe準拠）
    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),  # 親指
        (0, 5), (5, 6), (6, 7), (7, 8),  # 人差し指
        (5, 9), (9, 10), (10, 11), (11, 12),  # 中指
        (9, 13), (13, 14), (14, 15), (15, 16),  # 薬指
        (13, 17), (17, 18), (18, 19), (19, 20),  # 小指
        (0, 17)  # 手のひら
    ]

    # 指ごとの色定義
    FINGER_COLORS = {
        'thumb': (255, 0, 0),      # 青
        'index': (0, 255, 0),      # 緑
        'middle': (0, 255, 255),   # 黄
        'ring': (255, 0, 255),     # マゼンタ
        'pinky': (255, 128, 0)     # オレンジ
    }

    def __init__(self, input_video_path: str, output_video_path: str):
        """
        初期化

        Args:
            input_video_path: 入力動画パス
            output_video_path: 出力動画パス
        """
        self.input_path = Path(input_video_path)
        self.output_path = Path(output_video_path)

        # 検出器の初期化（最適化された設定）
        self.detector = HandSkeletonDetector(
            enable_glove_detection=True,
            min_detection_confidence=0.1,  # 最適化された閾値
            min_tracking_confidence=0.1,
            max_num_hands=2,
            static_image_mode=False
        )

        # 統計情報
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'total_hands': 0,
            'left_hands': 0,
            'right_hands': 0
        }

    def generate_video(self, skip_frames: int = 0):
        """
        検出結果を可視化した動画を生成

        Args:
            skip_frames: 処理をスキップするフレーム数（0=全フレーム処理）
        """
        logger.info(f"Processing video: {self.input_path}")

        # 入力動画を開く
        cap = cv2.VideoCapture(str(self.input_path))

        # 動画情報を取得
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video info: {width}x{height}, {fps}fps, {total_frames} frames")

        # 出力動画の設定
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(self.output_path),
            fourcc,
            fps // (skip_frames + 1),  # スキップに応じてFPS調整
            (width, height)
        )

        frame_count = 0
        processed_count = 0

        logger.info("Starting frame processing...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # フレームスキップ
            if skip_frames > 0 and frame_count % (skip_frames + 1) != 0:
                frame_count += 1
                continue

            # 手の検出
            result = self.detector.detect_from_frame(frame)
            hands = result.get("hands", [])

            # 可視化
            vis_frame = self._visualize_detection(frame, hands)

            # 統計情報の更新
            self._update_stats(hands)

            # フレーム番号と検出情報を表示
            self._add_info_overlay(vis_frame, frame_count, hands)

            # 動画に書き込み
            out.write(vis_frame)

            processed_count += 1

            # 進捗表示（10%ごと）
            if processed_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                logger.info(f"Progress: {progress:.1f}% ({frame_count}/{total_frames})")

            frame_count += 1

        # クリーンアップ
        cap.release()
        out.release()
        cv2.destroyAllWindows()

        self.stats['total_frames'] = processed_count

        logger.info(f"Video generation completed: {self.output_path}")
        self._print_stats()

    def _visualize_detection(self, frame: np.ndarray, hands: list) -> np.ndarray:
        """
        検出結果を可視化

        Args:
            frame: 元のフレーム
            hands: 検出された手のリスト

        Returns:
            可視化されたフレーム
        """
        vis_frame = frame.copy()

        for hand in hands:
            # ランドマークを描画
            if hand.get('landmarks'):
                self._draw_hand_landmarks(vis_frame, hand['landmarks'])

            # バウンディングボックスを描画
            if hand.get('bbox'):
                self._draw_bounding_box(vis_frame, hand['bbox'], hand)

            # 手の中心と開き具合を表示
            if hand.get('palm_center'):
                self._draw_palm_info(vis_frame, hand)

        return vis_frame

    def _draw_hand_landmarks(self, frame: np.ndarray, landmarks: list):
        """手のランドマークと接続線を描画"""

        # ランドマーク点を描画
        for i, landmark in enumerate(landmarks):
            x = int(landmark['x'])
            y = int(landmark['y'])

            # 指ごとに色を変える
            if i == 0:  # 手首
                color = (255, 255, 255)
                size = 7
            elif 1 <= i <= 4:  # 親指
                color = self.FINGER_COLORS['thumb']
                size = 5
            elif 5 <= i <= 8:  # 人差し指
                color = self.FINGER_COLORS['index']
                size = 5
            elif 9 <= i <= 12:  # 中指
                color = self.FINGER_COLORS['middle']
                size = 5
            elif 13 <= i <= 16:  # 薬指
                color = self.FINGER_COLORS['ring']
                size = 5
            else:  # 小指
                color = self.FINGER_COLORS['pinky']
                size = 5

            cv2.circle(frame, (x, y), size, color, -1)
            cv2.circle(frame, (x, y), size + 2, (0, 0, 0), 1)  # 黒枠

        # 接続線を描画
        for connection in self.HAND_CONNECTIONS:
            start_idx, end_idx = connection

            if start_idx < len(landmarks) and end_idx < len(landmarks):
                start = landmarks[start_idx]
                end = landmarks[end_idx]

                x1, y1 = int(start['x']), int(start['y'])
                x2, y2 = int(end['x']), int(end['y'])

                # 接続線の色（指ごと）
                if end_idx <= 4:
                    color = self.FINGER_COLORS['thumb']
                elif end_idx <= 8:
                    color = self.FINGER_COLORS['index']
                elif end_idx <= 12:
                    color = self.FINGER_COLORS['middle']
                elif end_idx <= 16:
                    color = self.FINGER_COLORS['ring']
                else:
                    color = self.FINGER_COLORS['pinky']

                cv2.line(frame, (x1, y1), (x2, y2), color, 2)

    def _draw_bounding_box(self, frame: np.ndarray, bbox: dict, hand: dict):
        """バウンディングボックスとラベルを描画"""

        x_min = int(bbox['x_min'])
        y_min = int(bbox['y_min'])
        x_max = int(bbox['x_max'])
        y_max = int(bbox['y_max'])

        # 手の左右で色を変える
        if hand['handedness'] == 'Left':
            color = (255, 100, 0)  # 青系
        else:
            color = (0, 100, 255)  # 赤系

        # バウンディングボックス
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)

        # ラベル背景
        label = f"{hand['handedness']} ({hand['confidence']:.2f})"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(frame,
                     (x_min, y_min - label_size[1] - 10),
                     (x_min + label_size[0] + 10, y_min),
                     color, -1)

        # ラベルテキスト
        cv2.putText(frame, label,
                   (x_min + 5, y_min - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    def _draw_palm_info(self, frame: np.ndarray, hand: dict):
        """手のひら中心と開き具合を表示"""

        center = hand['palm_center']
        x = int(center['x'])
        y = int(center['y'])

        # 手のひら中心を表示
        cv2.circle(frame, (x, y), 8, (255, 255, 0), -1)
        cv2.circle(frame, (x, y), 10, (0, 0, 0), 2)

        # 手の開き具合を表示
        openness = hand.get('hand_openness', 0)
        text = f"{openness:.0f}%"
        cv2.putText(frame, text,
                   (x - 20, y + 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    def _add_info_overlay(self, frame: np.ndarray, frame_num: int, hands: list):
        """フレーム情報のオーバーレイを追加"""

        # 背景の半透明ボックス
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (350, 100), (0, 0, 0), -1)
        frame[:] = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)

        # フレーム番号
        cv2.putText(frame, f"Frame: {frame_num}",
                   (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 検出情報
        hands_text = f"Hands: {len(hands)}"
        if hands:
            left_count = sum(1 for h in hands if h['handedness'] == 'Left')
            right_count = sum(1 for h in hands if h['handedness'] == 'Right')
            hands_text += f" (L:{left_count}, R:{right_count})"

        cv2.putText(frame, hands_text,
                   (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # 検出状態
        status = "DETECTED" if hands else "NO DETECTION"
        status_color = (0, 255, 0) if hands else (0, 0, 255)
        cv2.putText(frame, status,
                   (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

    def _update_stats(self, hands: list):
        """統計情報を更新"""

        if hands:
            self.stats['detected_frames'] += 1
            self.stats['total_hands'] += len(hands)

            for hand in hands:
                if hand['handedness'] == 'Left':
                    self.stats['left_hands'] += 1
                else:
                    self.stats['right_hands'] += 1

    def _print_stats(self):
        """統計情報を表示"""

        print("\n" + "=" * 60)
        print("DETECTION STATISTICS")
        print("=" * 60)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']

        if total > 0:
            detection_rate = (detected / total) * 100
            avg_hands = self.stats['total_hands'] / total
        else:
            detection_rate = 0
            avg_hands = 0

        print(f"Total frames: {total}")
        print(f"Frames with detection: {detected} ({detection_rate:.1f}%)")
        print(f"Total hands detected: {self.stats['total_hands']}")
        print(f"  - Left hands: {self.stats['left_hands']}")
        print(f"  - Right hands: {self.stats['right_hands']}")
        print(f"Average hands per frame: {avg_hands:.2f}")


def main():
    """メイン処理"""

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")
    output_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/Front_Angle_detection.mp4")

    # 出力ディレクトリの確認
    output_video.parent.mkdir(parents=True, exist_ok=True)

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    logger.info("Starting video generation with hand detection visualization...")

    # 動画生成
    generator = DetectionVideoGenerator(str(input_video), str(output_video))

    # skip_frames=1で処理（2フレームに1回処理して高速化）
    generator.generate_video(skip_frames=1)

    print(f"\nOutput video saved to: {output_video}")
    print(f"File size: {output_video.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()