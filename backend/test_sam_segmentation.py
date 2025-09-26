"""SAMセグメンテーション機能のテスト"""

import requests
import json
import base64
from pathlib import Path

def test_sam_with_video(video_id: str):
    """特定の動画でSAMをテスト"""

    print(f"Testing SAM with video ID: {video_id}")

    # 1. ポイント選択テスト
    print("\n" + "="*50)
    print("1. Testing point selection...")

    point_request = {
        "prompt_type": "point",
        "coordinates": [[320, 240], [350, 260]],  # 複数ポイント
        "labels": [1, 1],  # すべてforeground
        "frame_number": 0
    }

    response = requests.post(
        f"http://localhost:8000/api/v1/videos/{video_id}/segment",
        json=point_request
    )

    print(f"Response status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print("✅ Point selection successful!")

        if 'visualization' in result:
            # 可視化画像を保存
            vis_data = base64.b64decode(result['visualization'])
            output_path = f"sam_point_result_{video_id[:8]}.jpg"
            with open(output_path, "wb") as f:
                f.write(vis_data)
            print(f"Visualization saved to {output_path}")

        if 'score' in result:
            print(f"Confidence score: {result['score']}")

    else:
        print(f"❌ Error: {response.text}")

    # 2. ボックス選択テスト
    print("\n" + "="*50)
    print("2. Testing box selection...")

    box_request = {
        "prompt_type": "box",
        "coordinates": [[200, 150, 400, 350]],
        "frame_number": 0
    }

    response = requests.post(
        f"http://localhost:8000/api/v1/videos/{video_id}/segment",
        json=box_request
    )

    print(f"Response status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print("✅ Box selection successful!")

        if 'visualization' in result:
            vis_data = base64.b64decode(result['visualization'])
            output_path = f"sam_box_result_{video_id[:8]}.jpg"
            with open(output_path, "wb") as f:
                f.write(vis_data)
            print(f"Visualization saved to {output_path}")

    else:
        print(f"❌ Error: {response.text}")

    # 3. 混合選択テスト（ポイント＋背景）
    print("\n" + "="*50)
    print("3. Testing mixed selection (foreground + background)...")

    mixed_request = {
        "prompt_type": "point",
        "coordinates": [[300, 200], [400, 300], [100, 100]],
        "labels": [1, 1, 0],  # 最後は背景
        "frame_number": 0
    }

    response = requests.post(
        f"http://localhost:8000/api/v1/videos/{video_id}/segment",
        json=mixed_request
    )

    if response.status_code == 200:
        print("✅ Mixed selection successful!")
    else:
        print(f"❌ Error: {response.text}")

def main():
    # 最新のアップロード動画を取得
    response = requests.get("http://localhost:8000/api/v1/videos")
    videos = response.json()

    if not videos:
        print("No videos found. Please upload a video first.")
        return

    # 最新の動画を使用
    latest_video = videos[0]
    video_id = latest_video['id']

    print(f"Using latest video: {latest_video.get('filename', video_id)}")

    # SAMテスト実行
    test_sam_with_video(video_id)

    print("\n" + "="*50)
    print("SAM testing completed!")
    print(f"\n📍 You can now test the UI at:")
    print(f"   http://localhost:3005/upload")
    print(f"\n📍 Upload the video and select '外部カメラ（器具あり）'")
    print(f"   then click '映像から直接選択 (SAM)'")

if __name__ == "__main__":
    main()