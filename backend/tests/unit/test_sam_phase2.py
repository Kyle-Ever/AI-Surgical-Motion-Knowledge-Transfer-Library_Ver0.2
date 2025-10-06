"""
Phase 2 ユニットテスト: 動的信頼度閾値と適応的探索範囲拡張

テスト対象:
1. 動的信頼度閾値の計算（安定性に基づく調整）
2. 適応的探索範囲拡張（サイズ・速度ベース）
"""

import pytest
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
from collections import deque


@pytest.fixture
def tracker():
    """SAMTrackerUnifiedインスタンスを作成（SAMモデルなし）"""
    # SAMモデルロードをスキップするため、checkpoint_pathをモック
    class MockTracker(SAMTrackerUnified):
        def _load_sam_model(self, checkpoint_path):
            # SAMモデルのロードをスキップ
            self.predictor = None

    return MockTracker()


class TestDynamicConfidenceThreshold:
    """Phase 2.1: 動的信頼度閾値のテスト"""

    def test_initial_threshold_uses_base(self, tracker):
        """履歴が少ない場合はベース閾値を使用"""
        track_id = 0
        threshold = tracker._get_dynamic_confidence_threshold(track_id, 0.8)
        assert threshold == tracker.base_confidence_threshold

    def test_stable_high_scores_increase_threshold(self, tracker):
        """安定して高いスコアは高い閾値を生成"""
        track_id = 0

        # 安定した高スコアを追加
        for score in [0.9, 0.91, 0.89, 0.90, 0.92]:
            threshold = tracker._get_dynamic_confidence_threshold(track_id, score)

        # 最後の閾値は平均の80-90%程度（CV < 0.5）
        # 平均 ≈ 0.90, threshold ≈ 0.72-0.81
        assert threshold >= 0.7
        assert threshold <= 0.9

    def test_unstable_scores_decrease_threshold(self, tracker):
        """不安定なスコアは低い閾値を生成"""
        track_id = 1

        # 不安定なスコア（大きな変動）
        for score in [0.8, 0.4, 0.9, 0.3, 0.85]:
            threshold = tracker._get_dynamic_confidence_threshold(track_id, score)

        # 変動が大きいため低い閾値（平均の70%程度）
        assert threshold >= 0.3
        assert threshold <= 0.6

    def test_threshold_within_bounds(self, tracker):
        """閾値が0.3〜0.7の範囲内に制限される"""
        track_id = 2

        # 非常に低いスコア
        for score in [0.1, 0.15, 0.12]:
            threshold = tracker._get_dynamic_confidence_threshold(track_id, score)

        assert threshold >= 0.3
        assert threshold <= 0.7

    def test_different_tracks_independent(self, tracker):
        """異なるトラックIDは独立した履歴を持つ"""
        track1_threshold = tracker._get_dynamic_confidence_threshold(0, 0.9)
        track2_threshold = tracker._get_dynamic_confidence_threshold(1, 0.5)

        # 異なる履歴を持つため、異なる閾値になる可能性が高い
        assert 0 in tracker.track_confidence_history
        assert 1 in tracker.track_confidence_history


class TestAdaptiveSearchExpansion:
    """Phase 2.2: 適応的探索範囲拡張のテスト"""

    def test_size_based_expansion(self, tracker):
        """サイズベースの拡張が機能する"""
        track_id = 0
        small_bbox = [100, 100, 150, 140]  # 50x40 → max_side=50
        large_bbox = [100, 100, 300, 400]  # 200x300 → max_side=300

        small_expansion = tracker._get_adaptive_search_expansion(track_id, small_bbox)
        large_expansion = tracker._get_adaptive_search_expansion(track_id, large_bbox)

        # 大きいBBoxは大きい探索範囲
        # （ただし速度成分がないため、最小値50pxになる可能性あり）
        assert small_expansion >= 50
        assert large_expansion >= small_expansion

    def test_velocity_based_expansion(self, tracker):
        """速度ベースの拡張が機能する"""
        track_id = 0
        bbox = [100, 100, 200, 200]

        # 軌跡を追加（速い移動）
        tracker.trajectories[track_id] = deque(maxlen=30)
        tracker.trajectories[track_id].append((150, 150))
        tracker.trajectories[track_id].append((250, 250))  # 移動距離: ~141px

        expansion = tracker._get_adaptive_search_expansion(track_id, bbox)

        # 速度成分が追加されるため、基本値より大きい
        # 移動距離141 * 1.5 = 211 → min(200, ...) = 200px
        assert expansion >= 100

    def test_expansion_within_bounds(self, tracker):
        """探索範囲が50〜200pxに制限される"""
        track_id = 0

        # 非常に小さいBBox
        tiny_bbox = [100, 100, 110, 110]  # 10x10
        expansion = tracker._get_adaptive_search_expansion(track_id, tiny_bbox)
        assert expansion >= 50

        # 非常に大きいBBox + 高速移動
        huge_bbox = [100, 100, 1000, 1000]  # 900x900
        tracker.trajectories[track_id] = deque(maxlen=30)
        tracker.trajectories[track_id].append((500, 500))
        tracker.trajectories[track_id].append((1000, 1000))  # 移動距離: ~707px

        expansion = tracker._get_adaptive_search_expansion(track_id, huge_bbox)
        assert expansion <= 200

    def test_no_velocity_history(self, tracker):
        """速度履歴がない場合はサイズベースのみ"""
        track_id = 0
        bbox = [100, 100, 200, 200]  # 100x100 → max_side=100

        expansion = tracker._get_adaptive_search_expansion(track_id, bbox)

        # サイズベース: 100 * 0.3 = 30 → min(50, 30) = 50
        assert expansion == 50

    def test_single_point_trajectory(self, tracker):
        """軌跡が1点しかない場合は速度成分なし"""
        track_id = 0
        bbox = [100, 100, 200, 200]

        tracker.trajectories[track_id] = deque(maxlen=30)
        tracker.trajectories[track_id].append((150, 150))

        expansion = tracker._get_adaptive_search_expansion(track_id, bbox)

        # 速度成分なし → サイズベースのみ
        assert expansion >= 50


class TestIntegration:
    """Phase 2統合テスト"""

    def test_dynamic_threshold_and_adaptive_expansion_together(self, tracker):
        """動的閾値と適応的探索範囲が同時に機能する"""
        track_id = 0
        bbox = [100, 100, 200, 200]

        # 信頼度履歴を作成
        for score in [0.85, 0.87, 0.86]:
            tracker._get_dynamic_confidence_threshold(track_id, score)

        # 軌跡を追加
        tracker.trajectories[track_id] = deque(maxlen=30)
        tracker.trajectories[track_id].append((150, 150))
        tracker.trajectories[track_id].append((180, 180))

        threshold = tracker._get_dynamic_confidence_threshold(track_id, 0.85)
        expansion = tracker._get_adaptive_search_expansion(track_id, bbox)

        assert threshold > 0
        assert expansion >= 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
