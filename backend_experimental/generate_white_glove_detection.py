"""白い手袋の検出結果を可視化した動画を生成"""

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


class WhiteGloveDetectionGenerator:
    """白い手袋用の検出結果を可視化する動画生成クラス"""

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

        # 白い手袋用に最適化された検出器
        self.detectors = [
            # 超低閾値（白い手袋は検出しやすい）
            mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.01,
                min_tracking_confidence=0.01,
                model_complexity=1
            ),
            # 通常閾値
            mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.3,
                min_tracking_confidence=0.3,
                model_complexity=1
            ),
            # 静止画モード
            mp.solutions.hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=0.2,
                min_tracking_confidence=0.2,
                model_complexity=1
            ),
        ]

        # 描画用
        self.mp_drawing = mp.solutions.drawing_utils

        # トラッキング履歴
        self.detection_history = deque(maxlen=100)
        self.last_detections = deque(maxlen=5)

        # 統計情報
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'interpolated_frames': 0,
            'total_hands': 0,
            'left_hands': 0,
            'right_hands': 0,
            'max_confidence': 0,
            'min_confidence': 1.0,
            'detection_methods': {'direct': 0, 'preprocessed': 0, 'interpolated': 0}
        }

    def generate_video(self):
        """検出結果を可視化した動画を生成"""

        logger.info(f"Processing WHITE GLOVE video: {self.input_path}")
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
        logger.info("Starting white glove detection...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 白い手袋用の検出処理
            detection_result, confidence, method = self.detect_white_gloves(frame)

            # 統計情報の更新
            self._update_stats(detection_result, confidence, method)

            # 可視化
            vis_frame = self._create_visualization(
                frame, detection_result, frame_count, total_frames,
                confidence, method
            )

            # 動画に書き込み
            out.write(vis_frame)

            frame_count += 1

            # 進捗表示（10%ごと）
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                detection_rate = (self.stats['detected_frames'] / frame_count) * 100
                logger.info(f"Progress: {progress:.1f}% | Detection Rate: {detection_rate:.1f}%")

        # クリーンアップ
        cap.release()
        out.release()
        cv2.destroyAllWindows()

        self.stats['total_frames'] = frame_count

        logger.info("Video generation completed!")
        self._print_final_stats()

    def detect_white_gloves(self, frame):
        """白い手袋の検出（白は検出しやすいので前処理は最小限）"""

        best_result = None
        best_confidence = 0
        best_method = 'direct'

        # オリジナルフレームで検出を試行
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        for detector in self.detectors:
            try:
                result = detector.process(rgb_frame)
                if result.multi_hand_landmarks:
                    if result.multi_handedness:
                        conf = max([h.classification[0].score for h in result.multi_handedness])
                        if conf > best_confidence:
                            best_result = result
                            best_confidence = conf
                            best_method = 'direct'
            except:
                continue

            # 高い信頼度で検出できたら早期終了
            if best_confidence > 0.9:
                break

        # 検出できない場合は軽い前処理を試す
        if not best_result:
            preprocessed = self.preprocess_white_glove(frame)
            rgb_preprocessed = cv2.cvtColor(preprocessed, cv2.COLOR_BGR2RGB)

            result = self.detectors[0].process(rgb_preprocessed)
            if result and result.multi_hand_landmarks:
                best_result = result
                best_confidence = 0.5  # 前処理版は信頼度を下げる
                best_method = 'preprocessed'

        # それでも検出できない場合は補間
        if not best_result and len(self.last_detections) > 0:
            best_result = self.last_detections[-1]
            best_confidence = 0.3
            best_method = 'interpolated'

        # 履歴を更新
        if best_result and best_method != 'interpolated':
            self.last_detections.append(best_result)

        return best_result, best_confidence, best_method

    def preprocess_white_glove(self, frame):
        """白い手袋用の軽い前処理（コントラスト調整のみ）"""

        # コントラスト強調
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        enhanced = cv2.merge([l, a, b])
        result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        return result

    def _create_visualization(self, frame, detection_result, frame_num, total_frames, confidence, method):
        """フレームの可視化を作成"""

        vis_frame = frame.copy()

        # 検出結果の描画
        if detection_result and detection_result.multi_hand_landmarks:
            for i, (hand_landmarks, hand_handedness) in enumerate(zip(
                detection_result.multi_hand_landmarks,
                detection_result.multi_handedness if detection_result.multi_handedness else [None] * len(detection_result.multi_hand_landmarks)
            )):
                # 手の描画（白い手袋用に色を調整）
                self._draw_hand_on_white(vis_frame, hand_landmarks)

                # 手の左右を表示
                if hand_handedness:
                    label = hand_handedness.classification[0].label
                    score = hand_handedness.classification[0].score

                    h, w = frame.shape[:2]
                    x = int(hand_landmarks.landmark[0].x * w)
                    y = int(hand_landmarks.landmark[0].y * h)

                    # ラベルを表示（背景付き）
                    text = f"{label} ({score:.2f})"
                    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(vis_frame, (x - 50, y - 35), (x - 50 + tw + 10, y - 10), (0, 0, 0), -1)
                    cv2.putText(vis_frame, text, (x - 45, y - 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # 検出履歴を記録
        self.detection_history.append(1 if detection_result and detection_result.multi_hand_landmarks else 0)

        # 情報パネルを追加
        self._add_info_panel(vis_frame, frame_num, total_frames, detection_result, confidence, method)

        # 検出タイムラインを追加
        self._add_timeline(vis_frame)

        return vis_frame

    def _draw_hand_on_white(self, frame, hand_landmarks):
        """白い手袋上に手を描画（視認性を高める）"""

        h, w = frame.shape[:2]

        # 接続線を描画（濃い色で）
        for connection in self.HAND_CONNECTIONS:
            start_idx, end_idx = connection
            start = hand_landmarks.landmark[start_idx]
            end = hand_landmarks.landmark[end_idx]

            x1, y1 = int(start.x * w), int(start.y * h)
            x2, y2 = int(end.x * w), int(end.y * h)

            # 黒い外枠と赤い線で視認性を上げる
            cv2.line(frame, (x1, y1), (x2, y2), (0, 0, 0), 4)
            cv2.line(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

        # ランドマーク点を描画
        for i, landmark in enumerate(hand_landmarks.landmark):
            x, y = int(landmark.x * w), int(landmark.y * h)

            if i == 0:  # 手首
                cv2.circle(frame, (x, y), 8, (0, 0, 0), -1)
                cv2.circle(frame, (x, y), 6, (255, 0, 0), -1)
            elif i in [4, 8, 12, 16, 20]:  # 指先
                cv2.circle(frame, (x, y), 6, (0, 0, 0), -1)
                cv2.circle(frame, (x, y), 4, (0, 255, 255), -1)
            else:
                cv2.circle(frame, (x, y), 5, (0, 0, 0), -1)
                cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)

    def _add_info_panel(self, frame, frame_num, total_frames, detection_result, confidence, method):
        """情報パネルを追加"""

        # 上部に半透明パネル
        panel_height = 100
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (50, 50, 50), -1)
        frame[:panel_height] = cv2.addWeighted(overlay[:panel_height], 0.6, frame[:panel_height], 0.4, 0)

        # フレーム情報
        progress = (frame_num / total_frames) * 100
        frame_text = f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)"
        cv2.putText(frame, frame_text,
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出状態
        if detection_result and detection_result.multi_hand_landmarks:
            status_text = "DETECTED"
            status_color = (0, 255, 0)
            hands_count = len(detection_result.multi_hand_landmarks)
            hands_text = f"Hands: {hands_count}"
        else:
            status_text = "NO DETECTION"
            status_color = (0, 100, 255)
            hands_text = "Hands: 0"

        cv2.putText(frame, status_text,
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

        cv2.putText(frame, hands_text,
                   (200, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出方法と信頼度
        if confidence > 0:
            method_text = f"Method: {method}"
            cv2.putText(frame, method_text,
                       (350, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            conf_text = f"Conf: {confidence:.1%}"
            cv2.putText(frame, conf_text,
                       (500, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # 現在の検出率
        if frame_num > 0:
            current_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100
            rate_text = f"Detection Rate: {current_rate:.1f}%"
            rate_color = (0, 255, 0) if current_rate >= 90 else (255, 255, 0) if current_rate >= 70 else (0, 100, 255)
            cv2.putText(frame, rate_text,
                       (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, rate_color, 2)

        # 白い手袋インジケーター
        cv2.putText(frame, "[WHITE GLOVE MODE]",
                   (frame.shape[1] - 200, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def _add_timeline(self, frame):
        """検出履歴のタイムライン表示"""

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
                     (50, 50, 50), -1)
        frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5] = \
            cv2.addWeighted(overlay[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5],
                          0.6,
                          frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5],
                          0.4, 0)

        # グラフを描画
        for i, detected in enumerate(self.detection_history):
            x = graph_x + int(i * graph_width / len(self.detection_history))
            if detected:
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y), (0, 255, 0), 1)
            else:
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y + graph_height - 5), (0, 0, 255), 1)

        # ラベル
        cv2.putText(frame, "Detection Timeline",
                   (graph_x, graph_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

    def _update_stats(self, detection_result, confidence, method):
        """統計情報を更新"""

        if detection_result and detection_result.multi_hand_landmarks:
            self.stats['detected_frames'] += 1
            self.stats['total_hands'] += len(detection_result.multi_hand_landmarks)

            # 検出方法の統計
            self.stats['detection_methods'][method] = self.stats['detection_methods'].get(method, 0) + 1

            # 信頼度の更新
            if confidence > 0:
                self.stats['max_confidence'] = max(self.stats['max_confidence'], confidence)
                self.stats['min_confidence'] = min(self.stats['min_confidence'], confidence)

            # 手の左右をカウント
            if detection_result.multi_handedness:
                for hand in detection_result.multi_handedness:
                    if hand.classification[0].label == 'Left':
                        self.stats['left_hands'] += 1
                    else:
                        self.stats['right_hands'] += 1

            # 補間の場合
            if method == 'interpolated':
                self.stats['interpolated_frames'] += 1

    def _print_final_stats(self):
        """最終統計を表示"""

        print("\n" + "=" * 70)
        print("WHITE GLOVE DETECTION STATISTICS")
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

        if self.stats['max_confidence'] > 0:
            print(f"Confidence range: {self.stats['min_confidence']:.1%} - {self.stats['max_confidence']:.1%}")

        print("\nDetection method breakdown:")
        for method, count in self.stats['detection_methods'].items():
            percentage = (count / detected * 100) if detected > 0 else 0
            print(f"  - {method}: {count} ({percentage:.1f}%)")

        print(f"\nOutput video saved to: {self.output_path}")
        print(f"File size: {self.output_path.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    """メイン処理"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # resultsフォルダのWhite_Glove.mp4を入力として使用
    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/White_Glove.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/White_Glove_detection_{timestamp}.mp4")

    output_video.parent.mkdir(parents=True, exist_ok=True)

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 70)
    print("WHITE GLOVE DETECTION VIDEO GENERATION")
    print("=" * 70)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    generator = WhiteGloveDetectionGenerator(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()