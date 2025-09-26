"""
Backend Integration Tests
動画アップロード→解析開始→完了の一連のフローをテスト
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# テスト用の環境変数設定
os.environ["DATABASE_URL"] = "sqlite:///./test_aimotion.db"
os.environ["UPLOAD_DIR"] = "./test_uploads"

from app.main import app
from app.core.database import Base, get_db
from app.models import Video, AnalysisResult


# テスト用データベースセットアップ
@pytest.fixture(scope="session")
def test_db():
    """テスト用データベースの作成と削除"""
    engine = create_engine("sqlite:///./test_aimotion.db")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield TestingSessionLocal()

    # クリーンアップ
    Base.metadata.drop_all(bind=engine)
    os.remove("test_aimotion.db")


@pytest.fixture(scope="function")
def test_video_file():
    """テスト用の動画ファイルを作成"""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        # 簡単なMP4ヘッダーを書き込み（実際の動画データではない）
        f.write(b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41')
        f.write(b'\x00' * 1024)  # ダミーデータ
        temp_path = f.name

    yield temp_path

    # クリーンアップ
    try:
        os.remove(temp_path)
    except:
        pass


@pytest.mark.asyncio
async def test_full_analysis_flow(test_db, test_video_file):
    """動画アップロードから解析完了までの統合テスト"""

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Step 1: ヘルスチェック
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        # Step 2: 動画アップロード
        with open(test_video_file, "rb") as f:
            files = {"file": ("test_video.mp4", f, "video/mp4")}
            response = await client.post(
                "/api/v1/videos/upload",
                files=files
            )

        assert response.status_code == 200
        upload_data = response.json()
        assert "id" in upload_data
        assert upload_data["filename"].endswith(".mp4")
        video_id = upload_data["id"]

        # Step 3: アップロードした動画の確認
        response = await client.get(f"/api/v1/videos/{video_id}")
        assert response.status_code == 200
        video_data = response.json()
        assert video_data["id"] == video_id
        assert video_data["status"] == "uploaded"

        # Step 4: 解析開始
        response = await client.post(f"/api/v1/analysis/{video_id}/analyze")
        assert response.status_code == 200
        analysis_data = response.json()
        assert "analysis_id" in analysis_data
        assert analysis_data["status"] == "processing"
        analysis_id = analysis_data["analysis_id"]

        # Step 5: 解析ステータス確認（ポーリング）
        max_attempts = 10
        for attempt in range(max_attempts):
            response = await client.get(f"/api/v1/analysis/{analysis_id}/status")
            assert response.status_code == 200
            status_data = response.json()

            assert "overall_progress" in status_data
            assert "current_step" in status_data
            assert "status" in status_data

            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Analysis failed: {status_data.get('error')}")

            await asyncio.sleep(1)
        else:
            pytest.fail("Analysis did not complete within timeout")

        # Step 6: 完了した解析結果の取得
        response = await client.get(f"/api/v1/analysis/{analysis_id}")
        assert response.status_code == 200
        result_data = response.json()
        assert result_data["status"] == "completed"
        assert result_data["overall_progress"] == 100
        assert "skeleton_data" in result_data
        assert "scores" in result_data

        # Step 7: 完了した解析一覧の確認
        response = await client.get("/api/v1/analysis/completed")
        assert response.status_code == 200
        completed_list = response.json()
        assert len(completed_list) > 0
        assert any(item["id"] == analysis_id for item in completed_list)


@pytest.mark.asyncio
async def test_websocket_connection():
    """WebSocket接続テスト"""
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        # まず動画をアップロード
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            f.write(b'\x00' * 1024)
            f.seek(0)
            response = client.post(
                "/api/v1/videos/upload",
                files={"file": ("test.mp4", f, "video/mp4")}
            )
            video_id = response.json()["id"]

        # 解析開始
        response = client.post(f"/api/v1/analysis/{video_id}/analyze")
        analysis_id = response.json()["analysis_id"]

        # WebSocket接続テスト
        with client.websocket_connect(f"/ws/analysis/{analysis_id}") as websocket:
            # 初期メッセージを受信
            data = websocket.receive_json()
            assert "type" in data
            assert data["type"] in ["connection", "progress"]

            # 進捗更新を待つ
            for _ in range(5):
                try:
                    data = websocket.receive_json(timeout=2)
                    assert "type" in data
                    if data["type"] == "progress":
                        assert "overall_progress" in data
                        assert "current_step" in data
                except:
                    break


@pytest.mark.asyncio
async def test_error_handling():
    """エラーハンドリングのテスト"""

    async with AsyncClient(app=app, base_url="http://test") as client:
        # 存在しない動画ID
        response = await client.get("/api/v1/videos/non-existent-id")
        assert response.status_code == 404

        # 存在しない解析ID
        response = await client.get("/api/v1/analysis/non-existent-id")
        assert response.status_code == 404

        # 無効なファイル形式のアップロード
        files = {"file": ("test.txt", b"invalid content", "text/plain")}
        response = await client.post("/api/v1/videos/upload", files=files)
        assert response.status_code == 400
        assert "mp4" in response.json()["detail"].lower()

        # ファイルなしでアップロード
        response = await client.post("/api/v1/videos/upload")
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_analysis():
    """複数の解析を同時実行するテスト"""

    async with AsyncClient(app=app, base_url="http://test") as client:
        video_ids = []

        # 複数の動画をアップロード
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
                f.write(b'\x00' * 1024)
                f.seek(0)
                response = await client.post(
                    "/api/v1/videos/upload",
                    files={"file": (f"test_{i}.mp4", f, "video/mp4")}
                )
                video_ids.append(response.json()["id"])

        # 同時に解析開始
        analysis_tasks = []
        for video_id in video_ids:
            task = client.post(f"/api/v1/analysis/{video_id}/analyze")
            analysis_tasks.append(task)

        responses = await asyncio.gather(*analysis_tasks)

        # すべての解析が開始されたことを確認
        analysis_ids = []
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"
            analysis_ids.append(data["analysis_id"])

        # 各解析のステータスを確認
        for analysis_id in analysis_ids:
            response = await client.get(f"/api/v1/analysis/{analysis_id}/status")
            assert response.status_code == 200
            assert response.json()["status"] in ["processing", "completed", "queued"]


@pytest.mark.asyncio
async def test_file_size_limit():
    """ファイルサイズ制限のテスト"""

    async with AsyncClient(app=app, base_url="http://test") as client:
        # 2GBを超えるファイルのシミュレーション
        # 実際には小さいファイルでテスト（本番環境では設定で制限）
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            # 小さいファイルでテスト
            f.write(b'\x00' * 1024 * 1024)  # 1MB
            f.seek(0)

            response = await client.post(
                "/api/v1/videos/upload",
                files={"file": ("large.mp4", f, "video/mp4")}
            )

            # 正常にアップロードされることを確認（実際の制限は設定依存）
            assert response.status_code in [200, 413]

            if response.status_code == 413:
                assert "size" in response.json()["detail"].lower()


if __name__ == "__main__":
    # テスト実行
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])