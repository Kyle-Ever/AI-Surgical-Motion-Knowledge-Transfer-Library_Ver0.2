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
        
        if self.use_mock:
            logger.info("Using mock SAM implementation")
            self.predictor = None
            self.mask_generator = None
        else:
            try:
                # SAMモデルのロード
                if checkpoint_path and Path(checkpoint_path).exists():
                    sam = sam_model_registry[model_type](checkpoint=checkpoint_path)
                else:
                    # デフォルトのモデルを使用（ダウンロード必要）
                    logger.warning("SAM checkpoint not found. Using mock mode.")
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
        
        # ポイント周辺に円形のマスクを生成
        mask = np.zeros((h, w), dtype=bool)
        for (x, y), label in zip(point_coords, point_labels):
            if label == 1:  # 前景
                # 円形領域をマスク
                radius = np.random.randint(30, 80)
                y_grid, x_grid = np.ogrid[:h, :w]
                dist = np.sqrt((x_grid - x)**2 + (y_grid - y)**2)
                mask |= dist <= radius
        
        bbox = self._get_bbox_from_mask(mask)
        
        return {
            "mask": mask,
            "score": np.random.uniform(0.8, 0.95),
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
        
        # ボックス内に楕円形のマスクを生成
        mask = np.zeros((h, w), dtype=bool)
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        width = x2 - x1
        height = y2 - y1
        
        # 楕円形マスク
        y_grid, x_grid = np.ogrid[:h, :w]
        ellipse_mask = ((x_grid - center_x) / (width/2))**2 + \
                      ((y_grid - center_y) / (height/2))**2 <= 1
        
        # ボックス内に制限
        mask[y1:y2, x1:x2] = ellipse_mask[y1:y2, x1:x2]
        
        return {
            "mask": mask,
            "score": np.random.uniform(0.85, 0.98),
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