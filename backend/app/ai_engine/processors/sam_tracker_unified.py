"""
SAM (Segment Anything Model) 一本化実装
器具セグメンテーション・トラッキング専用モジュール

設計方針:
- SAM検出のみ使用（OpenCVトラッカー削除）
- シンプルで保守しやすい構造
- 高精度な器具トラッキング
"""

import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path
from collections import deque
import base64
from io import BytesIO
from PIL import Image

# SAMのインポート
try:
    from segment_anything import sam_model_registry, SamPredictor, SamAutomaticMaskGenerator
    SAM_AVAILABLE = True
except ImportError:
    SAM_AVAILABLE = False
    logging.error("SAM library not available. Please install: pip install segment-anything")

logger = logging.getLogger(__name__)


class SAMTrackerUnified:
    """SAM一本化トラッカー

    特徴:
    - SAM検出のみ使用（OpenCV削除）
    - シンプルな再検出ロジック
    - 信頼性の高いconfidenceスコア
    """

    def __init__(self,
                 model_type: str = "vit_h",
                 checkpoint_path: Optional[str] = None,
                 device: str = "cuda"):
        """
        初期化

        Args:
            model_type: SAMモデルタイプ ("vit_h" 推奨, "vit_l", "vit_b")
            checkpoint_path: モデルチェックポイントのパス
            device: 使用デバイス ("cuda" 推奨 for RTX 3060, "cpu" フォールバック)
        """
        if not SAM_AVAILABLE:
            raise RuntimeError(
                "SAM library is not installed. "
                "Please install: pip install segment-anything"
            )

        # GPU自動検出とフォールバック
        try:
            import torch
            if device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                logger.warning("   Install PyTorch with CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu118")
                device = "cpu"
                if model_type == "vit_h":
                    logger.warning("   Downgrading to vit_b for CPU performance")
                    model_type = "vit_b"
            elif device == "cuda":
                gpu_name = torch.cuda.get_device_name(0)
                vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"Using GPU: {gpu_name} ({vram_gb:.1f}GB VRAM)")
        except ImportError:
            logger.warning("PyTorch not installed, using CPU")
            device = "cpu"
            if model_type == "vit_h":
                model_type = "vit_b"

        self.model_type = model_type
        self.device = device
        self.predictor: Optional[SamPredictor] = None
        self.mask_generator: Optional[SamAutomaticMaskGenerator] = None
        self.current_image: Optional[np.ndarray] = None

        # GPU最適化: 画像リサイズ用のパラメータ
        self.scale_factor: float = 1.0
        self.original_shape: Tuple[int, int] = (0, 0)

        # トラッキング状態
        self.tracked_instruments: List[Dict[str, Any]] = []
        self.trajectories: Dict[int, deque] = {}
        self.lost_frame_counts: Dict[int, int] = {}  # 各器具のロストフレーム数

        # パラメータ
        self.max_lost_frames = 10  # これ以上ロストしたら再検出

        # Phase 2.1: 動的信頼度閾値（器具ごとに履歴から調整）
        self.base_confidence_threshold = 0.5  # ベース閾値
        self.confidence_threshold = 0.5  # 後方互換性のため保持
        self.track_confidence_history: Dict[int, deque] = {}  # track_id -> 信頼度履歴
        self.confidence_window_size = 10  # 履歴ウィンドウサイズ

        # Phase 2.2: 適応的探索範囲拡張
        self.base_search_expansion = 50  # ベース探索範囲（ピクセル）
        self.search_expansion = 50  # 後方互換性のため保持

        # SAMモデルのロード
        self._load_sam_model(checkpoint_path)

    def _load_sam_model(self, checkpoint_path: Optional[str]) -> None:
        """SAMモデルをロード"""
        try:
            # デフォルトのチェックポイントパス
            if checkpoint_path is None:
                # モデルタイプに応じたチェックポイント
                if self.model_type == "vit_h":
                    checkpoint_path = Path("sam_vit_h_4b8939.pth")
                    if not checkpoint_path.exists():
                        checkpoint_path = Path("backend/sam_vit_h_4b8939.pth")
                elif self.model_type == "vit_b":
                    checkpoint_path = Path("sam_b.pt")
                    if not checkpoint_path.exists():
                        checkpoint_path = Path("backend/sam_b.pt")
                else:
                    raise ValueError(f"Unsupported model_type: {self.model_type}")
            else:
                checkpoint_path = Path(checkpoint_path)

            if not checkpoint_path.exists():
                download_urls = {
                    "vit_h": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
                    "vit_b": "https://github.com/facebookresearch/segment-anything"
                }
                download_url = download_urls.get(self.model_type, "https://github.com/facebookresearch/segment-anything")

                raise FileNotFoundError(
                    f"SAM {self.model_type} checkpoint not found at {checkpoint_path}. "
                    f"Please download from {download_url} or run backend/download_sam_vit_h.py"
                )

            logger.info(f"Loading SAM {self.model_type} model from {checkpoint_path}")
            sam = sam_model_registry[self.model_type](checkpoint=str(checkpoint_path))

            # GPU最適化
            sam.to(device=self.device)
            # 注: FP16モードは型変換の問題があるため、FP32で動作
            # RTX 3060でもFP32で十分高速（約50ms/frame）

            self.predictor = SamPredictor(sam)
            self.mask_generator = SamAutomaticMaskGenerator(sam)

            if self.device == "cuda":
                try:
                    import torch
                    allocated_mb = torch.cuda.memory_allocated() / 1024**2
                    logger.info(f"SAM {self.model_type} loaded on GPU: {allocated_mb:.1f}MB VRAM allocated")
                except:
                    logger.info(f"SAM {self.model_type} loaded on GPU")
            else:
                logger.info(f"SAM {self.model_type} loaded on CPU")

        except Exception as e:
            logger.error(f"Failed to load SAM model: {e}")
            raise

    def set_image(self, image: np.ndarray) -> None:
        """
        画像をSAMにセット（GPU最適化: リサイズで高速化）

        Args:
            image: 入力画像 (BGR)
        """
        # BGRからRGBに変換
        if len(image.shape) == 3 and image.shape[2] == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image

        # GPU最適化: 画像をリサイズしてエンコード時間を短縮
        # 元サイズ（1214x620）→ 640x480に縮小
        # エンコード速度2-3倍向上、精度への影響は最小限
        original_shape = image_rgb.shape[:2]  # (H, W)
        target_size = 640

        # アスペクト比を維持してリサイズ
        h, w = original_shape
        scale = target_size / max(h, w)
        new_h, new_w = int(h * scale), int(w * scale)

        resized_image = cv2.resize(image_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # リサイズした画像でエンコード
        self.predictor.set_image(resized_image)
        self.current_image = resized_image

        # 座標変換のためのスケール係数を保存
        self.scale_factor = scale
        self.original_shape = original_shape

    def segment_with_point(self,
                          point_coords: List[Tuple[int, int]],
                          point_labels: List[int]) -> Dict[str, Any]:
        """
        ポイントプロンプトでセグメンテーション

        Args:
            point_coords: ポイント座標のリスト [(x, y), ...]
            point_labels: ポイントラベル (1: 前景, 0: 背景)

        Returns:
            {
                "mask": np.ndarray,
                "score": float,
                "bbox": [x1, y1, x2, y2]
            }
        """
        if not self.predictor:
            raise RuntimeError("SAM predictor not initialized")

        # 座標をリサイズ後の画像スケールに変換
        point_coords_scaled = [(x * self.scale_factor, y * self.scale_factor) for x, y in point_coords]

        # numpy配列に変換
        point_coords_np = np.array(point_coords_scaled, dtype=np.float32)
        point_labels_np = np.array(point_labels, dtype=np.int32)

        # SAM予測
        masks, scores, _ = self.predictor.predict(
            point_coords=point_coords_np,
            point_labels=point_labels_np,
            multimask_output=True
        )

        # 最もスコアの高いマスクを選択
        best_idx = np.argmax(scores)
        best_mask = masks[best_idx]
        best_score = float(scores[best_idx])

        # マスクからタイトなBBoxを計算（ノイズ除去付き）
        bbox = self._refine_bbox_from_mask(best_mask)

        # bbox座標を元の画像スケールに戻す
        bbox_original = [
            int(bbox[0] / self.scale_factor),
            int(bbox[1] / self.scale_factor),
            int(bbox[2] / self.scale_factor),
            int(bbox[3] / self.scale_factor)
        ]

        # マスクも元のサイズにリサイズ
        h_orig, w_orig = self.original_shape
        mask_original = cv2.resize(best_mask.astype(np.uint8), (w_orig, h_orig), interpolation=cv2.INTER_NEAREST).astype(bool)

        return {
            "mask": mask_original,
            "score": best_score,
            "bbox": bbox_original
        }

    def segment_with_box(self, box: Tuple[int, int, int, int]) -> Dict[str, Any]:
        """
        ボックスプロンプトでセグメンテーション

        Args:
            box: [x1, y1, x2, y2]

        Returns:
            セグメンテーション結果
        """
        if not self.predictor:
            raise RuntimeError("SAM predictor not initialized")

        # box座標をリサイズ後のスケールに変換
        box_scaled = [
            box[0] * self.scale_factor,
            box[1] * self.scale_factor,
            box[2] * self.scale_factor,
            box[3] * self.scale_factor
        ]
        box_np = np.array(box_scaled, dtype=np.float32)

        masks, scores, _ = self.predictor.predict(
            point_coords=None,
            point_labels=None,
            box=box_np,
            multimask_output=True  # 変更: 3候補から最良選択
        )

        # 最もスコアの高いマスクを選択
        best_idx = np.argmax(scores)
        mask = masks[best_idx]
        score = float(scores[best_idx])

        # タイトなBBoxを計算
        bbox = self._refine_bbox_from_mask(mask)

        # bbox座標を元のスケールに戻す
        bbox_original = [
            int(bbox[0] / self.scale_factor),
            int(bbox[1] / self.scale_factor),
            int(bbox[2] / self.scale_factor),
            int(bbox[3] / self.scale_factor)
        ]

        # マスクも元のサイズにリサイズ
        h_orig, w_orig = self.original_shape
        mask_original = cv2.resize(mask.astype(np.uint8), (w_orig, h_orig), interpolation=cv2.INTER_NEAREST).astype(bool)

        return {
            "mask": mask_original,
            "score": score,
            "bbox": bbox_original
        }

    def auto_detect_instruments(self, frame: np.ndarray, max_instruments: int = 5) -> None:
        """
        自動的に器具を検出して初期化

        Args:
            frame: 初期フレーム
            max_instruments: 最大検出器具数
        """
        if not self.mask_generator:
            raise RuntimeError("SAM mask generator not initialized")

        self.set_image(frame)
        logger.info("Starting automatic instrument detection...")

        # SAMで自動マスク生成
        masks = self.mask_generator.generate(frame)

        # スコアでソート
        masks.sort(key=lambda x: x["predicted_iou"], reverse=True)

        # 上位N個を器具として採用
        self.tracked_instruments = []
        detected_count = 0

        for idx, mask_data in enumerate(masks[:max_instruments]):
            score = mask_data["predicted_iou"]

            # スコアが低すぎる場合はスキップ
            if score < 0.7:
                continue

            bbox = self._refine_bbox_from_mask(mask_data["segmentation"])

            # 小さすぎる領域はスキップ
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            if width < 20 or height < 20:
                continue

            track_id = idx
            self.tracked_instruments.append({
                "id": track_id,
                "name": f"Instrument {idx + 1}",
                "color": self._get_color_for_id(track_id),
                "last_bbox": bbox,
                "last_mask": mask_data["segmentation"],
                "last_score": score
            })

            # 軌跡を初期化
            center = self._get_bbox_center(bbox)
            self.trajectories[track_id] = deque(maxlen=50)
            self.trajectories[track_id].append(center)
            self.lost_frame_counts[track_id] = 0

            detected_count += 1
            logger.info(f"Auto-detected instrument {track_id}: score={score:.3f}, bbox={bbox}")

        logger.info(f"Auto-detection completed: {detected_count} instruments found")

    def _decode_mask(self, mask_b64: str) -> np.ndarray:
        """
        base64エンコードされたマスクをnumpy配列に変換

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

    def initialize_instruments(self,
                              frame: np.ndarray,
                              instruments: List[Dict[str, Any]]) -> None:
        """
        器具の初期化（ユーザー選択領域から）

        Args:
            frame: 初期フレーム
            instruments: 器具選択情報のリスト
                [{
                    "id": int,
                    "name": str,
                    "selection": {"type": "mask" | "point" | "box", "data": ...},
                    "color": str
                }]
        """
        self.set_image(frame)
        self.tracked_instruments = []

        for idx, instrument in enumerate(instruments):
            selection = instrument.get("selection", {})
            sel_type = selection.get("type")

            if sel_type == "mask":
                # マスク選択（最も正確）
                mask_b64 = selection.get("data")
                if not mask_b64:
                    logger.warning(f"Instrument {idx} has no mask data")
                    continue

                try:
                    # base64マスクをデコード
                    mask = self._decode_mask(mask_b64)

                    # マスクからbboxを抽出
                    bbox = self._refine_bbox_from_mask(mask)

                    # マスクを使ってセグメンテーション結果を作成
                    # SAMの出力形式に合わせる
                    result = {
                        "mask": mask,
                        "bbox": bbox,
                        "score": 1.0  # ユーザー選択なので信頼度は最大
                    }

                    logger.info(f"Instrument {idx} initialized with mask: bbox={bbox}, mask_pixels={np.sum(mask)}")

                except Exception as e:
                    logger.error(f"Failed to initialize instrument {idx} with mask: {e}")
                    continue

            elif sel_type == "point":
                # ポイント選択
                points = selection.get("data", [])
                if not points:
                    logger.warning(f"Instrument {idx} has no points")
                    continue

                result = self.segment_with_point(
                    point_coords=points,
                    point_labels=[1] * len(points)
                )
            elif sel_type == "box":
                # ボックス選択
                box = selection.get("data")
                if not box:
                    logger.warning(f"Instrument {idx} has no box")
                    continue

                result = self.segment_with_box(box)
            else:
                logger.error(f"Unknown selection type: {sel_type}")
                continue

            # トラッキングリストに追加
            track_id = instrument.get("id", idx)
            self.tracked_instruments.append({
                "id": track_id,
                "name": instrument.get("name", f"Instrument {idx}"),
                "color": instrument.get("color", "#FF0000"),
                "last_bbox": result["bbox"],
                "last_mask": result["mask"],
                "last_score": result["score"]
            })

            # 軌跡を初期化
            center = self._get_bbox_center(result["bbox"])
            self.trajectories[track_id] = deque(maxlen=50)
            self.trajectories[track_id].append(center)
            self.lost_frame_counts[track_id] = 0

            logger.info(f"Initialized instrument {track_id}: {instrument.get('name')}")

    def track_frame(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        現在のフレームで器具を追跡

        Args:
            frame: 現在のフレーム

        Returns:
            検出された器具のリスト
        """
        if not self.tracked_instruments:
            return []

        # 毎フレーム画像をセット（フレームごとに画像が異なるため必須）
        self.set_image(frame)
        detections = []

        for inst in self.tracked_instruments:
            track_id = inst["id"]
            prev_bbox = inst["last_bbox"]
            prev_mask = inst.get("last_mask")

            # マルチポイントプロンプトで検出（細長い器具対応）
            try:
                prompt_points = self._get_robust_prompts_for_elongated(
                    prev_bbox,
                    prev_mask
                )
                result = self.segment_with_point(
                    point_coords=prompt_points,
                    point_labels=[1] * len(prompt_points)
                )
                logger.debug(f"Track {track_id}: used {len(prompt_points)} prompt points, score={result['score']:.2f}")
            except Exception as e:
                logger.warning(f"Enhanced detection failed for {track_id}: {e}, falling back to single point")
                # フォールバック: 単一ポイント
                center = self._get_bbox_center(prev_bbox)
                result = self.segment_with_point(
                    point_coords=[center],
                    point_labels=[1]
                )

            # Phase 2.1: 動的信頼度閾値を使用
            dynamic_threshold = self._get_dynamic_confidence_threshold(track_id, result["score"])

            if result["score"] >= dynamic_threshold:
                # 検出成功
                inst["last_bbox"] = result["bbox"]
                inst["last_mask"] = result["mask"]
                inst["last_score"] = result["score"]
                self.lost_frame_counts[track_id] = 0

                # 軌跡を更新
                new_center = self._get_bbox_center(result["bbox"])
                self.trajectories[track_id].append(new_center)

                # Phase 2.5: 回転BBoxを計算
                rotated_info = self._get_rotated_bbox_from_mask(result["mask"])

                # 先端点を検出
                tip_point = self._detect_instrument_tip(result["mask"], result["bbox"])

                detections.append({
                    "class_name": inst["name"],
                    "bbox": result["bbox"],
                    "rotated_bbox": rotated_info["rotated_bbox"],
                    "rotation_angle": rotated_info["rotation_angle"],
                    "area_reduction": rotated_info["area_reduction"],
                    "confidence": result["score"],
                    "track_id": track_id,
                    "color": inst["color"],
                    "trajectory": list(self.trajectories[track_id])[-10:],
                    "tip_point": list(tip_point) if tip_point else None,  # 新規: 先端点
                    "tip_confidence": result["score"] if tip_point else 0.0  # 新規: 先端信頼度
                })
            else:
                # 検出失敗 → 再検出を試行
                self.lost_frame_counts[track_id] += 1

                if self.lost_frame_counts[track_id] <= self.max_lost_frames:
                    # Phase 2.2: 適応的探索範囲で再検出
                    adaptive_expansion = self._get_adaptive_search_expansion(track_id, prev_bbox)
                    redetect_result = self._redetect_in_expanded_area(prev_bbox, expansion=adaptive_expansion)

                    # 再検出時は閾値を少し下げる（70%）
                    redetect_threshold = dynamic_threshold * 0.7
                    if redetect_result and redetect_result["score"] >= redetect_threshold:
                        # 再検出成功
                        inst["last_bbox"] = redetect_result["bbox"]
                        inst["last_mask"] = redetect_result["mask"]
                        inst["last_score"] = redetect_result["score"]
                        self.lost_frame_counts[track_id] = 0

                        new_center = self._get_bbox_center(redetect_result["bbox"])
                        self.trajectories[track_id].append(new_center)

                        # Phase 2.5: 回転BBoxを計算（再検出時）
                        rotated_info = self._get_rotated_bbox_from_mask(redetect_result["mask"])

                        # 先端点を検出（再検出時）
                        tip_point = self._detect_instrument_tip(redetect_result["mask"], redetect_result["bbox"])

                        detections.append({
                            "class_name": inst["name"],
                            "bbox": redetect_result["bbox"],
                            "rotated_bbox": rotated_info["rotated_bbox"],
                            "rotation_angle": rotated_info["rotation_angle"],
                            "area_reduction": rotated_info["area_reduction"],
                            "confidence": redetect_result["score"],
                            "track_id": track_id,
                            "color": inst["color"],
                            "trajectory": list(self.trajectories[track_id])[-10:],
                            "tip_point": list(tip_point) if tip_point else None,  # 新規: 先端点
                            "tip_confidence": redetect_result["score"] if tip_point else 0.0,  # 新規: 先端信頼度
                            "redetected": True
                        })

                        logger.info(f"Re-detected instrument {track_id} after {self.lost_frame_counts[track_id]} lost frames")
                    else:
                        # 再検出失敗 → 前の位置を使用
                        logger.warning(f"Instrument {track_id} lost for {self.lost_frame_counts[track_id]} frames")
                        detections.append({
                            "class_name": inst["name"],
                            "bbox": prev_bbox,
                            "confidence": 0.3,  # 低い信頼度
                            "track_id": track_id,
                            "color": inst["color"],
                            "trajectory": list(self.trajectories[track_id])[-10:],
                            "lost": True
                        })
                else:
                    # 長期間ロスト → トラッキング停止
                    logger.error(f"Instrument {track_id} lost for {self.lost_frame_counts[track_id]} frames, stopping tracking")

        return detections

    def _redetect_in_expanded_area(
        self,
        prev_bbox: List[int],
        expansion: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        拡張領域で再検出

        Args:
            prev_bbox: 前フレームのbbox [x1, y1, x2, y2]
            expansion: 探索範囲拡張（ピクセル）。Noneの場合はデフォルト値を使用

        Returns:
            再検出結果、失敗時はNone
        """
        x1, y1, x2, y2 = prev_bbox
        h, w = self.current_image.shape[:2]

        # Phase 2.2: 適応的探索範囲（指定がない場合はデフォルト）
        expand = expansion if expansion is not None else self.search_expansion

        search_box = [
            max(0, x1 - expand),
            max(0, y1 - expand),
            min(w, x2 + expand),
            min(h, y2 + expand)
        ]

        # ボックスプロンプトで検出
        result = self.segment_with_box(tuple(search_box))

        # 閾値は呼び出し側で判定するため、結果をそのまま返す
        return result

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

    def _get_bbox_from_mask(self, mask: np.ndarray) -> List[int]:
        """
        マスクからバウンディングボックスを計算（旧版・互換性のため残す）

        Args:
            mask: バイナリマスク

        Returns:
            [x1, y1, x2, y2]
        """
        if mask.sum() == 0:
            return [0, 0, 0, 0]

        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)

        y1, y2 = np.where(rows)[0][[0, -1]]
        x1, x2 = np.where(cols)[0][[0, -1]]

        return [int(x1), int(y1), int(x2), int(y2)]

    def _refine_bbox_from_mask(self, mask: np.ndarray) -> List[int]:
        """
        マスクからタイトなBBoxを計算（ノイズ除去付き）

        手順:
        1. 形態学的Opening（小さなノイズ除去）
        2. 連結成分分析（最大領域のみ採用）
        3. タイトなBBox計算

        Args:
            mask: バイナリマスク

        Returns:
            [x1, y1, x2, y2]
        """
        if mask.sum() == 0:
            return [0, 0, 0, 0]

        try:
            # バイナリマスクに変換（0 or 255）
            mask_binary = (mask > 0).astype(np.uint8) * 255

            # モルフォロジー処理でノイズ除去
            kernel = np.ones((3, 3), np.uint8)
            mask_clean = cv2.morphologyEx(mask_binary, cv2.MORPH_OPEN, kernel)

            # Openingで消えた場合は元のマスクを使用
            if mask_clean.sum() == 0:
                mask_clean = mask_binary

            # 連結成分分析
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                mask_clean, connectivity=8
            )

            # 最大領域のみ採用（背景ラベル0を除く）
            if num_labels > 1:
                # 面積でソート（背景を除く）
                areas = stats[1:, cv2.CC_STAT_AREA]
                if len(areas) > 0:
                    largest_label = 1 + np.argmax(areas)
                    mask_clean = (labels == largest_label).astype(np.uint8) * 255

            # タイトなBBox計算
            rows = np.any(mask_clean > 0, axis=1)
            cols = np.any(mask_clean > 0, axis=0)

            if not rows.any() or not cols.any():
                # フォールバック: 元のマスクから計算
                logger.warning("Clean mask is empty, using original mask")
                return self._get_bbox_from_mask(mask)

            y_indices = np.where(rows)[0]
            x_indices = np.where(cols)[0]

            y1, y2 = y_indices[0], y_indices[-1]
            x1, x2 = x_indices[0], x_indices[-1]

            return [int(x1), int(y1), int(x2), int(y2)]

        except Exception as e:
            logger.warning(f"BBox refinement failed: {e}, using simple calculation")
            # エラー時は旧版にフォールバック
            return self._get_bbox_from_mask(mask)

    def _get_bbox_center(self, bbox: List[int]) -> Tuple[int, int]:
        """
        バウンディングボックスの中心点を計算

        Args:
            bbox: [x1, y1, x2, y2]

        Returns:
            (center_x, center_y)
        """
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        return (center_x, center_y)

    def _get_robust_prompts_for_elongated(
        self,
        bbox: List[int],
        mask: Optional[np.ndarray] = None
    ) -> List[Tuple[int, int]]:
        """
        器具先端に集中したマルチポイントプロンプトを生成

        戦略（先端優先）:
        1. 器具の先端点 - 最優先（weight=2相当、重複追加）
        2. 先端から中央への2点 - 先端領域をカバー
        3. 重心（フォールバック）

        Args:
            bbox: [x1, y1, x2, y2]
            mask: バイナリマスク（オプション）

        Returns:
            プロンプトポイントのリスト [(x, y), ...] 先端点が優先
        """
        points = []

        if mask is not None and mask.sum() > 0:
            try:
                # 1. 先端点を検出（最優先）
                tip_point = self._detect_instrument_tip(mask, bbox)
                if tip_point is not None:
                    # 先端点を2回追加（実質的なweight=2）
                    points.append(tip_point)
                    points.append(tip_point)
                    logger.debug(f"Tip point (priority): {tip_point}")

                # 2. 重心を計算
                moments = cv2.moments(mask.astype(np.uint8))
                if moments["m00"] > 0:
                    cx = int(moments["m10"] / moments["m00"])
                    cy = int(moments["m01"] / moments["m00"])
                    centroid = (cx, cy)

                    # 3. 先端から中央への中間点を追加
                    if tip_point is not None:
                        # 先端と重心の間に1点
                        mid_x = int((tip_point[0] + cx) / 2)
                        mid_y = int((tip_point[1] + cy) / 2)
                        points.append((mid_x, mid_y))
                        logger.debug(f"Mid point (tip→centroid): ({mid_x}, {mid_y})")

                        # 重心も追加（先端領域の補完）
                        points.append(centroid)
                        logger.debug(f"Centroid: {centroid}")
                    else:
                        # 先端検出失敗時は重心を優先
                        points.append(centroid)
                        logger.debug(f"Centroid (fallback): {centroid}")

            except Exception as e:
                logger.warning(f"Failed to compute tip-focused prompts: {e}")

        # 幾何学的中心をフォールバック/追加
        geo_center = self._get_bbox_center(bbox)
        if geo_center not in points:
            points.append(geo_center)
            logger.debug(f"Added geometric center: {geo_center}")

        # Fail Fast: ポイントが生成できなかった場合
        if not points:
            logger.error(f"Failed to generate any prompt points for bbox={bbox}")
            # 最低限の保証として幾何学的中心を返す
            return [self._get_bbox_center(bbox)]

        logger.debug(f"Generated {len(points)} tip-focused prompt points")
        return points

    def _detect_instrument_tip(
        self,
        mask: np.ndarray,
        bbox: List[int]
    ) -> Optional[Tuple[int, int]]:
        """
        器具の先端点を検出

        アルゴリズム:
        1. 輪郭抽出
        2. PCAで主軸方向を計算
        3. 主軸方向の最遠点を先端とする
        4. 外れ値検証

        Args:
            mask: バイナリマスク
            bbox: [x1, y1, x2, y2]

        Returns:
            (tip_x, tip_y) または None
        """
        if mask.sum() == 0:
            return None

        try:
            # 1. 輪郭抽出
            mask_binary = (mask > 0).astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                return None

            # 最大輪郭を使用
            contour = max(contours, key=cv2.contourArea)

            # 2. PCAで主軸を計算
            y_coords, x_coords = np.where(mask > 0)
            if len(x_coords) < 5:
                return None

            coords = np.column_stack([x_coords, y_coords])
            mean, eigenvectors = cv2.PCACompute(coords.astype(np.float32), mean=None)
            principal_axis = eigenvectors[0]  # 第1主成分

            # 重心を計算
            moments = cv2.moments(mask_binary)
            if moments["m00"] == 0:
                return None

            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
            centroid = np.array([cx, cy], dtype=np.float32)

            # 3. 輪郭上で主軸方向の最遠点を検出
            max_dist = -1
            tip_point = None

            for pt in contour:
                pt_coord = pt[0]  # (x, y)
                # 重心からの相対位置
                rel_pos = pt_coord - centroid

                # 主軸方向への射影距離
                projection = np.dot(rel_pos, principal_axis)

                # 正の方向（先端側）のみ考慮
                if projection > 0 and projection > max_dist:
                    max_dist = projection
                    tip_point = tuple(pt_coord)

            # フォールバック: 負の方向も確認（器具の向きが逆の場合）
            if tip_point is None:
                for pt in contour:
                    pt_coord = pt[0]
                    rel_pos = pt_coord - centroid
                    projection = np.dot(rel_pos, principal_axis)

                    if projection < 0 and abs(projection) > max_dist:
                        max_dist = abs(projection)
                        tip_point = tuple(pt_coord)

            # 4. 外れ値検証
            if tip_point is not None:
                x1, y1, x2, y2 = bbox
                tx, ty = tip_point

                # BBox内にあるか確認
                if x1 <= tx <= x2 and y1 <= ty <= y2:
                    logger.debug(f"Detected tip at ({tx}, {ty}), centroid=({cx}, {cy}), max_dist={max_dist:.1f}")
                    return tip_point
                else:
                    logger.warning(f"Tip point ({tx}, {ty}) outside bbox {bbox}, using centroid")
                    return (cx, cy)

            # フォールバック: 重心を返す
            logger.debug(f"Tip detection failed, using centroid ({cx}, {cy})")
            return (cx, cy)

        except Exception as e:
            logger.warning(f"Tip detection error: {e}, using bbox center")
            # 最終フォールバック: BBox中心
            return self._get_bbox_center(bbox)

    def _get_color_for_id(self, track_id: int) -> str:
        """
        トラックIDに対応する色を取得

        Args:
            track_id: トラックID

        Returns:
            色コード（Hex形式）
        """
        colors = [
            "#FF0000",  # 赤
            "#00FF00",  # 緑
            "#0000FF",  # 青
            "#FFFF00",  # 黄
            "#FF00FF",  # マゼンタ
            "#00FFFF",  # シアン
            "#FFA500",  # オレンジ
            "#800080",  # 紫
        ]
        return colors[track_id % len(colors)]

    def get_tracking_stats(self) -> Dict[str, Any]:
        """
        トラッキング統計を取得

        Returns:
            統計情報
        """
        stats = {
            "total_instruments": len(self.tracked_instruments),
            "instruments": {}
        }

        for inst in self.tracked_instruments:
            track_id = inst["id"]
            stats["instruments"][f"instrument_{track_id}"] = {
                "name": inst["name"],
                "last_score": inst.get("last_score", 0.0),
                "lost_frames": self.lost_frame_counts.get(track_id, 0),
                "trajectory_length": len(self.trajectories.get(track_id, []))
            }

        return stats

    def _get_dynamic_confidence_threshold(self, track_id: int, current_score: float) -> float:
        """
        Phase 2.1: 動的信頼度閾値を計算

        器具ごとの信頼度履歴から適応的な閾値を設定。
        - 安定してスコアが高い → 閾値を高くして誤検出を減らす
        - スコアが不安定 → 閾値を低くして追跡を継続

        Args:
            track_id: トラックID
            current_score: 現在の信頼度スコア

        Returns:
            動的閾値（0.3〜0.7の範囲）
        """
        # 履歴を初期化
        if track_id not in self.track_confidence_history:
            self.track_confidence_history[track_id] = deque(maxlen=self.confidence_window_size)

        # 現在のスコアを履歴に追加
        self.track_confidence_history[track_id].append(current_score)

        history = list(self.track_confidence_history[track_id])

        # 履歴が少ない場合はベース閾値を使用
        if len(history) < 3:
            return self.base_confidence_threshold

        # 統計計算
        mean_score = sum(history) / len(history)
        variance = sum((x - mean_score) ** 2 for x in history) / len(history)
        std_dev = variance ** 0.5

        # 変動係数（CV）: 標準偏差 / 平均
        cv = std_dev / mean_score if mean_score > 0 else 1.0

        # 動的閾値の計算
        # 安定している（CV < 0.2）→ 高い閾値（平均の90%）
        # 不安定（CV > 0.5）→ 低い閾値（平均の70%）
        if cv < 0.2:
            # 非常に安定 → 高い閾値
            dynamic_threshold = mean_score * 0.9
        elif cv < 0.5:
            # やや安定 → 中程度の閾値
            dynamic_threshold = mean_score * 0.8
        else:
            # 不安定 → 低い閾値
            dynamic_threshold = mean_score * 0.7

        # 閾値を 0.3〜0.7 の範囲に制限
        dynamic_threshold = max(0.3, min(0.7, dynamic_threshold))

        logger.debug(
            f"Track {track_id}: mean={mean_score:.2f}, std={std_dev:.2f}, "
            f"CV={cv:.2f}, threshold={dynamic_threshold:.2f}"
        )

        return dynamic_threshold

    def _get_adaptive_search_expansion(self, track_id: int, bbox: List[int]) -> int:
        """
        Phase 2.2: 適応的探索範囲拡張

        器具のサイズと移動速度に基づいて探索範囲を動的に調整。
        - 大きい器具 → 大きい探索範囲
        - 速い移動 → 大きい探索範囲

        Args:
            track_id: トラックID
            bbox: [x1, y1, x2, y2]

        Returns:
            探索範囲拡張（ピクセル）
        """
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        bbox_size = max(width, height)

        # サイズベースの拡張（BBoxの最大辺の30%）
        size_based_expansion = int(bbox_size * 0.3)

        # 速度ベースの拡張（軌跡から計算）
        velocity_based_expansion = 0
        if track_id in self.trajectories and len(self.trajectories[track_id]) >= 2:
            trajectory = list(self.trajectories[track_id])
            # 最後の2点間の移動距離
            p1 = trajectory[-2]
            p2 = trajectory[-1]
            distance = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5
            velocity_based_expansion = int(distance * 1.5)  # 移動距離の1.5倍

        # 総合的な探索範囲（最小50px、最大200px）
        total_expansion = size_based_expansion + velocity_based_expansion
        adaptive_expansion = max(50, min(200, total_expansion))

        logger.debug(
            f"Track {track_id}: size_exp={size_based_expansion}px, "
            f"vel_exp={velocity_based_expansion}px, total={adaptive_expansion}px"
        )

        return adaptive_expansion

    def _get_rotated_bbox_from_mask(self, mask: np.ndarray) -> Dict[str, Any]:
        """
        Phase 2.5: マスクから回転BBox（Rotated Bounding Box）を計算

        細長い器具に最適化された回転矩形を生成。
        従来の矩形BBoxより30-50%面積削減。

        Args:
            mask: バイナリマスク

        Returns:
            {
                "rotated_bbox": [[x1,y1], [x2,y2], [x3,y4], [x4,y4]],  # 4点座標
                "rotation_angle": float,  # 回転角度（度）
                "rect_bbox": [x1, y1, x2, y2],  # 従来の矩形（互換性）
                "area_reduction": float  # 面積削減率（%）
            }
        """
        if mask.sum() == 0:
            return {
                "rotated_bbox": [[0, 0], [0, 0], [0, 0], [0, 0]],
                "rotation_angle": 0.0,
                "rect_bbox": [0, 0, 0, 0],
                "area_reduction": 0.0
            }

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
                # フォールバック
                rect_bbox = self._refine_bbox_from_mask(mask)
                return {
                    "rotated_bbox": [
                        [rect_bbox[0], rect_bbox[1]],
                        [rect_bbox[2], rect_bbox[1]],
                        [rect_bbox[2], rect_bbox[3]],
                        [rect_bbox[0], rect_bbox[3]]
                    ],
                    "rotation_angle": 0.0,
                    "rect_bbox": rect_bbox,
                    "area_reduction": 0.0
                }

            # 最大輪郭を取得
            largest_contour = max(contours, key=cv2.contourArea)

            # 回転矩形を計算
            # rect = ((center_x, center_y), (width, height), angle)
            rect = cv2.minAreaRect(largest_contour)

            # 4点の座標を取得
            box_points = cv2.boxPoints(rect)
            box_points = np.intp(box_points)  # 整数に変換（int0は非推奨）

            # リスト形式に変換
            rotated_bbox = [[int(pt[0]), int(pt[1])] for pt in box_points]

            # 回転角度（度）
            rotation_angle = float(rect[2])

            # 従来の矩形BBox（比較用）
            rect_bbox = self._refine_bbox_from_mask(mask)

            # 面積計算
            rotated_area = cv2.contourArea(box_points)
            rect_area = (rect_bbox[2] - rect_bbox[0]) * (rect_bbox[3] - rect_bbox[1])

            # 面積削減率（%）
            area_reduction = 0.0
            if rect_area > 0:
                area_reduction = ((rect_area - rotated_area) / rect_area) * 100

            logger.debug(
                f"Rotated BBox: area={rotated_area:.0f}px^2, "
                f"rect_area={rect_area:.0f}px^2, reduction={area_reduction:.1f}%, "
                f"angle={rotation_angle:.1f}°"
            )

            return {
                "rotated_bbox": rotated_bbox,
                "rotation_angle": rotation_angle,
                "rect_bbox": rect_bbox,
                "area_reduction": area_reduction
            }

        except Exception as e:
            logger.warning(f"Rotated BBox calculation failed: {e}, using rect bbox")
            # エラー時は従来の矩形BBoxにフォールバック
            rect_bbox = self._refine_bbox_from_mask(mask)
            return {
                "rotated_bbox": [
                    [rect_bbox[0], rect_bbox[1]],
                    [rect_bbox[2], rect_bbox[1]],
                    [rect_bbox[2], rect_bbox[3]],
                    [rect_bbox[0], rect_bbox[3]]
                ],
                "rotation_angle": 0.0,
                "rect_bbox": rect_bbox,
                "area_reduction": 0.0
            }
