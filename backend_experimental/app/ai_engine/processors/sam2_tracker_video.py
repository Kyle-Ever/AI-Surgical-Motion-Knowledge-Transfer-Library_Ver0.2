"""
SAM2 Video API を活用した器具トラッキング実装（実験版）

特徴:
- ビデオ全体の時間的コンテキストを考慮
- Memory Bankでオクルージョン耐性
- 一貫したオブジェクトID
- 複数器具の同時追跡
"""

import cv2
import numpy as np
import torch
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path
import asyncio
import base64
from io import BytesIO
from PIL import Image
from scipy.ndimage import median_filter

# SAM2のインポート
try:
    from sam2.build_sam import build_sam2_video_predictor
    SAM2_AVAILABLE = True
except ImportError:
    SAM2_AVAILABLE = False
    logging.error("SAM2 library not available. Please install: pip install sam2")

logger = logging.getLogger(__name__)


class SAM2TrackerVideo:
    """
    SAM2 Video API を使った器具トラッキング

    特徴:
    - ビデオ全体の時間的コンテキストを考慮
    - Memory Bankでオクルージョン耐性
    - 一貫したオブジェクトID
    - 複数器具の同時追跡
    """

    def __init__(
        self,
        model_type: str = "small",
        checkpoint_path: Optional[str] = None,
        device: str = "cpu"
    ):
        """
        初期化

        Args:
            model_type: "tiny", "small", "base_plus", "large"
            checkpoint_path: モデルファイルパス
            device: "cpu" or "cuda"
        """
        self.model_type = model_type
        self.device = device
        self.predictor = None
        self.inference_state = None

        # GPU検出
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, using CPU")
            self.device = "cpu"
        elif device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Auto-detected device: {self.device}")

        # モデルロード
        if SAM2_AVAILABLE:
            self._load_model(checkpoint_path)
        else:
            logger.error("SAM2 not available, tracker will not work")

    def _load_model(self, checkpoint_path: Optional[str]):
        """SAM2 Video Predictor をロード（Configベースのパス解決）"""
        from app.core.config import settings

        if checkpoint_path is None:
            # Configから取得（統一されたパス解決）
            checkpoint_path = settings.get_sam2_video_checkpoint(self.model_type)
        else:
            checkpoint_path = Path(checkpoint_path)

        if not checkpoint_path.exists():
            logger.error(f"SAM2 checkpoint not found: {checkpoint_path}")
            raise FileNotFoundError(
                f"SAM2 checkpoint not found: {checkpoint_path}\n"
                f"Download from: https://dl.fbaipublicfiles.com/segment_anything_2/"
            )

        # Configファイルパス（パッケージ内相対パス）
        config_path = settings.get_sam2_video_config(self.model_type)

        logger.info(f"Loading SAM2 Video Predictor: {self.model_type} on {self.device}")
        logger.info(f"  Checkpoint: {checkpoint_path}")
        logger.info(f"  Config: {config_path}")

        try:
            self.predictor = build_sam2_video_predictor(
                config_path,
                str(checkpoint_path),
                device=self.device
            )
            logger.info("SAM2 Video Predictor loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load SAM2: {e}")
            raise

    async def track_video(
        self,
        video_path: str,
        instruments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        ビデオ全体で器具を追跡

        Args:
            video_path: 動画ファイルパス（MP4形式）
            instruments: 器具情報
                [
                    {
                        "id": 0,
                        "name": "forceps",
                        "selection": {
                            "type": "point" | "box" | "mask",
                            "data": [...coordinates...]
                        }
                    }
                ]

        Returns:
            追跡結果
                {
                    "instruments": [
                        {
                            "instrument_id": 0,
                            "name": "forceps",
                            "trajectory": [
                                {
                                    "frame_index": 0,
                                    "center": [x, y],
                                    "bbox": [x1, y1, x2, y2],
                                    "confidence": 0.95,
                                    "mask": np.ndarray
                                },
                                ...
                            ]
                        }
                    ]
                }
        """
        logger.info(f"[SAM2 Video API] Starting tracking: {len(instruments)} instruments")

        if not SAM2_AVAILABLE or self.predictor is None:
            logger.error("SAM2 not available")
            return {"instruments": []}

        # フレーム数を動画から取得
        frame_count = self._get_video_frame_count(video_path)
        logger.info(f"[SAM2 Video API] Video has {frame_count} frames")

        # 1. Inference state初期化
        await asyncio.get_event_loop().run_in_executor(
            None, self._initialize_state, video_path
        )

        # 2. 初期フレーム（Frame 0）で器具を登録
        await asyncio.get_event_loop().run_in_executor(
            None, self._register_instruments, instruments
        )

        # 3. 全フレームに追跡を伝播（フレーム数を渡す）
        video_segments = await asyncio.get_event_loop().run_in_executor(
            None, self._propagate_tracking, frame_count
        )

        # 4. 軌跡データを抽出
        trajectories = self._extract_trajectories(video_segments, instruments)

        logger.info(f"[SAM2 Video API] Tracking completed: {len(trajectories)} instruments tracked")

        return {"instruments": trajectories}

    def _initialize_state(self, video_path: str):
        """Inference stateを初期化"""
        logger.info(f"[SAM2 Video API] Initializing inference state with video: {video_path}")

        with torch.inference_mode():
            # ビデオファイルパス（MP4）を渡す
            # SAM2 Video APIはMP4ファイルまたはJPEGフォルダを受け入れる
            self.inference_state = self.predictor.init_state(
                video_path=video_path,
                async_loading_frames=False
            )

        logger.info(f"[SAM2 Video API] Inference state initialized successfully")

    def _register_instruments(self, instruments: List[Dict[str, Any]]):
        """初期フレームで器具を登録"""
        logger.info(f"[SAM2 Video API] Registering {len(instruments)} instruments...")

        with torch.inference_mode():
            for inst in instruments:
                obj_id = inst["id"]
                # デバッグ：登録するobj_idの型と値を確認
                logger.info(f"[DEBUG] Registering obj_id={obj_id}, type={type(obj_id)}")
                selection = inst.get("selection", {})
                sel_type = selection.get("type")
                sel_data = selection.get("data")

                if sel_type == "point":
                    # ポイントプロンプト
                    points = np.array(sel_data, dtype=np.float32)
                    labels = np.ones(len(points), dtype=np.int32)

                    self.predictor.add_new_points_or_box(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        points=points,
                        labels=labels
                    )
                    logger.info(f"[SAM2 Video API] Registered instrument {obj_id} with {len(points)} points")

                elif sel_type == "box":
                    # ボックスプロンプト
                    box = np.array(sel_data, dtype=np.float32)

                    self.predictor.add_new_points_or_box(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        box=box
                    )
                    logger.info(f"[SAM2 Video API] Registered instrument {obj_id} with box")

                elif sel_type == "mask":
                    # マスクプロンプト（最も正確）
                    # Base64エンコードされたPNG画像をデコード
                    if isinstance(sel_data, str):
                        # Base64デコード
                        mask_bytes = base64.b64decode(sel_data)
                        # PILで画像として読み込み
                        mask_image = Image.open(BytesIO(mask_bytes))
                        # numpy配列に変換（グレースケール）
                        mask = np.array(mask_image.convert('L'), dtype=np.uint8)
                        # バイナリマスク（0 or 255 → 0 or 1）
                        mask = (mask > 127).astype(np.uint8)
                        logger.info(f"[SAM2 Video API] Decoded mask shape: {mask.shape}")
                    else:
                        # すでにnumpy配列の場合（後方互換性）
                        mask = np.array(sel_data, dtype=np.uint8)

                    self.predictor.add_new_mask(
                        inference_state=self.inference_state,
                        frame_idx=0,
                        obj_id=obj_id,
                        mask=mask
                    )
                    logger.info(f"[SAM2 Video API] Registered instrument {obj_id} with mask")

                else:
                    logger.warning(f"[SAM2 Video API] Unknown selection type: {sel_type}")

        logger.info("[SAM2 Video API] All instruments registered")

    def _propagate_tracking(self, total_frames: int) -> Dict[int, Dict[int, np.ndarray]]:
        """全フレームに追跡を伝播（🆕 Phase 4: 動的閾値調整対応）"""
        logger.info("[SAM2 Video API] Propagating tracking across video...")

        # 設定から閾値を取得
        from app.core.config import settings
        base_threshold = settings.SAM2_MASK_THRESHOLD
        use_dynamic = settings.SAM2_ENABLE_DYNAMIC_THRESHOLD

        if use_dynamic:
            logger.info(f"[DYNAMIC THRESHOLD] Enabled: min={settings.SAM2_DYNAMIC_THRESHOLD_MIN}, max={settings.SAM2_DYNAMIC_THRESHOLD_MAX}")
            logger.info(f"[DYNAMIC THRESHOLD] Motion thresholds: slow={settings.SAM2_MOTION_THRESHOLD_SLOW}px, fast={settings.SAM2_MOTION_THRESHOLD_FAST}px")
        else:
            logger.info(f"[SAM2 Video API] Using fixed threshold: {base_threshold}")

        video_segments = {}
        frame_count = 0
        processed_frames = 0  # 🆕 進捗追跡用カウンタ

        # 🆕 Phase 4: 前フレームの中心座標を記録（動き計算用）
        prev_centers = {}  # {obj_id: (x, y)}

        with torch.inference_mode():
            try:
                # SAM2が全フレームを自動追跡
                for out_frame_idx, out_obj_ids, out_mask_logits in \
                        self.predictor.propagate_in_video(self.inference_state):
                    processed_frames += 1  # 🆕 カウント

                    # デバッグ：最初のフレームでlogitsの情報を確認
                    if out_frame_idx == 0:
                        logger.info(f"[DEBUG] Frame 0 out_mask_logits: shape={out_mask_logits.shape}, dtype={out_mask_logits.dtype}, min={out_mask_logits.min().item():.4f}, max={out_mask_logits.max().item():.4f}")

                    masks = {}

                    for i, obj_id in enumerate(out_obj_ids):
                        # 🆕 Phase 4: 動的閾値調整
                        if use_dynamic and obj_id in prev_centers:
                            # マスクから現在の中心座標を計算
                            mask_logits = out_mask_logits[i].cpu().numpy()
                            temp_mask = mask_logits > 0.0  # 仮マスク（閾値0で全領域）

                            if temp_mask.sum() > 0:
                                # マスクの次元を確認して2次元に変換
                                temp_mask_2d = temp_mask.squeeze() if temp_mask.ndim > 2 else temp_mask
                                y_coords, x_coords = np.where(temp_mask_2d)
                                current_center = (np.mean(x_coords), np.mean(y_coords))

                                # 前フレームとの移動距離を計算
                                prev_x, prev_y = prev_centers[obj_id]
                                motion_distance = np.sqrt(
                                    (current_center[0] - prev_x)**2 +
                                    (current_center[1] - prev_y)**2
                                )

                                # 移動距離に応じて閾値を調整
                                if motion_distance < settings.SAM2_MOTION_THRESHOLD_SLOW:
                                    # 静止～低速: 高閾値（精度優先）
                                    threshold = settings.SAM2_DYNAMIC_THRESHOLD_MAX
                                elif motion_distance < settings.SAM2_MOTION_THRESHOLD_FAST:
                                    # 中速: 中間閾値
                                    threshold = (settings.SAM2_DYNAMIC_THRESHOLD_MIN + settings.SAM2_DYNAMIC_THRESHOLD_MAX) / 2
                                else:
                                    # 高速: 低閾値（追跡優先）
                                    threshold = settings.SAM2_DYNAMIC_THRESHOLD_MIN

                                # 閾値変更時のみログ出力
                                if processed_frames % 100 == 0 or motion_distance > settings.SAM2_MOTION_THRESHOLD_FAST:
                                    logger.debug(f"[DYNAMIC] Frame {out_frame_idx} obj {obj_id}: motion={motion_distance:.1f}px → threshold={threshold:.2f}")

                                prev_centers[obj_id] = current_center
                            else:
                                # マスクが空の場合は基本閾値を使用
                                threshold = base_threshold
                        else:
                            # 動的閾値無効 or 初回フレーム
                            threshold = base_threshold

                        # マスクをバイナリ化
                        mask = (out_mask_logits[i] > threshold).cpu().numpy()
                        masks[obj_id] = mask

                        # 🆕 Phase 4: 次フレーム用に中心座標を保存
                        if use_dynamic and mask.sum() > 0:
                            # マスクの次元を確認して2次元に変換
                            mask_2d = mask.squeeze() if mask.ndim > 2 else mask
                            y_coords, x_coords = np.where(mask_2d)
                            prev_centers[obj_id] = (np.mean(x_coords), np.mean(y_coords))

                    # デバッグ：最初のフレームでmasks辞書のキーを確認
                    if out_frame_idx == 0:
                        logger.info(f"[DEBUG] Frame 0 mask keys: {list(masks.keys())}, types: {[type(k) for k in masks.keys()]}")
                        # バイナリ化後のマスク情報
                        for obj_id in masks:
                            logger.info(f"[DEBUG] Frame 0 obj_id={obj_id}: mask shape={masks[obj_id].shape}, sum={masks[obj_id].sum()}")

                    # 🐛 FIX: 全フレームでマスクを保存（if文の外）
                    video_segments[out_frame_idx] = masks
                    frame_count += 1

                    # 🆕 進捗ログ強化（100フレームごと + 詳細情報）
                    if processed_frames % 100 == 0:
                        logger.warning(f"[PROPAGATION] Processed {processed_frames} frames, current frame_idx={out_frame_idx}, total expected={total_frames}")

            except Exception as e:
                logger.error(f"[PROPAGATION] Failed at frame {processed_frames}: {e}")
                import traceback
                logger.error(f"[PROPAGATION] Traceback: {traceback.format_exc()}")
                # 部分的な結果を返す（完全に失敗するよりマシ）
                logger.warning(f"[PROPAGATION] Returning partial results: {frame_count} frames")
                return video_segments

        logger.info(f"[SAM2 Video API] Tracking propagated to {frame_count} frames")
        return video_segments

    def _extract_trajectories(
        self,
        video_segments: Dict[int, Dict[int, np.ndarray]],
        instruments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """軌跡データを抽出"""
        logger.info("[SAM2 Video API] Extracting trajectories...")

        trajectories = []
        total_frames = len(video_segments.keys())
        logger.info(f"[DEBUG] Starting trajectory extraction: {total_frames} frames, {len(instruments)} instruments")

        for inst in instruments:
            obj_id = inst["id"]
            trajectory = []

            # デバッグ：最初の器具のみ詳細ログ
            is_first_inst = (inst == instruments[0])

            for frame_idx in sorted(video_segments.keys()):
                masks = video_segments[frame_idx]

                # デバッグ：最初のフレームで検索状況を確認
                if is_first_inst and frame_idx == sorted(video_segments.keys())[0]:
                    logger.info(f"[DEBUG] Looking for obj_id={obj_id} (type={type(obj_id)}) in masks with keys={list(masks.keys())}, types={[type(k) for k in masks.keys()]}")

                if obj_id not in masks:
                    # この器具が検出されなかったフレーム
                    continue

                mask = masks[obj_id]

                # マスクから情報を抽出
                if mask.sum() == 0:
                    # 空のマスク
                    if is_first_inst and frame_idx < 5:  # 最初の5フレームのみログ
                        logger.info(f"[DEBUG] Frame {frame_idx}: Empty mask (sum=0) before normalization, shape={mask.shape}, dtype={mask.dtype}")
                    continue

                # マスクを2次元に正規化
                original_shape = mask.shape
                if mask.ndim == 3:
                    # 3次元の場合 (B, H, W) → (H, W): バッチ次元を削除
                    mask = mask[0]
                elif mask.ndim == 4:
                    # 4次元の場合 (B, C, H, W) → (H, W): バッチとチャンネル次元を削除
                    mask = mask[0, 0]
                elif mask.ndim > 4:
                    raise ValueError(f"[SAM2 Video API] Unexpected mask dimension: {mask.ndim}, shape={mask.shape}")

                # 正規化後に再度空マスクチェック
                if mask.sum() == 0:
                    # 正規化後も空のマスク
                    if is_first_inst and frame_idx < 5:
                        logger.info(f"[DEBUG] Frame {frame_idx}: Empty mask (sum=0) after normalization, original_shape={original_shape}, normalized_shape={mask.shape}")
                    continue

                # 🆕 最小面積フィルタ（ノイズ除去）
                from app.core.config import settings
                min_area = settings.SAM2_MIN_MASK_AREA
                mask_area = mask.sum()
                if mask_area < min_area:
                    if is_first_inst and frame_idx < 5:
                        logger.info(f"[QUALITY] Frame {frame_idx}: Small mask filtered (area={mask_area} < {min_area})")
                    continue

                # デバッグ：初回のみマスク情報を出力（拡張：最初の3フレーム）
                if frame_idx < 3 and is_first_inst:
                    if original_shape != mask.shape:
                        logger.info(f"[DEBUG] Frame {frame_idx}: Normalized mask: {original_shape} → {mask.shape}")
                    logger.info(f"[DEBUG] Frame {frame_idx}: Mask info - shape={mask.shape}, dtype={mask.dtype}, sum={mask.sum()}, min={mask.min()}, max={mask.max()}")

                # 重心計算
                y_coords, x_coords = np.where(mask)

                # 空配列チェック（念のため）
                if len(x_coords) == 0 or len(y_coords) == 0:
                    continue
                center_x = float(np.mean(x_coords))
                center_y = float(np.mean(y_coords))

                # バウンディングボックス
                x_min, x_max = float(x_coords.min()), float(x_coords.max())
                y_min, y_max = float(y_coords.min()), float(y_coords.max())

                # 🆕 改善された信頼度計算（手術器具最適化版）
                # マスクの品質に基づいた信頼度スコア（0.0～1.0）
                mask_area = mask.sum()
                bbox_width = x_max - x_min
                bbox_height = y_max - y_min
                bbox_area = bbox_width * bbox_height
                aspect_ratio = bbox_height / bbox_width if bbox_width > 0 else 1.0

                # 1. BBox充填率の正規化（器具形状に応じた期待値で補正）
                fill_ratio = mask_area / bbox_area if bbox_area > 0 else 0.0

                # アスペクト比から期待fill_ratioを計算
                if aspect_ratio >= 3.0:
                    # 極細長器具: マスクがBBoxの30%を埋めれば十分
                    expected_fill = 0.3
                elif aspect_ratio >= 1.5:
                    # 中程度の細長さ: 50%期待
                    expected_fill = 0.5
                else:
                    # 正方形に近い: 70%必要（ノイズの可能性）
                    expected_fill = 0.7

                # 正規化（期待値で割る）
                fill_ratio_normalized = min(1.0, fill_ratio / expected_fill) if expected_fill > 0 else 0.0

                # 2. サイズの妥当性（極端に小さい/大きいマスクは低い信頼度）
                from app.core.config import settings
                min_area = settings.SAM2_MIN_MASK_AREA  # 例: 500
                max_area = mask.shape[0] * mask.shape[1] * 0.5  # 画像の50%以上は不自然

                if mask_area < min_area:
                    size_score = mask_area / min_area  # 0.0～1.0
                elif mask_area > max_area:
                    size_score = max_area / mask_area  # 1.0未満
                else:
                    size_score = 1.0  # 妥当なサイズ

                # 3. 形状の妥当性（手術器具は細長い形状が多い）
                # 理想的なアスペクト比: 1.5～15（幅広い器具に対応）
                if 1.5 <= aspect_ratio <= 15.0:
                    shape_score = 1.0  # 理想的な範囲
                elif aspect_ratio < 1.5:
                    # 正方形に近い（ノイズの可能性）
                    # アスペクト比0.75で0.5、1.5で1.0の線形スコア
                    shape_score = 0.5 + 0.5 * (aspect_ratio / 1.5)
                else:
                    # 極端に細長い（アスペクト比15以上）
                    # 15で1.0、65で0.5の線形減少
                    shape_score = max(0.5, 1.0 - (aspect_ratio - 15.0) / 50.0)

                # 最終的な信頼度：手術器具に最適化した重み配分
                confidence = (
                    fill_ratio_normalized * 0.3 +  # 充填率: 30%（正規化済み）
                    size_score * 0.2 +              # サイズ: 20%（補助的）
                    shape_score * 0.5               # 形状: 50%（最重要特徴）
                )
                confidence = min(1.0, max(0.0, confidence))  # 0.0～1.0にクリップ

                trajectory.append({
                    "frame_index": int(frame_idx),
                    "center": [center_x, center_y],
                    "bbox": [x_min, y_min, x_max, y_max],
                    "confidence": float(confidence),
                    "mask": mask  # 必要に応じて保存
                })

            trajectories.append({
                "instrument_id": obj_id,
                "name": inst.get("name", f"instrument_{obj_id}"),
                "trajectory": trajectory
            })

            logger.info(f"[SAM2 Video API] Extracted trajectory for {inst.get('name', 'Unknown')}: {len(trajectory)} frames")

            # デバッグ：空のtrajectoryの場合、詳細を出力
            if len(trajectory) == 0:
                logger.warning(f"[DEBUG] Zero-length trajectory! obj_id={obj_id}, instruments_count={len(instruments)}, video_segments_frames={len(video_segments.keys())}")

        # 🆕 Phase 2: 時間的平滑化を適用
        from app.core.config import settings
        if settings.SAM2_ENABLE_TEMPORAL_SMOOTHING and len(trajectories) > 0:
            logger.info("[SAM2 Video API] Applying temporal smoothing...")
            trajectories = self._apply_temporal_smoothing(trajectories, settings.SAM2_SMOOTHING_WINDOW)
            logger.info("[SAM2 Video API] Temporal smoothing applied")

        return trajectories

    def _bbox_to_sam_format(self, bbox: List[float]) -> np.ndarray:
        """BBoxをSAM形式に変換"""
        return np.array(bbox, dtype=np.float32)

    def _center_to_sam_format(self, center: List[float]) -> np.ndarray:
        """中心点をSAM形式に変換"""
        return np.array([center], dtype=np.float32)

    def _mask_to_bbox(self, mask: np.ndarray) -> List[float]:
        """マスクからBBoxを抽出"""
        if mask.sum() == 0:
            return [0, 0, 0, 0]

        y_coords, x_coords = np.where(mask)
        x_min, x_max = float(x_coords.min()), float(x_coords.max())
        y_min, y_max = float(y_coords.min()), float(y_coords.max())

        return [x_min, y_min, x_max, y_max]

    def _calculate_mask_center(self, mask: np.ndarray) -> List[float]:
        """マスクの中心を計算"""
        if mask.sum() == 0:
            return [0.0, 0.0]

        y_coords, x_coords = np.where(mask)
        center_x = float(np.mean(x_coords))
        center_y = float(np.mean(y_coords))

        return [center_x, center_y]

    def _calculate_mask_confidence(self, mask: np.ndarray) -> float:
        """マスクの信頼度を計算"""
        if mask.size == 0:
            return 0.0

        area = mask.sum()
        total_pixels = mask.shape[0] * mask.shape[1]
        confidence = min(1.0, area / total_pixels)

        return float(confidence)

    def _get_video_frame_count(self, video_path: str) -> int:
        """
        動画のフレーム数を取得

        Args:
            video_path: 動画ファイルパス

        Returns:
            フレーム数
        """
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        logger.info(f"[SAM2 Video API] Detected {frame_count} frames in video")
        return frame_count

    def _apply_temporal_smoothing(
        self,
        trajectories: List[Dict[str, Any]],
        window_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        時間的平滑化を適用してジッターを削減

        Args:
            trajectories: 軌跡データのリスト
            window_size: 平滑化ウィンドウサイズ（奇数推奨）

        Returns:
            平滑化された軌跡データ
        """
        smoothed_trajectories = []

        for traj_data in trajectories:
            trajectory = traj_data["trajectory"]

            # 軌跡が短すぎる場合はスキップ
            if len(trajectory) < window_size:
                logger.warning(f"[SMOOTHING] Trajectory too short ({len(trajectory)} frames), skipping smoothing")
                smoothed_trajectories.append(traj_data)
                continue

            # 中心座標を抽出
            centers = np.array([frame["center"] for frame in trajectory])  # (N, 2)
            bboxes = np.array([frame["bbox"] for frame in trajectory])    # (N, 4)

            # メディアンフィルタを適用（各次元独立に）
            smoothed_centers = np.zeros_like(centers)
            smoothed_bboxes = np.zeros_like(bboxes)

            for dim in range(2):  # x, y
                smoothed_centers[:, dim] = median_filter(centers[:, dim], size=window_size, mode='nearest')

            for dim in range(4):  # x_min, y_min, x_max, y_max
                smoothed_bboxes[:, dim] = median_filter(bboxes[:, dim], size=window_size, mode='nearest')

            # 平滑化されたデータで更新
            smoothed_trajectory = []
            for i, frame in enumerate(trajectory):
                smoothed_frame = frame.copy()
                smoothed_frame["center"] = smoothed_centers[i].tolist()
                smoothed_frame["bbox"] = smoothed_bboxes[i].tolist()
                smoothed_trajectory.append(smoothed_frame)

            smoothed_trajectories.append({
                "instrument_id": traj_data["instrument_id"],
                "name": traj_data["name"],
                "trajectory": smoothed_trajectory
            })

            logger.info(f"[SMOOTHING] Applied median filter (window={window_size}) to {traj_data['name']}: {len(smoothed_trajectory)} frames")

        return smoothed_trajectories
