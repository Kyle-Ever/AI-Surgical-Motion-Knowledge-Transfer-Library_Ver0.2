"""SAM API テストスクリプト"""
import requests
import json
import base64
from pathlib import Path

def test_sam_api():
    base_url = "http://localhost:8000/api/v1"
    
    # 1. テスト用の動画をアップロード
    test_video = Path("test.mp4")
    if not test_video.exists():
        print("test.mp4 not found, creating a dummy video...")
        # ダミー動画の作成
        import cv2
        import numpy as np
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter('test.mp4', fourcc, 20.0, (640, 480))
        for i in range(30):  # 1.5秒の動画
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            # 中央に四角を描画
            cv2.rectangle(frame, (200, 150), (440, 330), (0, 255, 0), -1)
            out.write(frame)
        out.release()
        print("Created test.mp4")
    
    # ビデオアップロード
    print("\n1. Uploading video...")
    with open("test.mp4", "rb") as f:
        files = {"file": ("test.mp4", f, "video/mp4")}
        data = {
            "video_type": "internal",
            "surgery_name": "SAM Test"
        }
        response = requests.post(f"{base_url}/videos/upload", files=files, data=data)
    
    if response.status_code != 201:
        print(f"Upload failed: {response.text}")
        return
    
    upload_result = response.json()
    video_id = upload_result["video_id"]
    print(f"Video uploaded: {video_id}")
    
    # 2. サムネイル取得テスト
    print("\n2. Getting thumbnail...")
    response = requests.get(f"{base_url}/videos/{video_id}/thumbnail")
    
    if response.status_code == 200:
        print(f"Thumbnail retrieved: {len(response.content)} bytes")
        # サムネイルを保存
        with open("test_thumbnail.jpg", "wb") as f:
            f.write(response.content)
        print("Saved as test_thumbnail.jpg")
    else:
        print(f"Thumbnail failed: {response.status_code}")
    
    # 3. SAMセグメンテーションテスト (ポイント)
    print("\n3. Testing SAM segmentation with point prompt...")
    segment_data = {
        "prompt_type": "point",
        "coordinates": [[320, 240]],  # 中央の点
        "labels": [1],  # 前景
        "frame_number": 0
    }
    
    response = requests.post(
        f"{base_url}/videos/{video_id}/segment",
        json=segment_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Segmentation successful!")
        print(f"  Score: {result['score']:.3f}")
        print(f"  Area: {result['area']:.0f} pixels")
        print(f"  BBox: {result['bbox']}")
        
        # 可視化を保存
        if result.get('visualization'):
            vis_data = base64.b64decode(result['visualization'])
            with open("test_segmentation_vis.jpg", "wb") as f:
                f.write(vis_data)
            print("  Saved visualization as test_segmentation_vis.jpg")
    else:
        print(f"Segmentation failed: {response.text}")
    
    # 4. SAMセグメンテーションテスト (ボックス)
    print("\n4. Testing SAM segmentation with box prompt...")
    segment_data = {
        "prompt_type": "box",
        "coordinates": [[200, 150, 440, 330]],  # 四角の領域
        "frame_number": 0
    }
    
    response = requests.post(
        f"{base_url}/videos/{video_id}/segment",
        json=segment_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Box segmentation successful!")
        print(f"  Score: {result['score']:.3f}")
        print(f"  Area: {result['area']:.0f} pixels")
    else:
        print(f"Box segmentation failed: {response.text}")
    
    # 5. 器具登録テスト
    print("\n5. Registering instruments...")
    instruments_data = {
        "instruments": [
            {
                "name": "Test Forceps",
                "bbox": [200, 150, 440, 330],
                "frame_number": 0,
                "mask": "dummy_mask_base64"
            }
        ]
    }
    
    response = requests.post(
        f"{base_url}/videos/{video_id}/instruments",
        json=instruments_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Instruments registered: {result['instruments_count']} items")
    else:
        print(f"Registration failed: {response.text}")
    
    # 6. 登録した器具の取得
    print("\n6. Getting registered instruments...")
    response = requests.get(f"{base_url}/videos/{video_id}/instruments")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Retrieved {len(result['instruments'])} instruments:")
        for inst in result['instruments']:
            print(f"  - {inst['name']} at bbox {inst['bbox']}")
    else:
        print(f"Get instruments failed: {response.text}")
    
    print("\n=== SAM API Test Complete ===")

if __name__ == "__main__":
    test_sam_api()