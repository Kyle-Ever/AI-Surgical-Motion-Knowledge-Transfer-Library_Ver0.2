"""
SAM2 (Segment Anything Model 2) Video Tracker
One-Shot Learning対応のビデオ追跡モジュール

特徴:
- ユーザー選択マスクを参照として学習
- メモリバンク機構でフレーム間一貫性を保持
- オクルージョンに強い追跡
- Real-time処理対応
"""

import cv2
import numpy as np
import torch
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path
from collections import deque
import base64
from io import BytesIO
from PIL import Image

# SAM2のインポート
try:
    from sam2.build_sam import build_sam2_video_predictor
    SAM2_AVAILABLE = True
except ImportError:
    SAM2_AVAILABLE = False
    logging.error("SAM2 library not available. Please install: pip install sam2")

logger = logging.getLogger(__name__)


class SAM2Tracker:
    """SAM2 Video Tracker

    特徴:
    - One-Shot Learning: ユーザー選択マスクから器具を学習
    - Memory Bank: 過去フレームを記憶し、フレーム間一貫性を保持
    - Occlusion Robust: 器具が一時的に隠れても再出現時に追跡継続
    - Real-time Ready: Efficient Frame Pruning対応
    """

    def __init__(self,
                 model_type: str = "small",  # "tiny", "small", "base_plus", "large"
                 checkpoint_path: Optional[str] = None,
                 config_path: Optional[str] = None,
                 device: str = "cuda"):
        """
        初期化

        Args:
            model_type: SAM2モデルタイプ ("tiny", "small", "base_plus", "large")
            checkpoint_path: モデルチェックポイントのパス
            config_path: 設定ファイルのパス
            device: 使用デバイス ("cuda" 推奨 for RTX 3060, "cpu" フォールバック)
        """
        if not SAM2_AVAILABLE:
            raise RuntimeError(
                "SAM2 library is not installed. "
                "Please install: pip install sam2"
            )

        # GPU自動検出とフォールバック
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU")
            device = "cpu"
            if model_type == "large":
                logger.warning("Downgrading to small for CPU performance")
                model_type = "small"
        elif device == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"Using GPU: {gpu_name} ({vram_gb:.1f}GB VRAM)")

        self.model_type = model_type
        self.device = device
        self.predictor = None
        self.inference_state = None

        # トラッキング状態
        self.tracked_instruments: List[Dict[str, Any]] = []
        self.trajectories: Dict[int, deque] = {}
        self.current_frame_idx = 0

        # detect_batch用の器具ID管理
        self.instrument_ids: List[int] = []

        # 参照マスク（One-Shot Learning用）
        self.reference_masks: Dict[int, np.ndarray] = {}

        # SAM2モデルのロード
        self._load_sam2_model(checkpoint_path, config_path)

    def _load_sam2_model(self, checkpoint_path: Optional[str], config_path: Optional[str]) -> None:
        """SAM2モデルをロード"""
        try:
            # デフォルトのチェックポイントパス
            if checkpoint_path is None:
                model_files = {
                    "tiny": "sam2.1_hiera_tiny.pt",
                    "small": "sam2.1_hiera_small.pt",
                    "base_plus": "sam2.1_hiera_base_plus.pt",
                    "large": "sam2.1_hiera_large.pt"
                }
                checkpoint_path = Path(model_files.get(self.model_type, "sam2.1_hiera_small.pt"))
                if not checkpoint_path.exists():
                    checkpoint_path = Path("backend") / checkpoint_path
            else:
                checkpoint_path = Path(checkpoint_path)

            if not checkpoint_path.exists():
                raise FileNotFoundError(
                    f"SAM2 {self.model_type} checkpoint not found at {checkpoint_path}. "
                    f"Please download from https://dl.fbaipublicfiles.com/segment_anything_2/"
                )

            # デフォルトの設定ファイルパス
            if config_path is None:
                config_files = {
                    "tiny": "configs/sam2.1/sam2.1_hiera_t.yaml",
                    "small": "configs/sam2.1/sam2.1_hiera_s.yaml",
                    "base_plus": "configs/sam2.1/sam2.1_hiera_b+.yaml",
                    "large": "configs/sam2.1/sam2.1_hiera_l.yaml"
                }
                config_path = config_files.get(self.model_type, "configs/sam2.1/sam2.1_hiera_s.yaml")

            logger.info(f"Loading SAM2 {self.model_type} model from {checkpoint_path}")

            # SAM2 Video Predictor構築
            self.predictor = build_sam2_video_predictor(
                config_path,
                str(checkpoint_path),
                device=self.device
            )

            if self.device == "cuda":
                allocated_mb = torch.cuda.memory_allocated() / 1024**2
                logger.info(f"SAM2 {self.model_type} loaded on GPU: {allocated_mb:.1f}MB VRAM allocated")
            else:
                logger.info(f"SAM2 {self.model_type} loaded on CPU")

        except Exception as e:
            logger.error(f"Failed to load SAM2 model: {e}")
            raise

    def _decode_mask(self, mask_b64: str) -> np.ndarray:
        """base64エンコードされたマスクをデコード

        Args:
            mask_b64: base64エンコードされたマスク画像（PNG形式）

        Returns:
            マスク配列 (H, W) のバイナリマスク
        """
        try:
            # base64デコード
            mask_bytes = base64.b64decode(mask_b64)

            # PNG画像として読み込み
            image = Image.open(BytesIO(mask_bytes))

            # numpy配列に変換（グレースケール）
            mask_array = np.array(image.convert('L'))

            # バイナリマスクに変換（0 or 1）
            mask_binary = (mask_array > 0).astype(np.uint8)

            logger.debug(f"Decoded mask shape: {mask_binary.shape}, non-zero pixels: {np.sum(mask_binary)}")
            return mask_binary

        except Exception as e:
            logger.error(f"Failed to decode mask from base64: {e}")
            raise ValueError(f"Invalid mask data: {e}")

    def initialize_from_frames(
        self,
        frames: List[np.ndarray],
        instruments: List[Dict[str, Any]]
    ) -> None:
        """フレーム配列から初期化（One-Shot Learning）

        Args:
            frames: ビデオフレームのリスト
            instruments: 器具選択情報のリスト
                [{
                    "id": int,
                    "name": str,
                    "selection": {"type": "mask" | "point" | "box", "data": ...},
                    "color": str
                }]
        """
        logger.info(f"Initializing SAM2 tracker with {len(frames)} frames, {len(instruments)} instruments")

        # SAM2のinference state初期化
        with torch.inference_mode(), torch.autocast(self.device, dtype=torch.bfloat16):
            # フレームリストから inference state を作成
            self.inference_state = self.predictor.init_state(
                video_path=frames,  # SAM2はフレームリストも受け入れ可能
                async_loading_frames=False
            )

            # 各器具について初期プロンプトを追加（Frame 0）
            for idx, instrument in enumerate(instruments):
                obj_id = instrument.get("id", idx)
                selection = instrument.get("selection", {})
                sel_type = selection.get("type")

                # 器具情報を保存
                self.tracked_instruments.append({
                    "id": obj_id,
                    "name": instrument.get("name", f"instrument_{obj_id}"),
                    "color": instrument.get("color", "#00FF00")
                })

                # 軌跡デキュー初期化
                self.trajectories[obj_id] = deque(maxlen=50)

                if sel_type == "mask":
                    # マスク選択（最も正確）
                    mask_b64 = selection.get("data")
                    if not mask_b64:
                        logger.warning(f"Instrument {idx} has no mask data")
                        continue

                    try:
                        # base64マスクをデコード
                        mask = self._decode_mask(mask_b64)

                        # 参照マスクとして保存（One-Shot Learning）
                        self.reference_masks[obj_id] = mask

                        # SAM2にマスクプロンプトを追加
                        _, out_obj_ids, out_mask_logits = self.predictor.add_new_mask(
                            inference_state=self.inference_state,
                            frame_idx=0,
                            obj_id=obj_id,
                            mask=mask
                        )

                        logger.info(f"Instrument {idx} initialized with mask (obj_id={obj_id})")

                    except Exception as e:
                        logger.error(f"Failed to initialize instrument {idx} with mask: {e}")
                        continue

                elif sel_type == "point":
                    # ポイント選択
                    points = selection.get("data", [])
                    if not points:
                        logger.warning(f"Instrument {idx} has no points")
                        continue

                    # ポイントをnumpy配列に変換
                    points_np = np.array(points, dtype=np.float32)
                    labels_np = np.ones(len(points), dtype=np.int32)  # すべて前景

                    # SAM2にポイントプロンプトを追加
                    _, out_obj_ids, out_mask_logits = self.predictor.add_new_points(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        points=points_np,
                        labels=labels_np
                    )

                    logger.info(f"Instrument {idx} initialized with {len(points)} points (obj_id={obj_id})")

                elif sel_type == "box":
                    # ボックス選択
                    box = selection.get("data")
                    if not box:
                        logger.warning(f"Instrument {idx} has no box")
                        continue

                    # SAM2にボックスプロンプトを追加
                    _, out_obj_ids, out_mask_logits = self.predictor.add_new_points(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        points=None,
                        labels=None,
                        box=np.array(box, dtype=np.float32)
                    )

                    logger.info(f"Instrument {idx} initialized with box (obj_id={obj_id})")

                else:
                    logger.error(f"Unknown selection type: {sel_type}")
                    continue

        logger.info(f"SAM2 tracker initialized successfully with {len(self.tracked_instruments)} instruments")

    def initialize_instruments(
        self,
        instruments: List[Dict[str, Any]],
        first_frame: np.ndarray
    ) -> None:
        """器具を初期化（detect_batch用）

        Args:
            instruments: 器具情報リスト
                [{"bbox": [x1, y1, x2, y2], "mask": np.ndarray (optional)}]
            first_frame: 初期フレーム（未使用、互換性のため保持）
        """
        logger.info(f"Initializing {len(instruments)} instruments for SAM2")

        with torch.inference_mode(), torch.autocast(self.device, dtype=torch.bfloat16):
            for idx, instrument in enumerate(instruments):
                obj_id = idx
                self.instrument_ids.append(obj_id)

                # BBoxプロンプト
                bbox = instrument.get("bbox")
                if bbox is not None:
                    # SAM2にボックスプロンプトを追加
                    _, out_obj_ids, out_mask_logits = self.predictor.add_new_points(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        points=None,
                        labels=None,
                        box=np.array(bbox, dtype=np.float32)
                    )
                    logger.debug(f"Instrument {idx} initialized with bbox {bbox}")

                # マスクがあれば使用（高精度）
                mask = instrument.get("mask")
                if mask is not None:
                    self.reference_masks[obj_id] = mask
                    logger.debug(f"Instrument {idx} reference mask stored")

        logger.info(f"Initialized {len(self.instrument_ids)} instruments")

    def track_all_frames(self) -> List[Dict[str, Any]]:
        """全フレームで器具を追跡

        Returns:
            フレームごとの検出結果リスト
            [{
                "frame_number": int,
                "detections": [{
                    "class_name": str,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float,
                    "track_id": int,
                    "color": str,
                    "mask": np.ndarray,
                    "tip_point": [x, y]
                }]
            }]
        """
        results = []

        logger.info("Starting SAM2 video propagation...")

        with torch.inference_mode(), torch.autocast(self.device, dtype=torch.bfloat16):
            # SAM2のメモリバンク機構で全フレームに伝播
            for frame_idx, object_ids, masks in self.predictor.propagate_in_video(self.inference_state):
                frame_detections = []

                for obj_id, mask_logits in zip(object_ids, masks):
                    # マスクlogitsを2値マスクに変換
                    mask = (mask_logits > 0.0).cpu().numpy().squeeze()

                    if mask.sum() == 0:
                        logger.debug(f"Frame {frame_idx}, obj {obj_id}: Empty mask, skipping")
                        continue

                    # マスクからBBoxを計算
                    bbox = self._compute_bbox_from_mask(mask)

                    # 先端点を検出
                    tip_point = self._detect_instrument_tip(mask, bbox)

                    # Rotated BBox計算
                    rotated_info = self._compute_rotated_bbox(mask)

                    # 軌跡に追加
                    centroid = self._get_bbox_center(bbox)
                    self.trajectories[obj_id].append(centroid)

                    # 器具情報を検索
                    inst_info = next((inst for inst in self.tracked_instruments if inst["id"] == obj_id), None)
                    if not inst_info:
                        logger.warning(f"Instrument info not found for obj_id={obj_id}")
                        continue

                    frame_detections.append({
                        "class_name": inst_info["name"],
                        "bbox": bbox,
                        "rotated_bbox": rotated_info["rotated_bbox"],
                        "rotation_angle": rotated_info["rotation_angle"],
                        "area_reduction": rotated_info["area_reduction"],
                        "confidence": 0.95,  # SAM2は高信頼度
                        "track_id": obj_id,
                        "color": inst_info["color"],
                        "trajectory": list(self.trajectories[obj_id])[-10:],
                        "tip_point": list(tip_point) if tip_point else None,
                        "tip_confidence": 0.95 if tip_point else 0.0
                    })

                results.append({
                    "frame_number": frame_idx,
                    "detections": frame_detections
                })

                if frame_idx % 30 == 0:
                    logger.info(f"Processed frame {frame_idx}, {len(frame_detections)} detections")

        logger.info(f"SAM2 tracking completed: {len(results)} frames processed")
        return results

    def _compute_bbox_from_mask(self, mask: np.ndarray) -> List[int]:
        """マスクからBBoxを計算

        Args:
            mask: バイナリマスク (H, W)

        Returns:
            [x1, y1, x2, y2]
        """
        if mask.sum() == 0:
            return [0, 0, 0, 0]

        y_coords, x_coords = np.where(mask > 0)
        x1, y1 = int(x_coords.min()), int(y_coords.min())
        x2, y2 = int(x_coords.max()), int(y_coords.max())

        return [x1, y1, x2, y2]

    def _compute_rotated_bbox(self, mask: np.ndarray) -> Dict[str, Any]:
        """回転BBoxを計算

        Args:
            mask: バイナリマスク

        Returns:
            {
                "rotated_bbox": [[x, y], ...],  # 4点の座標
                "rotation_angle": float,
                "area_reduction": float  # 通常BBoxとの面積比
            }
        """
        mask_binary = (mask > 0).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return {
                "rotated_bbox": [[0, 0], [0, 0], [0, 0], [0, 0]],
                "rotation_angle": 0.0,
                "area_reduction": 0.0
            }

        largest_contour = max(contours, key=cv2.contourArea)
        rotated_rect = cv2.minAreaRect(largest_contour)
        box_points = cv2.boxPoints(rotated_rect)

        # 通常のBBoxと比較
        normal_bbox = self._compute_bbox_from_mask(mask)
        normal_area = (normal_bbox[2] - normal_bbox[0]) * (normal_bbox[3] - normal_bbox[1])
        rotated_area = rotated_rect[1][0] * rotated_rect[1][1]

        area_reduction = 1.0 - (rotated_area / normal_area) if normal_area > 0 else 0.0

        return {
            "rotated_bbox": box_points.tolist(),
            "rotation_angle": float(rotated_rect[2]),
            "area_reduction": float(area_reduction)
        }

    def _detect_instrument_tip(self, mask: np.ndarray, bbox: List[int]) -> Optional[Tuple[int, int]]:
        """器具の先端点を検出（PCA + 輪郭解析）

        Args:
            mask: バイナリマスク
            bbox: [x1, y1, x2, y2]

        Returns:
            (x, y) 先端座標、失敗時はNone
        """
        if mask.sum() == 0:
            return None

        try:
            # 輪郭抽出
            mask_binary = (mask > 0).astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                return None

            contour = max(contours, key=cv2.contourArea)

            # PCAで主軸を計算
            y_coords, x_coords = np.where(mask > 0)
            if len(x_coords) < 5:
                return None

            coords = np.column_stack([x_coords, y_coords])
            mean, eigenvectors = cv2.PCACompute(coords.astype(np.float32), mean=None)
            principal_axis = eigenvectors[0]

            # 重心計算
            moments = cv2.moments(mask_binary)
            if moments["m00"] == 0:
                return None

            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])

            # 輪郭上で主軸方向の最遠点を検出
            max_dist = -1
            tip_point = None

            for pt in contour:
                pt_coord = pt[0]
                rel_pos = pt_coord - np.array([cx, cy])
                projection = np.dot(rel_pos, principal_axis)

                if projection > 0 and projection > max_dist:
                    max_dist = projection
                    tip_point = tuple(pt_coord)

            # フォールバック: 負の方向も確認
            if tip_point is None:
                for pt in contour:
                    pt_coord = pt[0]
                    rel_pos = pt_coord - np.array([cx, cy])
                    projection = np.dot(rel_pos, principal_axis)

                    if projection < 0 and abs(projection) > max_dist:
                        max_dist = abs(projection)
                        tip_point = tuple(pt_coord)

            # BBox内に存在するか確認
            if tip_point is not None:
                x1, y1, x2, y2 = bbox
                tx, ty = tip_point

                if x1 <= tx <= x2 and y1 <= ty <= y2:
                    return tip_point
                else:
                    logger.debug(f"Tip point ({tx}, {ty}) outside bbox {bbox}, using centroid")
                    return (cx, cy)

            # フォールバック: 重心
            return (cx, cy)

        except Exception as e:
            logger.warning(f"Tip detection error: {e}, using bbox center")
            return self._get_bbox_center(bbox)

    def detect_batch(
        self,
        frames: List[np.ndarray],
        instruments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """フレームバッチ解析（SAMTrackerUnified互換インターフェース）

        Args:
            frames: フレーム配列リスト
            instruments: 器具情報リスト
                - bbox: 初期BBox [x1, y1, x2, y2]
                - mask: 初期マスク (optional)

        Returns:
            {
                "instrument_data": [
                    {
                        "frame_number": int,
                        "detections": [
                            {
                                "bbox": [x1, y1, x2, y2],
                                "mask": np.ndarray,
                                "confidence": float,
                                "rotated_bbox": [(x1,y1), (x2,y2), (x3,y3), (x4,y4)],
                                "tip_point": (x, y),
                                "tip_confidence": float
                            }
                        ]
                    }
                ]
            }
        """
        from app.utils.temp_frame_storage import TemporaryFrameStorage

        logger.info(f"SAM2 detect_batch: {len(frames)} frames, {len(instruments)} instruments")

        # 解析IDを生成（タイムスタンプベース）
        import time
        analysis_id = f"sam2_{int(time.time() * 1000)}"

        # 一時フレームストレージ作成
        storage = TemporaryFrameStorage(analysis_id)

        try:
            # JPEG保存
            logger.info(f"Saving {len(frames)} frames as JPEG (quality=95)")
            jpeg_dir = storage.save_frames(frames, quality=95, parallel=True)
            logger.info(f"JPEG folder created: {jpeg_dir}")

            # SAM2初期化
            logger.info("Initializing SAM2 Video Predictor")
            self.inference_state = self.predictor.init_state(
                video_path=str(jpeg_dir),
                async_loading_frames=False
            )
            logger.info("SAM2 inference state initialized")

            # 器具を登録
            self.initialize_instruments(instruments, frames[0])
            logger.info(f"Initialized {len(self.instrument_ids)} instruments")

            # SAM2で全フレームを処理（propagate_in_videoは一度に全フレーム処理）
            logger.info(f"Running SAM2 propagation on {len(frames)} frames...")
            results = []

            # propagate_in_videoはイテレータを返す（各フレームごと）
            with torch.inference_mode(), torch.autocast(self.device, dtype=torch.bfloat16):
                for frame_idx, object_ids, mask_logits in self.predictor.propagate_in_video(
                    self.inference_state
                ):
                    frame_detections = []

                    # 各器具について処理
                    for inst_id in self.instrument_ids:
                        try:
                            # 該当器具のマスクを取得
                            if inst_id in object_ids:
                                obj_idx = list(object_ids).index(inst_id)
                                mask_logit = mask_logits[obj_idx]

                                # logitsを2値マスクに変換
                                mask = (mask_logit > 0.0).cpu().numpy().squeeze()

                                if mask.sum() == 0:
                                    logger.debug(f"Frame {frame_idx} instrument {inst_id}: empty mask")
                                    continue

                                # マスク → BBox変換
                                bbox = self._mask_to_bbox(mask)

                                if bbox is not None:
                                    # 回転BBox計算
                                    rotated_bbox = self._get_rotated_bbox(mask)

                                    # Tip検出
                                    tip_point = self._detect_instrument_tip(mask, bbox)
                                    tip_confidence = 0.9 if tip_point is not None else 0.0

                                    # 信頼度計算（マスク面積ベース）
                                    confidence = float(np.sum(mask)) / (mask.shape[0] * mask.shape[1])

                                    frame_detections.append({
                                        "bbox": bbox,
                                        "mask": mask,
                                        "confidence": confidence,
                                        "rotated_bbox": rotated_bbox,
                                        "tip_point": tip_point,
                                        "tip_confidence": tip_confidence
                                    })

                        except Exception as e:
                            logger.warning(f"Frame {frame_idx} instrument {inst_id} error: {e}")
                            continue

                    results.append({
                        "frame_number": frame_idx,
                        "detections": frame_detections
                    })

            logger.info(f"SAM2 batch detection completed: {len(results)} frames")

            return {
                "instrument_data": results
            }

        finally:
            # 一時フォルダクリーンアップ
            logger.info("Cleaning up temporary JPEG files")
            storage.cleanup(ignore_errors=True)

    def _mask_to_bbox(self, mask: np.ndarray) -> Optional[List[int]]:
        """マスクからBBoxを計算

        Args:
            mask: セグメンテーションマスク (H, W)

        Returns:
            [x1, y1, x2, y2] or None
        """
        if mask is None or mask.sum() == 0:
            return None

        # マスクの座標を取得
        coords = np.argwhere(mask > 0.5)

        if len(coords) == 0:
            return None

        # BBox計算
        y_coords = coords[:, 0]
        x_coords = coords[:, 1]

        x1 = int(x_coords.min())
        y1 = int(y_coords.min())
        x2 = int(x_coords.max())
        y2 = int(y_coords.max())

        return [x1, y1, x2, y2]

    def _get_rotated_bbox(self, mask: np.ndarray) -> List[List[int]]:
        """マスクから回転BBoxを計算

        Args:
            mask: セグメンテーションマスク (H, W)

        Returns:
            [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        if mask.sum() == 0:
            return [[0, 0], [0, 0], [0, 0], [0, 0]]

        try:
            # バイナリマスクに変換
            mask_binary = (mask > 0).astype(np.uint8) * 255

            # 輪郭抽出
            contours, _ = cv2.findContours(
                mask_binary,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                # フォールバック: 通常のBBox
                bbox = self._mask_to_bbox(mask)
                if bbox is None:
                    return [[0, 0], [0, 0], [0, 0], [0, 0]]
                return [
                    [bbox[0], bbox[1]],
                    [bbox[2], bbox[1]],
                    [bbox[2], bbox[3]],
                    [bbox[0], bbox[3]]
                ]

            # 最大輪郭を取得
            largest_contour = max(contours, key=cv2.contourArea)

            # 回転矩形を計算
            rect = cv2.minAreaRect(largest_contour)

            # 4点の座標を取得
            box_points = cv2.boxPoints(rect)
            box_points = np.intp(box_points)

            # リスト形式に変換
            rotated_bbox = [[int(pt[0]), int(pt[1])] for pt in box_points]

            return rotated_bbox

        except Exception as e:
            logger.warning(f"Rotated bbox calculation failed: {e}, using regular bbox")
            bbox = self._mask_to_bbox(mask)
            if bbox is None:
                return [[0, 0], [0, 0], [0, 0], [0, 0]]
            return [
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]]
            ]

    def _get_bbox_center(self, bbox: List[int]) -> Tuple[int, int]:
        """BBoxの中心座標を計算"""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)
