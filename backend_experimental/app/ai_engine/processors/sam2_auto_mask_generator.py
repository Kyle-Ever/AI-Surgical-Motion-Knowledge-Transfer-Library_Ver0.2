"""
SAM2 Automatic Mask Generator
自動マスク生成機能を使用した器具検出
"""
import cv2
import numpy as np
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SAM2AutoMaskGenerator:
    """
    SAM2の自動マスク生成機能を使用した器具検出

    YOLOとの違い:
    - クラス分類なし（すべてのオブジェクトを検出）
    - より高精度なセグメンテーション
    - 小さい物体や細長い物体の検出に優れる
    """

    def __init__(self, min_mask_area: int = 100):
        """
        初期化

        Args:
            min_mask_area: 検出する最小マスク面積（ピクセル数）
        """
        self.min_mask_area = min_mask_area
        self.is_mock = True  # 現在はモック実装
        logger.info(f"SAM2AutoMaskGenerator initialized (min_area={min_mask_area})")

    def generate_masks(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        フレームから自動的にマスクを生成

        Args:
            frame: 入力画像フレーム

        Returns:
            検出されたマスクのリスト
        """
        if self.is_mock:
            return self._mock_generate_masks(frame)
        else:
            return self._real_generate_masks(frame)

    def _mock_generate_masks(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        モック実装：シンプルな輪郭検出

        実装方針:
        1. グレースケール変換
        2. 適応的二値化
        3. 輪郭検出
        4. 面積フィルタリング
        """
        height, width = frame.shape[:2]

        # グレースケール変換
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 適応的二値化（局所的な明度変化に対応）
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=21,
            C=10
        )

        # ノイズ除去（モルフォロジー演算）
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # 輪郭検出
        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        masks = []
        for i, contour in enumerate(contours):
            # 面積計算
            area = cv2.contourArea(contour)

            # 小さすぎる領域は除外
            if area < self.min_mask_area:
                continue

            # バウンディングボックス
            x, y, w, h = cv2.boundingRect(contour)

            # マスク生成
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, -1)

            # 中心座標
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx, cy = x + w // 2, y + h // 2

            # アスペクト比（細長さの指標）
            aspect_ratio = float(w) / float(h) if h > 0 else 0

            # 信頼度スコア（面積ベース）
            # 大きい物体ほど高スコア（ただし上限あり）
            confidence = min(0.95, 0.5 + (area / (width * height)) * 2)

            masks.append({
                "id": i,
                "mask": mask,
                "bbox": [x, y, x + w, y + h],
                "area": int(area),
                "center": {"x": float(cx), "y": float(cy)},
                "aspect_ratio": float(aspect_ratio),
                "confidence": float(confidence),
                "suggested_name": self._suggest_instrument_name(
                    aspect_ratio, area, width * height
                )
            })

        # 面積の大きい順にソート
        masks.sort(key=lambda m: m["area"], reverse=True)

        # IDを振り直し
        for i, mask in enumerate(masks):
            mask["id"] = i

        logger.info(f"Generated {len(masks)} masks from frame")
        return masks

    def _real_generate_masks(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        実SAM2の自動マスク生成

        TODO: SAM2の実装時に有効化
        """
        raise NotImplementedError("Real SAM2 auto mask generation not implemented yet")

    def _suggest_instrument_name(
        self,
        aspect_ratio: float,
        area: int,
        frame_area: int
    ) -> str:
        """
        形状特徴から器具名を推定

        Args:
            aspect_ratio: アスペクト比（幅/高さ）
            area: マスク面積
            frame_area: フレーム全体の面積

        Returns:
            推定器具名
        """
        relative_area = area / frame_area

        # 細長い物体（アスペクト比 > 3 または < 0.33）
        if aspect_ratio > 3 or (aspect_ratio < 0.33 and aspect_ratio > 0):
            if relative_area > 0.1:
                return "鉗子（大）"
            elif relative_area > 0.05:
                return "鉗子"
            else:
                return "細長い器具"

        # 中程度の大きさの物体
        elif 0.5 <= aspect_ratio <= 2.0:
            if relative_area > 0.15:
                return "手"
            elif relative_area > 0.05:
                return "器具"
            else:
                return "小型器具"

        # その他
        else:
            return "検出物体"

    def filter_by_confidence(
        self,
        masks: List[Dict[str, Any]],
        min_confidence: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        信頼度でフィルタリング

        Args:
            masks: マスクリスト
            min_confidence: 最小信頼度

        Returns:
            フィルタリング後のマスク
        """
        filtered = [m for m in masks if m["confidence"] >= min_confidence]
        logger.info(f"Filtered {len(masks)} -> {len(filtered)} masks (min_confidence={min_confidence})")
        return filtered

    def merge_overlapping_masks(
        self,
        masks: List[Dict[str, Any]],
        iou_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        重複するマスクをマージ

        Args:
            masks: マスクリスト
            iou_threshold: IoU閾値（これ以上で重複とみなす）

        Returns:
            マージ後のマスク
        """
        if len(masks) <= 1:
            return masks

        # 面積の大きい順にソート済みと仮定
        merged = []
        used = set()

        for i, mask1 in enumerate(masks):
            if i in used:
                continue

            current_mask = mask1
            for j, mask2 in enumerate(masks[i + 1:], start=i + 1):
                if j in used:
                    continue

                # IoU計算
                iou = self._calculate_iou(
                    mask1["bbox"],
                    mask2["bbox"]
                )

                if iou > iou_threshold:
                    # 大きい方を採用
                    if mask2["area"] > current_mask["area"]:
                        current_mask = mask2
                    used.add(j)

            merged.append(current_mask)

        logger.info(f"Merged {len(masks)} -> {len(merged)} masks (iou_threshold={iou_threshold})")
        return merged

    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """
        IoU（Intersection over Union）を計算

        Args:
            bbox1: [x1, y1, x2, y2]
            bbox2: [x1, y1, x2, y2]

        Returns:
            IoU値（0-1）
        """
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        # 交差領域
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)

        if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
            return 0.0

        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)

        # 各ボックスの面積
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)

        # Union
        union_area = area1 + area2 - inter_area

        if union_area == 0:
            return 0.0

        return inter_area / union_area
