"""SAMエンドポイントのテスト"""

import requests
import json
import cv2
import numpy as np
from pathlib import Path

def test_sam_segmentation():
    """SAMセグメンテーションAPIのテスト"""

    # まずビデオリストを取得
    response = requests.get("http://localhost:8000/api/v1/videos")
    videos = response.json()

    if not videos:
        print("No videos found. Please upload a video first.")
        return

    video_id = videos[0]['id']
    print(f"Using video: {video_id}")

    # テスト用のポイント座標（画像中央付近）
    test_request = {
        "prompt_type": "point",
        "coordinates": [[320, 240]],  # 画像中央
        "labels": [1],  # foreground
        "frame_number": 0
    }

    print(f"\nSending request: {json.dumps(test_request, indent=2)}")

    # SAMセグメンテーションを実行
    response = requests.post(
        f"http://localhost:8000/api/v1/videos/{video_id}/segment",
        json=test_request
    )

    print(f"Response status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print("Success! Response keys:", result.keys())

        if 'mask' in result:
            print(f"Mask shape info: {len(result['mask'])} characters")

        if 'visualization' in result:
            print(f"Visualization available: {len(result['visualization'])} characters")

            # 可視化画像を保存
            import base64
            vis_data = base64.b64decode(result['visualization'])
            with open("sam_test_result.jpg", "wb") as f:
                f.write(vis_data)
            print("Visualization saved to sam_test_result.jpg")

        if 'score' in result:
            print(f"Confidence score: {result['score']}")

    else:
        print(f"Error: {response.text}")

    # ボックス選択もテスト
    print("\n" + "="*50)
    print("Testing box selection...")

    box_request = {
        "prompt_type": "box",
        "coordinates": [[200, 150, 400, 350]],  # [x1, y1, x2, y2]
        "frame_number": 0
    }

    response = requests.post(
        f"http://localhost:8000/api/v1/videos/{video_id}/segment",
        json=box_request
    )

    print(f"Box selection status: {response.status_code}")
    if response.status_code == 200:
        print("Box selection successful!")
    else:
        print(f"Box selection error: {response.text}")

if __name__ == "__main__":
    test_sam_segmentation()