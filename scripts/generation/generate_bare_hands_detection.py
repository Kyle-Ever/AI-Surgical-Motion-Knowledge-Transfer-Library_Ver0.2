"""素手の動画で両手の動きを検出"""

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


class BareHandsDetector:
    """素手の検出（高精度）"""

    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),  # 親指
        (0, 5), (5, 6), (6, 7), (7, 8),  # 人差し指
        (5, 9), (9, 10), (10, 11), (11, 12),  # 中指
        (9, 13), (13, 14), (14, 15), (15, 16),  # 薬指
        (13, 17), (17, 18), (18, 19), (19, 20),  # 小指
        (0, 17)  # 手のひら
    ]

    # 指の色分け
    FINGER_COLORS = {
        'thumb': (255, 0, 0),      # 青
        'index': (0, 255, 0),      # 緑
        'middle': (0, 255, 255),   # 黄
        'ring': (255, 0, 255),     # マゼンタ
        'pinky': (255, 128, 0)     # オレンジ
    }

    def __init__(self, input_video_path: str, output_video_path: str):
        """初期化"""
        self.input_path = Path(input_video_path)
        self.output_path = Path(output_video_path)

        # MediaPipe手検出（素手用に最適化）
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,  # 素手なので標準閾値
            min_tracking_confidence=0.5,
            model_complexity=1
        )

        self.mp_drawing = mp.solutions.drawing_utils

        # トラッキング履歴
        self.detection_history = deque(maxlen=100)
        self.left_hand_trajectory = deque(maxlen=30)
        self.right_hand_trajectory = deque(maxlen=30)

        # 統計
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'both_hands_frames': 0,
            'left_only_frames': 0,
            'right_only_frames': 0,
            'total_hands': 0
        }

    def generate_video(self):
        """検出結果動画を生成"""

        logger.info(f"Processing: {self.input_path}")
        logger.info("BARE HANDS DETECTION - Optimized for natural skin")

        cap = cv2.VideoCapture(str(self.input_path))

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video: {width}x{height} @ {fps}fps, {total_frames} frames")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(self.output_path),
            fourcc,
            fps,
            (width, height)
        )

        frame_count = 0
        logger.info("Starting detection...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 手を検出
            detection_result = self.detect_hands(frame)

            # 統計更新
            self._update_stats(detection_result)

            # 検出履歴
            self.detection_history.append(1 if detection_result else 0)

            # 可視化
            vis_frame = self._create_visualization(
                frame, detection_result, frame_count, total_frames
            )

            out.write(vis_frame)

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                detection_rate = (self.stats['detected_frames'] / frame_count) * 100
                both_rate = (self.stats['both_hands_frames'] / frame_count) * 100
                logger.info(f"Progress: {progress:.1f}% | Detection: {detection_rate:.1f}% | Both hands: {both_rate:.1f}%")

        cap.release()
        out.release()
        cv2.destroyAllWindows()

        logger.info("Video generation completed!")
        self._print_final_stats()

    def detect_hands(self, frame):
        """手を検出"""

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.mp_hands.process(rgb_frame)

        if result.multi_hand_landmarks:
            hands_info = []

            for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
                hand_info = {
                    'landmarks': hand_landmarks,
                    'handedness': None,
                    'confidence': 0.5
                }

                # 手の左右と信頼度
                if result.multi_handedness and idx < len(result.multi_handedness):
                    handedness = result.multi_handedness[idx]
                    hand_info['handedness'] = handedness.classification[0].label
                    hand_info['confidence'] = handedness.classification[0].score

                    # 軌跡を記録
                    h, w = frame.shape[:2]
                    wrist = hand_landmarks.landmark[0]
                    wrist_point = (int(wrist.x * w), int(wrist.y * h))

                    if hand_info['handedness'] == 'Left':
                        self.left_hand_trajectory.append(wrist_point)
                    else:
                        self.right_hand_trajectory.append(wrist_point)

                hands_info.append(hand_info)

            return {
                'hands': hands_info,
                'count': len(hands_info)
            }

        return None

    def _update_stats(self, detection):
        """統計を更新"""

        if detection:
            self.stats['detected_frames'] += 1
            self.stats['total_hands'] += detection['count']

            if detection['count'] == 2:
                self.stats['both_hands_frames'] += 1
            elif detection['count'] == 1:
                # 左右どちらか判定
                if detection['hands'][0]['handedness'] == 'Left':
                    self.stats['left_only_frames'] += 1
                else:
                    self.stats['right_only_frames'] += 1

    def _create_visualization(self, frame, detection, frame_num, total_frames):
        """可視化"""

        vis_frame = frame.copy()

        # 手の検出を描画
        if detection and detection['hands']:
            for hand_info in detection['hands']:
                hand_landmarks = hand_info['landmarks']

                # カスタム描画（指ごとに色分け）
                self._draw_hand_custom(vis_frame, hand_landmarks)

                # 手の情報を表示
                if hand_info['handedness']:
                    h, w = frame.shape[:2]
                    wrist = hand_landmarks.landmark[0]
                    wrist_x = int(wrist.x * w)
                    wrist_y = int(wrist.y * h)

                    # ラベルと信頼度
                    label = hand_info['handedness']
                    conf = hand_info['confidence']
                    text = f"{label} ({conf:.2f})"

                    # 背景付きテキスト
                    (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(vis_frame,
                                (wrist_x - 40, wrist_y - 30),
                                (wrist_x - 40 + text_width + 10, wrist_y - 10),
                                (0, 0, 0), -1)
                    cv2.putText(vis_frame, text,
                               (wrist_x - 35, wrist_y - 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 手の軌跡を描画
        self._draw_trajectories(vis_frame)

        # 情報パネル
        self._add_info_panel(vis_frame, frame_num, total_frames, detection)

        # 検出タイムライン
        self._add_timeline(vis_frame)

        return vis_frame

    def _draw_hand_custom(self, frame, hand_landmarks):
        """手をカスタム描画（指ごとに色分け）"""

        h, w = frame.shape[:2]

        # 指ごとの接続を色分けして描画
        connections = {
            'thumb': [(0, 1), (1, 2), (2, 3), (3, 4)],
            'index': [(0, 5), (5, 6), (6, 7), (7, 8)],
            'middle': [(5, 9), (9, 10), (10, 11), (11, 12)],
            'ring': [(9, 13), (13, 14), (14, 15), (15, 16)],
            'pinky': [(13, 17), (17, 18), (18, 19), (19, 20)]
        }

        # 各指の接続線を描画
        for finger, finger_connections in connections.items():
            color = self.FINGER_COLORS[finger]
            for connection in finger_connections:
                start_idx, end_idx = connection
                start = hand_landmarks.landmark[start_idx]
                end = hand_landmarks.landmark[end_idx]

                x1, y1 = int(start.x * w), int(start.y * h)
                x2, y2 = int(end.x * w), int(end.y * h)

                cv2.line(frame, (x1, y1), (x2, y2), color, 3)

        # 手のひらの接続
        palm_connections = [(0, 5), (5, 9), (9, 13), (13, 17), (0, 17)]
        for connection in palm_connections:
            start_idx, end_idx = connection
            start = hand_landmarks.landmark[start_idx]
            end = hand_landmarks.landmark[end_idx]

            x1, y1 = int(start.x * w), int(start.y * h)
            x2, y2 = int(end.x * w), int(end.y * h)

            cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)

        # ランドマーク点を描画
        for i, landmark in enumerate(hand_landmarks.landmark):
            x, y = int(landmark.x * w), int(landmark.y * h)

            if i == 0:  # 手首
                cv2.circle(frame, (x, y), 8, (255, 255, 255), -1)
                cv2.circle(frame, (x, y), 9, (0, 0, 0), 2)
            elif i in [4, 8, 12, 16, 20]:  # 指先
                cv2.circle(frame, (x, y), 6, (0, 255, 255), -1)
                cv2.circle(frame, (x, y), 7, (0, 0, 0), 1)
            else:
                cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)

    def _draw_trajectories(self, frame):
        """手の軌跡を描画"""

        # 左手の軌跡（赤）
        if len(self.left_hand_trajectory) > 1:
            points = list(self.left_hand_trajectory)
            for i in range(1, len(points)):
                opacity = i / len(points)
                thickness = int(1 + opacity * 2)
                cv2.line(frame, points[i-1], points[i], (0, 0, 255), thickness)

        # 右手の軌跡（青）
        if len(self.right_hand_trajectory) > 1:
            points = list(self.right_hand_trajectory)
            for i in range(1, len(points)):
                opacity = i / len(points)
                thickness = int(1 + opacity * 2)
                cv2.line(frame, points[i-1], points[i], (255, 0, 0), thickness)

    def _add_info_panel(self, frame, frame_num, total_frames, detection):
        """情報パネル"""

        # 半透明パネル
        panel_height = 100
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
        frame[:panel_height] = cv2.addWeighted(overlay[:panel_height], 0.7, frame[:panel_height], 0.3, 0)

        # フレーム情報
        progress = (frame_num / total_frames) * 100
        cv2.putText(frame, f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出状態
        if detection:
            if detection['count'] == 2:
                status = "BOTH HANDS DETECTED"
                color = (0, 255, 0)
            elif detection['count'] == 1:
                hand = detection['hands'][0]['handedness']
                status = f"{hand.upper()} HAND ONLY"
                color = (0, 200, 255)
            else:
                status = "DETECTED"
                color = (0, 255, 0)
        else:
            status = "NO DETECTION"
            color = (0, 100, 255)

        cv2.putText(frame, status,
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # 統計
        if frame_num > 0:
            detection_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100
            both_rate = (self.stats['both_hands_frames'] / (frame_num + 1)) * 100

            cv2.putText(frame, f"Detection: {detection_rate:.1f}%",
                       (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.putText(frame, f"Both hands: {both_rate:.1f}%",
                       (200, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)

        # モード表示
        cv2.putText(frame, "[BARE HANDS MODE]",
                   (frame.shape[1] - 180, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # 色の凡例
        cv2.putText(frame, "Colors:",
                   (frame.shape[1] - 180, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        finger_names = ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']
        for i, (finger, color) in enumerate(self.FINGER_COLORS.items()):
            cv2.putText(frame, finger_names[i][:3],
                       (frame.shape[1] - 180 + i * 35, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)

    def _add_timeline(self, frame):
        """検出タイムライン"""

        if len(self.detection_history) < 2:
            return

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
                          0.7, frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5], 0.3, 0)

        # グラフ
        for i, detected in enumerate(self.detection_history):
            x = graph_x + int(i * graph_width / len(self.detection_history))
            if detected:
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y), (0, 255, 0), 1)

        cv2.putText(frame, "Detection Timeline",
                   (graph_x, graph_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

    def _print_final_stats(self):
        """最終統計"""

        print("\n" + "=" * 80)
        print("BARE HANDS DETECTION RESULTS")
        print("=" * 80)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']
        both = self.stats['both_hands_frames']
        left_only = self.stats['left_only_frames']
        right_only = self.stats['right_only_frames']

        detection_rate = (detected / total * 100) if total > 0 else 0
        both_rate = (both / total * 100) if total > 0 else 0

        print(f"Total frames: {total}")
        print(f"Frames with detection: {detected} ({detection_rate:.1f}%)")
        print(f"  - Both hands: {both} ({both_rate:.1f}%)")
        print(f"  - Left hand only: {left_only}")
        print(f"  - Right hand only: {right_only}")
        print(f"Total hand instances: {self.stats['total_hands']}")

        avg_hands = self.stats['total_hands'] / detected if detected > 0 else 0
        print(f"Average hands per detected frame: {avg_hands:.2f}")

        print(f"\nOutput saved to: {self.output_path}")


def main():
    """メイン処理"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # コマンドライン引数から動画パスを取得（デフォルトはVID_20250926_120743.mp4）
    import sys
    if len(sys.argv) > 1:
        video_name = sys.argv[1]
    else:
        video_name = "VID_20250926_120743.mp4"

    input_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/{video_name}")

    # 出力ファイル名を入力ファイル名から生成
    output_name = video_name.replace('.mp4', f'_detection_{timestamp}.mp4').replace('VID_', '')
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/{output_name}")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 80)
    print("BARE HANDS DETECTION")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    generator = BareHandsDetector(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()