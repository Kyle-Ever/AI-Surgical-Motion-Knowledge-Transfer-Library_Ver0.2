"""青い手袋の手技検出結果を見やすく可視化した動画を生成（改良版）"""

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


class EnhancedDetectionVideoGenerator:
    """改良版の検出結果可視化動画生成クラス"""

    # 手のランドマーク接続情報
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

        # 検出器の初期化（最適化された設定）
        self.detector = HandSkeletonDetector(
            enable_glove_detection=True,
            min_detection_confidence=0.1,
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
            'right_hands': 0,
            'max_confidence': 0,
            'min_confidence': 1.0
        }

        # トラッキング用
        self.last_detection = None
        self.detection_history = []

    def generate_video(self):
        """検出結果を可視化した動画を生成"""

        logger.info(f"Processing: {self.input_path}")
        logger.info(f"Output will be saved to: {self.output_path}")

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
        logger.info("Starting video generation...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 手の検出
            result = self.detector.detect_from_frame(frame)
            hands = result.get("hands", [])

            # 統計情報の更新
            self._update_stats(hands)
            self.detection_history.append(len(hands) > 0)

            # 可視化
            vis_frame = self._create_visualization(frame, hands, frame_count, total_frames)

            # 動画に書き込み
            out.write(vis_frame)

            frame_count += 1

            # 進捗表示（10%ごと）
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                logger.info(f"Progress: {progress:.1f}% ({frame_count}/{total_frames})")

        # クリーンアップ
        cap.release()
        out.release()
        cv2.destroyAllWindows()

        self.stats['total_frames'] = frame_count

        logger.info(f"Video generation completed!")
        self._print_final_stats()

    def _create_visualization(self, frame: np.ndarray, hands: list, frame_num: int, total_frames: int) -> np.ndarray:
        """フレームの可視化を作成"""

        vis_frame = frame.copy()

        # 検出がある場合は描画
        if hands:
            for hand in hands:
                self._draw_hand_skeleton(vis_frame, hand)
                self._draw_hand_info(vis_frame, hand)

        # 情報パネルを追加
        self._add_info_panel(vis_frame, hands, frame_num, total_frames)

        # 検出履歴グラフを追加
        self._add_detection_timeline(vis_frame)

        return vis_frame

    def _draw_hand_skeleton(self, frame: np.ndarray, hand: dict):
        """手の骨格を描画"""

        if not hand.get('landmarks'):
            return

        landmarks = hand['landmarks']

        # 接続線を先に描画（細い線）
        for connection in self.HAND_CONNECTIONS:
            start_idx, end_idx = connection
            if start_idx < len(landmarks) and end_idx < len(landmarks):
                start = landmarks[start_idx]
                end = landmarks[end_idx]
                x1, y1 = int(start['x']), int(start['y'])
                x2, y2 = int(end['x']), int(end['y'])

                # 手の左右で色を変える
                if hand['handedness'] == 'Left':
                    line_color = (255, 150, 0)  # 青系
                else:
                    line_color = (0, 150, 255)  # 赤系

                cv2.line(frame, (x1, y1), (x2, y2), line_color, 2)

        # ランドマーク点を描画
        for i, landmark in enumerate(landmarks):
            x = int(landmark['x'])
            y = int(landmark['y'])

            # 重要な点は大きく
            if i == 0:  # 手首
                size = 6
                color = (255, 255, 255)
            elif i in [4, 8, 12, 16, 20]:  # 指先
                size = 5
                color = (0, 255, 255)
            else:
                size = 3
                color = (0, 255, 0)

            cv2.circle(frame, (x, y), size, color, -1)
            cv2.circle(frame, (x, y), size + 1, (0, 0, 0), 1)

    def _draw_hand_info(self, frame: np.ndarray, hand: dict):
        """手の情報を描画"""

        if not hand.get('bbox'):
            return

        bbox = hand['bbox']
        x_min = int(bbox['x_min'])
        y_min = int(bbox['y_min'])
        x_max = int(bbox['x_max'])
        y_max = int(bbox['y_max'])

        # バウンディングボックス
        if hand['handedness'] == 'Left':
            box_color = (255, 100, 0)  # 青系
        else:
            box_color = (0, 100, 255)  # 赤系

        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), box_color, 2)

        # ラベル
        label = f"{hand['handedness']} {hand['confidence']:.0%}"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]

        # ラベル背景
        cv2.rectangle(frame,
                     (x_min, y_min - label_size[1] - 8),
                     (x_min + label_size[0] + 8, y_min),
                     box_color, -1)

        # ラベルテキスト
        cv2.putText(frame, label,
                   (x_min + 4, y_min - 4),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # 手の開き具合を表示
        if hand.get('hand_openness') is not None:
            openness = hand['hand_openness']
            openness_text = f"Open: {openness:.0f}%"
            cv2.putText(frame, openness_text,
                       (x_min, y_max + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, box_color, 1)

    def _add_info_panel(self, frame: np.ndarray, hands: list, frame_num: int, total_frames: int):
        """情報パネルを追加"""

        # 上部に半透明パネル
        panel_height = 80
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
        frame[:panel_height] = cv2.addWeighted(overlay[:panel_height], 0.6, frame[:panel_height], 0.4, 0)

        # フレーム情報
        progress = (frame_num / total_frames) * 100
        frame_text = f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)"
        cv2.putText(frame, frame_text,
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出状態
        if hands:
            status_text = "DETECTED"
            status_color = (0, 255, 0)

            # 手の詳細
            left_count = sum(1 for h in hands if h['handedness'] == 'Left')
            right_count = sum(1 for h in hands if h['handedness'] == 'Right')
            hands_text = f"Hands: L={left_count} R={right_count}"

            # 平均信頼度
            avg_conf = np.mean([h['confidence'] for h in hands])
            conf_text = f"Confidence: {avg_conf:.0%}"
        else:
            status_text = "NO DETECTION"
            status_color = (0, 100, 255)
            hands_text = "Hands: None"
            conf_text = "Confidence: --"

        cv2.putText(frame, status_text,
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

        cv2.putText(frame, hands_text,
                   (200, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.putText(frame, conf_text,
                   (350, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 統計情報
        if self.stats['detected_frames'] > 0:
            detection_rate = (self.stats['detected_frames'] / max(1, frame_num)) * 100
            stats_text = f"Detection Rate: {detection_rate:.1f}%"
            cv2.putText(frame, stats_text,
                       (500, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)

    def _add_detection_timeline(self, frame: np.ndarray):
        """検出履歴のタイムライン表示"""

        if len(self.detection_history) < 2:
            return

        # 最近100フレームの履歴を表示
        recent_history = self.detection_history[-100:]

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

        # グラフを描画
        for i, detected in enumerate(recent_history):
            x = graph_x + int(i * graph_width / len(recent_history))
            if detected:
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y), (0, 255, 0), 1)
            else:
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y + graph_height - 5), (0, 0, 255), 1)

        # ラベル
        cv2.putText(frame, "Detection Timeline (last 100 frames)",
                   (graph_x, graph_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

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

                conf = hand['confidence']
                self.stats['max_confidence'] = max(self.stats['max_confidence'], conf)
                self.stats['min_confidence'] = min(self.stats['min_confidence'], conf)

    def _print_final_stats(self):
        """最終統計を表示"""

        print("\n" + "=" * 70)
        print("FINAL STATISTICS")
        print("=" * 70)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']

        if total > 0:
            detection_rate = (detected / total) * 100
            avg_hands = self.stats['total_hands'] / detected if detected > 0 else 0
        else:
            detection_rate = 0
            avg_hands = 0

        print(f"Total frames processed: {total}")
        print(f"Frames with detection: {detected} ({detection_rate:.1f}%)")
        print(f"Total hands detected: {self.stats['total_hands']}")
        print(f"  - Left hands: {self.stats['left_hands']}")
        print(f"  - Right hands: {self.stats['right_hands']}")
        print(f"Average hands per detected frame: {avg_hands:.2f}")

        if self.stats['detected_frames'] > 0:
            print(f"Confidence range: {self.stats['min_confidence']:.2f} - {self.stats['max_confidence']:.2f}")

        print(f"\nOutput video saved to: {self.output_path}")
        print(f"File size: {self.output_path.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    """メイン処理"""

    # タイムスタンプ付きのファイル名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/Front_Angle_detection_{timestamp}.mp4")

    # 出力ディレクトリの確認
    output_video.parent.mkdir(parents=True, exist_ok=True)

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 70)
    print("ENHANCED DETECTION VIDEO GENERATION")
    print("=" * 70)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    # 動画生成
    generator = EnhancedDetectionVideoGenerator(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()