"""
SAMTrackerUnified Enhanced Detection ユニットテスト

Phase 1 の改善項目をテスト:
- マルチポイントプロンプト生成
- BBox精密化（ノイズ除去）
- 細長い器具への対応
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import sys

# バックエンドモジュールへのパスを追加
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified


class TestRobustPromptsForElongated:
    """_get_robust_prompts_for_elongated() のテスト"""

    def test_prompt_generation_with_mask(self):
        """マスク有りでプロンプトポイントが生成されるか"""
        # モックトラッカー（SAMなしで初期化可能にする）
        tracker = SAMTrackerUnified.__new__(SAMTrackerUnified)
        tracker.predictor = None
        tracker.mask_generator = None

        # 細長いマスクを作成（100x20の長方形）
        mask = np.zeros((200, 200), dtype=np.uint8)
        mask[90:110, 50:150] = 255  # 幅100px, 高さ20px

        bbox = [50, 90, 150, 110]

        points = tracker._get_robust_prompts_for_elongated(bbox, mask)

        # 最低1点（重心）+ 主軸方向2点 = 3点以上生成されるはず
        assert len(points) >= 1, "最低1点のプロンプトが必要"
        assert len(points) <= 5, "最大5点まで"

        # すべてのポイントがBBox内にあるか確認
        x1, y1, x2, y2 = bbox
        for px, py in points:
            assert x1 <= px <= x2, f"X座標がBBox外: {px} not in [{x1}, {x2}]"
            assert y1 <= py <= y2, f"Y座標がBBox外: {py} not in [{y1}, {y2}]"

    def test_prompt_generation_without_mask(self):
        """マスク無しでもフォールバックでポイント生成されるか"""
        tracker = SAMTrackerUnified.__new__(SAMTrackerUnified)
        tracker.predictor = None

        bbox = [50, 50, 150, 150]
        points = tracker._get_robust_prompts_for_elongated(bbox, mask=None)

        # 幾何学的中心が返されるはず
        assert len(points) == 1, "マスク無しでは幾何学的中心1点のみ"

        px, py = points[0]
        expected_cx = (50 + 150) // 2  # 100
        expected_cy = (50 + 150) // 2  # 100

        assert px == expected_cx, f"中心X座標が正しくない: {px} != {expected_cx}"
        assert py == expected_cy, f"中心Y座標が正しくない: {py} != {expected_cy}"

    def test_prompt_generation_with_empty_mask(self):
        """空のマスクでもエラーにならないか"""
        tracker = SAMTrackerUnified.__new__(SAMTrackerUnified)
        tracker.predictor = None

        mask = np.zeros((200, 200), dtype=np.uint8)  # 全て0
        bbox = [50, 50, 150, 150]

        points = tracker._get_robust_prompts_for_elongated(bbox, mask)

        # 幾何学的中心にフォールバック
        assert len(points) >= 1, "空マスクでもフォールバックで1点以上"


class TestRefineBBoxFromMask:
    """_refine_bbox_from_mask() のテスト"""

    def test_bbox_refinement_with_noise(self):
        """ノイズがある場合、精密化されたBBoxが取得できるか"""
        tracker = SAMTrackerUnified.__new__(SAMTrackerUnified)
        tracker.predictor = None

        # メインの領域 (50x50の正方形)
        mask = np.zeros((200, 200), dtype=np.uint8)
        mask[75:125, 75:125] = 255

        # ノイズピクセルを追加（端に数ピクセル）
        mask[10, 10] = 255
        mask[190, 190] = 255

        refined_bbox = tracker._refine_bbox_from_mask(mask)

        # ノイズが除去され、メイン領域のBBoxが取得されるはず
        x1, y1, x2, y2 = refined_bbox

        # 許容範囲: ±5px程度
        assert 70 <= x1 <= 80, f"X1がノイズの影響を受けている: {x1}"
        assert 70 <= y1 <= 80, f"Y1がノイズの影響を受けている: {y1}"
        assert 120 <= x2 <= 130, f"X2がノイズの影響を受けている: {x2}"
        assert 120 <= y2 <= 130, f"Y2がノイズの影響を受けている: {y2}"

    def test_bbox_refinement_empty_mask(self):
        """空のマスクでエラーにならないか"""
        tracker = SAMTrackerUnified.__new__(SAMTrackerUnified)
        tracker.predictor = None

        mask = np.zeros((200, 200), dtype=np.uint8)
        bbox = tracker._refine_bbox_from_mask(mask)

        assert bbox == [0, 0, 0, 0], "空マスクでは[0,0,0,0]を返す"

    def test_bbox_refinement_multiple_regions(self):
        """複数の連結成分がある場合、最大領域のみ採用されるか"""
        tracker = SAMTrackerUnified.__new__(SAMTrackerUnified)
        tracker.predictor = None

        mask = np.zeros((200, 200), dtype=np.uint8)

        # 小さい領域1 (10x10)
        mask[10:20, 10:20] = 255

        # 大きい領域2 (50x50) - これが採用されるべき
        mask[100:150, 100:150] = 255

        # 小さい領域3 (5x5)
        mask[180:185, 180:185] = 255

        bbox = tracker._refine_bbox_from_mask(mask)
        x1, y1, x2, y2 = bbox

        # 大きい領域のBBoxが取得されるはず
        assert 95 <= x1 <= 105, f"最大領域のX1が取得されていない: {x1}"
        assert 95 <= y1 <= 105, f"最大領域のY1が取得されていない: {y1}"
        assert 145 <= x2 <= 155, f"最大領域のX2が取得されていない: {x2}"
        assert 145 <= y2 <= 155, f"最大領域のY2が取得されていない: {y2}"


class TestElongatedInstrumentHandling:
    """細長い器具への対応テスト"""

    def test_elongated_mask_prompts(self):
        """細長いマスク（aspect ratio > 3）で主軸方向のプロンプトが生成されるか"""
        tracker = SAMTrackerUnified.__new__(SAMTrackerUnified)
        tracker.predictor = None

        # 非常に細長いマスク (150x10)
        mask = np.zeros((200, 200), dtype=np.uint8)
        mask[95:105, 25:175] = 255  # 幅150px, 高さ10px (aspect ratio = 15)

        bbox = [25, 95, 175, 105]

        points = tracker._get_robust_prompts_for_elongated(bbox, mask)

        # 細長い器具では、主軸方向に複数点が配置されるはず
        assert len(points) >= 3, f"細長い器具では最低3点必要: got {len(points)}"

        # X座標のバリエーションがあるか確認（横方向に分散）
        x_coords = [p[0] for p in points]
        x_range = max(x_coords) - min(x_coords)
        assert x_range > 50, f"主軸方向に分散していない: x_range={x_range}"


def test_integration_with_fallback():
    """エラー発生時にフォールバックが機能するか"""
    tracker = SAMTrackerUnified.__new__(SAMTrackerUnified)
    tracker.predictor = None

    # 不正なマスク（None）
    bbox = [50, 50, 150, 150]
    points = tracker._get_robust_prompts_for_elongated(bbox, mask=None)

    # フォールバックで幾何学的中心が返されるはず
    assert len(points) >= 1, "フォールバック失敗"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
