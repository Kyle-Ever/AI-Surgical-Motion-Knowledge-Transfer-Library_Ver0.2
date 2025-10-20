"""
Unit tests for FrameExtractionService

テスト対象:
1. frame_skip計算（round vs int）
2. 25fps動画の抽出
3. メタデータ取得
4. リトライ機構
5. 連続失敗時の早期停止
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import cv2

from app.services.frame_extraction_service import (
    FrameExtractionService,
    ExtractionConfig,
    VideoMetadata,
    ExtractionResult
)


class TestExtractionConfig:
    """ExtractionConfigのテスト"""

    def test_calculate_frame_skip_with_round(self):
        """round()を使用したframe_skip計算"""
        config = ExtractionConfig(target_fps=15.0, use_round=True)

        # 30fps → 15fps: 30/15 = 2.0 → round(2.0) = 2
        assert config.calculate_frame_skip(30.0) == 2

        # 25fps → 15fps: 25/15 = 1.666... → round(1.666) = 2
        assert config.calculate_frame_skip(25.0) == 2

        # 60fps → 15fps: 60/15 = 4.0 → round(4.0) = 4
        assert config.calculate_frame_skip(60.0) == 4

        # 10fps → 15fps: 10/15 = 0.666... → max(1, round(0.666)) = 1
        assert config.calculate_frame_skip(10.0) == 1

    def test_calculate_frame_skip_with_int(self):
        """int()を使用したframe_skip計算（後方互換性）"""
        config = ExtractionConfig(target_fps=15.0, use_round=False)

        # 30fps → 15fps: 30/15 = 2.0 → int(2.0) = 2
        assert config.calculate_frame_skip(30.0) == 2

        # 25fps → 15fps: 25/15 = 1.666... → int(1.666) = 1（問題！）
        assert config.calculate_frame_skip(25.0) == 1

        # 60fps → 15fps: 60/15 = 4.0 → int(4.0) = 4
        assert config.calculate_frame_skip(60.0) == 4

    def test_round_vs_int_difference(self):
        """round()とint()の違いを明示的にテスト"""
        config_round = ExtractionConfig(target_fps=15.0, use_round=True)
        config_int = ExtractionConfig(target_fps=15.0, use_round=False)

        # 25fpsの場合、round()とint()で結果が異なる
        assert config_round.calculate_frame_skip(25.0) == 2
        assert config_int.calculate_frame_skip(25.0) == 1

        # 30fpsの場合は同じ
        assert config_round.calculate_frame_skip(30.0) == 2
        assert config_int.calculate_frame_skip(30.0) == 2


class TestVideoMetadata:
    """VideoMetadataのテスト"""

    def test_metadata_str_representation(self):
        """文字列表現のテスト"""
        metadata = VideoMetadata(
            width=1920,
            height=1080,
            fps=25.0,
            total_frames=563,
            duration=22.52,
            codec="H264"
        )

        str_repr = str(metadata)
        assert "1920x1080" in str_repr
        assert "25.00" in str_repr
        assert "563" in str_repr
        assert "22.52" in str_repr
        assert "H264" in str_repr


class TestExtractionResult:
    """ExtractionResultのテスト"""

    def test_success_rate_calculation(self):
        """成功率の計算"""
        # 100フレーム抽出、10フレーム失敗 → 90.9%
        result = ExtractionResult(
            frames=[np.zeros((480, 640, 3), dtype=np.uint8)] * 100,
            frame_indices=list(range(100)),
            timestamps=[i * 0.04 for i in range(100)],
            failed_indices=list(range(100, 110)),
            metadata=VideoMetadata(640, 480, 25.0, 563, 22.52, "H264"),
            effective_fps=25.0,
            frame_skip=1
        )

        assert result.success_rate == pytest.approx(100 / 110, abs=0.01)
        assert result.total_attempted == 110

    def test_success_rate_zero_frames(self):
        """フレームが0の場合"""
        result = ExtractionResult(
            frames=[],
            frame_indices=[],
            timestamps=[],
            failed_indices=[],
            metadata=VideoMetadata(640, 480, 25.0, 563, 22.52, "H264"),
            effective_fps=0.0,
            frame_skip=1
        )

        assert result.success_rate == 0.0
        assert result.total_attempted == 0


class TestFrameExtractionService:
    """FrameExtractionServiceのテスト"""

    @patch('cv2.VideoCapture')
    def test_get_video_metadata(self, mock_cv2_capture):
        """メタデータ取得のテスト"""
        # モック設定
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_WIDTH: 1920,
            cv2.CAP_PROP_FRAME_HEIGHT: 1080,
            cv2.CAP_PROP_FPS: 25.0,
            cv2.CAP_PROP_FRAME_COUNT: 563,
            cv2.CAP_PROP_FOURCC: 0x34363248  # "H264"
        }.get(prop, 0)
        mock_cv2_capture.return_value = mock_cap

        service = FrameExtractionService()
        metadata = service._get_video_metadata("dummy.mp4")

        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.fps == 25.0
        assert metadata.total_frames == 563
        assert metadata.duration == pytest.approx(22.52, abs=0.01)
        assert metadata.codec == "H264"

        mock_cap.release.assert_called_once()

    @patch('cv2.VideoCapture')
    def test_extract_frames_success(self, mock_cv2_capture):
        """正常なフレーム抽出"""
        # モック設定
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        # メタデータ用のget
        def get_side_effect(prop):
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_FPS: 30.0,
                cv2.CAP_PROP_FRAME_COUNT: 100,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        # read()は常に成功
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)

        mock_cv2_capture.return_value = mock_cap

        # テスト実行
        service = FrameExtractionService(ExtractionConfig(target_fps=15.0, use_round=True))

        with patch.object(Path, 'exists', return_value=True):
            result = service.extract_frames("dummy.mp4")

        # 検証
        # 30fps → 15fps with round(): frame_skip = 2
        # 100フレーム, skip=2 → 50フレーム抽出
        assert len(result.frames) == 50
        assert len(result.failed_indices) == 0
        assert result.success_rate == 1.0
        assert result.frame_skip == 2

    @patch('cv2.VideoCapture')
    def test_extract_frames_with_25fps_round(self, mock_cv2_capture):
        """25fps動画のround()使用時のテスト"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_FPS: 25.0,  # 25fps
                cv2.CAP_PROP_FRAME_COUNT: 563,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)
        mock_cv2_capture.return_value = mock_cap

        # round()使用
        service = FrameExtractionService(ExtractionConfig(target_fps=15.0, use_round=True))

        with patch.object(Path, 'exists', return_value=True):
            result = service.extract_frames("dummy.mp4")

        # 25fps → 15fps with round(): frame_skip = 2
        # 563フレーム, skip=2 → 282フレーム抽出
        assert result.frame_skip == 2
        assert len(result.frames) == 282  # range(0, 563, 2) = 282 frames

        # effective_fps = 12.5fps (25/2)
        assert result.effective_fps == pytest.approx(12.5, abs=0.5)

    @patch('cv2.VideoCapture')
    def test_extract_frames_with_25fps_int(self, mock_cv2_capture):
        """25fps動画のint()使用時のテスト（後方互換性）"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_FPS: 25.0,
                cv2.CAP_PROP_FRAME_COUNT: 563,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)
        mock_cv2_capture.return_value = mock_cap

        # int()使用
        service = FrameExtractionService(ExtractionConfig(target_fps=15.0, use_round=False))

        with patch.object(Path, 'exists', return_value=True):
            result = service.extract_frames("dummy.mp4")

        # 25fps → 15fps with int(): frame_skip = 1（問題！）
        # 563フレーム, skip=1 → 563フレーム全て抽出
        assert result.frame_skip == 1
        assert len(result.frames) == 563

        # effective_fps = 25fps（意図しない結果）
        assert result.effective_fps == pytest.approx(25.0, abs=0.5)

    @patch('cv2.VideoCapture')
    @patch('time.sleep')  # sleep()をモック化して高速化
    def test_retry_mechanism(self, mock_sleep, mock_cv2_capture):
        """リトライ機構のテスト"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_FPS: 30.0,
                cv2.CAP_PROP_FRAME_COUNT: 10,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        # 1回目失敗、2回目成功
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (False, None),  # 1回目失敗
            (True, mock_frame),  # 2回目成功
            (True, mock_frame), (True, mock_frame), (True, mock_frame),
            (True, mock_frame), (True, mock_frame)
        ]

        mock_cv2_capture.return_value = mock_cap

        service = FrameExtractionService(ExtractionConfig(target_fps=15.0, max_retries=3))

        with patch.object(Path, 'exists', return_value=True):
            result = service.extract_frames("dummy.mp4")

        # 1フレーム目は2回目で成功するので、全5フレーム抽出できる
        assert len(result.frames) == 5
        assert len(result.failed_indices) == 0
        mock_sleep.assert_called()  # リトライ時にsleep()が呼ばれる

    @patch('cv2.VideoCapture')
    def test_consecutive_failure_early_stop(self, mock_cv2_capture):
        """連続失敗による早期停止のテスト"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_FPS: 30.0,
                cv2.CAP_PROP_FRAME_COUNT: 100,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        # 最初の5フレーム成功、その後すべて失敗
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        read_results = [(True, mock_frame)] * 5 + [(False, None)] * 100
        mock_cap.read.side_effect = read_results

        mock_cv2_capture.return_value = mock_cap

        service = FrameExtractionService(
            ExtractionConfig(
                target_fps=15.0,
                max_retries=1,
                max_consecutive_failures=10
            )
        )

        with patch.object(Path, 'exists', return_value=True):
            # 成功率が50%未満なのでValueError
            with pytest.raises(ValueError, match="Frame extraction failed"):
                service.extract_frames("dummy.mp4")

    @patch('cv2.VideoCapture')
    def test_low_success_rate_raises_error(self, mock_cv2_capture):
        """成功率が50%未満でエラーを発生させる"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_FPS: 30.0,
                cv2.CAP_PROP_FRAME_COUNT: 100,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        # 40%の成功率（20成功、30失敗）
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        read_results = [(True, mock_frame)] * 20 + [(False, None)] * 100
        mock_cap.read.side_effect = read_results

        mock_cv2_capture.return_value = mock_cap

        service = FrameExtractionService(
            ExtractionConfig(target_fps=15.0, max_retries=1, max_consecutive_failures=100)
        )

        with patch.object(Path, 'exists', return_value=True):
            with pytest.raises(ValueError, match="success rate"):
                service.extract_frames("dummy.mp4")

    def test_file_not_found(self):
        """存在しないファイルのテスト"""
        service = FrameExtractionService()

        with pytest.raises(FileNotFoundError):
            service.extract_frames("/nonexistent/video.mp4")

    @patch('cv2.VideoCapture')
    def test_cannot_open_video(self, mock_cv2_capture):
        """動画が開けない場合のテスト"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2_capture.return_value = mock_cap

        service = FrameExtractionService()

        with patch.object(Path, 'exists', return_value=True):
            with pytest.raises(ValueError, match="Cannot open video"):
                service.extract_frames("corrupted.mp4")
