"""Front_Angle.mp4の検出（背景の顔を除外）"""

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


class FrontAngleNoFaceDetector:
    """青い手袋用検出器（背景の顔を除外）"""

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

        # 複数の検出器（異なる設定）
        self.detectors = [
            # 青い手袋用 - 超低閾値
            mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.005,
                min_tracking_confidence=0.005,
                model_complexity=1
            ),
            # バックアップ検出器
            mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.01,
                min_tracking_confidence=0.01,
                model_complexity=1
            ),
            # 静止画モード
            mp.solutions.hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=0.05,
                min_tracking_confidence=0.05,
                model_complexity=1
            ),
        ]

        # Poseで顔の位置を検出
        self.mp_pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3
        )

        # FaceMeshで顔を検出（より精密）
        self.mp_face = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=3,  # 複数の顔を検出
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3
        )

        # 描画用
        self.mp_drawing = mp.solutions.drawing_utils

        # トラッキング履歴
        self.detection_history = deque(maxlen=100)
        self.last_valid_detection = None
        self.face_regions = []

        # 統計
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'face_filtered': 0,
            'total_hands': 0,
            'interpolated': 0
        }

    def generate_video(self):
        """検出結果動画を生成（顔除外付き）"""

        logger.info(f"Processing: {self.input_path}")
        logger.info("NO FACE MODE: Excluding face detections for blue gloves")

        cap = cv2.VideoCapture(str(self.input_path))

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video info: {width}x{height} @ {fps}fps, {total_frames} frames")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(self.output_path),
            fourcc,
            fps,
            (width, height)
        )

        frame_count = 0
        logger.info("Starting face-filtered detection...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 顔の領域を検出
            face_regions = self.detect_all_faces(frame)

            # 青い手袋を検出（前処理付き）
            preprocessed = self.preprocess_blue_glove(frame)
            detection_result = self.detect_hands_filtered(preprocessed, face_regions, frame.shape[:2])

            # 統計更新
            if detection_result:
                self.stats['detected_frames'] += 1
                if detection_result['hands']:
                    self.stats['total_hands'] += len(detection_result['hands'].multi_hand_landmarks)
                if detection_result.get('interpolated'):
                    self.stats['interpolated'] += 1

            self.detection_history.append(1 if detection_result else 0)

            # 可視化
            vis_frame = self._create_visualization(
                frame, detection_result, face_regions, frame_count, total_frames
            )

            out.write(vis_frame)

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                detection_rate = (self.stats['detected_frames'] / frame_count) * 100
                logger.info(f"Progress: {progress:.1f}% | Detection: {detection_rate:.1f}% | Face filtered: {self.stats['face_filtered']}")

        cap.release()
        out.release()
        cv2.destroyAllWindows()

        logger.info("Video generation completed!")
        self._print_final_stats()

    def detect_all_faces(self, frame):
        """すべての顔の領域を検出"""

        face_regions = []
        h, w = frame.shape[:2]

        # FaceMeshで顔を検出
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_result = self.mp_face.process(rgb_frame)

        if face_result.multi_face_landmarks:
            for face_landmarks in face_result.multi_face_landmarks:
                # 顔の境界ボックスを計算
                x_coords = [lm.x * w for lm in face_landmarks.landmark]
                y_coords = [lm.y * h for lm in face_landmarks.landmark]

                min_x = max(0, int(min(x_coords) - 50))
                max_x = min(w, int(max(x_coords) + 50))
                min_y = max(0, int(min(y_coords) - 50))
                max_y = min(h, int(max(y_coords) + 50))

                face_regions.append({
                    'left': min_x,
                    'right': max_x,
                    'top': min_y,
                    'bottom': max_y
                })

        # Poseでも顔を検出（バックアップ）
        pose_result = self.mp_pose.process(rgb_frame)
        if pose_result.pose_landmarks:
            # 顔のランドマーク
            nose = pose_result.pose_landmarks.landmark[0]
            if nose.visibility > 0.5:
                face_x = int(nose.x * w)
                face_y = int(nose.y * h)

                # 顔の領域（推定サイズ）
                face_size = 100
                face_regions.append({
                    'left': max(0, face_x - face_size),
                    'right': min(w, face_x + face_size),
                    'top': max(0, face_y - face_size),
                    'bottom': min(h, face_y + face_size)
                })

        return face_regions

    def preprocess_blue_glove(self, frame):
        """青い手袋用の前処理"""

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 青色の範囲（広め）
        lower_blue = np.array([50, 5, 5])
        upper_blue = np.array([160, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # ノイズ除去
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)

        # 青を肌色に変換
        hsv_copy = hsv.copy()
        hsv_copy[blue_mask > 0, 0] = 18  # 肌色
        hsv_copy[blue_mask > 0, 1] = hsv_copy[blue_mask > 0, 1] * 0.4

        result = cv2.cvtColor(hsv_copy, cv2.COLOR_HSV2BGR)

        # コントラスト強調
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        # オリジナルとブレンド
        return cv2.addWeighted(frame, 0.2, result, 0.8, 0)

    def detect_hands_filtered(self, frame, face_regions, frame_shape):
        """手を検出（顔領域を除外）"""

        best_result = None
        best_confidence = 0
        h, w = frame_shape

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 複数の検出器で試行
        for detector in self.detectors:
            try:
                result = detector.process(rgb_frame)
                if result.multi_hand_landmarks:
                    # 顔領域のフィルタリング
                    filtered_hands = []
                    filtered_handedness = []

                    for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
                        if not self.is_in_face_region(hand_landmarks, w, h, face_regions):
                            filtered_hands.append(hand_landmarks)
                            if result.multi_handedness and idx < len(result.multi_handedness):
                                filtered_handedness.append(result.multi_handedness[idx])
                        else:
                            self.stats['face_filtered'] += 1

                    if filtered_hands:
                        # フィルタリング後の結果を作成
                        result.multi_hand_landmarks = filtered_hands
                        result.multi_handedness = filtered_handedness if filtered_handedness else None

                        # 信頼度計算
                        confidence = self.calculate_confidence(result)
                        if confidence > best_confidence:
                            best_result = result
                            best_confidence = confidence
                            self.last_valid_detection = result
            except:
                continue

            if best_confidence > 0.8:
                break

        # 検出がない場合は補間
        if not best_result and self.last_valid_detection:
            return {
                'hands': self.last_valid_detection,
                'confidence': 0.3,
                'interpolated': True
            }

        if best_result:
            return {
                'hands': best_result,
                'confidence': best_confidence,
                'interpolated': False
            }

        return None

    def is_in_face_region(self, hand_landmarks, width, height, face_regions):
        """手が顔の領域内にあるかチェック"""

        # 手の中心を計算
        center_x = sum([lm.x for lm in hand_landmarks.landmark]) / 21 * width
        center_y = sum([lm.y for lm in hand_landmarks.landmark]) / 21 * height

        # 手のサイズ
        x_coords = [lm.x * width for lm in hand_landmarks.landmark]
        y_coords = [lm.y * height for lm in hand_landmarks.landmark]
        hand_width = max(x_coords) - min(x_coords)
        hand_height = max(y_coords) - min(y_coords)
        hand_size = max(hand_width, hand_height)

        # 各顔領域をチェック
        for face in face_regions:
            # 顔領域内か
            if (face['left'] <= center_x <= face['right'] and
                face['top'] <= center_y <= face['bottom']):

                # ただし、手が前面にある場合（サイズで判断）は除外しない
                face_width = face['right'] - face['left']
                if hand_size < face_width * 0.3:  # 顔より明らかに小さい場合は顔の一部
                    return True

        # 追加条件：画面最上部で大きすぎる場合
        if center_y < height * 0.15 and hand_size > min(width, height) * 0.3:
            return True

        return False

    def calculate_confidence(self, result):
        """検出の信頼度を計算"""

        if not result.multi_handedness:
            return 0.5

        scores = [h.classification[0].score for h in result.multi_handedness]
        return np.mean(scores)

    def _create_visualization(self, frame, detection, face_regions, frame_num, total_frames):
        """可視化"""

        vis_frame = frame.copy()

        # 顔領域を表示（半透明）
        overlay = vis_frame.copy()
        for face in face_regions:
            cv2.rectangle(overlay,
                         (face['left'], face['top']),
                         (face['right'], face['bottom']),
                         (255, 200, 200), 2)
            cv2.putText(overlay, "FACE",
                       (face['left'], face['top'] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 200), 1)
        vis_frame = cv2.addWeighted(vis_frame, 0.7, overlay, 0.3, 0)

        # 手の検出を描画
        if detection and detection['hands'] and detection['hands'].multi_hand_landmarks:
            for hand_landmarks in detection['hands'].multi_hand_landmarks:
                # 青い手袋用に色を調整
                self.mp_drawing.draw_landmarks(
                    vis_frame,
                    hand_landmarks,
                    mp.solutions.hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                    self.mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)
                )

            # 補間の場合は表示
            if detection.get('interpolated'):
                cv2.putText(vis_frame, "[INTERPOLATED]",
                           (10, vis_frame.shape[0] - 10),
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
        if detection and detection['hands'] and detection['hands'].multi_hand_landmarks:
            num_hands = len(detection['hands'].multi_hand_landmarks)
            status = f"DETECTED ({num_hands} hand{'s' if num_hands > 1 else ''})"
            color = (0, 255, 0)
            conf = detection.get('confidence', 0)
            conf_text = f"Conf: {conf:.2f}"
        else:
            status = "NO DETECTION"
            color = (0, 100, 255)
            conf_text = ""

        cv2.putText(frame, status,
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        if conf_text:
            cv2.putText(frame, conf_text,
                       (250, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # 検出率と顔フィルタ数
        if frame_num > 0:
            detection_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100
            cv2.putText(frame, f"Detection: {detection_rate:.1f}%",
                       (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.putText(frame, f"Face filtered: {self.stats['face_filtered']}",
                       (200, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 100), 1)

        # モード
        cv2.putText(frame, "[BLUE GLOVE + NO FACE MODE]",
                   (frame.shape[1] - 280, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

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
        print("FRONT ANGLE DETECTION STATISTICS (NO FACE)")
        print("=" * 80)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']

        detection_rate = (detected / total * 100) if total > 0 else 0

        print(f"Total frames: {total}")
        print(f"Frames with detection: {detected} ({detection_rate:.1f}%)")
        print(f"Total hands detected: {self.stats['total_hands']}")
        print(f"Face regions filtered: {self.stats['face_filtered']}")
        print(f"Interpolated frames: {self.stats['interpolated']}")

        avg_hands = self.stats['total_hands'] / detected if detected > 0 else 0
        print(f"Average hands per frame: {avg_hands:.2f}")

        print(f"\nOutput saved to: {self.output_path}")


def main():
    """メイン処理"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/Front_Angle_no_face_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 80)
    print("FRONT ANGLE DETECTION (NO FACE)")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    generator = FrontAngleNoFaceDetector(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()