"""
強化された手検出モジュール
手袋（青い手術用手袋）の検出を改善するための前処理を追加
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class EnhancedHandDetector:
    """手袋対応の強化版手検出クラス"""

    FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']

    FINGER_LANDMARK_IDS = {
        'thumb': [1, 2, 3, 4],
        'index': [5, 6, 7, 8],
        'middle': [9, 10, 11, 12],
        'ring': [13, 14, 15, 16],
        'pinky': [17, 18, 19, 20]
    }

    def __init__(self,
                 static_image_mode: bool = True,
                 max_num_hands: int = 2,
                 min_detection_confidence: float = 0.2,
                 min_tracking_confidence: float = 0.2,
                 enable_preprocessing: bool = True):
        """
        初期化

        Args:
            static_image_mode: 静止画モード
            max_num_hands: 検出する最大手数
            min_detection_confidence: 検出の最小信頼度
            min_tracking_confidence: トラッキングの最小信頼度
            enable_preprocessing: 前処理を有効にするか
        """
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.enable_preprocessing = enable_preprocessing
        self.max_num_hands = max_num_hands

        # メインのMediaPipeハンドトラッカー
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

        logger.info("EnhancedHandDetector initialized")

    def detect_from_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        フレームから手を検出（手袋対応）

        Args:
            frame: 入力画像フレーム (BGR)

        Returns:
            検出結果の辞書
        """
        detection_result = {
            "hands": [],
            "frame_shape": frame.shape[:2],
            "preprocessing_applied": False
        }

        # 1. まず通常の検出を試みる
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)

        if results.multi_hand_landmarks:
            # 通常検出で成功
            for hand_idx, (hand_landmarks, hand_info) in enumerate(
                zip(results.multi_hand_landmarks, results.multi_handedness)
            ):
                hand_data = self._process_hand_landmarks(
                    hand_landmarks, hand_info, frame.shape, hand_idx
                )
                detection_result["hands"].append(hand_data)
        elif self.enable_preprocessing:
            # 2. 検出失敗時は前処理を適用して再試行
            detection_result["preprocessing_applied"] = True

            # 複数の前処理手法を試す
            preprocessing_methods = [
                ("blue_to_skin", self._convert_blue_to_skin),
                ("enhance_contrast", self._enhance_contrast),
                ("adaptive_threshold", self._adaptive_preprocessing)
            ]

            for method_name, method_func in preprocessing_methods:
                processed_frame = method_func(frame)
                rgb_processed = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_processed)

                if results.multi_hand_landmarks:
                    logger.info(f"Detection successful with {method_name} preprocessing")
                    for hand_idx, (hand_landmarks, hand_info) in enumerate(
                        zip(results.multi_hand_landmarks, results.multi_handedness)
                    ):
                        hand_data = self._process_hand_landmarks(
                            hand_landmarks, hand_info, frame.shape, hand_idx
                        )
                        hand_data["preprocessing_method"] = method_name
                        detection_result["hands"].append(hand_data)
                    break  # 成功したら終了

        return detection_result

    def _convert_blue_to_skin(self, frame: np.ndarray) -> np.ndarray:
        """青い手袋を肌色に変換"""
        # HSV色空間に変換
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 青色の範囲を定義（手術用手袋の青）
        lower_blue = np.array([100, 50, 50])
        upper_blue = np.array([130, 255, 255])

        # 青色マスクを作成
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # ノイズ除去
        kernel = np.ones((5, 5), np.uint8)
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, kernel)

        # 結果画像を作成
        result = frame.copy()

        # 青い部分を肌色に変換
        # BGR -> HSVで肌色に近い色に変更
        skin_hsv = hsv.copy()
        skin_hsv[blue_mask > 0, 0] = 15  # 肌色のHue (オレンジ系)
        skin_hsv[blue_mask > 0, 1] = 100  # 適度な彩度
        skin_hsv[blue_mask > 0, 2] = np.clip(skin_hsv[blue_mask > 0, 2] * 1.2, 0, 255)  # 明度を少し上げる

        # HSVからBGRに戻す
        result = cv2.cvtColor(skin_hsv, cv2.COLOR_HSV2BGR)

        return result

    def _enhance_contrast(self, frame: np.ndarray) -> np.ndarray:
        """コントラスト強調"""
        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        return enhanced

    def _adaptive_preprocessing(self, frame: np.ndarray) -> np.ndarray:
        """適応的前処理"""
        # 複数の処理を組み合わせる
        result = frame.copy()

        # 1. 明度調整
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 1.3, 0, 255)  # 明度を上げる
        result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        # 2. エッジ強調
        kernel = np.array([[-1, -1, -1],
                          [-1, 9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(result, -1, kernel)

        # 3. ブレンド
        result = cv2.addWeighted(result, 0.7, sharpened, 0.3, 0)

        return result

    def _process_hand_landmarks(self,
                               hand_landmarks,
                               hand_info,
                               frame_shape: Tuple[int, int, int],
                               hand_idx: int = 0) -> Dict[str, Any]:
        """手のランドマークを処理"""
        height, width = frame_shape[:2]

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

        return {
            "hand_id": hand_idx,
            "label": hand_info.classification[0].label,
            "handedness": hand_info.classification[0].label,
            "confidence": hand_info.classification[0].score,
            "landmarks": landmarks_list,
            "finger_angles": finger_angles,
            "palm_center": palm_center,
            "hand_openness": hand_openness,
            "bbox": self._calculate_bbox(landmarks_list)
        }

    def _calculate_finger_angles(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """各指の曲がり角度を計算"""
        angles = {}

        for finger_name in self.FINGER_NAMES:
            landmark_ids = self.FINGER_LANDMARK_IDS[finger_name]

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
        palm_landmarks = [0, 1, 5, 9, 13, 17]

        x_coords = [landmarks[i]["x"] for i in palm_landmarks]
        y_coords = [landmarks[i]["y"] for i in palm_landmarks]

        return {
            "x": float(np.mean(x_coords)),
            "y": float(np.mean(y_coords))
        }

    def _calculate_hand_openness(self, finger_angles: Dict[str, float]) -> float:
        """手の開き具合を計算（0-100%）"""
        max_angle = 180.0

        total_openness = 0
        for finger, angle in finger_angles.items():
            openness = (max_angle - angle) / max_angle
            total_openness += openness

        average_openness = (total_openness / len(finger_angles)) * 100

        return float(np.clip(average_openness, 0, 100))

    def _calculate_bbox(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """手の境界ボックスを計算"""
        x_coords = [lm["x"] for lm in landmarks]
        y_coords = [lm["y"] for lm in landmarks]

        margin = 20

        return {
            "x_min": float(max(0, min(x_coords) - margin)),
            "y_min": float(max(0, min(y_coords) - margin)),
            "x_max": float(max(x_coords) + margin),
            "y_max": float(max(y_coords) + margin)
        }

    def draw_landmarks(self, frame: np.ndarray, detection_result: Dict[str, Any]) -> np.ndarray:
        """検出結果を画像に描画"""
        annotated_frame = frame.copy()

        for hand_data in detection_result.get("hands", []):
            landmarks = hand_data["landmarks"]

            # ランドマークを描画
            for i, landmark in enumerate(landmarks):
                x = int(landmark["x"])
                y = int(landmark["y"])
                cv2.circle(annotated_frame, (x, y), 5, (0, 255, 0), -1)

                # 接続線を描画
                if i > 0:
                    if i in [1, 5, 9, 13, 17]:
                        prev_idx = 0
                    elif i in [2, 6, 10, 14, 18]:
                        prev_idx = i - 1
                    elif i in [3, 7, 11, 15, 19]:
                        prev_idx = i - 1
                    elif i in [4, 8, 12, 16, 20]:
                        prev_idx = i - 1
                    else:
                        prev_idx = i - 1

                    prev_x = int(landmarks[prev_idx]["x"])
                    prev_y = int(landmarks[prev_idx]["y"])
                    cv2.line(annotated_frame, (prev_x, prev_y), (x, y), (0, 255, 0), 2)

            # ラベルとバウンディングボックス
            label = f"{hand_data['label']} ({hand_data['confidence']:.2f})"
            if hand_data.get("preprocessing_method"):
                label += f" [{hand_data['preprocessing_method']}]"

            bbox = hand_data["bbox"]
            cv2.putText(annotated_frame, label,
                       (int(bbox["x_min"]), int(bbox["y_min"]) - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            cv2.rectangle(annotated_frame,
                         (int(bbox["x_min"]), int(bbox["y_min"])),
                         (int(bbox["x_max"]), int(bbox["y_max"])),
                         (0, 255, 0), 2)

        return annotated_frame

    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, 'hands'):
            self.hands.close()