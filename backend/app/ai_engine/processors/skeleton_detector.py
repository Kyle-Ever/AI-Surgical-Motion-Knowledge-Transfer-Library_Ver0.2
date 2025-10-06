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
                 static_image_mode: bool = False,
                 max_num_hands: int = 2,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5,
                 flip_handedness: bool = False):
        """
        初期化 - 純粋なMediaPipe実装

        Args:
            static_image_mode: 静止画モード（Trueで各フレーム完全検出、両手検出に推奨）
            max_num_hands: 検出する最大手数
            min_detection_confidence: 検出の最小信頼度
            min_tracking_confidence: トラッキングの最小信頼度
            flip_handedness: 手の左右を反転するか（外部カメラの場合True）
        """
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.flip_handedness = flip_handedness
        self.max_num_hands = max_num_hands

        # 純粋なMediaPipe Hands初期化
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
    
    def _normalize_landmarks(self, landmarks):
        """
        landmarksを常に辞書のリストに正規化

        Args:
            landmarks: numpy配列、リスト、または辞書のリスト

        Returns:
            正規化された辞書のリスト
        """
        if landmarks is None:
            return []

        # numpy配列の場合
        if isinstance(landmarks, np.ndarray):
            logger.debug(f"Converting numpy array landmarks with shape {landmarks.shape}")
            normalized = []
            for i in range(len(landmarks)):
                if len(landmarks[i]) >= 2:
                    normalized.append({
                        "x": float(landmarks[i][0]),
                        "y": float(landmarks[i][1]),
                        "z": float(landmarks[i][2]) if len(landmarks[i]) > 2 else 0.0,
                        "visibility": float(landmarks[i][3]) if len(landmarks[i]) > 3 else 1.0
                    })
            return normalized

        # リストの場合
        if isinstance(landmarks, list):
            if len(landmarks) == 0:
                return []

            # 最初の要素をチェック
            if isinstance(landmarks[0], dict):
                # 既に正しい形式
                return landmarks
            elif isinstance(landmarks[0], (list, tuple, np.ndarray)):
                # リストのリストまたはタプルのリスト
                logger.debug("Converting list of arrays/tuples to dict format")
                normalized = []
                for point in landmarks:
                    if len(point) >= 2:
                        normalized.append({
                            "x": float(point[0]),
                            "y": float(point[1]),
                            "z": float(point[2]) if len(point) > 2 else 0.0,
                            "visibility": float(point[3]) if len(point) > 3 else 1.0
                        })
                return normalized

        logger.warning(f"Unexpected landmarks format: {type(landmarks)}")
        return landmarks if isinstance(landmarks, list) else []

    def detect_from_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        フレームから手の骨格を検出 - 純粋なMediaPipe実装

        Args:
            frame: 入力画像フレーム (BGR)

        Returns:
            検出結果の辞書
        """
        # BGR to RGB変換のみ（前処理なし）
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # MediaPipeで検出
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
                # landmarksを正規化
                if "landmarks" in hand_data:
                    hand_data["landmarks"] = self._normalize_landmarks(hand_data["landmarks"])
                detection_result["hands"].append(hand_data)

        # 両手検出モードで1つしか検出されなかった場合、分割処理を試みる
        if self.max_num_hands == 2 and len(detection_result["hands"]) < 2 and self.hands_left and self.hands_right:
            detection_result["hands"] = self._detect_both_hands_split(frame, rgb_frame, detection_result["hands"])

        # デバッグログ（最初のフレームのみ詳細出力）
        if hasattr(self, '_debug_logged'):
            pass  # 既にログ出力済み
        else:
            self._debug_logged = True
            logger.info("=== SKELETON DETECTOR OUTPUT DEBUG ===")
            logger.info(f"Result type: {type(detection_result)}")
            logger.info(f"Number of hands: {len(detection_result.get('hands', []))}")
            if detection_result.get('hands'):
                first_hand = detection_result['hands'][0]
                logger.info(f"First hand keys: {list(first_hand.keys())}")
                if 'landmarks' in first_hand:
                    lm = first_hand['landmarks']
                    logger.info(f"Landmarks type: {type(lm)}")
                    if isinstance(lm, list) and len(lm) > 0:
                        logger.info(f"First landmark type: {type(lm[0])}")
                        if isinstance(lm[0], dict):
                            logger.info(f"First landmark keys: {list(lm[0].keys())}")

        # 🔴 CRITICAL FIX: detectedキーを追加（analysis_service_v2が依存）
        detection_result['detected'] = len(detection_result.get('hands', [])) > 0

        return detection_result


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

    def detect_batch(self, frames: List[np.ndarray]) -> List[Dict[str, Any]]:
        """
        複数フレームに対してバッチ検出を実行

        Args:
            frames: フレームのリスト

        Returns:
            検出結果のリスト
        """
        results = []
        for idx, frame in enumerate(frames):
            result = self.detect_from_frame(frame)
            result['frame_index'] = idx  # フレームインデックスを追加
            results.append(result)
        return results

    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, 'hands'):
            self.hands.close()
        if hasattr(self, 'hands_left') and self.hands_left:
            self.hands_left.close()
        if hasattr(self, 'hands_right') and self.hands_right:
            self.hands_right.close()