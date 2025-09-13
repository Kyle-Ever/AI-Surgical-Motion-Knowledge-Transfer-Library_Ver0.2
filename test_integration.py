"""統合テストスクリプト - エンドツーエンドの動作確認"""

import requests
import time
import json
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"

def test_health_check():
    """ヘルスチェック"""
    print("1. ヘルスチェック...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    print("✓ サーバーは正常に動作しています")
    return True

def test_upload_video():
    """動画アップロードテスト（モック）"""
    print("\n2. 動画アップロードテスト...")
    
    # テスト用の小さな動画ファイルを作成（実際の動画の代わり）
    test_video_path = Path("test_video.mp4")
    if not test_video_path.exists():
        # ダミーファイルを作成
        with open(test_video_path, "wb") as f:
            f.write(b"dummy video content")
    
    # アップロードリクエスト
    with open(test_video_path, "rb") as f:
        files = {"file": ("test_video.mp4", f, "video/mp4")}
        data = {
            "video_type": "external",
            "surgery_name": "テスト手術",
            "surgeon_name": "テスト医師"
        }
        
        response = requests.post(
            f"{BASE_URL}/videos/upload",
            files=files,
            data=data
        )
    
    if response.status_code == 200:
        video_data = response.json()
        print(f"✓ 動画アップロード成功: ID={video_data['id']}")
        return video_data['id']
    else:
        print(f"✗ アップロード失敗: {response.status_code}")
        print(response.text)
        return None

def test_start_analysis(video_id):
    """解析開始テスト"""
    print(f"\n3. 解析開始テスト (Video ID: {video_id})...")
    
    response = requests.post(
        f"{BASE_URL}/analysis/{video_id}/analyze",
        json={
            "instruments": [],
            "sampling_rate": 5
        }
    )
    
    if response.status_code == 200:
        analysis_data = response.json()
        print(f"✓ 解析開始成功: Analysis ID={analysis_data['id']}")
        return analysis_data['id']
    else:
        print(f"✗ 解析開始失敗: {response.status_code}")
        print(response.text)
        return None

def test_check_progress(analysis_id):
    """解析進捗確認テスト"""
    print(f"\n4. 解析進捗確認 (Analysis ID: {analysis_id})...")
    
    max_attempts = 30  # 最大30秒待機
    for i in range(max_attempts):
        response = requests.get(
            f"{BASE_URL}/analysis/{analysis_id}/status"
        )
        
        if response.status_code == 200:
            status_data = response.json()
            progress = status_data.get("overall_progress", 0)
            steps = status_data.get("steps", [])
            
            print(f"  進捗: {progress}%", end="")
            
            # 各ステップの状態を表示
            step_status = []
            for step in steps:
                if step['status'] == 'completed':
                    step_status.append('✓')
                elif step['status'] == 'processing':
                    step_status.append('◆')
                else:
                    step_status.append('○')
            print(f" [{' '.join(step_status)}]")
            
            if progress >= 100:
                print("✓ 解析完了！")
                return True
            
            time.sleep(1)
        else:
            print(f"✗ ステータス取得失敗: {response.status_code}")
            return False
    
    print("✗ タイムアウト: 解析が完了しませんでした")
    return False

def test_get_results(analysis_id):
    """解析結果取得テスト"""
    print(f"\n5. 解析結果取得 (Analysis ID: {analysis_id})...")
    
    response = requests.get(
        f"{BASE_URL}/analysis/{analysis_id}"
    )
    
    if response.status_code == 200:
        result_data = response.json()
        print("✓ 解析結果取得成功")
        
        # 主要な結果を表示
        if result_data.get("scores"):
            scores = json.loads(result_data["scores"])
            print(f"  - 総合スコア: {scores.get('overall', 0):.1f}")
            print(f"  - スムーズネス: {scores.get('smoothness', 0):.1f}")
            print(f"  - スピード: {scores.get('speed', 0):.1f}")
        
        if result_data.get("total_frames"):
            print(f"  - 処理フレーム数: {result_data['total_frames']}")
        
        return True
    else:
        print(f"✗ 結果取得失敗: {response.status_code}")
        return False

def main():
    """メインテスト実行"""
    print("=" * 50)
    print("AI外科手技知識移転ライブラリ - 統合テスト")
    print("=" * 50)
    
    try:
        # 1. ヘルスチェック
        if not test_health_check():
            print("\nエラー: サーバーが起動していません")
            print("以下のコマンドでサーバーを起動してください:")
            print("  cd backend && py -3.11 -m uvicorn app.main:app --reload")
            return
        
        # 2. 動画アップロード
        video_id = test_upload_video()
        if not video_id:
            print("\nエラー: 動画アップロードに失敗しました")
            return
        
        # 3. 解析開始
        analysis_id = test_start_analysis(video_id)
        if not analysis_id:
            print("\nエラー: 解析開始に失敗しました")
            return
        
        # 4. 進捗確認
        if not test_check_progress(analysis_id):
            print("\nエラー: 解析が正常に完了しませんでした")
            return
        
        # 5. 結果取得
        if not test_get_results(analysis_id):
            print("\nエラー: 結果取得に失敗しました")
            return
        
        print("\n" + "=" * 50)
        print("✓ すべてのテストが成功しました！")
        print("=" * 50)
        
    except requests.exceptions.ConnectionError:
        print("\nエラー: サーバーに接続できません")
        print("サーバーが起動していることを確認してください")
    except Exception as e:
        print(f"\n予期しないエラー: {e}")

if __name__ == "__main__":
    main()