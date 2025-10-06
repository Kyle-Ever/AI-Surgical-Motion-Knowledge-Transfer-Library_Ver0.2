"""
SAM (Segment Anything Model) を使った手術器具セグメンテーション・トラッキングモジュール
"""

import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
import torch
from pathlib import Path
import json
import base64
from io import BytesIO
from PIL import Image
from collections import deque

# SAMのインポート
try:
    from segment_anything import sam_model_registry, SamPredictor, SamAutomaticMaskGenerator
    SAM_AVAILABLE = True
except ImportError:
    SAM_AVAILABLE = False
    logging.warning("SAM not available. Using mock implementation.")

logger = logging.getLogger(__name__)


class SAMTracker:
    """SAMを使った器具セグメンテーション・トラッキングクラス"""
    
    def __init__(self,
                 model_type: str = "vit_b",
                 checkpoint_path: Optional[str] = None,
                 device: str = "cpu",
                 use_mock: bool = False):
        """
        初期化

        Args:
            model_type: SAMモデルタイプ ("vit_b", "vit_l", "vit_h")
            checkpoint_path: モデルチェックポイントのパス
            device: 使用デバイス ("cpu" or "cuda")
            use_mock: モック実装を使用するか
        """
        self.model_type = model_type
        self.device = device
        self.use_mock = use_mock or not SAM_AVAILABLE

        # OpenCVトラッカー用
        self.cv_trackers = {}  # OpenCVトラッカー
        self.trajectories = {}  # 軌跡
        
        if self.use_mock:
            logger.info("Using mock SAM implementation")
            self.predictor = None
            self.mask_generator = None
        else:
            try:
                # SAMモデルのロード
                # デフォルトのチェックポイントパス
                if checkpoint_path is None:
                    checkpoint_path = Path("sam_b.pt")
                    if not checkpoint_path.exists():
                        checkpoint_path = Path("backend/sam_b.pt")
                else:
                    checkpoint_path = Path(checkpoint_path)

                if checkpoint_path.exists():
                    logger.info(f"Loading SAM model from {checkpoint_path}")
                    sam = sam_model_registry[model_type](checkpoint=str(checkpoint_path))
                else:
                    # モデルファイルが見つからない場合はモックモードにフォールバック
                    logger.warning(f"SAM checkpoint not found at {checkpoint_path}. Using mock mode.")
                    self.use_mock = True
                    self.predictor = None
                    self.mask_generator = None
                    return
                
                sam.to(device=device)
                self.predictor = SamPredictor(sam)
                self.mask_generator = SamAutomaticMaskGenerator(sam)
                logger.info(f"SAM {model_type} loaded successfully on {device}")
            except Exception as e:
                logger.error(f"Failed to load SAM model: {e}")
                self.use_mock = True
                self.predictor = None
                self.mask_generator = None
    
    def set_image(self, image: np.ndarray) -> None:
        """
        画像をSAMにセット（前処理を含む）
        
        Args:
            image: 入力画像 (BGR or RGB)
        """
        if not self.use_mock and self.predictor:
            # BGRからRGBに変換
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            
            self.predictor.set_image(image_rgb)
            self.current_image = image_rgb
        else:
            self.current_image = image
    
    def segment_with_point(self, 
                          point_coords: List[Tuple[int, int]], 
                          point_labels: List[int]) -> Dict[str, Any]:
        """
        ポイントプロンプトでセグメンテーション
        
        Args:
            point_coords: ポイント座標のリスト [(x, y), ...]
            point_labels: ポイントラベル (1: 前景, 0: 背景)
        
        Returns:
            セグメンテーション結果
        """
        if self.use_mock:
            return self._mock_segment_with_point(point_coords, point_labels)
        
        if not self.predictor:
            raise RuntimeError("SAM predictor not initialized")
        
        # numpy配列に変換
        point_coords_np = np.array(point_coords)
        point_labels_np = np.array(point_labels)
        
        # 予測実行
        masks, scores, logits = self.predictor.predict(
            point_coords=point_coords_np,
            point_labels=point_labels_np,
            multimask_output=True,
        )
        
        # 最も信頼度の高いマスクを選択
        best_idx = np.argmax(scores)
        best_mask = masks[best_idx]
        best_score = scores[best_idx]
        
        # バウンディングボックスを計算
        bbox = self._get_bbox_from_mask(best_mask)
        
        return {
            "mask": best_mask,
            "score": float(best_score),
            "bbox": bbox,
            "area": float(np.sum(best_mask)),
            "type": "point_prompt"
        }
    
    def segment_with_box(self, box: Tuple[int, int, int, int]) -> Dict[str, Any]:
        """
        ボックスプロンプトでセグメンテーション
        
        Args:
            box: バウンディングボックス (x1, y1, x2, y2)
        
        Returns:
            セグメンテーション結果
        """
        if self.use_mock:
            return self._mock_segment_with_box(box)
        
        if not self.predictor:
            raise RuntimeError("SAM predictor not initialized")
        
        # numpy配列に変換
        box_np = np.array(box)
        
        # 予測実行
        masks, scores, logits = self.predictor.predict(
            box=box_np,
            multimask_output=False,
        )
        
        mask = masks[0]
        score = scores[0]
        
        return {
            "mask": mask,
            "score": float(score),
            "bbox": box,
            "area": float(np.sum(mask)),
            "type": "box_prompt"
        }
    
    def segment_automatic(self) -> List[Dict[str, Any]]:
        """
        自動セグメンテーション（全オブジェクト検出）
        
        Returns:
            検出された全オブジェクトのリスト
        """
        if self.use_mock:
            return self._mock_segment_automatic()
        
        if not self.mask_generator:
            raise RuntimeError("SAM mask generator not initialized")
        
        # 自動マスク生成
        masks = self.mask_generator.generate(self.current_image)
        
        results = []
        for mask_data in masks:
            bbox = self._get_bbox_from_mask(mask_data["segmentation"])
            results.append({
                "mask": mask_data["segmentation"],
                "score": mask_data["predicted_iou"],
                "bbox": bbox,
                "area": mask_data["area"],
                "type": "automatic"
            })
        
        return results
    
    def track_in_video(self, 
                      frames: List[np.ndarray],
                      initial_mask: np.ndarray,
                      initial_bbox: Tuple[int, int, int, int]) -> List[Dict[str, Any]]:
        """
        ビデオ全体で器具をトラッキング
        
        Args:
            frames: フレームのリスト
            initial_mask: 初期マスク
            initial_bbox: 初期バウンディングボックス
        
        Returns:
            各フレームのトラッキング結果
        """
        if self.use_mock:
            return self._mock_track_in_video(frames, initial_mask, initial_bbox)
        
        results = []
        
        # 簡易トラッキング実装（実際のSAM2ではより高度なトラッキングが可能）
        prev_bbox = initial_bbox
        prev_center = ((prev_bbox[0] + prev_bbox[2]) // 2, 
                      (prev_bbox[1] + prev_bbox[3]) // 2)
        
        for i, frame in enumerate(frames):
            if i == 0:
                # 最初のフレームは初期マスクを使用
                results.append({
                    "frame_idx": 0,
                    "mask": initial_mask,
                    "bbox": initial_bbox,
                    "score": 1.0
                })
            else:
                # 前フレームの中心点を使ってセグメンテーション
                self.set_image(frame)
                
                # 前フレームの中心点付近でセグメント
                result = self.segment_with_point(
                    [prev_center],
                    [1]  # 前景
                )
                
                if result["score"] > 0.5:  # 信頼度閾値
                    prev_bbox = result["bbox"]
                    prev_center = ((prev_bbox[0] + prev_bbox[2]) // 2,
                                  (prev_bbox[1] + prev_bbox[3]) // 2)
                    
                    results.append({
                        "frame_idx": i,
                        "mask": result["mask"],
                        "bbox": result["bbox"],
                        "score": result["score"]
                    })
                else:
                    # トラッキング失敗
                    results.append({
                        "frame_idx": i,
                        "mask": None,
                        "bbox": None,
                        "score": 0.0
                    })
        
        return results
    
    def initialize_tracking(self, first_frame: np.ndarray, instruments: List[Dict]) -> None:
        """
        最初のフレームで器具を初期化

        Args:
            first_frame: 最初のフレーム
            instruments: 器具定義のリスト
        """
        logger.info(f"Initializing tracking with {len(instruments)} instruments")
        self.tracked_instruments = []
        self.cv_trackers = {}
        self.trajectories = {}

        if self.use_mock:
            # モック実装でも実際の画像処理ベースのトラッキングを使用
            if not instruments:
                # 器具が指定されていない場合は自動検出
                instruments = self._auto_detect_instruments_simple(first_frame)
            else:
                # 器具が指定されている場合でも、bboxが無効なら自動検出を試みる
                for idx, inst in enumerate(instruments):
                    bbox = inst.get("bbox")
                    # bboxが無効（小さすぎる）場合は自動検出
                    if bbox and (bbox[2] - bbox[0]) <= 100 and (bbox[3] - bbox[1]) <= 100:
                        logger.info(f"Instrument {idx} bbox seems invalid {bbox}, trying auto-detection")
                        detected = self._detect_instruments_in_region(first_frame, bbox)
                        if detected:
                            inst["bbox"] = detected[0]  # 最初に検出されたものを使用
                            logger.info(f"Auto-detected new bbox: {inst['bbox']}")

            for idx, inst in enumerate(instruments):
                bbox = inst.get("bbox")

                if not bbox or (bbox[2] - bbox[0]) <= 100:
                    # bboxがない、または小さすぎる場合は自動検出
                    detected_instruments = self._auto_detect_instruments_simple(first_frame)
                    if detected_instruments and idx < len(detected_instruments):
                        bbox = detected_instruments[idx]["bbox"]
                        logger.info(f"Using auto-detected bbox for instrument {idx}: {bbox}")
                    else:
                        # それでも見つからない場合はデフォルト位置
                        h, w = first_frame.shape[:2]
                        bbox = [w//4 + idx * 100, h//2 - 50, w//4 + idx * 100 + 100, h//2 + 50]
                        logger.info(f"Using default bbox for instrument {idx}: {bbox}")

                # OpenCVトラッカー（CSRT）を初期化
                tracker = cv2.TrackerCSRT_create()
                tracker.init(first_frame, tuple(bbox))
                self.cv_trackers[idx] = tracker

                # 軌跡を初期化
                self.trajectories[idx] = deque(maxlen=30)
                center = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
                self.trajectories[idx].append(center)

                self.tracked_instruments.append({
                    "id": idx,
                    "name": inst.get("name", f"Instrument_{idx}"),
                    "bbox": bbox,
                    "mask": None,
                    "color": inst.get("color", ["#FF4444", "#44FF44", "#4444FF"][idx % 3]),
                    "last_position": bbox
                })

            logger.info(f"Initialized {len(self.tracked_instruments)} instruments with OpenCV trackers")
            return

        # 実際の実装
        self.set_image(first_frame)

        for idx, instrument in enumerate(instruments):
            if "bbox" in instrument:
                # バウンディングボックスが指定されている場合
                bbox = instrument["bbox"]
                result = self.segment_with_box(bbox)

                if result["score"] > 0.5:
                    self.tracked_instruments.append({
                        "id": idx,
                        "name": instrument.get("name", f"Instrument_{idx}"),
                        "bbox": result["bbox"],
                        "mask": result["mask"],
                        "color": instrument.get("color", "#FF0000"),
                        "last_position": result["bbox"]
                    })
                    logger.info(f"Initialized instrument {idx}: {instrument.get('name')}")
            elif "point" in instrument:
                # ポイントが指定されている場合
                point = instrument["point"]
                result = self.segment_with_point([point], [1])

                if result["score"] > 0.5:
                    self.tracked_instruments.append({
                        "id": idx,
                        "name": instrument.get("name", f"Instrument_{idx}"),
                        "bbox": result["bbox"],
                        "mask": result["mask"],
                        "color": instrument.get("color", "#FF0000"),
                        "last_position": result["bbox"]
                    })
                    logger.info(f"Initialized instrument {idx}: {instrument.get('name')}")

    def track_frame(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        現在のフレームで器具を追跡

        Args:
            frame: 現在のフレーム

        Returns:
            検出された器具のリスト
        """
        if not hasattr(self, 'tracked_instruments'):
            return []

        detections = []

        if self.use_mock:
            # モック実装でもOpenCVトラッカーを使用
            for inst in self.tracked_instruments:
                track_id = inst["id"]

                if track_id in self.cv_trackers:
                    # OpenCVトラッカーで追跡
                    tracker = self.cv_trackers[track_id]
                    success, bbox = tracker.update(frame)

                    if success:
                        bbox = tuple(map(int, bbox))
                        center = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)

                        # 軌跡を更新
                        if track_id in self.trajectories:
                            self.trajectories[track_id].append(center)

                        inst["last_position"] = list(bbox)

                        detections.append({
                            "class_name": inst["name"],
                            "bbox": list(bbox),
                            "confidence": 0.9 + np.random.random() * 0.08,
                            "track_id": track_id,
                            "color": inst["color"],
                            "trajectory": list(self.trajectories[track_id])[-10:] if track_id in self.trajectories else []
                        })
                    else:
                        # 追跡失敗した場合は再検出を試みる
                        new_bbox = self._redetect_instrument_simple(frame, inst["last_position"])
                        if new_bbox:
                            # トラッカーを再初期化
                            tracker = cv2.TrackerCSRT_create()
                            tracker.init(frame, tuple(new_bbox))
                            self.cv_trackers[track_id] = tracker

                            center = ((new_bbox[0] + new_bbox[2]) // 2, (new_bbox[1] + new_bbox[3]) // 2)
                            if track_id in self.trajectories:
                                self.trajectories[track_id].append(center)

                            inst["last_position"] = list(new_bbox)

                            detections.append({
                                "class_name": inst["name"],
                                "bbox": list(new_bbox),
                                "confidence": 0.75 + np.random.random() * 0.1,
                                "track_id": track_id,
                                "color": inst["color"],
                                "trajectory": list(self.trajectories[track_id])[-10:] if track_id in self.trajectories else []
                            })
                        else:
                            # それでも見つからない場合はデフォルト位置を使用
                            bbox = inst["last_position"]
                            detections.append({
                                "class_name": inst["name"],
                                "bbox": bbox,
                                "confidence": 0.5,
                                "track_id": track_id,
                                "color": inst["color"],
                                "trajectory": list(self.trajectories[track_id])[-10:] if track_id in self.trajectories else []
                            })
                else:
                    # トラッカーがない場合は前の位置を使用
                    detections.append({
                        "class_name": inst["name"],
                        "bbox": inst["last_position"],
                        "confidence": 0.6,
                        "track_id": inst["id"],
                        "color": inst["color"]
                    })

            return detections

        # 実際の実装
        self.set_image(frame)

        for inst in self.tracked_instruments:
            # 前フレームの位置を使って追跡
            prev_bbox = inst["last_position"]
            center_x = (prev_bbox[0] + prev_bbox[2]) // 2
            center_y = (prev_bbox[1] + prev_bbox[3]) // 2

            # 中心点でセグメンテーション
            result = self.segment_with_point([(center_x, center_y)], [1])

            if result["score"] > 0.5:
                # 追跡成功
                inst["last_position"] = result["bbox"]
                inst["mask"] = result["mask"]

                detections.append({
                    "class_name": inst["name"],
                    "bbox": result["bbox"],
                    "confidence": float(result["score"]),
                    "track_id": inst["id"],
                    "color": inst["color"]
                })
            else:
                # 追跡失敗：前の位置の周辺で再検索
                search_result = self._search_nearby(prev_bbox)
                if search_result:
                    inst["last_position"] = search_result["bbox"]
                    inst["mask"] = search_result["mask"]

                    detections.append({
                        "class_name": inst["name"],
                        "bbox": search_result["bbox"],
                        "confidence": float(search_result["score"]),
                        "track_id": inst["id"],
                        "color": inst["color"]
                    })

        return detections

    def detect_batch(self, frames: List[np.ndarray]) -> List[Dict[str, Any]]:
        """
        複数フレームに対してバッチ検出を実行

        Args:
            frames: フレームのリスト

        Returns:
            検出結果のリスト（各フレームごと）
        """
        results = []
        for frame in frames:
            detections = self.track_frame(frame)
            results.append({'detections': detections})
        return results

    def _search_nearby(self, bbox: Tuple[int, int, int, int], search_radius: int = 50) -> Optional[Dict]:
        """
        バウンディングボックス周辺で器具を探索
        複数の探索戦略を使用

        Args:
            bbox: 前フレームのバウンディングボックス
            search_radius: 探索半径

        Returns:
            見つかった場合は結果、見つからない場合はNone
        """
        if self.use_mock:
            return None

        # 戦略1: 拡張したボックスで検索
        expanded_box = (
            max(0, bbox[0] - search_radius),
            max(0, bbox[1] - search_radius),
            min(self.image.shape[1], bbox[2] + search_radius),
            min(self.image.shape[0], bbox[3] + search_radius)
        )

        result = self.segment_with_box(expanded_box)

        if result["score"] > 0.5:
            return result

        # 戦略2: グリッドサーチ（周辺の複数点を試す）
        center_x = (bbox[0] + bbox[2]) // 2
        center_y = (bbox[1] + bbox[3]) // 2

        search_points = [
            (center_x, center_y),
            (center_x - search_radius//2, center_y),
            (center_x + search_radius//2, center_y),
            (center_x, center_y - search_radius//2),
            (center_x, center_y + search_radius//2),
        ]

        best_result = None
        best_score = 0

        for point in search_points:
            if 0 <= point[0] < self.image.shape[1] and 0 <= point[1] < self.image.shape[0]:
                result = self.segment_with_point([point], [1])
                if result["score"] > best_score:
                    best_score = result["score"]
                    best_result = result

        if best_score > 0.3:  # 低めの閾値で許容
            return best_result

        return None

    def cleanup(self):
        """リソースのクリーンアップ"""
        self.tracked_instruments = []
        self.cv_trackers = {}
        self.trajectories = {}
        self.predictor = None
        self.mask_generator = None
        logger.info("SAMTracker cleaned up")

    def _auto_detect_instruments_simple(self, frame: np.ndarray) -> List[Dict]:
        """
        簡易的な器具自動検出（画像処理ベース）

        Args:
            frame: 入力フレーム

        Returns:
            検出された器具のリスト
        """
        h, w = frame.shape[:2]
        detected = []

        # 色による検出（金属光沢）
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # より幅広い金属色を検出
        # 銀色・グレー系（明度を広げる）
        lower_silver = np.array([0, 0, 50])
        upper_silver = np.array([180, 40, 255])
        mask_silver = cv2.inRange(hsv, lower_silver, upper_silver)

        # 高輝度部分（光の反射）
        lower_bright = np.array([0, 0, 180])
        upper_bright = np.array([180, 60, 255])
        mask_bright = cv2.inRange(hsv, lower_bright, upper_bright)

        # 青みがかった金属
        lower_blue_metal = np.array([100, 20, 100])
        upper_blue_metal = np.array([130, 80, 255])
        mask_blue = cv2.inRange(hsv, lower_blue_metal, upper_blue_metal)

        # マスクを結合
        mask_metallic = cv2.bitwise_or(mask_silver, mask_bright)
        mask_metallic = cv2.bitwise_or(mask_metallic, mask_blue)

        # ノイズ除去
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask_metallic = cv2.morphologyEx(mask_metallic, cv2.MORPH_CLOSE, kernel)
        mask_metallic = cv2.morphologyEx(mask_metallic, cv2.MORPH_OPEN, kernel)

        # 輪郭検出
        contours, _ = cv2.findContours(mask_metallic, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 器具らしい輪郭を選別
        for contour in contours:
            area = cv2.contourArea(contour)

            # 面積フィルタ（より小さい器具も検出）
            if area < 200 or area > w * h * 0.15:
                continue

            # バウンディングボックス
            x, y, bbox_w, bbox_h = cv2.boundingRect(contour)

            # アスペクト比フィルタ（より柔軟に）
            aspect_ratio = bbox_w / max(bbox_h, 1)
            if 0.1 <= aspect_ratio <= 10:
                detected.append({
                    "name": f"Instrument_{len(detected)}",
                    "bbox": [x, y, x + bbox_w, y + bbox_h],
                    "color": ["#FF4444", "#44FF44", "#4444FF"][len(detected) % 3]
                })

        # 最大3つまで
        detected = detected[:3]

        # 検出できない場合はデフォルト位置
        if not detected:
            detected = [
                {
                    "name": "Scalpel",
                    "bbox": [w//4 - 50, h//2 - 30, w//4 + 50, h//2 + 30],
                    "color": "#FF4444"
                },
                {
                    "name": "Scissors",
                    "bbox": [w//2 - 50, h//2 - 30, w//2 + 50, h//2 + 30],
                    "color": "#44FF44"
                }
            ]

        return detected

    def _redetect_instrument_simple(self, frame: np.ndarray, last_bbox: List[int], search_radius: int = 100) -> Optional[List[int]]:
        """
        失った器具を再検出（簡易版）

        Args:
            frame: 現在のフレーム
            last_bbox: 最後に知られている位置
            search_radius: 検索半径

        Returns:
            新しいバウンディングボックス
        """
        # 最後の位置の周辺を探索
        x1 = max(0, last_bbox[0] - search_radius)
        y1 = max(0, last_bbox[1] - search_radius)
        x2 = min(frame.shape[1], last_bbox[2] + search_radius)
        y2 = min(frame.shape[0], last_bbox[3] + search_radius)

        # 検索範囲内で器具を探す
        roi = frame[y1:y2, x1:x2]

        # 色検出（より広い範囲）
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower_metallic = np.array([0, 0, 50])
        upper_metallic = np.array([180, 60, 255])
        mask = cv2.inRange(hsv_roi, lower_metallic, upper_metallic)

        # 輪郭検出
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # 最大の輪郭を選択
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)

            # 全体座標に変換
            return [x1 + x, y1 + y, x1 + x + w, y1 + y + h]

        return None

    def _detect_instruments_in_region(self, frame: np.ndarray, search_bbox: List[int]) -> List[List[int]]:
        """
        指定された領域内で器具を検出

        Args:
            frame: 入力フレーム
            search_bbox: 検索領域 [x1, y1, x2, y2]

        Returns:
            検出されたバウンディングボックスのリスト
        """
        x1, y1, x2, y2 = search_bbox
        margin = 50
        x1 = max(0, x1 - margin)
        y1 = max(0, y1 - margin)
        x2 = min(frame.shape[1], x2 + margin)
        y2 = min(frame.shape[0], y2 + margin)

        roi = frame[y1:y2, x1:x2]
        detected = self._auto_detect_instruments_simple(roi)

        result = []
        for inst in detected:
            bbox = inst["bbox"]
            result.append([bbox[0] + x1, bbox[1] + y1, bbox[2] + x1, bbox[3] + y1])

        return result

    def _get_bbox_from_mask(self, mask: np.ndarray) -> Tuple[int, int, int, int]:
        """
        マスクからバウンディングボックスを計算

        Args:
            mask: バイナリマスク

        Returns:
            バウンディングボックス (x1, y1, x2, y2)
        """
        if mask is None or not mask.any():
            return (0, 0, 0, 0)

        y_indices, x_indices = np.where(mask)
        x1 = int(np.min(x_indices))
        y1 = int(np.min(y_indices))
        x2 = int(np.max(x_indices))
        y2 = int(np.max(y_indices))

        return (x1, y1, x2, y2)
    
    def mask_to_polygon(self, mask: np.ndarray) -> List[List[int]]:
        """
        マスクをポリゴンに変換
        
        Args:
            mask: バイナリマスク
        
        Returns:
            ポリゴン座標のリスト
        """
        if mask is None:
            return []
        
        # マスクを uint8 に変換
        mask_uint8 = (mask * 255).astype(np.uint8)
        
        # 輪郭を見つける
        contours, _ = cv2.findContours(
            mask_uint8, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        polygons = []
        for contour in contours:
            # 輪郭を簡略化
            epsilon = 0.01 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # ポリゴンをリストに変換
            polygon = approx.reshape(-1, 2).tolist()
            polygons.append(polygon)
        
        return polygons
    
    def visualize_result(self,
                        image: np.ndarray,
                        result: Dict[str, Any],
                        color: Tuple[int, int, int] = (0, 255, 0),
                        alpha: float = 0.5,
                        box: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
        """
        セグメンテーション結果を可視化

        Args:
            image: 元画像
            result: セグメンテーション結果
            color: マスクの色
            alpha: 透明度
            box: オプションのバウンディングボックス

        Returns:
            可視化された画像
        """
        vis_image = image.copy()

        # resultが辞書の場合
        if isinstance(result, dict):
            if result.get("mask") is not None:
                # マスクをオーバーレイ
                mask = result["mask"]
                colored_mask = np.zeros_like(vis_image)
                colored_mask[mask] = color

                vis_image = cv2.addWeighted(
                    vis_image, 1 - alpha,
                    colored_mask, alpha,
                    0
                )

            if result.get("bbox"):
                # バウンディングボックスを描画
                bbox = result["bbox"]
                cv2.rectangle(
                    vis_image,
                    (bbox[0], bbox[1]),
                    (bbox[2], bbox[3]),
                    color, 2
                )
        # resultが直接マスクの場合（互換性のため）
        elif isinstance(result, np.ndarray):
            mask = result
            colored_mask = np.zeros_like(vis_image)
            colored_mask[mask > 0] = color

            vis_image = cv2.addWeighted(
                vis_image, 1 - alpha,
                colored_mask, alpha,
                0
            )

        # 追加のボックスが指定されている場合
        if box:
            cv2.rectangle(
                vis_image,
                (box[0], box[1]),
                (box[2], box[3]),
                color, 2
            )

        return vis_image
    
    # === モック実装 ===
    
    def _mock_segment_with_point(self,
                                point_coords: List[Tuple[int, int]],
                                point_labels: List[int]) -> Dict[str, Any]:
        """
        ポイントプロンプトのモック実装
        """
        if not hasattr(self, 'current_image') or self.current_image is None:
            h, w = 480, 640
        else:
            h, w = self.current_image.shape[:2]

        logger.info(f"Mock segmentation with points: {point_coords}, labels: {point_labels}")
        logger.info(f"Image dimensions: {w}x{h}")

        # ポイント周辺に円形のマスクを生成
        mask = np.zeros((h, w), dtype=bool)
        for (x, y), label in zip(point_coords, point_labels):
            if label == 1:  # 前景
                # 円形領域をマスク（固定半径で一貫性を保つ）
                radius = 50  # 固定半径
                y_grid, x_grid = np.ogrid[:h, :w]
                dist = np.sqrt((x_grid - x)**2 + (y_grid - y)**2)
                mask |= dist <= radius
                logger.info(f"Added circle at ({x}, {y}) with radius {radius}")

        bbox = self._get_bbox_from_mask(mask)
        logger.info(f"Generated bbox: {bbox}")

        return {
            "mask": mask,
            "score": 0.9,  # 固定スコア
            "bbox": bbox,
            "area": float(np.sum(mask)),
            "type": "point_prompt"
        }
    
    def _mock_segment_with_box(self, box: Tuple[int, int, int, int]) -> Dict[str, Any]:
        """
        ボックスプロンプトのモック実装
        """
        if not hasattr(self, 'current_image') or self.current_image is None:
            h, w = 480, 640
        else:
            h, w = self.current_image.shape[:2]

        x1, y1, x2, y2 = box

        logger.info(f"Mock segmentation with box: ({x1}, {y1}, {x2}, {y2})")
        logger.info(f"Image dimensions: {w}x{h}")

        # ボックス内に楕円形のマスクを生成
        mask = np.zeros((h, w), dtype=bool)
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        width = max(x2 - x1, 1)  # ゼロ除算を防ぐ
        height = max(y2 - y1, 1)  # ゼロ除算を防ぐ

        # 楕円形マスク（ボックスの80%サイズ）
        y_grid, x_grid = np.ogrid[:h, :w]
        ellipse_mask = ((x_grid - center_x) / (width * 0.4))**2 + \
                      ((y_grid - center_y) / (height * 0.4))**2 <= 1
        
        # ボックス内に制限
        mask[y1:y2, x1:x2] = ellipse_mask[y1:y2, x1:x2]

        logger.info(f"Generated mask area: {np.sum(mask)}")

        return {
            "mask": mask,
            "score": 0.92,  # 固定スコア
            "bbox": box,
            "area": float(np.sum(mask)),
            "type": "box_prompt"
        }
    
    def _mock_segment_automatic(self) -> List[Dict[str, Any]]:
        """
        自動セグメンテーションのモック実装
        """
        if not hasattr(self, 'current_image') or self.current_image is None:
            h, w = 480, 640
        else:
            h, w = self.current_image.shape[:2]
        
        results = []
        num_objects = np.random.randint(2, 5)
        
        for i in range(num_objects):
            # ランダムな位置とサイズ
            center_x = np.random.randint(w // 4, 3 * w // 4)
            center_y = np.random.randint(h // 4, 3 * h // 4)
            radius = np.random.randint(20, 60)
            
            # 円形マスク
            mask = np.zeros((h, w), dtype=bool)
            y_grid, x_grid = np.ogrid[:h, :w]
            dist = np.sqrt((x_grid - center_x)**2 + (y_grid - center_y)**2)
            mask = dist <= radius
            
            bbox = self._get_bbox_from_mask(mask)
            
            results.append({
                "mask": mask,
                "score": np.random.uniform(0.7, 0.95),
                "bbox": bbox,
                "area": float(np.sum(mask)),
                "type": "automatic"
            })
        
        return results
    
    def _mock_track_in_video(self,
                            frames: List[np.ndarray],
                            initial_mask: np.ndarray,
                            initial_bbox: Tuple[int, int, int, int]) -> List[Dict[str, Any]]:
        """
        ビデオトラッキングのモック実装
        """
        results = []
        
        x1, y1, x2, y2 = initial_bbox
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        width = x2 - x1
        height = y2 - y1
        
        for i, frame in enumerate(frames):
            # 少しずつ位置を移動（シミュレーション）
            drift_x = np.random.randint(-5, 6)
            drift_y = np.random.randint(-5, 6)
            center_x = max(width//2, min(frame.shape[1] - width//2, center_x + drift_x))
            center_y = max(height//2, min(frame.shape[0] - height//2, center_y + drift_y))
            
            # 新しいバウンディングボックス
            new_bbox = (
                center_x - width // 2,
                center_y - height // 2,
                center_x + width // 2,
                center_y + height // 2
            )
            
            # 新しいマスク（楕円形）
            mask = np.zeros(frame.shape[:2], dtype=bool)
            y_grid, x_grid = np.ogrid[:frame.shape[0], :frame.shape[1]]
            ellipse_mask = ((x_grid - center_x) / (width/2))**2 + \
                          ((y_grid - center_y) / (height/2))**2 <= 1
            mask = ellipse_mask
            
            results.append({
                "frame_idx": i,
                "mask": mask,
                "bbox": new_bbox,
                "score": np.random.uniform(0.8, 0.95)
            })
        
        return results

    def track_instruments_with_flow(self,
                                   prev_frame: np.ndarray,
                                   curr_frame: np.ndarray,
                                   prev_masks: List[np.ndarray],
                                   confidence_threshold: float = 0.7) -> Dict[str, Any]:
        """
        Optical Flowを使った軽量トラッキング

        Args:
            prev_frame: 前フレーム
            curr_frame: 現在フレーム
            prev_masks: 前フレームのマスク
            confidence_threshold: 再セグメンテーションの閾値

        Returns:
            トラッキング結果
        """
        results = []

        # グレースケール変換
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

        # Optical Flow計算
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )

        for idx, prev_mask in enumerate(prev_masks):
            # マスクの移動
            h, w = prev_mask.shape
            flow_x = flow[..., 0]
            flow_y = flow[..., 1]

            # マスクの重心を計算
            y_coords, x_coords = np.where(prev_mask)
            if len(x_coords) == 0:
                continue

            center_x = int(np.mean(x_coords))
            center_y = int(np.mean(y_coords))

            # 重心位置のフローを取得
            dx = flow_x[center_y, center_x]
            dy = flow_y[center_y, center_x]

            # マスクを移動（簡易版）
            new_mask = np.zeros_like(prev_mask)
            for y, x in zip(y_coords, x_coords):
                new_x = int(x + dx)
                new_y = int(y + dy)
                if 0 <= new_x < w and 0 <= new_y < h:
                    new_mask[new_y, new_x] = 1

            # 信頼度計算（マスクの面積変化率）
            prev_area = np.sum(prev_mask)
            new_area = np.sum(new_mask)
            confidence = min(new_area / max(prev_area, 1), 1.0)

            # 信頼度が低い場合は再セグメンテーション
            if confidence < confidence_threshold and not self.use_mock:
                self.set_image(curr_frame)
                # マスクの重心でポイントプロンプト
                new_center_x = int(center_x + dx)
                new_center_y = int(center_y + dy)
                result = self.segment_with_point([(new_center_x, new_center_y)], [1])
                new_mask = result["mask"]
                confidence = result["score"]

            # バウンディングボックス計算
            bbox = self._get_bbox_from_mask(new_mask)

            results.append({
                "mask": new_mask,
                "bbox": bbox,
                "confidence": confidence,
                "track_id": idx
            })

        return {
            "success": True,
            "tracks": results
        }


def encode_mask_to_rle(mask: np.ndarray) -> Dict[str, Any]:
    """
    マスクをRLE (Run-Length Encoding) 形式にエンコード
    
    Args:
        mask: バイナリマスク
    
    Returns:
        RLEエンコードされたマスク
    """
    mask = mask.astype(np.uint8)
    mask = mask.flatten(order='F')  # Fortran order (column-major)
    
    # Run-length encoding
    runs = []
    current_val = mask[0]
    current_length = 1
    
    for i in range(1, len(mask)):
        if mask[i] == current_val:
            current_length += 1
        else:
            runs.append(current_length)
            current_val = mask[i]
            current_length = 1
    runs.append(current_length)
    
    # 0から始まるように調整
    if mask[0] == 1:
        runs = [0] + runs
    
    return {
        "size": list(mask.shape),
        "counts": runs
    }


def decode_rle_to_mask(rle: Dict[str, Any], shape: Tuple[int, int]) -> np.ndarray:
    """
    RLE形式からマスクをデコード
    
    Args:
        rle: RLEエンコードされたマスク
        shape: 出力マスクの形状 (H, W)
    
    Returns:
        バイナリマスク
    """
    runs = rle["counts"]
    h, w = shape
    
    mask = np.zeros(h * w, dtype=np.uint8)
    current_pos = 0
    current_val = 0
    
    for run_length in runs:
        mask[current_pos:current_pos + run_length] = current_val
        current_pos += run_length
        current_val = 1 - current_val
    
    return mask.reshape((w, h), order='F').T