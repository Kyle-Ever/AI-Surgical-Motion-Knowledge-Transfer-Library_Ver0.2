"""
手袋着用時の手検出モジュール
YOLOv8を使用して手袋を着用した手を検出し、MediaPipeで詳細なランドマークを推定
"""

import cv2
import numpy as np
import mediapipe as mp
from ultralytics import YOLO
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class GloveHandDetector:
    """手袋着用時の手検出クラス"""

    FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']

    FINGER_LANDMARK_IDS = {
        'thumb': [1, 2, 3, 4],
        'index': [5, 6, 7, 8],
        'middle': [9, 10, 11, 12],
        'ring': [13, 14, 15, 16],
        'pinky': [17, 18, 19, 20]
    }

    def __init__(self,
                 yolo_model_path: str = "yolov8n.pt",
                 use_color_enhancement: bool = True,
                 min_hand_confidence: float = 0.3):
        """
        初期化

        Args:
            yolo_model_path: YOLOモデルのパス
            use_color_enhancement: 色補正を使用するか
            min_hand_confidence: 手検出の最小信頼度
        """
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.use_color_enhancement = use_color_enhancement
        self.min_hand_confidence = min_hand_confidence

        # YOLOモデルの初期化
        model_path = Path(yolo_model_path)
        if not model_path.exists():
            logger.warning(f"YOLO model not found at {yolo_model_path}, downloading...")
            self.yolo = YOLO(yolo_model_path)
        else:
            self.yolo = YOLO(str(model_path))

        # MediaPipeハンドトラッカー（フォールバック用）
        self.hands = self.mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=2,
            min_detection_confidence=0.1,  # 非常に低い閾値
            min_tracking_confidence=0.1
        )

        logger.info("GloveHandDetector initialized with YOLO and MediaPipe")

    def detect_from_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        フレームから手袋を着用した手を検出

        Args:
            frame: 入力画像フレーム (BGR)

        Returns:
            検出結果の辞書
        """
        detection_result = {
            "hands": [],
            "frame_shape": frame.shape[:2],
            "detection_method": "none"
        }

        # 1. 前処理：色補正で手袋を強調
        if self.use_color_enhancement:
            enhanced_frame = self._enhance_glove_colors(frame)
        else:
            enhanced_frame = frame

        # 2. YOLOで人物検出し、手の位置を推定
        hand_regions = self._detect_hand_regions_yolo(frame)

        if hand_regions:
            detection_result["detection_method"] = "yolo"

            # 3. 各手領域でMediaPipeを試みる
            for i, region in enumerate(hand_regions):
                x1, y1, x2, y2 = region
                hand_roi = enhanced_frame[y1:y2, x1:x2]

                # ROIが小さすぎる場合はスキップ
                if hand_roi.shape[0] < 50 or hand_roi.shape[1] < 50:
                    continue

                # 色変換してMediaPipeで処理
                processed_roi = self._preprocess_for_mediapipe(hand_roi)
                rgb_roi = cv2.cvtColor(processed_roi, cv2.COLOR_BGR2RGB)

                results = self.hands.process(rgb_roi)

                if results.multi_hand_landmarks:
                    for hand_landmarks, hand_info in zip(
                        results.multi_hand_landmarks,
                        results.multi_handedness
                    ):
                        # 座標を元画像の座標系に変換
                        hand_data = self._process_hand_landmarks_roi(
                            hand_landmarks, hand_info,
                            region, frame.shape, i
                        )
                        detection_result["hands"].append(hand_data)
                else:
                    # MediaPipeで検出できない場合、領域情報だけ追加
                    hand_data = self._create_approximate_hand_data(region, frame.shape, i)
                    detection_result["hands"].append(hand_data)

        # 4. フォールバック：全体画像で色変換後MediaPipe
        if not detection_result["hands"]:
            detection_result = self._fallback_mediapipe_detection(enhanced_frame)
            if detection_result["hands"]:
                detection_result["detection_method"] = "mediapipe_enhanced"

        return detection_result

    def _enhance_glove_colors(self, frame: np.ndarray) -> np.ndarray:
        """手袋の色を強調する前処理"""
        # HSV色空間で青い手袋を検出・強調
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 青い手袋の色範囲（拡張版）
        # より広範囲の青色をカバー
        lower_blue = np.array([70, 30, 30])   # より明るい青も検出
        upper_blue = np.array([140, 255, 255]) # より広い範囲

        # マスクを作成
        mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # モルフォロジー処理でノイズ除去
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 色を肌色に近づける変換
        result = frame.copy()
        result[mask > 0] = self._blue_to_skin_color(frame[mask > 0])

        return result

    def _blue_to_skin_color(self, blue_pixels: np.ndarray) -> np.ndarray:
        """青色ピクセルを肌色に変換（明度保持版）"""
        # 元の明度を計算
        original_brightness = np.mean(blue_pixels, axis=-1, keepdims=True)

        # 肌色のベース値（BGR）
        skin_base = np.array([180, 150, 120], dtype=np.float32)

        # 明度に応じて肌色を調整
        brightness_factor = original_brightness / 255.0
        skin_color = skin_base * brightness_factor

        # さらに自然な変換のため、元の色の一部を残す
        result = blue_pixels * 0.2 + skin_color * 0.8

        return np.clip(result, 0, 255).astype(np.uint8)

    def _detect_hand_regions_yolo(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """YOLOで人物を検出し、手の領域を推定"""
        results = self.yolo(frame, verbose=False)
        hand_regions = []

        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    # 人物クラス（class_id = 0）のみ
                    if int(box.cls) == 0 and float(box.conf) > 0.3:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])

                        # 人物のバウンディングボックスから手の領域を推定
                        person_height = y2 - y1
                        person_width = x2 - x1

                        # 手の推定領域（人物の上半身の両側）
                        # 左手領域
                        left_hand = (
                            max(0, x1 - person_width // 4),
                            y1 + person_height // 3,
                            x1 + person_width // 3,
                            min(frame.shape[0], y1 + 2 * person_height // 3)
                        )

                        # 右手領域
                        right_hand = (
                            x2 - person_width // 3,
                            y1 + person_height // 3,
                            min(frame.shape[1], x2 + person_width // 4),
                            min(frame.shape[0], y1 + 2 * person_height // 3)
                        )

                        hand_regions.extend([left_hand, right_hand])

        return hand_regions

    def _preprocess_for_mediapipe(self, roi: np.ndarray) -> np.ndarray:
        """MediaPipe用にROIを前処理"""
        # コントラスト調整
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # CLAHE適用
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        return enhanced

    def _process_hand_landmarks_roi(self,
                                    hand_landmarks,
                                    hand_info,
                                    roi_bbox: Tuple[int, int, int, int],
                                    frame_shape: Tuple[int, int, int],
                                    hand_idx: int) -> Dict[str, Any]:
        """ROI内のランドマークを元画像座標に変換"""
        x1, y1, x2, y2 = roi_bbox
        roi_width = x2 - x1
        roi_height = y2 - y1

        landmarks_list = []
        for landmark in hand_landmarks.landmark:
            # ROI内の座標から元画像の座標に変換
            x = landmark.x * roi_width + x1
            y = landmark.y * roi_height + y1
            landmarks_list.append({
                "x": x,
                "y": y,
                "z": landmark.z,
                "visibility": landmark.visibility
            })

        finger_angles = self._calculate_finger_angles(landmarks_list)
        palm_center = self._calculate_palm_center(landmarks_list)
        hand_openness = self._calculate_hand_openness(finger_angles)

        return {
            "hand_id": hand_idx,
            "label": hand_info.classification[0].label,
            "handedness": hand_info.classification[0].label,
            "confidence": hand_info.classification[0].score,
            "landmarks": landmarks_list,
            "finger_angles": finger_angles,
            "palm_center": palm_center,
            "hand_openness": hand_openness,
            "bbox": self._calculate_bbox(landmarks_list),
            "detection_method": "yolo+mediapipe"
        }

    def _create_approximate_hand_data(self,
                                      bbox: Tuple[int, int, int, int],
                                      frame_shape: Tuple[int, int, int],
                                      hand_idx: int) -> Dict[str, Any]:
        """MediaPipeで検出できない場合の近似データ"""
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        return {
            "hand_id": hand_idx,
            "label": "Unknown",
            "handedness": "Unknown",
            "confidence": 0.5,
            "landmarks": [],  # ランドマークなし
            "finger_angles": {},
            "palm_center": {"x": center_x, "y": center_y},
            "hand_openness": 50.0,  # デフォルト値
            "bbox": {
                "x_min": float(x1),
                "y_min": float(y1),
                "x_max": float(x2),
                "y_max": float(y2)
            },
            "detection_method": "yolo_only"
        }

    def _fallback_mediapipe_detection(self, frame: np.ndarray) -> Dict[str, Any]:
        """フォールバック：色変換後の全体画像でMediaPipe検出"""
        processed_frame = self._preprocess_for_mediapipe(frame)
        rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)

        results = self.hands.process(rgb_frame)

        detection_result = {
            "hands": [],
            "frame_shape": frame.shape[:2],
            "detection_method": "mediapipe_enhanced"
        }

        if results.multi_hand_landmarks:
            for hand_idx, (hand_landmarks, hand_info) in enumerate(
                zip(results.multi_hand_landmarks, results.multi_handedness)
            ):
                height, width = frame.shape[:2]

                landmarks_list = []
                for landmark in hand_landmarks.landmark:
                    landmarks_list.append({
                        "x": landmark.x * width,
                        "y": landmark.y * height,
                        "z": landmark.z,
                        "visibility": landmark.visibility
                    })

                finger_angles = self._calculate_finger_angles(landmarks_list)
                palm_center = self._calculate_palm_center(landmarks_list)
                hand_openness = self._calculate_hand_openness(finger_angles)

                detection_result["hands"].append({
                    "hand_id": hand_idx,
                    "label": hand_info.classification[0].label,
                    "handedness": hand_info.classification[0].label,
                    "confidence": hand_info.classification[0].score,
                    "landmarks": landmarks_list,
                    "finger_angles": finger_angles,
                    "palm_center": palm_center,
                    "hand_openness": hand_openness,
                    "bbox": self._calculate_bbox(landmarks_list),
                    "detection_method": "mediapipe_enhanced"
                })

        return detection_result

    def _calculate_finger_angles(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """各指の曲がり角度を計算"""
        if len(landmarks) < 21:
            return {}

        angles = {}

        for finger_name in self.FINGER_NAMES:
            landmark_ids = self.FINGER_LANDMARK_IDS[finger_name]

            try:
                if finger_name == 'thumb':
                    p1 = np.array([landmarks[0]["x"], landmarks[0]["y"]])
                    p2 = np.array([landmarks[landmark_ids[1]]["x"],
                                 landmarks[landmark_ids[1]]["y"]])
                    p3 = np.array([landmarks[landmark_ids[2]]["x"],
                                 landmarks[landmark_ids[2]]["y"]])
                else:
                    p1 = np.array([landmarks[landmark_ids[0]]["x"],
                                 landmarks[landmark_ids[0]]["y"]])
                    p2 = np.array([landmarks[landmark_ids[1]]["x"],
                                 landmarks[landmark_ids[1]]["y"]])
                    p3 = np.array([landmarks[landmark_ids[2]]["x"],
                                 landmarks[landmark_ids[2]]["y"]])

                angle = self._calculate_angle(p1, p2, p3)
                angles[finger_name] = angle
            except (IndexError, KeyError):
                angles[finger_name] = 0.0

        return angles

    def _calculate_angle(self, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
        """3点間の角度を計算"""
        v1 = p1 - p2
        v2 = p3 - p2

        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.degrees(np.arccos(cos_angle))

        return float(angle)

    def _calculate_palm_center(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """手のひらの中心座標を計算"""
        if len(landmarks) < 21:
            return {"x": 0.0, "y": 0.0}

        palm_landmarks = [0, 1, 5, 9, 13, 17]

        try:
            x_coords = [landmarks[i]["x"] for i in palm_landmarks]
            y_coords = [landmarks[i]["y"] for i in palm_landmarks]

            return {
                "x": float(np.mean(x_coords)),
                "y": float(np.mean(y_coords))
            }
        except (IndexError, KeyError):
            return {"x": 0.0, "y": 0.0}

    def _calculate_hand_openness(self, finger_angles: Dict[str, float]) -> float:
        """手の開き具合を計算（0-100%）"""
        if not finger_angles:
            return 50.0

        max_angle = 180.0

        total_openness = 0
        for finger, angle in finger_angles.items():
            openness = (max_angle - angle) / max_angle
            total_openness += openness

        average_openness = (total_openness / len(finger_angles)) * 100 if finger_angles else 50.0

        return float(np.clip(average_openness, 0, 100))

    def _calculate_bbox(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """手の境界ボックスを計算"""
        if not landmarks:
            return {"x_min": 0.0, "y_min": 0.0, "x_max": 100.0, "y_max": 100.0}

        x_coords = [lm["x"] for lm in landmarks]
        y_coords = [lm["y"] for lm in landmarks]

        margin = 20

        return {
            "x_min": float(max(0, min(x_coords) - margin)),
            "y_min": float(max(0, min(y_coords) - margin)),
            "x_max": float(max(x_coords) + margin),
            "y_max": float(max(y_coords) + margin)
        }

    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, 'hands'):
            self.hands.close()