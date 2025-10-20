"""
Integration tests for 25fps video analysis pipeline

25fps動画での解析パイプライン統合テスト:
1. フレーム抽出がround()を使用して正しいframe_skipを計算
2. タイムスタンプが正確にマッピングされる
3. 全フレームが抽出される（4秒で止まらない）
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from app.services.analysis_service_v2 import AnalysisServiceV2
from app.services.frame_extraction_service import FrameExtractionService, ExtractionConfig
from app.models import SessionLocal
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.models.video import Video, VideoType


class TestAnalysisPipeline25fps:
    """25fps動画解析パイプラインのテスト"""

    @pytest.fixture
    def mock_25fps_video_path(self, tmp_path):
        """25fps動画のモックパスを作成"""
        video_path = tmp_path / "test_25fps.mp4"
        video_path.touch()
        return str(video_path)

    @pytest.fixture
    def mock_db_session(self):
        """モックDBセッション"""
        session = Mock()

        # モック動画レコード
        mock_video = Mock(spec=Video)
        mock_video.id = "test-video-id"
        mock_video.file_path = "test_25fps.mp4"
        mock_video.video_type = VideoType.EXTERNAL_WITH_INSTRUMENTS
        mock_video.fps = 25.0
        mock_video.frame_count = 563
        mock_video.duration = 22.52

        # モック解析レコード
        mock_analysis = Mock(spec=AnalysisResult)
        mock_analysis.id = "test-analysis-id"
        mock_analysis.video_id = "test-video-id"
        mock_analysis.status = AnalysisStatus.PENDING

        session.query.return_value.filter.return_value.first.side_effect = [
            mock_analysis,  # 最初の呼び出し: AnalysisResult
            mock_video      # 2番目の呼び出し: Video
        ]

        return session

    @patch('cv2.VideoCapture')
    async def test_25fps_video_extraction_with_round(self, mock_cv2_capture, mock_25fps_video_path):
        """25fps動画でround()を使用したframe_skip計算のテスト"""

        # モックVideoCapture設定
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            import cv2
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 1920,
                cv2.CAP_PROP_FRAME_HEIGHT: 1080,
                cv2.CAP_PROP_FPS: 25.0,
                cv2.CAP_PROP_FRAME_COUNT: 563,
                cv2.CAP_PROP_FOURCC: 0x34363248  # "H264"
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        # 全フレーム読み込み成功
        mock_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)

        mock_cv2_capture.return_value = mock_cap

        # フレーム抽出サービスでテスト
        service = FrameExtractionService(
            ExtractionConfig(target_fps=15.0, use_round=True)
        )

        with patch.object(Path, 'exists', return_value=True):
            result = service.extract_frames(mock_25fps_video_path)

        # 検証
        # 25fps → 15fps with round(): frame_skip = round(25/15) = round(1.666) = 2
        assert result.frame_skip == 2

        # 563フレーム, skip=2 → 282フレーム抽出
        assert len(result.frames) == 282

        # effective_fps ≈ 12.5fps (25/2)
        assert result.effective_fps == pytest.approx(12.5, abs=0.5)

        # タイムスタンプが正確
        assert result.timestamps[0] == pytest.approx(0.0, abs=0.01)
        assert result.timestamps[-1] == pytest.approx(22.48, abs=0.1)  # (563-1)/25

    @patch('cv2.VideoCapture')
    async def test_25fps_vs_int_difference(self, mock_cv2_capture, mock_25fps_video_path):
        """25fps動画でround()とint()の違いを検証"""

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            import cv2
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 1920,
                cv2.CAP_PROP_FRAME_HEIGHT: 1080,
                cv2.CAP_PROP_FPS: 25.0,
                cv2.CAP_PROP_FRAME_COUNT: 563,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect
        mock_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)
        mock_cv2_capture.return_value = mock_cap

        # round()使用
        service_round = FrameExtractionService(
            ExtractionConfig(target_fps=15.0, use_round=True)
        )

        # int()使用（旧実装）
        service_int = FrameExtractionService(
            ExtractionConfig(target_fps=15.0, use_round=False)
        )

        with patch.object(Path, 'exists', return_value=True):
            result_round = service_round.extract_frames(mock_25fps_video_path)
            result_int = service_int.extract_frames(mock_25fps_video_path)

        # round(): frame_skip=2, 282フレーム, 12.5fps
        assert result_round.frame_skip == 2
        assert len(result_round.frames) == 282
        assert result_round.effective_fps == pytest.approx(12.5, abs=0.5)

        # int(): frame_skip=1, 563フレーム, 25fps（問題！）
        assert result_int.frame_skip == 1
        assert len(result_int.frames) == 563
        assert result_int.effective_fps == pytest.approx(25.0, abs=0.5)

    @patch('cv2.VideoCapture')
    async def test_frame_extraction_stops_at_113(self, mock_cv2_capture, mock_25fps_video_path):
        """フレーム113で停止する問題のシミュレーション"""

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            import cv2
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 1920,
                cv2.CAP_PROP_FRAME_HEIGHT: 1080,
                cv2.CAP_PROP_FPS: 25.0,
                cv2.CAP_PROP_FRAME_COUNT: 563,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect

        # フレーム113以降は読み込み失敗
        def read_side_effect():
            current_frame = int(mock_cap.set.call_args[0][1]) if mock_cap.set.called else 0
            if current_frame < 113:
                mock_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
                return (True, mock_frame)
            else:
                return (False, None)

        mock_cap.read.side_effect = lambda: read_side_effect()
        mock_cv2_capture.return_value = mock_cap

        # リトライありでテスト
        service = FrameExtractionService(
            ExtractionConfig(
                target_fps=15.0,
                use_round=True,
                max_retries=3,
                max_consecutive_failures=10
            )
        )

        with patch.object(Path, 'exists', return_value=True):
            # 成功率が50%未満なのでValueError
            with pytest.raises(ValueError, match="Frame extraction failed"):
                service.extract_frames(mock_25fps_video_path)

    @patch('app.services.analysis_service_v2.SessionLocal')
    @patch('cv2.VideoCapture')
    @patch('app.core.websocket.manager')
    async def test_full_analysis_pipeline_25fps(
        self,
        mock_manager,
        mock_cv2_capture,
        mock_session_local,
        mock_25fps_video_path,
        mock_db_session
    ):
        """25fps動画の完全な解析パイプラインテスト"""

        mock_session_local.return_value = mock_db_session

        # VideoCapture設定
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        def get_side_effect(prop):
            import cv2
            return {
                cv2.CAP_PROP_FRAME_WIDTH: 1920,
                cv2.CAP_PROP_FRAME_HEIGHT: 1080,
                cv2.CAP_PROP_FPS: 25.0,
                cv2.CAP_PROP_FRAME_COUNT: 563,
                cv2.CAP_PROP_FOURCC: 0x34363248
            }.get(prop, 0)

        mock_cap.get.side_effect = get_side_effect
        mock_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)
        mock_cv2_capture.return_value = mock_cap

        # WebSocketマネージャーをモック
        mock_manager.send_update = AsyncMock()

        # 解析サービス
        service = AnalysisServiceV2()

        # HandSkeletonDetectorをモック
        with patch('app.services.analysis_service_v2.HandSkeletonDetector') as mock_skeleton:
            mock_detector = Mock()
            mock_detector.detect_batch.return_value = [
                {
                    'detected': True,
                    'frame_index': i,
                    'hands': [
                        {
                            'hand_type': 'Right',
                            'landmarks': {},
                            'palm_center': {'x': 100, 'y': 100},
                            'finger_angles': {},
                            'hand_openness': 0.5
                        }
                    ]
                }
                for i in range(282)  # 25fps → 15fps with round() = 282 frames
            ]
            mock_skeleton.return_value = mock_detector

            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'is_absolute', return_value=True):
                    result = await service.analyze_video(
                        video_id="test-video-id",
                        analysis_id="test-analysis-id",
                        instruments=None
                    )

        # 検証
        assert result['status'] == 'completed'
        assert 'skeleton_data' in result

        # 282フレーム抽出されている
        skeleton_data = result['skeleton_data']
        assert len(skeleton_data) == 282

        # タイムスタンプが正確（2フレームごと = 0.08s間隔）
        assert skeleton_data[0]['timestamp'] == pytest.approx(0.0, abs=0.01)
        assert skeleton_data[1]['timestamp'] == pytest.approx(0.08, abs=0.01)  # 2/25
        assert skeleton_data[-1]['timestamp'] == pytest.approx(22.48, abs=0.1)


class AsyncMock(Mock):
    """非同期関数用のモック"""
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
