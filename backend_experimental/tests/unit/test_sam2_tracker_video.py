"""
SAM2TrackerVideo単体テスト

SAM2 Video APIの機能を個別に検証
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from app.ai_engine.processors.sam2_tracker_video import SAM2TrackerVideo


class TestSAM2TrackerVideo:
    """SAM2TrackerVideo単体テスト"""

    @pytest.fixture
    def mock_predictor(self):
        """モック予測器を作成"""
        predictor = MagicMock()
        predictor.init_state = MagicMock()
        predictor.add_new_points_or_box = MagicMock()
        predictor.propagate_in_video = MagicMock()
        return predictor

    @pytest.fixture
    def sample_frames(self):
        """サンプルフレームを作成"""
        # 10フレーム、640x480、RGB
        return [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(10)]

    @pytest.fixture
    def sample_instruments(self):
        """サンプル器具データを作成"""
        return [
            {
                "instrument_id": "inst_1",
                "name": "Forceps",
                "bbox": [100, 100, 200, 200],
                "center": [150, 150],
                "confidence": 0.95
            },
            {
                "instrument_id": "inst_2",
                "name": "Scalpel",
                "bbox": [300, 300, 400, 400],
                "center": [350, 350],
                "confidence": 0.88
            }
        ]

    def test_initialization_cpu(self):
        """CPU初期化のテスト"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo(device="cpu")
            assert tracker.device == "cpu"
            assert tracker.model_type == "small"

    def test_initialization_gpu_auto_detect(self):
        """GPU自動検出のテスト"""
        with patch('torch.cuda.is_available', return_value=True), \
             patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo(device="auto")
            assert tracker.device == "cuda"

    def test_initialization_gpu_unavailable(self):
        """GPU利用不可時のフォールバックテスト"""
        with patch('torch.cuda.is_available', return_value=False), \
             patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo(device="auto")
            assert tracker.device == "cpu"

    @pytest.mark.asyncio
    async def test_track_video_empty_frames(self, sample_instruments):
        """空フレームリストのエラーハンドリング"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            with pytest.raises(ValueError) as exc_info:
                await tracker.track_video([], sample_instruments)

            assert "frames" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_track_video_empty_instruments(self, sample_frames):
        """器具なしの場合の処理"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            result = await tracker.track_video(sample_frames, [])

            assert result is not None
            assert "instruments" in result
            assert len(result["instruments"]) == 0

    @pytest.mark.asyncio
    async def test_track_video_success(self, mock_predictor, sample_frames, sample_instruments):
        """正常なトラッキングのテスト"""
        # モック設定
        mock_inference_state = MagicMock()
        mock_predictor.init_state.return_value = mock_inference_state

        # propagate_in_videoの戻り値をモック
        mock_mask = np.random.rand(1, 480, 640) > 0.5
        mock_propagate_results = [
            (0, [1, 2], mock_mask),  # frame 0
            (1, [1, 2], mock_mask),  # frame 1
        ]
        mock_predictor.propagate_in_video.return_value = mock_propagate_results

        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor',
                   return_value=mock_predictor):
            tracker = SAM2TrackerVideo()

            result = await tracker.track_video(sample_frames[:2], sample_instruments)

            # 結果検証
            assert result is not None
            assert "instruments" in result
            assert len(result["instruments"]) == 2

            # 各器具のトラジェクトリを確認
            for instrument in result["instruments"]:
                assert "instrument_id" in instrument
                assert "name" in instrument
                assert "trajectory" in instrument
                assert len(instrument["trajectory"]) > 0

    def test_bbox_to_sam_format(self):
        """BBoxのSAM形式変換テスト"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            bbox = [100, 100, 200, 200]  # [x1, y1, x2, y2]
            sam_box = tracker._bbox_to_sam_format(bbox)

            assert sam_box.shape == (4,)
            assert sam_box[0] == 100  # x1
            assert sam_box[1] == 100  # y1
            assert sam_box[2] == 200  # x2
            assert sam_box[3] == 200  # y2

    def test_center_to_sam_format(self):
        """中心点のSAM形式変換テスト"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            center = [150, 150]
            sam_points = tracker._center_to_sam_format(center)

            assert sam_points.shape == (1, 2)
            assert sam_points[0, 0] == 150
            assert sam_points[0, 1] == 150

    def test_extract_trajectories_invalid_data(self):
        """無効なセグメンテーションデータのエラーハンドリング"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            invalid_segments = {}  # 空のセグメント
            instruments = [{"id": "inst_1", "name": "Test"}]  # "id"フィールドを使用

            trajectories = tracker._extract_trajectories(invalid_segments, instruments)

            # エラーなく処理され、空のトラジェクトリが返される
            assert len(trajectories) == 1
            assert len(trajectories[0]["trajectory"]) == 0

    def test_mask_to_bbox(self):
        """マスクからBBox抽出のテスト"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            # 簡単なマスクを作成
            mask = np.zeros((100, 100), dtype=bool)
            mask[20:80, 30:70] = True  # 60x40の矩形

            bbox = tracker._mask_to_bbox(mask)

            assert bbox[0] == 30  # x1
            assert bbox[1] == 20  # y1
            assert bbox[2] == 69  # x2 (maxインデックスは69)
            assert bbox[3] == 79  # y2 (maxインデックスは79)

    def test_mask_to_bbox_empty_mask(self):
        """空マスクのBBox抽出テスト"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            empty_mask = np.zeros((100, 100), dtype=bool)

            bbox = tracker._mask_to_bbox(empty_mask)

            # デフォルト値が返される
            assert bbox == [0, 0, 0, 0]

    def test_calculate_mask_center(self):
        """マスク中心計算のテスト"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            # 中心が(50, 50)のマスクを作成
            mask = np.zeros((100, 100), dtype=bool)
            mask[40:60, 40:60] = True

            center = tracker._calculate_mask_center(mask)

            # 中心は大体(50, 50)付近
            assert abs(center[0] - 50) < 5
            assert abs(center[1] - 50) < 5

    def test_calculate_mask_confidence(self):
        """マスク信頼度計算のテスト"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            # 50%のピクセルが陽性のマスク
            mask = np.zeros((100, 100), dtype=bool)
            mask[:50, :] = True

            confidence = tracker._calculate_mask_confidence(mask)

            # 0.0～1.0の範囲
            assert 0.0 <= confidence <= 1.0
            assert confidence > 0.3  # 50%のマスクなので低すぎないはず


class TestSAM2TrackerVideoEdgeCases:
    """エッジケーステスト"""

    @pytest.mark.asyncio
    async def test_single_frame_video(self):
        """1フレームのみの動画処理"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            frames = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)]
            instruments = [{"instrument_id": "inst_1", "name": "Test", "bbox": [0, 0, 100, 100]}]

            # エラーなく処理できるはず
            result = await tracker.track_video(frames, instruments)
            assert result is not None

    @pytest.mark.asyncio
    async def test_many_instruments(self):
        """多数の器具（10個以上）の処理"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            frames = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(5)]
            instruments = [
                {
                    "instrument_id": f"inst_{i}",
                    "name": f"Instrument{i}",
                    "bbox": [i*50, i*50, i*50+100, i*50+100]
                }
                for i in range(15)  # 15個の器具
            ]

            # エラーなく処理できるはず
            result = await tracker.track_video(frames, instruments)
            assert result is not None
            assert len(result["instruments"]) == 15

    @pytest.mark.asyncio
    async def test_invalid_bbox_format(self):
        """不正なBBoxフォーマットのエラーハンドリング"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            frames = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)]
            instruments = [
                {"instrument_id": "inst_1", "name": "Test", "bbox": [100, 100]}  # 不完全なbbox
            ]

            # graceful degradation（エラーを出すか、スキップするか）
            with pytest.raises((ValueError, IndexError)):
                await tracker.track_video(frames, instruments)

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        """必須フィールド欠損のエラーハンドリング"""
        with patch('app.ai_engine.processors.sam2_tracker_video.build_sam2_video_predictor'):
            tracker = SAM2TrackerVideo()

            frames = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)]
            instruments = [
                {"name": "Test"}  # instrument_id とbbox が欠損
            ]

            # 必須フィールドがないのでエラー
            with pytest.raises((KeyError, ValueError)):
                await tracker.track_video(frames, instruments)
