"""SAMを使った高精度器具トラッキングシステム"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
import mediapipe as mp
from collections import deque
import json
from skimage.morphology import skeletonize
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SAMのインポートを試みる
try:
    from ultralytics import SAM
    SAM_AVAILABLE = True
    logger.info("SAM is available")
except ImportError:
    SAM_AVAILABLE = False
    logger.warning("SAM not available, using fallback method")


class SAMInstrumentTracker:
    """SAMで器具を正確にセグメント・追跡"""

    def __init__(self, input_video: str, output_video: str):
        self.input_path = Path(input_video)
        self.output_path = Path(output_video)

        # MediaPipe手検出
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.5,
            model_complexity=1
        )

        self.mp_drawing = mp.solutions.drawing_utils

        # SAMモデル
        self.sam_model = None
        if SAM_AVAILABLE:
            try:
                # 軽量版SAMを使用
                self.sam_model = SAM('sam_b.pt')  # sam_b.ptは自動ダウンロード
                logger.info("SAM model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load SAM: {e}")
                self.sam_model = None

        # ランドマーク数
        self.num_landmarks = 12

        # Optical Flow設定
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

        # トラッキング状態
        self.tracking_state = {
            'left': {
                'active': False,
                'mask': None,
                'landmarks': None,
                'confidence': 0,
                'lost_frames': 0
            },
            'right': {
                'active': False,
                'mask': None,
                'landmarks': None,
                'confidence': 0,
                'lost_frames': 0
            }
        }

        # 前フレーム
        self.prev_gray = None
        self.prev_frame = None

        # 統計
        self.stats = {
            'total_frames': 0,
            'sam_detections': {'left': 0, 'right': 0},
            'optical_flow_frames': {'left': 0, 'right': 0},
            'total_tracked': {'left': 0, 'right': 0}
        }

    def detect_instrument_with_sam(self, frame, hand_landmarks, hand_label):
        """SAMで器具をセグメント"""
        if not SAM_AVAILABLE or self.sam_model is None:
            return self.fallback_detection(frame, hand_landmarks)

        h, w = frame.shape[:2]

        # 手の位置を取得
        hand_points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

        # 手の中心と主要ポイント
        hand_center_x = sum(p[0] for p in hand_points) // len(hand_points)
        hand_center_y = sum(p[1] for p in hand_points) // len(hand_points)

        # 親指と人差し指（握り部）
        thumb_tip = hand_points[4]
        index_tip = hand_points[8]
        grip_x = (thumb_tip[0] + index_tip[0]) // 2
        grip_y = (thumb_tip[1] + index_tip[1]) // 2

        # 手首から中指への方向（器具の延長方向）
        wrist = hand_points[0]
        middle_tip = hand_points[12]
        direction_x = middle_tip[0] - wrist[0]
        direction_y = middle_tip[1] - wrist[1]
        norm = np.sqrt(direction_x**2 + direction_y**2)
        if norm > 0:
            direction_x /= norm
            direction_y /= norm

        # プロンプトポイントを設定
        prompt_points = []
        prompt_labels = []

        # 1. 握り部（前景）
        prompt_points.append([grip_x, grip_y])
        prompt_labels.append(1)

        # 2. 器具の延長方向（前景）
        for dist in [50, 100, 150]:
            px = int(grip_x + direction_x * dist)
            py = int(grip_y + direction_y * dist)
            if 0 <= px < w and 0 <= py < h:
                prompt_points.append([px, py])
                prompt_labels.append(1)

        # 3. 手の中心（背景 - 手自体を除外）
        prompt_points.append([hand_center_x, hand_center_y])
        prompt_labels.append(0)

        if len(prompt_points) < 2:
            return None

        try:
            # SAMで予測
            results = self.sam_model(
                frame,
                points=prompt_points,
                labels=prompt_labels,
                verbose=False
            )

            if results and len(results) > 0:
                # 最初の結果を使用
                result = results[0]

                if hasattr(result, 'masks') and result.masks is not None:
                    masks = result.masks.data.cpu().numpy()

                    if len(masks) > 0:
                        # 最も細長いマスクを選択
                        best_mask = None
                        best_ratio = 0

                        for mask in masks:
                            # マスクを2値化
                            binary_mask = (mask > 0.5).astype(np.uint8)

                            # 輪郭を検出
                            contours, _ = cv2.findContours(
                                binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                            )

                            if contours:
                                # 最大の輪郭
                                cnt = max(contours, key=cv2.contourArea)
                                area = cv2.contourArea(cnt)

                                if area > 500:  # 最小面積
                                    # アスペクト比を計算
                                    rect = cv2.minAreaRect(cnt)
                                    width, height = rect[1]

                                    if width > 0 and height > 0:
                                        ratio = max(width, height) / min(width, height)

                                        if ratio > best_ratio and ratio > 2.5:  # 細長い
                                            best_ratio = ratio
                                            best_mask = binary_mask

                        if best_mask is not None:
                            return {
                                'mask': best_mask,
                                'confidence': min(1.0, best_ratio / 5.0)
                            }

        except Exception as e:
            logger.warning(f"SAM prediction failed: {e}")

        return None

    def fallback_detection(self, frame, hand_landmarks):
        """SAMが使えない場合のフォールバック検出"""
        h, w = frame.shape[:2]

        # 手の位置を取得
        hand_points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

        # 拡張領域
        x_coords = [p[0] for p in hand_points]
        y_coords = [p[1] for p in hand_points]

        padding = 150
        x1 = max(0, min(x_coords) - padding)
        y1 = max(0, min(y_coords) - padding)
        x2 = min(w, max(x_coords) + padding)
        y2 = min(h, max(y_coords) + padding)

        roi = frame[y1:y2, x1:x2]

        # エッジとカラー検出
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 30, 100)

        # HSVで金属検出
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower = np.array([0, 0, 100])
        upper = np.array([180, 50, 255])
        metal_mask = cv2.inRange(hsv, lower, upper)

        # 結合
        combined = cv2.bitwise_or(edges, metal_mask)

        # ノイズ除去
        kernel = np.ones((3, 3), np.uint8)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)

        # グローバルマスクに変換
        full_mask = np.zeros((h, w), dtype=np.uint8)
        full_mask[y1:y2, x1:x2] = combined

        return {'mask': full_mask, 'confidence': 0.5}

    def mask_to_landmarks(self, mask):
        """マスクからランドマークを生成"""
        if mask is None:
            return None

        # スケルトン化
        skeleton = skeletonize(mask // 255).astype(np.uint8) * 255

        # スケルトン点を取得
        points = np.column_stack(np.where(skeleton > 0))

        if len(points) < 10:
            return None

        # 点を順序付け（簡易版）
        ordered = []
        current = points[0]
        ordered.append(current)
        remaining = list(points[1:])

        while remaining and len(ordered) < 100:
            # 最近傍を探す
            min_dist = float('inf')
            min_idx = -1

            for i, p in enumerate(remaining):
                dist = np.linalg.norm(p - current)
                if dist < min_dist:
                    min_dist = dist
                    min_idx = i

            if min_idx >= 0 and min_dist < 20:
                current = remaining[min_idx]
                ordered.append(current)
                remaining.pop(min_idx)
            else:
                break

        if len(ordered) < 10:
            return None

        # 等間隔でサンプリング
        indices = np.linspace(0, len(ordered)-1, self.num_landmarks).astype(int)
        landmarks = []

        for idx in indices:
            point = ordered[idx]
            # y, x -> x, y に変換
            landmarks.append([point[1], point[0]])

        return np.array(landmarks, dtype=np.float32).reshape(-1, 1, 2)

    def track_with_optical_flow(self, prev_gray, curr_gray, prev_landmarks):
        """Optical Flowで追跡"""
        if prev_landmarks is None:
            return None, 0

        next_landmarks, status, error = cv2.calcOpticalFlowPyrLK(
            prev_gray, curr_gray, prev_landmarks, None, **self.lk_params
        )

        if next_landmarks is None:
            return None, 0

        # 有効な点の割合
        valid_ratio = np.sum(status == 1) / len(status)

        if valid_ratio < 0.3:
            return None, 0

        # 信頼度計算
        if error is not None and np.any(status == 1):
            avg_error = np.mean(error[status == 1])
            confidence = min(1.0, 10.0 / (avg_error + 1))
        else:
            confidence = valid_ratio

        return next_landmarks, confidence

    def visualize(self, frame, tracking_state):
        """可視化"""
        vis_frame = frame.copy()

        for hand_label, state in tracking_state.items():
            if not state['active']:
                continue

            color = (0, 255, 0) if hand_label == 'left' else (0, 0, 255)

            # マスクを半透明で表示
            if state['mask'] is not None:
                colored_mask = np.zeros_like(vis_frame)
                colored_mask[:, :] = color

                # マスクを3チャンネルに変換
                if len(state['mask'].shape) == 2:
                    mask_3ch = cv2.cvtColor(state['mask'], cv2.COLOR_GRAY2BGR)
                else:
                    mask_3ch = state['mask']

                # マスク領域を半透明で着色
                mask_indices = mask_3ch[:, :, 0] > 0
                overlay = vis_frame.copy()
                overlay[mask_indices] = color
                vis_frame = cv2.addWeighted(vis_frame, 0.6, overlay, 0.4, 0)

            # ランドマークを表示
            if state['landmarks'] is not None:
                points = state['landmarks'].reshape(-1, 2)

                # 線で接続
                for i in range(len(points) - 1):
                    pt1 = tuple(points[i].astype(int))
                    pt2 = tuple(points[i+1].astype(int))
                    thickness = 3 if state['confidence'] > 0.5 else 2
                    cv2.line(vis_frame, pt1, pt2, color, thickness)

                # 点を描画
                for i, pt in enumerate(points):
                    point = tuple(pt.astype(int))
                    if i == 0:  # 始点
                        cv2.circle(vis_frame, point, 6, (0, 255, 255), -1)
                    elif i == len(points) - 1:  # 終点
                        cv2.circle(vis_frame, point, 6, (255, 0, 255), -1)
                    else:
                        cv2.circle(vis_frame, point, 3, color, -1)

            # 状態表示
            status = "SAM" if state.get('sam_detected', False) else "Tracking"
            text = f"{hand_label.upper()}: {status} ({state['confidence']:.2f})"
            y_pos = 60 if hand_label == 'left' else 90
            cv2.putText(vis_frame, text,
                       (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return vis_frame

    def generate_video(self):
        """動画生成"""
        logger.info(f"Processing: {self.input_path}")
        logger.info(f"SAM-BASED INSTRUMENT TRACKING")
        logger.info(f"SAM available: {SAM_AVAILABLE}")

        cap = cv2.VideoCapture(str(self.input_path))

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video: {width}x{height} @ {fps}fps, {total_frames} frames")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(self.output_path), fourcc, fps, (width, height))

        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 手を検出
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands_result = self.mp_hands.process(rgb_frame)

            if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
                for hand_landmarks, handedness in zip(
                    hands_result.multi_hand_landmarks,
                    hands_result.multi_handedness
                ):
                    hand_label = 'left' if handedness.classification[0].label == 'Right' else 'right'
                    state = self.tracking_state[hand_label]

                    # Optical Flowでの追跡を試みる
                    tracked = False
                    if state['active'] and self.prev_gray is not None and state['landmarks'] is not None:
                        new_landmarks, confidence = self.track_with_optical_flow(
                            self.prev_gray, gray, state['landmarks']
                        )

                        if new_landmarks is not None and confidence > 0.3:
                            state['landmarks'] = new_landmarks
                            state['confidence'] = confidence
                            state['lost_frames'] = 0
                            state['sam_detected'] = False
                            tracked = True
                            self.stats['optical_flow_frames'][hand_label] += 1

                    # 追跡失敗または未初期化の場合、SAMで検出
                    if not tracked or state['lost_frames'] > 10:
                        detection = self.detect_instrument_with_sam(frame, hand_landmarks, hand_label)

                        if detection:
                            state['mask'] = detection['mask']
                            state['landmarks'] = self.mask_to_landmarks(detection['mask'])
                            state['confidence'] = detection['confidence']
                            state['active'] = True
                            state['lost_frames'] = 0
                            state['sam_detected'] = True
                            self.stats['sam_detections'][hand_label] += 1
                            logger.info(f"SAM detection for {hand_label} at frame {frame_count}")
                        else:
                            state['lost_frames'] += 1

                            if state['lost_frames'] > 30:
                                state['active'] = False

                    if state['active']:
                        self.stats['total_tracked'][hand_label] += 1

                    # 手を薄く表示
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(240, 240, 240), thickness=1, circle_radius=1),
                        self.mp_drawing.DrawingSpec(color=(240, 240, 240), thickness=1)
                    )

            # 可視化
            vis_frame = self.visualize(frame, self.tracking_state)

            # フレーム情報
            progress = (frame_count / total_frames * 100) if total_frames > 0 else 0
            info = f"Frame: {frame_count}/{total_frames} ({progress:.1f}%)"
            cv2.putText(vis_frame, info,
                       (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            out.write(vis_frame)

            self.prev_gray = gray.copy()
            self.prev_frame = frame.copy()

            frame_count += 1
            self.stats['total_frames'] = frame_count

            # 進捗
            if frame_count % max(1, total_frames // 10) == 0:
                logger.info(f"Progress: {progress:.1f}%")

        cap.release()
        out.release()
        self.mp_hands.close()

        self._print_stats()

    def _print_stats(self):
        """統計表示"""
        print("\n" + "=" * 80)
        print("SAM-BASED TRACKING COMPLETE")
        print("=" * 80)

        print(f"\nTotal frames: {self.stats['total_frames']}")

        for hand in ['left', 'right']:
            sam = self.stats['sam_detections'][hand]
            flow = self.stats['optical_flow_frames'][hand]
            total = self.stats['total_tracked'][hand]
            rate = total / max(1, self.stats['total_frames']) * 100

            print(f"\n{hand.capitalize()} hand:")
            print(f"  - SAM detections: {sam}")
            print(f"  - Optical flow: {flow}")
            print(f"  - Total tracked: {total} ({rate:.1f}%)")

        print(f"\nOutput: {self.output_path}")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_video = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")
    output_video = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/sam_tracking_{timestamp}.mp4")

    if not input_video.exists():
        logger.error(f"Input video not found: {input_video}")
        return

    output_video.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("SAM-BASED INSTRUMENT TRACKING")
    print("=" * 80)
    print(f"Input: {input_video.name}")
    print(f"Output: {output_video.name}\n")

    tracker = SAMInstrumentTracker(str(input_video), str(output_video))
    tracker.generate_video()


if __name__ == "__main__":
    main()