"""白い手袋の検出（バランス調整版）- 手の検出と誤検出除外のバランス"""

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


class BalancedWhiteGloveDetector:
    """バランスの取れた白い手袋検出器"""

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

        # 複数の検出器を使用（異なる閾値）
        self.detectors = [
            # 超低閾値（メイン）
            {
                'name': 'ultra_low',
                'detector': mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    min_detection_confidence=0.01,
                    min_tracking_confidence=0.01,
                    model_complexity=1
                ),
                'weight': 1.0
            },
            # 低閾値（バックアップ）
            {
                'name': 'low',
                'detector': mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    min_detection_confidence=0.1,
                    min_tracking_confidence=0.1,
                    model_complexity=1
                ),
                'weight': 1.2  # より高い信頼度
            }
        ]

        # 描画用
        self.mp_drawing = mp.solutions.drawing_utils

        # トラッキング履歴
        self.detection_history = deque(maxlen=100)
        self.position_history = deque(maxlen=30)  # 位置の履歴
        self.size_history = deque(maxlen=30)  # サイズの履歴

        # 統計情報
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'filtered_frames': 0,
            'total_hands': 0,
            'face_filtered': 0,
            'size_filtered': 0,
            'motion_filtered': 0
        }

    def generate_video(self):
        """検出結果を可視化した動画を生成"""

        logger.info(f"Processing: {self.input_path}")
        logger.info("BALANCED DETECTION MODE: Optimized for white gloves")

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
        logger.info("Starting balanced detection...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 複数の検出器で検出
            all_detections = self.detect_with_multiple_methods(frame)

            # 最適な検出結果を選択
            best_detection = self.select_best_detection(all_detections, frame.shape[:2])

            # フィルタリング（緩い条件）
            if best_detection:
                valid, reason = self.validate_detection_lenient(best_detection['hands'], frame.shape[1], frame.shape[0])
                if not valid:
                    self.stats['filtered_frames'] += 1
                    if reason == 'face_area':
                        self.stats['face_filtered'] += 1
                    elif reason == 'size':
                        self.stats['size_filtered'] += 1
                    elif reason == 'motion':
                        self.stats['motion_filtered'] += 1
                    best_detection = None

            # 統計更新
            if best_detection:
                self.stats['detected_frames'] += 1
                self.stats['total_hands'] += len(best_detection['hands'].multi_hand_landmarks)

            # 検出履歴
            self.detection_history.append(1 if best_detection else 0)

            # 可視化
            vis_frame = self._create_visualization(
                frame, best_detection, frame_count, total_frames
            )

            # 動画に書き込み
            out.write(vis_frame)

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                detection_rate = (self.stats['detected_frames'] / frame_count) * 100
                logger.info(f"Progress: {progress:.1f}% | Detection: {detection_rate:.1f}% | Filtered: {self.stats['filtered_frames']}")

        # クリーンアップ
        cap.release()
        out.release()
        cv2.destroyAllWindows()

        logger.info("Video generation completed!")
        self._print_final_stats()

    def detect_with_multiple_methods(self, frame):
        """複数の方法で検出"""

        all_detections = []
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        for detector_info in self.detectors:
            try:
                result = detector_info['detector'].process(rgb_frame)
                if result.multi_hand_landmarks:
                    confidence = self.calculate_detection_confidence(result)
                    all_detections.append({
                        'hands': result,
                        'method': detector_info['name'],
                        'confidence': confidence * detector_info['weight']
                    })
            except:
                continue

        return all_detections

    def calculate_detection_confidence(self, result):
        """検出の信頼度を計算"""

        if not result.multi_handedness:
            return 0.5

        confidences = [h.classification[0].score for h in result.multi_handedness]
        return np.mean(confidences)

    def select_best_detection(self, detections, frame_shape):
        """最適な検出結果を選択"""

        if not detections:
            return None

        # 信頼度が最も高いものを選択
        best = max(detections, key=lambda x: x['confidence'])
        return best

    def validate_detection_lenient(self, hands_result, width, height):
        """緩い条件で検出を検証（実際の手を除外しないように）"""

        if not hands_result.multi_hand_landmarks:
            return True, None

        for hand_landmarks in hands_result.multi_hand_landmarks:
            # 手の位置とサイズを計算
            landmarks_x = [lm.x for lm in hand_landmarks.landmark]
            landmarks_y = [lm.y for lm in hand_landmarks.landmark]

            center_x = sum(landmarks_x) / len(landmarks_x) * width
            center_y = sum(landmarks_y) / len(landmarks_y) * height

            hand_width = (max(landmarks_x) - min(landmarks_x)) * width
            hand_height = (max(landmarks_y) - min(landmarks_y)) * height
            hand_size = max(hand_width, hand_height)

            # 位置とサイズの履歴に追加
            self.position_history.append((center_x, center_y))
            self.size_history.append(hand_size)

            # 1. 極端に画面上部（上5%）かつ非常に大きい場合のみ除外
            if center_y < height * 0.05 and hand_size > min(width, height) * 0.4:
                return False, 'face_area'

            # 2. 異常に大きい場合（画面の50%以上）のみ除外 - 手術動画では手が大きく映る
            if hand_size > min(width, height) * 0.5:
                return False, 'size'

            # 3. 動きの一貫性チェック（オプション）
            if len(self.position_history) >= 10:
                # 過去10フレームの平均位置
                avg_x = np.mean([p[0] for p in list(self.position_history)[-10:]])
                avg_y = np.mean([p[1] for p in list(self.position_history)[-10:]])

                # 突然の大きなジャンプ（画面の50%以上）
                distance = np.sqrt((center_x - avg_x)**2 + (center_y - avg_y)**2)
                if distance > min(width, height) * 0.5:
                    # ただし、最初の検出や再検出は許可
                    recent_detections = sum(list(self.detection_history)[-5:]) if len(self.detection_history) >= 5 else 5
                    if recent_detections > 3:  # 最近検出が安定していた場合のみ
                        return False, 'motion'

        return True, None

    def _create_visualization(self, frame, detection, frame_num, total_frames):
        """検出結果の可視化"""

        vis_frame = frame.copy()

        # 検出結果の描画
        if detection and detection['hands'].multi_hand_landmarks:
            for hand_landmarks in detection['hands'].multi_hand_landmarks:
                # 標準の描画
                self.mp_drawing.draw_landmarks(
                    vis_frame,
                    hand_landmarks,
                    mp.solutions.hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                    self.mp_drawing.DrawingSpec(color=(255, 255, 0), thickness=2)
                )

                # 検出方法を表示
                h, w = frame.shape[:2]
                wrist = hand_landmarks.landmark[0]
                wrist_x = int(wrist.x * w)
                wrist_y = int(wrist.y * h)

                method_text = f"[{detection['method']}]"
                cv2.putText(vis_frame, method_text,
                           (wrist_x - 30, wrist_y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

        # 情報パネル
        self._add_info_panel(vis_frame, frame_num, total_frames, detection)

        # タイムライン
        self._add_timeline(vis_frame)

        return vis_frame

    def _add_info_panel(self, frame, frame_num, total_frames, detection):
        """情報パネル"""

        # パネル背景
        panel_height = 100
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
        frame[:panel_height] = cv2.addWeighted(overlay[:panel_height], 0.7, frame[:panel_height], 0.3, 0)

        # 基本情報
        progress = (frame_num / total_frames) * 100
        cv2.putText(frame, f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出状態
        if detection:
            num_hands = len(detection['hands'].multi_hand_landmarks)
            status = f"DETECTED ({num_hands} hand{'s' if num_hands > 1 else ''})"
            color = (0, 255, 0)
            conf_text = f"Conf: {detection['confidence']:.2f}"
        else:
            status = "NO DETECTION"
            color = (0, 100, 255)
            conf_text = ""

        cv2.putText(frame, status,
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        if conf_text:
            cv2.putText(frame, conf_text,
                       (250, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # 検出率
        if frame_num > 0:
            detection_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100
            filter_rate = (self.stats['filtered_frames'] / (frame_num + 1)) * 100

            cv2.putText(frame, f"Detection: {detection_rate:.1f}%",
                       (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.putText(frame, f"Filtered: {filter_rate:.1f}%",
                       (200, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 100), 1)

        # モード表示
        cv2.putText(frame, "[BALANCED WHITE GLOVE MODE]",
                   (frame.shape[1] - 250, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

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

        cv2.putText(frame, "Detection Timeline (100 frames)",
                   (graph_x, graph_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

    def _print_final_stats(self):
        """最終統計"""

        print("\n" + "=" * 80)
        print("BALANCED DETECTION STATISTICS")
        print("=" * 80)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']
        filtered = self.stats['filtered_frames']

        detection_rate = (detected / total * 100) if total > 0 else 0
        filter_rate = (filtered / total * 100) if total > 0 else 0

        print(f"Total frames: {total}")
        print(f"Frames with detection: {detected} ({detection_rate:.1f}%)")
        print(f"Frames filtered: {filtered} ({filter_rate:.1f}%)")
        print(f"Total hands detected: {self.stats['total_hands']}")

        if filtered > 0:
            print("\nFiltering breakdown:")
            print(f"  - Face area: {self.stats['face_filtered']}")
            print(f"  - Large size: {self.stats['size_filtered']}")
            print(f"  - Sudden motion: {self.stats['motion_filtered']}")

        avg_hands = self.stats['total_hands'] / detected if detected > 0 else 0
        print(f"\nAverage hands per frame: {avg_hands:.2f}")

        print(f"\nOutput saved to: {self.output_path}")


def main():
    """メイン処理"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/White_Glove.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/White_Glove_balanced_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 80)
    print("BALANCED WHITE GLOVE DETECTION")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    generator = BalancedWhiteGloveDetector(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()