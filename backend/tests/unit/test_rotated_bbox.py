"""
Phase 2.5 ユニットテスト: 回転BBox（Rotated Bounding Box）

テスト対象:
1. 回転BBox計算の正確性
2. 面積削減効果の検証
3. エラーハンドリング
4. 後方互換性
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified


@pytest.fixture
def tracker():
    """SAMTrackerUnifiedインスタンスを作成（SAMモデルなし）"""
    class MockTracker(SAMTrackerUnified):
        def _load_sam_model(self, checkpoint_path):
            # SAMモデルのロードをスキップ
            self.predictor = None

    return MockTracker()


class TestRotatedBBox:
    """回転BBoxのテスト"""

    def test_vertical_instrument(self, tracker):
        """垂直器具の回転BBox"""
        # 垂直の細長いマスク（10x100ピクセル）
        mask = np.zeros((120, 30), dtype=np.uint8)
        mask[10:110, 10:20] = 255

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 検証
        assert "rotated_bbox" in result
        assert "rotation_angle" in result
        assert "rect_bbox" in result
        assert "area_reduction" in result

        # 回転BBoxは4点
        assert len(result["rotated_bbox"]) == 4

        # 垂直器具なので回転角度は0度付近
        assert abs(result["rotation_angle"]) < 10 or abs(result["rotation_angle"] - 90) < 10

    def test_horizontal_instrument(self, tracker):
        """水平器具の回転BBox"""
        # 水平の細長いマスク（100x10ピクセル）
        mask = np.zeros((30, 120), dtype=np.uint8)
        mask[10:20, 10:110] = 255

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 回転BBoxは4点
        assert len(result["rotated_bbox"]) == 4

        # 水平器具なので回転角度は0度または90度付近
        angle = result["rotation_angle"]
        assert abs(angle) < 10 or abs(angle - 90) < 10 or abs(angle + 90) < 10

    def test_diagonal_instrument(self, tracker):
        """斜め器具の回転BBox（面積削減効果）"""
        # 45度傾斜の細長いマスク
        mask = np.zeros((150, 150), dtype=np.uint8)

        # 対角線上にマスクを描画
        for i in range(20, 130):
            x = i
            y = i
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    if 0 <= x+dx < 150 and 0 <= y+dy < 150:
                        mask[y+dy, x+dx] = 255

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 面積削減率が30%以上（斜め器具は大きな削減効果）
        assert result["area_reduction"] > 30.0

        print(f"Diagonal instrument: area_reduction = {result['area_reduction']:.1f}%")

    def test_area_reduction_calculation(self, tracker):
        """面積削減率の計算精度"""
        # 細長い矩形マスク（アスペクト比 5:1）
        mask = np.zeros((60, 260), dtype=np.uint8)
        mask[20:40, 10:250] = 255  # 20x240 = 4800 px^2

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 矩形BBoxの面積計算
        rect_bbox = result["rect_bbox"]
        rect_area = (rect_bbox[2] - rect_bbox[0]) * (rect_bbox[3] - rect_bbox[1])

        # 面積削減率は0-100%の範囲
        assert 0 <= result["area_reduction"] <= 100

        print(f"Rect area: {rect_area} px^2, reduction: {result['area_reduction']:.1f}%")

    def test_empty_mask(self, tracker):
        """空のマスクのエラーハンドリング"""
        mask = np.zeros((100, 100), dtype=np.uint8)

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 空マスクでもエラーにならず、デフォルト値を返す
        assert result["rotated_bbox"] == [[0, 0], [0, 0], [0, 0], [0, 0]]
        assert result["rotation_angle"] == 0.0
        assert result["rect_bbox"] == [0, 0, 0, 0]
        assert result["area_reduction"] == 0.0

    def test_square_instrument(self, tracker):
        """正方形器具（面積削減効果は小さい）"""
        # 正方形マスク（50x50ピクセル）
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[25:75, 25:75] = 255

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 正方形は回転しても面積変化が小さい
        assert result["area_reduction"] < 15.0

    def test_complex_shape(self, tracker):
        """複雑な形状のマスク"""
        # L字型マスク
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:40] = 255  # 縦棒
        mask[60:80, 20:80] = 255  # 横棒

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 複雑形状でもエラーにならない
        assert len(result["rotated_bbox"]) == 4
        assert isinstance(result["rotation_angle"], float)

    def test_backward_compatibility(self, tracker):
        """後方互換性: rect_bboxが常に存在"""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[30:70, 40:60] = 255

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 従来の矩形BBoxが必ず存在
        assert "rect_bbox" in result
        assert len(result["rect_bbox"]) == 4
        assert all(isinstance(x, int) for x in result["rect_bbox"])


class TestRotatedBBoxIntegration:
    """回転BBoxの統合テスト"""

    def test_rotated_bbox_format(self, tracker):
        """回転BBoxのフォーマット検証"""
        mask = np.zeros((100, 200), dtype=np.uint8)
        mask[30:70, 50:150] = 255

        result = tracker._get_rotated_bbox_from_mask(mask)

        # rotated_bboxは [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 形式
        assert isinstance(result["rotated_bbox"], list)
        assert len(result["rotated_bbox"]) == 4
        for point in result["rotated_bbox"]:
            assert isinstance(point, list)
            assert len(point) == 2
            assert isinstance(point[0], int)
            assert isinstance(point[1], int)

    def test_area_reduction_accuracy(self, tracker):
        """面積削減率の精度検証"""
        # 細長い斜め器具
        mask = np.zeros((200, 200), dtype=np.uint8)

        # 30度傾斜
        import cv2
        center = (100, 100)
        axes = (80, 20)  # 長軸80px, 短軸20px
        angle = 30
        cv2.ellipse(mask, center, axes, angle, 0, 360, 255, -1)

        result = tracker._get_rotated_bbox_from_mask(mask)

        # 斜め器具は20-40%の削減効果
        assert 15 < result["area_reduction"] < 50

        print(f"30° ellipse: reduction = {result['area_reduction']:.1f}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
