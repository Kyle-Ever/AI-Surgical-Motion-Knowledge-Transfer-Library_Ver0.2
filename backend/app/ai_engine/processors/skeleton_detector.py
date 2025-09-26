"""
手の骨格検出モジュール

MediaPipeを使用して手の21個のランドマークを検出し、
指の角度や動きを解析する
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class HandSkeletonDetector:
    """手の骨格検出クラス"""
    
    FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']
    
    FINGER_LANDMARK_IDS = {
        'thumb': [1, 2, 3, 4],
        'index': [5, 6, 7, 8],
        'middle': [9, 10, 11, 12],
        'ring': [13, 14, 15, 16],
        'pinky': [17, 18, 19, 20]
    }
    
    def __init__(self,
                 static_image_mode: bool = False,  # Use tracking mode like reference code
                 max_num_hands: int = 2,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5,
                 flip_handedness: bool = False,
                 enable_glove_detection: bool = False):
        """
        初期化

        Args:
            static_image_mode: 静止画モード（Trueで各フレーム完全検出、両手検出に推奨）
            max_num_hands: 検出する最大手数
            min_detection_confidence: 検出の最小信頼度
            min_tracking_confidence: トラッキングの最小信頼度
            flip_handedness: 手の左右を反転するか（外部カメラの場合True）
            enable_glove_detection: 手袋検出モードを有効にするか
        """
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.flip_handedness = flip_handedness
        self.max_num_hands = max_num_hands
        self.enable_glove_detection = enable_glove_detection

        # 手袋検出モードの場合は低い閾値を使用
        if enable_glove_detection:
            min_detection_confidence = min(min_detection_confidence, 0.2)
            min_tracking_confidence = min(min_tracking_confidence, 0.2)

        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

        # 両手検出用の追加インスタンス（分割処理用）
        if max_num_hands == 2:
            self.hands_left = self.mp_hands.Hands(
                static_image_mode=True,
                max_num_hands=1,
                min_detection_confidence=min_detection_confidence * 0.8,  # やや低めの閾値
                min_tracking_confidence=min_tracking_confidence * 0.8
            )
            self.hands_right = self.mp_hands.Hands(
                static_image_mode=True,
                max_num_hands=1,
                min_detection_confidence=min_detection_confidence * 0.8,
                min_tracking_confidence=min_tracking_confidence * 0.8
            )
        else:
            self.hands_left = None
            self.hands_right = None

        logger.info("HandSkeletonDetector initialized with MediaPipe")
    
    def detect_from_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        フレームから手の骨格を検出

        Args:
            frame: 入力画像フレーム (BGR)

        Returns:
            検出結果の辞書
        """
        # 手袋検出モードの場合は前処理を適用
        if self.enable_glove_detection:
            processed_frame = self._preprocess_for_gloves(frame)
            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
        else:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # まず通常の検出を試みる
        results = self.hands.process(rgb_frame)

        detection_result = {
            "hands": [],
            "frame_shape": frame.shape[:2]
        }

        if results.multi_hand_landmarks:
            # Log detection info
            num_hands = len(results.multi_hand_landmarks)
            if num_hands > 1:
                logger.debug(f"Detected {num_hands} hands in frame")

            for hand_idx, (hand_landmarks, hand_info) in enumerate(
                zip(results.multi_hand_landmarks, results.multi_handedness)
            ):
                hand_data = self._process_hand_landmarks(
                    hand_landmarks,
                    hand_info,
                    frame.shape,
                    hand_idx
                )
                detection_result["hands"].append(hand_data)

        # 両手検出モードで1つしか検出されなかった場合、分割処理を試みる
        if self.max_num_hands == 2 and len(detection_result["hands"]) < 2 and self.hands_left and self.hands_right:
            detection_result["hands"] = self._detect_both_hands_split(frame, rgb_frame, detection_result["hands"])

        return detection_result

    def _preprocess_for_gloves(self, frame: np.ndarray) -> np.ndarray:
        """手袋検出用の前処理（青・白両対応）"""
        # 複数の前処理手法を組み合わせる

        # 方法1: 青い手袋と白い手袋を肌色に変換
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 青色の範囲を拡張（手術用手袋の幅広い青色に対応）
        # 明るい青から濃い青まで広範囲をカバー
        lower_blue1 = np.array([70, 20, 20])   # より明るい青も検出
        upper_blue1 = np.array([140, 255, 255]) # より広い範囲

        lower_blue2 = np.array([85, 40, 40])   # 中間の青
        upper_blue2 = np.array([125, 255, 255])

        # 白色の範囲（白い手袋用）
        # 彩度が低く、明度が高い範囲
        lower_white1 = np.array([0, 0, 200])    # H=任意, S=0-30, V=200-255
        upper_white1 = np.array([180, 30, 255])

        # より広い白色範囲（薄い色も含む）
        lower_white2 = np.array([0, 0, 180])    # やや暗めの白も含む
        upper_white2 = np.array([180, 50, 255])

        # 複数のマスクを作成
        blue_mask1 = cv2.inRange(hsv, lower_blue1, upper_blue1)
        blue_mask2 = cv2.inRange(hsv, lower_blue2, upper_blue2)
        white_mask1 = cv2.inRange(hsv, lower_white1, upper_white1)
        white_mask2 = cv2.inRange(hsv, lower_white2, upper_white2)

        # すべてのマスクを結合
        blue_mask = cv2.bitwise_or(blue_mask1, blue_mask2)
        white_mask = cv2.bitwise_or(white_mask1, white_mask2)
        glove_mask = cv2.bitwise_or(blue_mask, white_mask)

        # ノイズ除去と領域拡張
        kernel = np.ones((7, 7), np.uint8)
        glove_mask = cv2.morphologyEx(glove_mask, cv2.MORPH_CLOSE, kernel)
        glove_mask = cv2.dilate(glove_mask, kernel, iterations=1)

        # 手袋領域をより自然な肌色に変換（明度を考慮）
        result = frame.copy()
        if np.any(glove_mask > 0):
            # 元の明度を保持しながら色相・彩度を調整
            glove_pixels = frame[glove_mask > 0]
            # 各ピクセルの明度を保持
            brightness = np.mean(glove_pixels, axis=1, keepdims=True)
            # 肌色のベース（明度に応じて調整）
            skin_base = np.array([180, 150, 120])  # BGR
            skin_color = skin_base * (brightness / 255.0)
            skin_color = np.clip(skin_color, 0, 255).astype(np.uint8)
            result[glove_mask > 0] = skin_color.reshape(-1, 3)

        # 方法2: CLAHE適用でコントラスト改善
        # LAB色空間でCLAHE適用
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        result = cv2.merge([l, a, b])
        result = cv2.cvtColor(result, cv2.COLOR_LAB2BGR)

        # 方法3: ガンマ補正で明るさ調整
        gamma = 1.1  # より控えめなガンマ値
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        result = cv2.LUT(result, table)

        # エッジ強調
        kernel_sharpen = np.array([[-1,-1,-1],
                                   [-1, 9,-1],
                                   [-1,-1,-1]])
        sharpened = cv2.filter2D(result, -1, kernel_sharpen)

        # オリジナルとブレンド
        result = cv2.addWeighted(result, 0.7, sharpened, 0.3, 0)

        return result

    def _detect_both_hands_split(self, frame: np.ndarray, rgb_frame: np.ndarray, initial_hands: List[Dict]) -> List[Dict]:
        """
        画像を左右に分割して両手を検出する改善メソッド

        Args:
            frame: 元のフレーム (BGR)
            rgb_frame: RGB変換済みフレーム
            initial_hands: 初回検出で見つかった手

        Returns:
            改善された検出結果
        """
        h, w = frame.shape[:2]
        mid_x = w // 2

        # 左半分と右半分を処理
        left_half = rgb_frame[:, :mid_x + 50]  # 少しオーバーラップ
        right_half = rgb_frame[:, mid_x - 50:]  # 少しオーバーラップ

        all_hands = []

        # 左半分を処理（通常右手が映る）
        left_results = self.hands_left.process(left_half)
        if left_results.multi_hand_landmarks:
            for hand_landmarks, hand_info in zip(left_results.multi_hand_landmarks, left_results.multi_handedness):
                # 座標を元画像の座標系に変換
                adjusted_landmarks = []
                for lm in hand_landmarks.landmark:
                    adjusted_landmarks.append({
                        "x": lm.x * left_half.shape[1] / w,  # 正規化座標に調整
                        "y": lm.y,
                        "z": lm.z,
                        "visibility": lm.visibility
                    })

                # MediaPipeのランドマークオブジェクトを作成
                class FakeLandmark:
                    def __init__(self, x, y, z, visibility):
                        self.x = x
                        self.y = y
                        self.z = z
                        self.visibility = visibility

                class FakeLandmarks:
                    def __init__(self, landmarks):
                        self.landmark = [FakeLandmark(lm["x"], lm["y"], lm["z"], lm["visibility"]) for lm in landmarks]

                fake_landmarks = FakeLandmarks(adjusted_landmarks)
                hand_data = self._process_hand_landmarks(fake_landmarks, hand_info, frame.shape, 0)
                all_hands.append(hand_data)

        # 右半分を処理（通常左手が映る）
        right_results = self.hands_right.process(right_half)
        if right_results.multi_hand_landmarks:
            for hand_landmarks, hand_info in zip(right_results.multi_hand_landmarks, right_results.multi_handedness):
                # 座標を元画像の座標系に変換
                adjusted_landmarks = []
                for lm in hand_landmarks.landmark:
                    adjusted_landmarks.append({
                        "x": (lm.x * right_half.shape[1] + (mid_x - 50)) / w,  # 正規化座標に調整
                        "y": lm.y,
                        "z": lm.z,
                        "visibility": lm.visibility
                    })

                class FakeLandmark:
                    def __init__(self, x, y, z, visibility):
                        self.x = x
                        self.y = y
                        self.z = z
                        self.visibility = visibility

                class FakeLandmarks:
                    def __init__(self, landmarks):
                        self.landmark = [FakeLandmark(lm["x"], lm["y"], lm["z"], lm["visibility"]) for lm in landmarks]

                fake_landmarks = FakeLandmarks(adjusted_landmarks)
                hand_data = self._process_hand_landmarks(fake_landmarks, hand_info, frame.shape, 1)
                all_hands.append(hand_data)

        # 重複を除去（同じ手が2回検出された場合）
        if len(all_hands) > 1:
            # 手の位置が近すぎる場合は信頼度の高い方を選択
            hand1_center = all_hands[0]["palm_center"]
            hand2_center = all_hands[1]["palm_center"]
            distance = np.sqrt((hand1_center["x"] - hand2_center["x"])**2 +
                              (hand1_center["y"] - hand2_center["y"])**2)

            # 距離が近すぎる場合（画像幅の10%未満）
            if distance < w * 0.1:
                # 信頼度の高い方を残す
                if all_hands[0]["confidence"] > all_hands[1]["confidence"]:
                    all_hands = [all_hands[0]]
                else:
                    all_hands = [all_hands[1]]

        # 初回検出の結果と統合
        if initial_hands:
            # 既に検出されている手と重複しないものだけ追加
            for new_hand in all_hands:
                is_duplicate = False
                for existing_hand in initial_hands:
                    existing_center = existing_hand["palm_center"]
                    new_center = new_hand["palm_center"]
                    distance = np.sqrt((existing_center["x"] - new_center["x"])**2 +
                                      (existing_center["y"] - new_center["y"])**2)
                    if distance < w * 0.1:  # 重複判定
                        is_duplicate = True
                        break

                if not is_duplicate and len(initial_hands) < 2:
                    initial_hands.append(new_hand)

            return initial_hands
        else:
            return all_hands[:2]  # 最大2つまで
    
    def _process_hand_landmarks(self,
                                hand_landmarks,
                                hand_info,
                                frame_shape: Tuple[int, int, int],
                                hand_idx: int = 0) -> Dict[str, Any]:
        """
        手のランドマークを処理
        
        Args:
            hand_landmarks: MediaPipeのランドマーク
            hand_info: 手の情報（左右など）
            frame_shape: フレームの形状
        
        Returns:
            処理された手のデータ
        """
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

        # Get the raw handedness from MediaPipe
        raw_label = hand_info.classification[0].label

        # Apply flip if needed (for external cameras)
        if self.flip_handedness:
            # External camera: flip the handedness
            final_label = "Left" if raw_label == "Right" else "Right"
        else:
            # Internal camera or no flip: use as-is
            final_label = raw_label

        # Add hand_id for tracking (like in reference code)
        hand_id = hand_idx

        return {
            "hand_id": hand_id,  # Add hand_id like reference code
            "label": final_label,
            "handedness": final_label,
            "confidence": hand_info.classification[0].score,
            "landmarks": landmarks_list,
            "finger_angles": finger_angles,
            "palm_center": palm_center,
            "hand_openness": hand_openness,
            "bbox": self._calculate_bbox(landmarks_list)
        }
    
    def _calculate_finger_angles(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """
        各指の曲がり角度を計算
        
        Args:
            landmarks: ランドマークのリスト
        
        Returns:
            各指の角度（度数）
        """
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
        """
        3点間の角度を計算
        
        Args:
            p1, p2, p3: 3つの点の座標
        
        Returns:
            角度（度数）
        """
        v1 = p1 - p2
        v2 = p3 - p2
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        
        angle = np.degrees(np.arccos(cos_angle))
        
        return float(angle)
    
    def _calculate_palm_center(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """
        手のひらの中心座標を計算
        
        Args:
            landmarks: ランドマークのリスト
        
        Returns:
            中心座標
        """
        palm_landmarks = [0, 1, 5, 9, 13, 17]
        
        x_coords = [landmarks[i]["x"] for i in palm_landmarks]
        y_coords = [landmarks[i]["y"] for i in palm_landmarks]
        
        return {
            "x": float(np.mean(x_coords)),
            "y": float(np.mean(y_coords))
        }
    
    def _calculate_hand_openness(self, finger_angles: Dict[str, float]) -> float:
        """
        手の開き具合を計算（0-100%）
        
        Args:
            finger_angles: 各指の角度
        
        Returns:
            開き具合のパーセンテージ
        """
        max_angle = 180.0
        
        total_openness = 0
        for finger, angle in finger_angles.items():
            openness = (max_angle - angle) / max_angle
            total_openness += openness
        
        average_openness = (total_openness / len(finger_angles)) * 100
        
        return float(np.clip(average_openness, 0, 100))
    
    def _calculate_bbox(self, landmarks: List[Dict[str, float]]) -> Dict[str, float]:
        """
        手の境界ボックスを計算
        
        Args:
            landmarks: ランドマークのリスト
        
        Returns:
            境界ボックス座標
        """
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
        """
        検出結果を画像に描画
        
        Args:
            frame: 入力画像
            detection_result: 検出結果
        
        Returns:
            描画された画像
        """
        annotated_frame = frame.copy()
        
        for hand_data in detection_result.get("hands", []):
            landmarks = hand_data["landmarks"]
            
            for i, landmark in enumerate(landmarks):
                x = int(landmark["x"])
                y = int(landmark["y"])
                cv2.circle(annotated_frame, (x, y), 5, (0, 255, 0), -1)
                
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
            
            label = f"{hand_data['label']} ({hand_data['confidence']:.2f})"
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
        if hasattr(self, 'hands_left') and self.hands_left:
            self.hands_left.close()
        if hasattr(self, 'hands_right') and self.hands_right:
            self.hands_right.close()