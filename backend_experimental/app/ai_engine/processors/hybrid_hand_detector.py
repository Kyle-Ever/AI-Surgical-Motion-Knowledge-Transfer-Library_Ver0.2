"""
Hybrid Hand Detector: YOLO + MediaPipe
YOLOで手の領域を検出し、MediaPipeで詳細な関節位置を取得
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from ultralytics import YOLO
import mediapipe as mp


class HybridHandDetector:
    """
    YOLOv8とMediaPipeを組み合わせた高精度手検出器
    - YOLO: 複数の手を確実に検出（バウンディングボックス）
    - MediaPipe: 各手の21点の詳細な関節位置を取得
    """

    def __init__(
        self,
        yolo_model_path: str = "yolov8n-pose.pt",  # YOLOv8 poseモデル（手首検出可能）
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        flip_handedness: bool = False
    ):
        """
        初期化

        Args:
            yolo_model_path: YOLOモデルのパス
            confidence_threshold: 検出信頼度の閾値
            iou_threshold: NMS (Non-Maximum Suppression) の閾値
            flip_handedness: 手の左右を反転するか（外部カメラ用）
        """
        # YOLO初期化（pose検出用）
        # PyTorch 2.6のweights_only問題を回避
        import os
        os.environ['TORCH_WEIGHTS_ONLY'] = '0'

        self.yolo = YOLO(yolo_model_path)
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.flip_handedness = flip_handedness

        # MediaPipe Hands初期化（詳細な関節検出用）
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=True,  # 各領域を独立して処理
            max_num_hands=1,         # 各切り出し領域で1つの手を検出
            min_detection_confidence=0.3,  # YOLOで領域特定済みなので低めでOK
            min_tracking_confidence=0.3
        )

        # 描画用
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def detect_hand_regions(self, image: np.ndarray) -> List[Dict]:
        """
        YOLOで手の領域を検出

        Args:
            image: 入力画像 (BGR)

        Returns:
            手の領域情報のリスト
        """
        # YOLOで姿勢検出
        results = self.yolo(image, conf=self.confidence_threshold, iou=self.iou_threshold)

        hand_regions = []

        for r in results:
            if r.keypoints is not None and r.keypoints.xy is not None:
                keypoints = r.keypoints.xy.cpu().numpy()

                # YOLOv8-poseのキーポイントインデックス
                # 9: left_wrist, 10: right_wrist
                for person_idx, person_kpts in enumerate(keypoints):
                    if len(person_kpts) > 10:
                        # 左手首（人物の左手）
                        left_wrist = person_kpts[9]
                        if left_wrist[0] > 0 and left_wrist[1] > 0:
                            left_region = self._create_hand_region_from_wrist(
                                image, left_wrist, is_left=True
                            )
                            if left_region:
                                hand_regions.append(left_region)

                        # 右手首（人物の右手）
                        right_wrist = person_kpts[10]
                        if right_wrist[0] > 0 and right_wrist[1] > 0:
                            right_region = self._create_hand_region_from_wrist(
                                image, right_wrist, is_left=False
                            )
                            if right_region:
                                hand_regions.append(right_region)

        return hand_regions

    def _create_hand_region_from_wrist(
        self,
        image: np.ndarray,
        wrist_point: np.ndarray,
        is_left: bool
    ) -> Optional[Dict]:
        """
        手首の位置から手の領域を作成

        Args:
            image: 入力画像
            wrist_point: 手首の座標 [x, y]
            is_left: 左手かどうか

        Returns:
            手の領域情報
        """
        h, w = image.shape[:2]
        wrist_x, wrist_y = int(wrist_point[0]), int(wrist_point[1])

        # 手のサイズを画像サイズから推定（約10%の幅）
        hand_size = int(min(w, h) * 0.15)

        # 手首を中心に領域を作成
        x1 = max(0, wrist_x - hand_size // 2)
        y1 = max(0, wrist_y - hand_size // 2)
        x2 = min(w, x1 + hand_size)
        y2 = min(h, y1 + hand_size)

        # 領域が有効かチェック
        if x2 <= x1 or y2 <= y1:
            return None

        return {
            "bbox": [x1, y1, x2, y2],
            "estimated_hand": "Left" if is_left else "Right",
            "confidence": 0.9,  # YOLOの検出結果に基づくので高め
            "wrist_point": [wrist_x, wrist_y]
        }


    def detect_landmarks_in_region(self, image: np.ndarray, region: Dict) -> Optional[Dict]:
        """
        指定領域内でMediaPipeを使って手の関節を検出

        Args:
            image: 入力画像 (BGR)
            region: 手の領域情報

        Returns:
            検出された手の情報
        """
        x1, y1, x2, y2 = region["bbox"]

        # 領域を切り出し
        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return None

        # BGRからRGBに変換
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)

        # MediaPipeで手を検出
        results = self.hands.process(roi_rgb)

        if not results.multi_hand_landmarks:
            return None

        # 最初の手を取得
        hand_landmarks = results.multi_hand_landmarks[0]
        handedness = results.multi_handedness[0] if results.multi_handedness else None

        # ランドマークを元画像の座標系に変換
        h_roi, w_roi = roi.shape[:2]
        landmarks = []
        for landmark in hand_landmarks.landmark:
            x = int(landmark.x * w_roi) + x1
            y = int(landmark.y * h_roi) + y1
            z = landmark.z
            landmarks.append({
                "x": x / image.shape[1],  # 正規化座標
                "y": y / image.shape[0],
                "z": z
            })

        # 手の左右を判定
        if handedness:
            raw_label = handedness.classification[0].label
            confidence = handedness.classification[0].score
        else:
            # MediaPipeで判定できない場合は推定値を使用
            raw_label = region["estimated_hand"]
            confidence = region["confidence"]

        # 外部カメラの場合は左右反転
        if self.flip_handedness:
            final_label = "Left" if raw_label == "Right" else "Right"
        else:
            final_label = raw_label

        return {
            "handedness": final_label,
            "confidence": confidence,
            "landmarks": landmarks,
            "bbox": region["bbox"]
        }

    def detect_from_frame(self, frame: np.ndarray) -> Dict:
        """
        フレームから両手を検出

        Args:
            frame: 入力フレーム (BGR)

        Returns:
            検出結果
        """
        # Step 1: YOLOで手の領域を検出
        hand_regions = self.detect_hand_regions(frame)

        # Step 2: 各領域でMediaPipeを実行
        detected_hands = []
        for region in hand_regions:
            hand_data = self.detect_landmarks_in_region(frame, region)
            if hand_data:
                detected_hands.append(hand_data)

        # 左右の手を分類
        left_hands = [h for h in detected_hands if h["handedness"] == "Left"]
        right_hands = [h for h in detected_hands if h["handedness"] == "Right"]

        # 最も信頼度の高い手を選択
        if len(left_hands) > 1:
            left_hands = [max(left_hands, key=lambda h: h["confidence"])]
        if len(right_hands) > 1:
            right_hands = [max(right_hands, key=lambda h: h["confidence"])]

        all_hands = left_hands + right_hands

        return {
            "hands": all_hands,
            "num_hands": len(all_hands),
            "has_left": len(left_hands) > 0,
            "has_right": len(right_hands) > 0,
            "frame_shape": frame.shape
        }

    def draw_landmarks(self, image: np.ndarray, detection_result: Dict) -> np.ndarray:
        """
        検出結果を画像に描画

        Args:
            image: 入力画像
            detection_result: 検出結果

        Returns:
            描画済み画像
        """
        annotated_image = image.copy()

        for hand in detection_result["hands"]:
            # バウンディングボックスを描画
            x1, y1, x2, y2 = hand["bbox"]
            color = (255, 0, 0) if hand["handedness"] == "Left" else (0, 0, 255)
            cv2.rectangle(annotated_image, (x1, y1), (x2, y2), color, 2)

            # ラベルを描画
            label = f"{hand['handedness']} ({hand['confidence']:.2f})"
            cv2.putText(
                annotated_image, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )

            # ランドマークを描画
            h, w = image.shape[:2]
            for i, landmark in enumerate(hand["landmarks"]):
                x = int(landmark["x"] * w)
                y = int(landmark["y"] * h)
                cv2.circle(annotated_image, (x, y), 3, color, -1)

                # 接続線を描画
                if i > 0:
                    prev_landmark = hand["landmarks"][i - 1]
                    prev_x = int(prev_landmark["x"] * w)
                    prev_y = int(prev_landmark["y"] * h)
                    cv2.line(annotated_image, (prev_x, prev_y), (x, y), color, 1)

        return annotated_image

    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, 'hands'):
            self.hands.close()