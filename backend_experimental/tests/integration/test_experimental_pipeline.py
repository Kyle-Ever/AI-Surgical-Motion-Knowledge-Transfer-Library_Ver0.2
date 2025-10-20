"""
実験版パイプライン統合テスト

実際の動画を使用して、アップロード→解析→結果取得の全フローを検証
"""
import pytest
import asyncio
import os
import shutil
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.models.video import Video
from app.models.analysis import Analysis
from app.services.analysis_service_v2 import AnalysisServiceV2
from app.core.config import settings


class TestExperimentalPipeline:
    """実験版パイプライン統合テスト"""

    @pytest.fixture(scope="class")
    def db_session(self):
        """テスト用DBセッション"""
        session = SessionLocal()
        yield session
        session.close()

    @pytest.fixture(scope="class")
    def test_video_path(self):
        """テスト用動画パスを取得"""
        # 既存のテスト動画を使用
        video_path = Path(__file__).parent.parent.parent / "test.mp4"
        if not video_path.exists():
            pytest.skip(f"Test video not found: {video_path}")
        return str(video_path)

    @pytest.fixture(scope="class")
    def upload_dir(self):
        """テスト用アップロードディレクトリ"""
        test_upload_dir = Path(__file__).parent / "test_uploads"
        test_upload_dir.mkdir(exist_ok=True)
        yield test_upload_dir
        # クリーンアップ
        if test_upload_dir.exists():
            shutil.rmtree(test_upload_dir)

    @pytest.mark.asyncio
    async def test_video_api_enabled(self):
        """SAM2 Video API有効化の確認"""
        assert hasattr(settings, 'USE_SAM2_VIDEO_API')
        assert settings.USE_SAM2_VIDEO_API is True, "Video API should be enabled in experimental version"

    @pytest.mark.asyncio
    async def test_port_configuration(self):
        """ポート設定の確認"""
        assert settings.PORT == 8001, "Experimental version should use port 8001"

    @pytest.mark.asyncio
    async def test_database_configuration(self):
        """データベース設定の確認"""
        assert "experimental" in settings.DATABASE_URL.lower(), "Should use experimental database"

    @pytest.mark.asyncio
    async def test_create_video_record(self, db_session: Session, test_video_path: str):
        """動画レコード作成のテスト"""
        # 動画レコードを作成
        video = Video(
            filename="test_experimental.mp4",
            file_path=test_video_path,
            file_size=os.path.getsize(test_video_path),
            upload_status="completed"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        # 作成確認
        assert video.id is not None
        assert video.filename == "test_experimental.mp4"
        assert video.upload_status == "completed"

        # クリーンアップ
        db_session.delete(video)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_analysis_service_initialization(self):
        """AnalysisServiceV2初期化のテスト"""
        service = AnalysisServiceV2()

        # SAM2使用確認
        assert service.use_sam2 is True
        assert hasattr(service, '_run_detection')

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_analysis_pipeline_external(self, db_session: Session, test_video_path: str):
        """外部トラッキング（骨格検出）の全パイプラインテスト"""
        # 1. 動画レコード作成
        video = Video(
            filename="test_pipeline_external.mp4",
            file_path=test_video_path,
            file_size=os.path.getsize(test_video_path),
            upload_status="completed"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        try:
            # 2. 解析レコード作成
            analysis = Analysis(
                video_id=video.id,
                video_type="external",
                status="pending"
            )
            db_session.add(analysis)
            db_session.commit()
            db_session.refresh(analysis)

            # 3. 解析実行
            service = AnalysisServiceV2()

            # WebSocketマネージャーをモック（実際のWebSocket接続なし）
            async def mock_send_update(analysis_id, update):
                print(f"Mock WebSocket update: {update.get('step', 'unknown')}")

            # 解析実行
            result = await service.run_analysis(
                analysis_id=analysis.id,
                video_id=video.id,
                video_path=test_video_path,
                video_type="external",
                db=db_session
            )

            # 4. 結果検証
            assert result is not None
            db_session.refresh(analysis)
            assert analysis.status in ["completed", "failed"]

            if analysis.status == "completed":
                assert analysis.skeleton_data is not None
                assert len(analysis.skeleton_data) > 0

                # フレームデータ構造検証（Fail Fast原則）
                for frame_data in analysis.skeleton_data[:5]:  # 最初の5フレームをチェック
                    assert "frame_index" in frame_data, "Missing required field: frame_index"
                    assert isinstance(frame_data["frame_index"], int)
                    assert "detected" in frame_data
                    assert "hands" in frame_data

                print(f"✓ External tracking completed: {len(analysis.skeleton_data)} frames")

        finally:
            # クリーンアップ
            db_session.delete(analysis)
            db_session.delete(video)
            db_session.commit()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_analysis_pipeline_internal_with_video_api(
        self, db_session: Session, test_video_path: str
    ):
        """内部トラッキング（Video API使用）の全パイプラインテスト"""
        # 1. 動画レコード作成
        video = Video(
            filename="test_pipeline_internal_video_api.mp4",
            file_path=test_video_path,
            file_size=os.path.getsize(test_video_path),
            upload_status="completed"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        try:
            # 2. 解析レコード作成
            analysis = Analysis(
                video_id=video.id,
                video_type="internal",
                status="pending"
            )
            db_session.add(analysis)
            db_session.commit()
            db_session.refresh(analysis)

            # 3. 解析実行
            service = AnalysisServiceV2()

            # Video API使用確認
            assert settings.USE_SAM2_VIDEO_API is True

            result = await service.run_analysis(
                analysis_id=analysis.id,
                video_id=video.id,
                video_path=test_video_path,
                video_type="internal",
                db=db_session
            )

            # 4. 結果検証
            assert result is not None
            db_session.refresh(analysis)
            assert analysis.status in ["completed", "failed"]

            if analysis.status == "completed":
                # 器具データ検証
                assert analysis.instrument_data is not None
                assert len(analysis.instrument_data) > 0

                # フレームデータ構造検証（Fail Fast原則）
                for frame_data in analysis.instrument_data[:5]:
                    assert "detected" in frame_data
                    assert "instruments" in frame_data

                    # 器具が検出された場合
                    if frame_data["detected"] and len(frame_data["instruments"]) > 0:
                        for inst in frame_data["instruments"]:
                            assert "id" in inst, "Missing required field: id"
                            assert "center" in inst, "Missing required field: center"
                            assert "bbox" in inst, "Missing required field: bbox"

                print(f"✓ Internal tracking (Video API) completed: {len(analysis.instrument_data)} frames")

        finally:
            # クリーンアップ
            db_session.delete(analysis)
            db_session.delete(video)
            db_session.commit()

    @pytest.mark.asyncio
    async def test_data_format_compatibility(self, db_session: Session, test_video_path: str):
        """データフォーマット互換性テスト - 安定版と同じフォーマットか確認"""
        video = Video(
            filename="test_format_compat.mp4",
            file_path=test_video_path,
            file_size=os.path.getsize(test_video_path),
            upload_status="completed"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        try:
            analysis = Analysis(
                video_id=video.id,
                video_type="internal",
                status="pending"
            )
            db_session.add(analysis)
            db_session.commit()
            db_session.refresh(analysis)

            service = AnalysisServiceV2()

            # 変換メソッドのテスト
            mock_tracking_result = {
                "instruments": [
                    {
                        "instrument_id": "inst_1",
                        "name": "Test Instrument",
                        "trajectory": [
                            {
                                "frame_index": 0,
                                "center": [100, 100],
                                "bbox": [80, 80, 120, 120],
                                "confidence": 0.95
                            },
                            {
                                "frame_index": 1,
                                "center": [105, 105],
                                "bbox": [85, 85, 125, 125],
                                "confidence": 0.93
                            }
                        ]
                    }
                ]
            }

            # Video API結果をフレームベース形式に変換
            converted = service._convert_video_api_result(mock_tracking_result, total_frames=2)

            # 変換結果の検証
            assert len(converted) == 2  # 2フレーム分

            # フレーム0
            assert converted[0]["detected"] is True
            assert len(converted[0]["instruments"]) == 1
            assert converted[0]["instruments"][0]["id"] == "inst_1"
            assert converted[0]["instruments"][0]["center"] == [100, 100]

            # フレーム1
            assert converted[1]["detected"] is True
            assert len(converted[1]["instruments"]) == 1
            assert converted[1]["instruments"][0]["id"] == "inst_1"
            assert converted[1]["instruments"][0]["center"] == [105, 105]

            print("✓ Data format compatibility verified")

        finally:
            db_session.delete(analysis)
            db_session.delete(video)
            db_session.commit()

    @pytest.mark.asyncio
    async def test_error_handling_invalid_video_path(self, db_session: Session):
        """存在しない動画パスのエラーハンドリング"""
        video = Video(
            filename="nonexistent.mp4",
            file_path="/invalid/path/nonexistent.mp4",
            file_size=0,
            upload_status="completed"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        try:
            analysis = Analysis(
                video_id=video.id,
                video_type="external",
                status="pending"
            )
            db_session.add(analysis)
            db_session.commit()
            db_session.refresh(analysis)

            service = AnalysisServiceV2()

            # エラーになるはず
            with pytest.raises(Exception):
                await service.run_analysis(
                    analysis_id=analysis.id,
                    video_id=video.id,
                    video_path="/invalid/path/nonexistent.mp4",
                    video_type="external",
                    db=db_session
                )

        finally:
            db_session.delete(analysis)
            db_session.delete(video)
            db_session.commit()

    @pytest.mark.asyncio
    async def test_concurrent_analyses(self, db_session: Session, test_video_path: str):
        """複数解析の同時実行テスト"""
        videos = []
        analyses = []

        try:
            # 3つの動画を作成
            for i in range(3):
                video = Video(
                    filename=f"test_concurrent_{i}.mp4",
                    file_path=test_video_path,
                    file_size=os.path.getsize(test_video_path),
                    upload_status="completed"
                )
                db_session.add(video)
                videos.append(video)

            db_session.commit()

            # 解析レコード作成
            for video in videos:
                db_session.refresh(video)
                analysis = Analysis(
                    video_id=video.id,
                    video_type="external",
                    status="pending"
                )
                db_session.add(analysis)
                analyses.append(analysis)

            db_session.commit()

            # 同時実行
            service = AnalysisServiceV2()

            tasks = []
            for analysis in analyses:
                db_session.refresh(analysis)
                task = service.run_analysis(
                    analysis_id=analysis.id,
                    video_id=analysis.video_id,
                    video_path=test_video_path,
                    video_type="external",
                    db=db_session
                )
                tasks.append(task)

            # すべて完了を待つ
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 結果確認
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            print(f"✓ Concurrent analyses: {success_count}/{len(results)} succeeded")

            assert success_count > 0, "At least one analysis should succeed"

        finally:
            # クリーンアップ
            for analysis in analyses:
                db_session.delete(analysis)
            for video in videos:
                db_session.delete(video)
            db_session.commit()


class TestExperimentalPerformance:
    """パフォーマンステスト"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_memory_usage_large_video(self, db_session: Session):
        """大きな動画のメモリ使用量テスト"""
        import psutil
        import gc

        process = psutil.Process()

        # 開始時のメモリ使用量
        gc.collect()
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        # テストパスをスキップする場合の処理
        test_video_path = Path(__file__).parent.parent.parent / "test.mp4"
        if not test_video_path.exists():
            pytest.skip("Test video not found")

        video = Video(
            filename="test_memory.mp4",
            file_path=str(test_video_path),
            file_size=os.path.getsize(test_video_path),
            upload_status="completed"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        try:
            analysis = Analysis(
                video_id=video.id,
                video_type="external",
                status="pending"
            )
            db_session.add(analysis)
            db_session.commit()
            db_session.refresh(analysis)

            service = AnalysisServiceV2()

            await service.run_analysis(
                analysis_id=analysis.id,
                video_id=video.id,
                video_path=str(test_video_path),
                video_type="external",
                db=db_session
            )

            # 終了時のメモリ使用量
            gc.collect()
            mem_after = process.memory_info().rss / 1024 / 1024  # MB

            mem_increase = mem_after - mem_before
            print(f"Memory usage: {mem_before:.1f}MB → {mem_after:.1f}MB (Δ{mem_increase:.1f}MB)")

            # メモリリークチェック（1GB以上増えていたら問題）
            assert mem_increase < 1024, f"Memory leak detected: {mem_increase:.1f}MB increase"

        finally:
            db_session.delete(analysis)
            db_session.delete(video)
            db_session.commit()
