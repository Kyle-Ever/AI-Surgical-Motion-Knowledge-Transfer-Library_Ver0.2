"""テスト動画のアップロード"""

import requests
import os
from pathlib import Path

def upload_test_video():
    """テスト用動画をアップロード"""

    # テスト動画を探す
    test_videos = [
        "data/uploads/VID_20250926_123049.mp4",
        "data/results/auto_selection_20250926_173322.mp4",
        "test.mp4"
    ]

    video_path = None
    for path in test_videos:
        if Path(path).exists():
            video_path = path
            print(f"Found test video: {video_path}")
            break

    if not video_path:
        print("No test video found. Please ensure a test video exists.")
        return None

    # アップロード
    url = "http://localhost:8000/api/v1/videos/upload"

    with open(video_path, 'rb') as f:
        files = {'file': ('test_video.mp4', f, 'video/mp4')}
        data = {
            'video_type': 'external_with_instruments',
            'surgery_name': 'Test Surgery',
            'surgeon_name': 'Test Surgeon',
            'memo': 'Test video for instrument tracking'
        }

        response = requests.post(url, files=files, data=data)

    if response.status_code in [200, 201]:
        result = response.json()
        print(f"Upload successful! Video ID: {result['video_id']}")
        return result['video_id']
    else:
        print(f"Upload failed: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    video_id = upload_test_video()
    if video_id:
        print(f"\nVideo uploaded successfully!")
        print(f"Video ID: {video_id}")
        print(f"\nYou can now test SAM at:")
        print(f"http://localhost:3005/upload")
        print(f"\nOr test the API directly with video ID: {video_id}")