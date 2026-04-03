"""SAMを使用した器具の検出と追跡"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from collections import deque
import torch
from ultralytics import SAM
import mediapipe as mp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InstrumentDetectorSAM:
    """SAMで器具を検出・追跡"""

    def __init__(self, input_video_path: str, output_video_path: str):
        """初期化"""
        self.input_path = Path(input_video_path)
        self.output_path = Path(output_video_path)

        # SAMモデルをロード
        try:
            self.sam = SAM('sam_b.pt')  # SAM Base model
            logger.info("SAM model loaded successfully")
        except:
            logger.warning("SAM model not found, will use alternative detection")
            self.sam = None

        # MediaPipe Handsで手の位置を検出（器具を持っている位置の推定用）
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1
        )

        self.mp_drawing = mp.solutions.drawing_utils

        # トラッキング履歴
        self.tracked_objects = {}
        self.detection_history = deque(maxlen=100)

        # 統計
        self.stats = {
            'total_frames': 0,
            'detected_frames': 0,
            'total_instruments': 0,
            'hands_detected': 0
        }

    def generate_video(self):
        """検出結果動画を生成"""

        logger.info(f"Processing: {self.input_path}")
        logger.info("INSTRUMENT DETECTION using SAM + Hand tracking")

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
        prev_frame = None
        prev_hand_positions = []

        logger.info("Starting instrument detection...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 手の位置を検出
            hand_positions = self.detect_hands(frame)

            # 器具を検出（手の位置を元に）
            instruments = self.detect_instruments(frame, hand_positions, prev_frame, prev_hand_positions)

            # 統計更新
            if instruments:
                self.stats['detected_frames'] += 1
                self.stats['total_instruments'] += len(instruments)

            if hand_positions:
                self.stats['hands_detected'] += 1

            self.detection_history.append(1 if instruments else 0)

            # 可視化
            vis_frame = self._create_visualization(
                frame, instruments, hand_positions, frame_count, total_frames
            )

            out.write(vis_frame)

            # 次のフレームのために保存
            prev_frame = frame.copy()
            prev_hand_positions = hand_positions

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗
            if frame_count % max(1, total_frames // 10) == 0:
                progress = (frame_count / total_frames) * 100
                detection_rate = (self.stats['detected_frames'] / frame_count) * 100
                logger.info(f"Progress: {progress:.1f}% | Instrument detection: {detection_rate:.1f}%")

        cap.release()
        out.release()
        cv2.destroyAllWindows()

        logger.info("Video generation completed!")
        self._print_final_stats()

    def detect_hands(self, frame):
        """手の位置を検出"""

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.mp_hands.process(rgb_frame)

        hand_positions = []

        if result.multi_hand_landmarks:
            h, w = frame.shape[:2]

            for hand_landmarks in result.multi_hand_landmarks:
                # 手の中心と範囲を計算
                x_coords = [lm.x * w for lm in hand_landmarks.landmark]
                y_coords = [lm.y * h for lm in hand_landmarks.landmark]

                center_x = sum(x_coords) / 21
                center_y = sum(y_coords) / 21

                # 手の領域（バウンディングボックス）
                min_x = max(0, int(min(x_coords)) - 50)
                max_x = min(w, int(max(x_coords)) + 50)
                min_y = max(0, int(min(y_coords)) - 50)
                max_y = min(h, int(max(y_coords)) + 50)

                hand_positions.append({
                    'center': (int(center_x), int(center_y)),
                    'bbox': (min_x, min_y, max_x, max_y),
                    'landmarks': hand_landmarks
                })

        return hand_positions

    def detect_instruments(self, frame, hand_positions, prev_frame, prev_hand_positions):
        """器具を検出"""

        instruments = []

        # SAMが利用可能な場合
        if self.sam and hand_positions:
            try:
                # 手の周辺で器具を探す
                for hand in hand_positions:
                    x1, y1, x2, y2 = hand['bbox']

                    # プロンプトポイント（手の位置から器具の可能性がある場所）
                    prompt_points = []
                    prompt_labels = []

                    # 手の中心から周辺にポイントを配置
                    cx, cy = hand['center']

                    # 器具は通常、手から延びている
                    offsets = [
                        (0, -30), (0, 30),  # 上下
                        (-30, 0), (30, 0),  # 左右
                        (-20, -20), (20, 20),  # 斜め
                    ]

                    for dx, dy in offsets:
                        px = cx + dx
                        py = cy + dy
                        if 0 <= px < frame.shape[1] and 0 <= py < frame.shape[0]:
                            prompt_points.append([px, py])
                            prompt_labels.append(1)  # Positive prompt

                    if prompt_points:
                        # SAMで領域をセグメント化
                        results = self.sam.predict(
                            frame,
                            points=prompt_points,
                            labels=prompt_labels
                        )

                        if results and len(results) > 0:
                            for result in results:
                                if hasattr(result, 'masks') and result.masks is not None:
                                    # マスクから輪郭を抽出
                                    for mask in result.masks.data:
                                        mask_np = mask.cpu().numpy()
                                        mask_uint8 = (mask_np * 255).astype(np.uint8)

                                        contours, _ = cv2.findContours(
                                            mask_uint8,
                                            cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE
                                        )

                                        for contour in contours:
                                            area = cv2.contourArea(contour)
                                            # 適切なサイズの物体のみを器具として検出
                                            if 500 < area < 50000:
                                                instruments.append({
                                                    'contour': contour,
                                                    'area': area,
                                                    'mask': mask_np
                                                })

            except Exception as e:
                logger.debug(f"SAM detection error: {e}")

        # SAMが使えない場合の代替方法（色・形状ベース）
        if not instruments:
            instruments = self.detect_instruments_fallback(frame, hand_positions)

        return instruments

    def detect_instruments_fallback(self, frame, hand_positions):
        """代替の器具検出（色・形状ベース）"""

        instruments = []

        if not hand_positions:
            return instruments

        # グレースケール変換
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # エッジ検出
        edges = cv2.Canny(gray, 50, 150)

        for hand in hand_positions:
            x1, y1, x2, y2 = hand['bbox']

            # 手の領域を拡大して器具を含める
            x1 = max(0, x1 - 100)
            x2 = min(frame.shape[1], x2 + 100)
            y1 = max(0, y1 - 100)
            y2 = min(frame.shape[0], y2 + 100)

            # ROI内のエッジを検出
            roi_edges = edges[y1:y2, x1:x2]

            # 輪郭を検出
            contours, _ = cv2.findContours(roi_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)

                # 細長い形状（器具の特徴）を検出
                if len(contour) >= 5:
                    (cx, cy), (width, height), angle = cv2.minAreaRect(contour)

                    # アスペクト比で細長い物体を検出
                    if width > 0 and height > 0:
                        aspect_ratio = max(width, height) / min(width, height)

                        if aspect_ratio > 3 and area > 200:
                            # 元の座標系に変換
                            contour_shifted = contour + np.array([x1, y1])
                            instruments.append({
                                'contour': contour_shifted,
                                'area': area,
                                'aspect_ratio': aspect_ratio
                            })

        return instruments

    def _create_visualization(self, frame, instruments, hand_positions, frame_num, total_frames):
        """可視化"""

        vis_frame = frame.copy()

        # 手を描画
        if hand_positions:
            for hand in hand_positions:
                # 手のランドマーク
                self.mp_drawing.draw_landmarks(
                    vis_frame,
                    hand['landmarks'],
                    mp.solutions.hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                    self.mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=1)
                )

                # 手の領域
                x1, y1, x2, y2 = hand['bbox']
                cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
                cv2.putText(vis_frame, "Hand", (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # 器具を描画
        if instruments:
            for i, instrument in enumerate(instruments):
                # 輪郭を描画
                cv2.drawContours(vis_frame, [instrument['contour']], -1, (0, 255, 255), 2)

                # マスクがある場合は半透明で表示
                if 'mask' in instrument:
                    mask = instrument['mask']
                    colored_mask = np.zeros_like(vis_frame)
                    colored_mask[:, :, 1] = (mask * 128).astype(np.uint8)  # 緑色
                    vis_frame = cv2.addWeighted(vis_frame, 0.7, colored_mask, 0.3, 0)

                # ラベル
                M = cv2.moments(instrument['contour'])
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    cv2.putText(vis_frame, f"Instrument {i+1}",
                               (cx - 30, cy),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        # 情報パネル
        self._add_info_panel(vis_frame, frame_num, total_frames, instruments, hand_positions)

        # タイムライン
        self._add_timeline(vis_frame)

        return vis_frame

    def _add_info_panel(self, frame, frame_num, total_frames, instruments, hand_positions):
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
        hand_count = len(hand_positions) if hand_positions else 0
        instrument_count = len(instruments) if instruments else 0

        status_text = f"Hands: {hand_count} | Instruments: {instrument_count}"
        color = (0, 255, 0) if instrument_count > 0 else (255, 255, 0)

        cv2.putText(frame, status_text,
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # 統計
        if frame_num > 0:
            detection_rate = (self.stats['detected_frames'] / (frame_num + 1)) * 100
            hand_rate = (self.stats['hands_detected'] / (frame_num + 1)) * 100

            cv2.putText(frame, f"Instrument detection: {detection_rate:.1f}%",
                       (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            cv2.putText(frame, f"Hand tracking: {hand_rate:.1f}%",
                       (250, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # モード表示
        method = "SAM" if self.sam else "Edge Detection"
        cv2.putText(frame, f"[INSTRUMENT DETECTION - {method}]",
                   (frame.shape[1] - 280, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

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
                cv2.line(frame, (x, graph_y + graph_height), (x, graph_y), (0, 255, 255), 1)

        cv2.putText(frame, "Instrument Detection Timeline",
                   (graph_x, graph_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

    def _print_final_stats(self):
        """最終統計"""

        print("\n" + "=" * 80)
        print("INSTRUMENT DETECTION RESULTS")
        print("=" * 80)

        total = self.stats['total_frames']
        detected = self.stats['detected_frames']
        hands = self.stats['hands_detected']

        detection_rate = (detected / total * 100) if total > 0 else 0
        hand_rate = (hands / total * 100) if total > 0 else 0

        print(f"Total frames: {total}")
        print(f"Frames with instruments: {detected} ({detection_rate:.1f}%)")
        print(f"Frames with hands: {hands} ({hand_rate:.1f}%)")
        print(f"Total instruments detected: {self.stats['total_instruments']}")

        avg_instruments = self.stats['total_instruments'] / detected if detected > 0 else 0
        print(f"Average instruments per frame: {avg_instruments:.2f}")

        print(f"\nDetection method: {'SAM' if self.sam else 'Edge Detection (fallback)'}")
        print(f"Output saved to: {self.output_path}")


def main():
    """メイン処理"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/instrument_detection_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    print("\n" + "=" * 80)
    print("INSTRUMENT DETECTION WITH SAM")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}")
    print("")

    generator = InstrumentDetectorSAM(str(input_video), str(output_video))
    generator.generate_video()


if __name__ == "__main__":
    main()