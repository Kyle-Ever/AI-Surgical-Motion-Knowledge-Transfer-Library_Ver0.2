"""API経由での手袋検出テスト"""

import asyncio
import json
import requests
import websocket
import threading
import time
from pathlib import Path

API_URL = "http://localhost:8000/api/v1"
WS_URL = "ws://localhost:8000/ws"

def test_upload_and_analyze():
    """動画アップロードと解析のテスト"""

    # Front_Angle.mp4のアップロード
    video_path = Path("../data/uploads/Front_Angle.mp4")

    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    print("\n" + "="*60)
    print("GLOVE DETECTION API TEST")
    print("="*60)

    # 1. 動画アップロード
    print("\n1. Uploading video...")

    # すでに存在する場合は既存のビデオIDを取得
    response = requests.get(f"{API_URL}/videos/")
    if response.status_code == 200:
        videos = response.json()
        front_angle = next((v for v in videos if v["filename"] == "Front_Angle.mp4"), None)

        if front_angle:
            video_id = front_angle["id"]
            print(f"   Using existing video ID: {video_id}")
        else:
            # 新規アップロード
            with open(video_path, "rb") as f:
                files = {"file": ("Front_Angle.mp4", f, "video/mp4")}
                data = {
                    "title": "Front Angle Test",
                    "video_type": "external"  # 外部カメラ = 手袋検出モード
                }
                response = requests.post(f"{API_URL}/videos/upload", files=files, data=data)

                if response.status_code == 200:
                    result = response.json()
                    video_id = result["id"]
                    print(f"   Upload successful. Video ID: {video_id}")
                else:
                    print(f"   Upload failed: {response.text}")
                    return
    else:
        print("   Failed to get video list")
        return

    # 2. 解析開始
    print("\n2. Starting analysis...")

    response = requests.post(f"{API_URL}/analysis/{video_id}/analyze")

    if response.status_code == 200:
        result = response.json()
        analysis_id = result["analysis_id"]
        print(f"   Analysis started. ID: {analysis_id}")
    else:
        print(f"   Failed to start analysis: {response.text}")
        return

    # 3. WebSocket接続で進捗監視
    print("\n3. Monitoring progress via WebSocket...")

    ws_connected = False
    analysis_complete = False
    final_result = None

    def on_message(ws, message):
        nonlocal analysis_complete, final_result
        try:
            data = json.loads(message)

            if data.get("type") == "progress":
                progress = data.get("progress", 0)
                step = data.get("step", "")
                message_text = data.get("message", "")
                print(f"   [{progress:3d}%] {step}: {message_text}")

                if step == "completed":
                    analysis_complete = True

            elif data.get("type") == "result":
                final_result = data
                analysis_complete = True

        except json.JSONDecodeError:
            print(f"   Received: {message}")

    def on_error(ws, error):
        print(f"   WebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        nonlocal ws_connected
        ws_connected = False
        print(f"   WebSocket closed")

    def on_open(ws):
        nonlocal ws_connected
        ws_connected = True
        print(f"   WebSocket connected")

    # WebSocket接続
    ws = websocket.WebSocketApp(
        f"{WS_URL}/analysis/{analysis_id}",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # 別スレッドで実行
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()

    # 解析完了を待つ（最大60秒）
    start_time = time.time()
    timeout = 60

    while not analysis_complete and (time.time() - start_time) < timeout:
        time.sleep(1)

    if ws_connected:
        ws.close()

    # 4. 結果の確認
    print("\n4. Checking analysis results...")

    response = requests.get(f"{API_URL}/analysis/{analysis_id}")

    if response.status_code == 200:
        result = response.json()

        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)

        print(f"Status: {result.get('status')}")
        print(f"Progress: {result.get('progress')}%")

        if result.get("result_data"):
            data = result["result_data"]
            if isinstance(data, str):
                data = json.loads(data)

            # 骨格検出結果の統計
            skeleton_data = data.get("skeleton_data", [])
            frames_with_detection = sum(1 for frame in skeleton_data if frame.get("hands"))
            total_frames = len(skeleton_data)

            print(f"\nSkeleton Detection:")
            print(f"  - Total frames: {total_frames}")
            print(f"  - Frames with detection: {frames_with_detection}")
            print(f"  - Detection rate: {frames_with_detection/total_frames*100:.1f}%")

            # 各フレームの詳細（最初の10フレーム）
            print(f"\nFirst 10 frames:")
            for i, frame in enumerate(skeleton_data[:10]):
                hands = frame.get("hands", [])
                if hands:
                    print(f"  Frame {i}: {len(hands)} hand(s) detected")
                else:
                    print(f"  Frame {i}: No hands detected")

            # スコア
            scores = data.get("scores", {})
            if scores:
                print(f"\nScores:")
                print(f"  - Smoothness: {scores.get('smoothness', 0):.1f}")
                print(f"  - Speed: {scores.get('speed', 0):.1f}")
                print(f"  - Accuracy: {scores.get('accuracy', 0):.1f}")
                print(f"  - Total: {scores.get('total', 0):.1f}")
    else:
        print(f"Failed to get analysis results: {response.text}")

    print("\nTest completed!")

if __name__ == "__main__":
    print("Testing glove detection via API...")
    test_upload_and_analyze()