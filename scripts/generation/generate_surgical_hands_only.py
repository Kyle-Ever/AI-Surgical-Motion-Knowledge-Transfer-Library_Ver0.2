"""手術手技分析専用 - 顔領域を完全除外した手検出"""

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


class SurgicalHandsOnlyDetector:
    """手術手技分析専用の手検出器（顔を完全除外）"""

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

        # 手術領域の設定（画面の何%を使用するか）
        self.roi_config = {
            'top_exclude': 0.20,     # 上部20%を除外（顔がある領域）
            'bottom_exclude': 0.05,  # 下部5%を除外
            'left_exclude': 0.0,     # 左は除外しない
            'right_exclude': 0.0     # 右は除外しない
        }

        # 複数の検出器
        self.detectors = [
            # 青い手袋用 - 超低閾値
            mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.01,
                min_tracking_confidence=0.01,
                model_complexity=1
            ),
            # 通常検出
            mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.1,
                min_tracking_confidence=0.1,
                model_complexity=1
            )
        ]

        # 描画用
        self.mp_drawing = mp.solutions.drawing_utils

        # トラッキング履歴
        self.detection_history = deque(maxlen=100)
        self.position_history = deque(maxlen=20)
        self.last_valid_detection = None
        self.frames_since_detection = 0

        # 統計
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'roi_filtered': 0,
            'position_filtered': 0,
            'shape_filtered': 0,
            'total_hands': 0
        }

    def generate_video(self):
        """手術手技検出動画を生成"""

        logger.info(f"Processing: {self.input_path}")
        logger.info("SURGICAL HANDS ONLY MODE - Face regions completely excluded")

        cap = cv2.VideoCapture(str(self.input_path))

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # ROI（関心領域）の計算
        self.roi = {
            'top': int(height * self.roi_config['top_exclude']),
            'bottom': int(height * (1 - self.roi_config['bottom_exclude'])),
            'left': int(width * self.roi_config['left_exclude']),
            'right': int(width * (1 - self.roi_config['right_exclude']))
        }

        logger.info(f"Video: {width}x{height} @ {fps}fps")
        logger.info(f"ROI: Y={self.roi['top']}-{self.roi['bottom']}, X={self.roi['left']}-{self.roi['right']}")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(self.output_path),
            fourcc,
            fps,
            (width, height)
        )

        frame_count = 0
        logger.info("Starting surgical hands detection...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 前処理（青い手袋対応）
            preprocessed = self.preprocess_frame(frame)

            # ROI内のみで手を検出
            detection_result = self.detect_surgical_hands(preprocessed, width, height)

            # 統計更新
            if detection_result:
                self.stats['detected_frames'] += 1
                if detection_result['hands']:
                    self.stats['total_hands'] += len(detection_result['hands'])

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
                roi_filtered = self.stats['roi_filtered']
                logger.info(f"Progress: {progress:.1f}% | Detection: {detection_rate:.1f}% | ROI filtered: {roi_filtered}")

        cap.release()
        out.release()
        cv2.destroyAllWindows()

        logger.info("Video generation completed!")
        self._print_final_stats()

    def preprocess_frame(self, frame):
        """青い手袋用の前処理"""

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 青色の範囲
        lower_blue = np.array([60, 10, 10])
        upper_blue = np.array([150, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # ノイズ除去
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)

        # 青を肌色に変換
        hsv_copy = hsv.copy()
        hsv_copy[blue_mask > 0, 0] = 18  # 肌色
        hsv_copy[blue_mask > 0, 1] = hsv_copy[blue_mask > 0, 1] * 0.3

        result = cv2.cvtColor(hsv_copy, cv2.COLOR_HSV2BGR)

        # コントラスト強調
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        return cv2.addWeighted(frame, 0.2, result, 0.8, 0)

    def detect_surgical_hands(self, frame, width, height):
        """手術領域内の手のみを検出"""

        best_hands = []
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        for detector in self.detectors:
            try:
                result = detector.process(rgb_frame)

                if result.multi_hand_landmarks:
                    for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
                        # 手の位置を確認
                        is_valid, reason = self.validate_surgical_hand(
                            hand_landmarks, width, height
                        )

                        if is_valid:
                            # 手の情報を保存
                            hand_info = {
                                'landmarks': hand_landmarks,
                                'handedness': result.multi_handedness[idx] if result.multi_handedness and idx < len(result.multi_handedness) else None
                            }
                            best_hands.append(hand_info)
                        else:
                            # フィルタリング理由を記録
                            if reason == 'roi':
                                self.stats['roi_filtered'] += 1
                            elif reason == 'position':
                                self.stats['position_filtered'] += 1
                            elif reason == 'shape':
                                self.stats['shape_filtered'] += 1
            except:
                continue

            # 良い結果が得られたら終了
            if len(best_hands) >= 2:
                break

        # 検出結果がない場合、短時間の補間
        if not best_hands and self.last_valid_detection and self.frames_since_detection < 3:
            self.frames_since_detection += 1
            return self.last_valid_detection

        if best_hands:
            self.frames_since_detection = 0
            detection_result = {
                'hands': best_hands,
                'count': len(best_hands)
            }
            self.last_valid_detection = detection_result
            return detection_result

        self.frames_since_detection += 1
        return None

    def validate_surgical_hand(self, hand_landmarks, width, height):
        """手術手技として妥当な手かを検証"""

        # 手の中心位置を計算
        center_x = sum([lm.x for lm in hand_landmarks.landmark]) / 21 * width
        center_y = sum([lm.y for lm in hand_landmarks.landmark]) / 21 * height

        # 手のサイズを計算
        x_coords = [lm.x * width for lm in hand_landmarks.landmark]
        y_coords = [lm.y * height for lm in hand_landmarks.landmark]
        hand_width = max(x_coords) - min(x_coords)
        hand_height = max(y_coords) - min(y_coords)
        hand_size = max(hand_width, hand_height)

        # 1. ROI（手術領域）チェック - これが最も重要
        if center_y < self.roi['top'] or center_y > self.roi['bottom']:
            return False, 'roi'

        if center_x < self.roi['left'] or center_x > self.roi['right']:
            return False, 'roi'

        # 2. 手のサイズチェック（手術手技では手は適度なサイズ）
        # 小さすぎる（ノイズ）または大きすぎる（顔）を除外
        min_size = min(width, height) * 0.03  # 画面の3%以上（小さめも許可）
        max_size = min(width, height) * 0.45  # 画面の45%以下（手が近くても許可）

        if hand_size < min_size or hand_size > max_size:
            return False, 'shape'

        # 3. 手の形状チェック
        aspect_ratio = hand_height / hand_width if hand_width > 0 else 0
        if aspect_ratio < 0.3 or aspect_ratio > 3.0:  # より緩い制限
            return False, 'shape'

        # 4. 手首の位置チェック（手首が画面最上部にある場合のみ顔の可能性）
        wrist = hand_landmarks.landmark[0]
        wrist_y = wrist.y * height

        # 画面の上10%にあり、かつ大きい場合のみ顔として除外
        if wrist_y < height * 0.1 and hand_size > min(width, height) * 0.3:
            return False, 'position'

        # 5. 指先の配置チェック
        # 少なくとも一部の指先がROI内にあること
        fingertips = [4, 8, 12, 16, 20]  # 各指の先端
        tips_in_roi = 0

        for tip_idx in fingertips:
            tip = hand_landmarks.landmark[tip_idx]
            tip_y = tip.y * height
            if self.roi['top'] <= tip_y <= self.roi['bottom']:
                tips_in_roi += 1

        if tips_in_roi < 2:  # 少なくとも2つの指先がROI内にあるべき
            return False, 'position'

        # 位置履歴に追加（動きの追跡用）
        self.position_history.append((center_x, center_y))

        return True, None

    def _create_visualization(self, frame, detection, frame_num, total_frames):
        """可視化（ROI表示付き）"""

        vis_frame = frame.copy()

        # ROI（手術領域）を表示
        # 上部の除外領域を暗く
        overlay = vis_frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], self.roi['top']), (0, 0, 0), -1)
        vis_frame[:self.roi['top']] = cv2.addWeighted(
            vis_frame[:self.roi['top']], 0.3, overlay[:self.roi['top']], 0.7, 0
        )

        # ROI境界線を描画
        cv2.line(vis_frame, (0, self.roi['top']), (frame.shape[1], self.roi['top']), (0, 255, 255), 2)
        cv2.putText(vis_frame, "SURGICAL AREA",
                   (10, self.roi['top'] + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.putText(vis_frame, "EXCLUDED (FACE AREA)",
                   (10, self.roi['top'] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 1)

        # 手の検出を描画
        if detection and detection['hands']:
            for hand_info in detection['hands']:
                hand_landmarks = hand_info['landmarks']

                # 手を描画
                self.mp_drawing.draw_landmarks(
                    vis_frame,
                    hand_landmarks,
                    mp.solutions.hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                    self.mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)
                )

                # 手の左右を表示
                if hand_info['handedness']:
                    label = hand_info['handedness'].classification[0].label
                    score = hand_info['handedness'].classification[0].score

                    h, w = frame.shape[:2]
                    wrist = hand_landmarks.landmark[0]
                    wrist_x = int(wrist.x * w)
                    wrist_y = int(wrist.y * h)

                    text = f"{label} ({score:.2f})"
                    cv2.putText(vis_frame, text,
                               (wrist_x - 30, wrist_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # 情報パネル
        self._add_info_panel(vis_frame, frame_num, total_frames, detection)

        # タイムライン
        self._add_timeline(vis_frame)

        return vis_frame

    def _add_info_panel(self, frame, frame_num, total_frames, detection):
        """情報パネル"""

        panel_height = 100
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
        frame[:panel_height] = cv2.addWeighted(overlay[:panel_height], 0.7, frame[:panel_height], 0.3, 0)

        # 基本情報
        progress = (frame_num / total_frames) * 100
        cv2.putText(frame, f"Frame: {frame_num}/{total_frames} ({progress:.1f}%)",
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # 検出状態
        if detection and detection['hands']:
            num_hands = detection['count']
            status = f"DETECTED ({num_hands} hand{'s' if num_hands > 1 else ''})"
            color = (0, 255, 0)
        else:
            status = "NO DETECTION"
            color = (0, 100, 255)

        cv2.putText(frame, status,
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # 統計
        if frame_num > 0:
            detection_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100
            cv2.putText(frame, f"Detection: {detection_rate:.1f}%",
                       (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.putText(frame, f"ROI filtered: {self.stats['roi_filtered']}",
                       (200, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 100), 1)

        # モード
        cv2.putText(frame, "[SURGICAL HANDS ONLY]",
                   (frame.shape[1] - 220, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    def _add_timeline(self, frame):
        """検出タイムライン"""

        if len(self.detection_history) < 2:
            return

        graph_x = frame.shape[1] - 220
        graph_y = frame.shape[0] - 70
        graph_width = 200
        graph_height = 50

        overlay = frame.copy()
        cv2.rectangle(overlay,
                     (graph_x - 5, graph_y - 5),
                     (graph_x + graph_width + 5, graph_y + graph_height + 5),
                     (0, 0, 0), -1)
        frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5] = \
            cv2.addWeighted(overlay[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5],
                          0.7, frame[graph_y-5:graph_y+graph_height+5, graph_x-5:graph_x+graph_width+5], 0.3, 0)

        for i, detected in enumerate(self.detection_history):
            x = graph_x + int(i * graph_width / len(self.detection_history))
            if detected:
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y), (0, 255, 0), 1)

        cv2.putText(frame, "Detection History",
                   (graph_x, graph_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

    def _print_final_stats(self):
        """最終統計"""

        print("\n" + "=" * 80)
        print("SURGICAL HANDS DETECTION STATISTICS")
        print("=" * 80)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']

        detection_rate = (detected / total * 100) if total > 0 else 0

        print(f"Total frames: {total}")
        print(f"Frames with detection: {detected} ({detection_rate:.1f}%)")
        print(f"Total hands detected: {self.stats['total_hands']}")

        print("\nFiltering statistics:")
        print(f"  - ROI filtered (outside surgical area): {self.stats['roi_filtered']}")
        print(f"  - Position filtered: {self.stats['position_filtered']}")
        print(f"  - Shape filtered: {self.stats['shape_filtered']}")

        total_filtered = (self.stats['roi_filtered'] +
                         self.stats['position_filtered'] +
                         self.stats['shape_filtered'])
        print(f"  - Total filtered: {total_filtered}")

        avg_hands = self.stats['total_hands'] / detected if detected > 0 else 0
        print(f"\nAverage hands per frame: {avg_hands:.2f}")

        print(f"\nROI configuration:")
        print(f"  - Top {self.roi_config['top_exclude']*100:.0f}% excluded (face area)")
        print(f"  - Surgical area: Middle {(1-self.roi_config['top_exclude']-self.roi_config['bottom_exclude'])*100:.0f}%")

        print(f"\nOutput saved to: {self.output_path}")


def main():
    """メイン処理"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/Front_Angle_surgical_only_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 80)
    print("SURGICAL HANDS ONLY DETECTION")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    generator = SurgicalHandsOnlyDetector(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()