"""究極の強化版検出結果を可視化した動画を生成（全フレーム処理）"""

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


class UltraEnhancedVideoGenerator:
    """究極の検出精度を実現する動画生成クラス"""

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

        # 複数の検出器を準備（異なる設定）
        self.detectors = [
            # 超低閾値
            mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.005,  # 極限の低閾値
                min_tracking_confidence=0.005,
                model_complexity=1
            ),
            # 低閾値
            mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.01,
                min_tracking_confidence=0.01,
                model_complexity=1
            ),
            # 静止画モード低閾値
            mp.solutions.hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=0.03,
                min_tracking_confidence=0.03,
                model_complexity=1
            ),
            # 静止画モード中閾値
            mp.solutions.hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=0.1,
                min_tracking_confidence=0.1,
                model_complexity=1
            ),
        ]

        # 描画用
        self.mp_drawing = mp.solutions.drawing_utils

        # トラッキング履歴
        self.detection_history = deque(maxlen=100)
        self.last_detections = deque(maxlen=10)  # 過去10フレームの検出結果を保持
        self.tracking_points = {}  # トラッキング用ポイント

        # 統計情報
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'interpolated_frames': 0,
            'total_hands': 0,
            'max_confidence': 0,
            'min_confidence': 1.0
        }

    def generate_video(self):
        """検出結果を可視化した動画を生成"""

        logger.info(f"Processing: {self.input_path}")
        logger.info("Using ULTRA enhanced detection with multiple strategies")

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
        consecutive_failures = 0

        logger.info("Starting ULTRA enhanced video generation...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 究極の検出処理
            detection_result, confidence = self.detect_hands_ultra(frame)

            # 検出失敗時の補間
            if not detection_result:
                detection_result = self.interpolate_detection()
                if detection_result:
                    self.stats['interpolated_frames'] += 1

            # 統計情報の更新
            if detection_result:
                self.stats['detected_frames'] += 1
                consecutive_failures = 0
                if confidence:
                    self.stats['max_confidence'] = max(self.stats['max_confidence'], confidence)
                    self.stats['min_confidence'] = min(self.stats['min_confidence'], confidence)
            else:
                consecutive_failures += 1

            # 検出履歴を更新
            self.detection_history.append(1 if detection_result else 0)
            if detection_result:
                self.last_detections.append(detection_result)

            # 可視化
            vis_frame = self._create_ultra_visualization(
                frame, detection_result, frame_count, total_frames,
                confidence, consecutive_failures
            )

            # 動画に書き込み
            out.write(vis_frame)

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗表示（5%ごと）
            if frame_count % max(1, total_frames // 20) == 0:
                progress = (frame_count / total_frames) * 100
                detection_rate = (self.stats['detected_frames'] / frame_count) * 100
                logger.info(f"Progress: {progress:.1f}% | Detection: {detection_rate:.1f}% | Consecutive fails: {consecutive_failures}")

        # クリーンアップ
        cap.release()
        out.release()
        cv2.destroyAllWindows()

        logger.info("Video generation completed!")
        self._print_ultra_stats()

    def detect_hands_ultra(self, frame):
        """究極の手検出（全戦略を投入）"""

        best_result = None
        best_confidence = 0

        # 複数の前処理バージョンを生成
        preprocessed_versions = [
            frame,  # オリジナル
            self.preprocess_blue_to_skin(frame),  # 青→肌色
            self.preprocess_contrast(frame),  # コントラスト強調
            self.preprocess_combined(frame),  # 組み合わせ
        ]

        # 各検出器と各前処理バージョンで試行
        for preprocessed in preprocessed_versions:
            rgb_frame = cv2.cvtColor(preprocessed, cv2.COLOR_BGR2RGB)

            for detector in self.detectors:
                try:
                    result = detector.process(rgb_frame)
                    if result.multi_hand_landmarks:
                        # 信頼度を計算
                        if result.multi_handedness:
                            conf = max([h.classification[0].score for h in result.multi_handedness])
                            if conf > best_confidence:
                                best_result = result
                                best_confidence = conf
                except:
                    continue

                # 良い結果が得られたら早期終了
                if best_confidence > 0.8:
                    return best_result, best_confidence

        return best_result, best_confidence if best_result else 0

    def preprocess_blue_to_skin(self, frame):
        """青を肌色に変換（最適化版）"""

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 広い青色範囲
        lower_blue = np.array([50, 5, 5])
        upper_blue = np.array([160, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # ノイズ除去とスムージング
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        # 肌色に変換
        hsv_copy = hsv.copy()
        hsv_copy[blue_mask > 0, 0] = 18  # 肌色の色相
        hsv_copy[blue_mask > 0, 1] = hsv_copy[blue_mask > 0, 1] * 0.4
        hsv_copy[blue_mask > 0, 2] = np.minimum(hsv_copy[blue_mask > 0, 2] * 1.1, 255)

        result = cv2.cvtColor(hsv_copy, cv2.COLOR_HSV2BGR)
        return cv2.addWeighted(frame, 0.2, result, 0.8, 0)

    def preprocess_contrast(self, frame):
        """コントラストを強調"""

        # CLAHE適用
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def preprocess_combined(self, frame):
        """全ての前処理を組み合わせ"""

        # まず青を肌色に
        result = self.preprocess_blue_to_skin(frame)

        # その後コントラスト強調
        result = self.preprocess_contrast(result)

        # シャープネス
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(result, -1, kernel)

        return cv2.addWeighted(result, 0.7, sharpened, 0.3, 0)

    def interpolate_detection(self):
        """過去の検出結果から補間"""

        if len(self.last_detections) > 0:
            # 最新の検出結果を使用
            return self.last_detections[-1]
        return None

    def _create_ultra_visualization(self, frame, detection_result, frame_num, total_frames, confidence, consecutive_failures):
        """究極の可視化"""

        vis_frame = frame.copy()

        # 検出結果の描画
        if detection_result and detection_result.multi_hand_landmarks:
            for hand_landmarks in detection_result.multi_hand_landmarks:
                # カスタム描画（より鮮明に）
                self._draw_hand_ultra(vis_frame, hand_landmarks)

        # 強化版情報パネル
        self._add_ultra_info_panel(vis_frame, frame_num, total_frames, detection_result, confidence, consecutive_failures)

        # 検出タイムライン
        self._add_ultra_timeline(vis_frame)

        return vis_frame

    def _draw_hand_ultra(self, frame, hand_landmarks):
        """手の描画（究極版）"""

        h, w = frame.shape[:2]

        # 接続線を描画
        for connection in self.HAND_CONNECTIONS:
            start_idx, end_idx = connection
            start = hand_landmarks.landmark[start_idx]
            end = hand_landmarks.landmark[end_idx]

            x1, y1 = int(start.x * w), int(start.y * h)
            x2, y2 = int(end.x * w), int(end.y * h)

            # グラデーション効果
            cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 255), 3)
            cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # ランドマーク点を描画
        for i, landmark in enumerate(hand_landmarks.landmark):
            x, y = int(landmark.x * w), int(landmark.y * h)

            # 重要な点は大きく
            if i == 0:  # 手首
                cv2.circle(frame, (x, y), 8, (255, 255, 255), -1)
                cv2.circle(frame, (x, y), 9, (0, 0, 0), 2)
            elif i in [4, 8, 12, 16, 20]:  # 指先
                cv2.circle(frame, (x, y), 6, (0, 255, 255), -1)
                cv2.circle(frame, (x, y), 7, (0, 0, 0), 1)
            else:
                cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)
                cv2.circle(frame, (x, y), 5, (0, 0, 0), 1)

    def _add_ultra_info_panel(self, frame, frame_num, total_frames, detection_result, confidence, consecutive_failures):
        """究極の情報パネル"""

        # パネル背景
        panel_height = 120
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
        frame[:panel_height] = cv2.addWeighted(overlay[:panel_height], 0.7, frame[:panel_height], 0.3, 0)

        # 基本情報
        progress = (frame_num / total_frames) * 100
        detection_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100 if frame_num > 0 else 0

        cv2.putText(frame, f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出状態
        if detection_result and detection_result.multi_hand_landmarks:
            status = "DETECTED"
            color = (0, 255, 0)
            hands_count = len(detection_result.multi_hand_landmarks)
        else:
            status = "NO DETECTION"
            color = (0, 100, 255)
            hands_count = 0

        cv2.putText(frame, status, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(frame, f"Hands: {hands_count}", (200, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 信頼度
        if confidence > 0:
            cv2.putText(frame, f"Confidence: {confidence:.2%}",
                       (350, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)

        # 検出率
        rate_color = (0, 255, 0) if detection_rate >= 80 else (255, 255, 0) if detection_rate >= 60 else (0, 100, 255)
        cv2.putText(frame, f"Detection Rate: {detection_rate:.1f}%",
                   (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, rate_color, 2)

        # 補間率
        if self.stats['detected_frames'] > 0:
            interp_rate = (self.stats['interpolated_frames'] / self.stats['detected_frames']) * 100
            cv2.putText(frame, f"Interpolation: {interp_rate:.1f}%",
                       (250, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)

        # 連続失敗カウント
        if consecutive_failures > 0:
            cv2.putText(frame, f"Consecutive fails: {consecutive_failures}",
                       (450, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 100), 1)

        # パフォーマンス指標
        cv2.putText(frame, "ULTRA Enhanced Detection Active",
                   (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    def _add_ultra_timeline(self, frame):
        """究極のタイムライン表示"""

        if len(self.detection_history) < 2:
            return

        # グラフ領域
        graph_x = frame.shape[1] - 250
        graph_y = frame.shape[0] - 80
        graph_width = 230
        graph_height = 60

        # 背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (graph_x - 5, graph_y - 5),
                     (graph_x + graph_width + 5, graph_y + graph_height + 5),
                     (0, 0, 0), -1)
        frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5] = \
            cv2.addWeighted(overlay[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5],
                          0.8, frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5], 0.2, 0)

        # グラフ描画（バー形式）
        for i, detected in enumerate(self.detection_history):
            x = graph_x + int(i * graph_width / len(self.detection_history))
            if detected:
                # 検出成功は緑のバー
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y), (0, 255, 0), 2)
            else:
                # 検出失敗は赤の短いバー
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y + graph_height - 10), (0, 0, 255), 2)

        # ラベル
        cv2.putText(frame, "Detection History (100 frames)",
                   (graph_x, graph_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    def _print_ultra_stats(self):
        """究極の統計表示"""

        print("\n" + "=" * 80)
        print("ULTRA ENHANCED DETECTION STATISTICS")
        print("=" * 80)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']
        interpolated = self.stats['interpolated_frames']

        if total > 0:
            detection_rate = (detected / total) * 100
            direct_detection = detected - interpolated
            direct_rate = (direct_detection / total) * 100
            interp_rate = (interpolated / total) * 100
        else:
            detection_rate = direct_rate = interp_rate = 0

        print(f"Total frames processed: {total}")
        print(f"Total detection rate: {detection_rate:.1f}%")
        print(f"  - Direct detection: {direct_rate:.1f}%")
        print(f"  - With interpolation: {interp_rate:.1f}%")

        if self.stats['max_confidence'] > 0:
            print(f"Confidence range: {self.stats['min_confidence']:.2%} - {self.stats['max_confidence']:.2%}")

        print(f"\nOutput video saved to: {self.output_path}")
        print(f"File size: {self.output_path.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    """メイン処理"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 動画パスを引数から取得（デフォルトはFront_Angle.mp4）
    import sys
    if len(sys.argv) > 1:
        video_name = sys.argv[1]
    else:
        video_name = "Front_Angle.mp4"

    input_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/{video_name}")
    output_name = video_name.replace('.mp4', f'_ultra_{timestamp}.mp4')
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/{output_name}")

    output_video.parent.mkdir(parents=True, exist_ok=True)

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 80)
    print("ULTRA ENHANCED DETECTION VIDEO GENERATION")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    generator = UltraEnhancedVideoGenerator(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()