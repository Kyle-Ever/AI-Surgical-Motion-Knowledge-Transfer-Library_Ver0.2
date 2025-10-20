"""
新規解析をトリガーして修正を検証

手順:
1. 既存の動画を使用 (ad6de8d5-af49-470a-96f9-36b1925028dc)
2. 既存の器具マスクを使用
3. 新規解析を開始
4. 完了まで待機
5. contourデータを検証
"""

import requests
import json
import time
from pathlib import Path

API_BASE = "http://localhost:8001/api/v1"
VIDEO_ID = "ad6de8d5-af49-470a-96f9-36b1925028dc"

def load_saved_instruments():
    """保存された器具データを読み込み"""
    file_path = Path(f"data/instruments/{VIDEO_ID}.json")
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def trigger_analysis():
    """新規解析を開始"""
    print("\n" + "="*80)
    print("Starting New Analysis (with fixed code)")
    print("="*80 + "\n")

    # 器具データを読み込み
    instruments = load_saved_instruments()
    if not instruments:
        print("[ERROR] No saved instruments found")
        print(f"[INFO] Expected file: data/instruments/{VIDEO_ID}.json")
        return None

    print(f"[INFO] Loaded {len(instruments)} instruments from saved file")

    # 解析を開始
    url = f"{API_BASE}/analysis/{VIDEO_ID}/analyze"
    payload = {
        "video_type": "external_with_instruments",
        "instruments": instruments
    }

    print(f"[INFO] Sending POST to {url}")
    response = requests.post(url, json=payload)

    if response.status_code != 200:
        print(f"[FAIL] Failed to start analysis: {response.status_code}")
        print(f"[INFO] Response: {response.text}")
        return None

    result = response.json()
    analysis_id = result.get('analysis_id')

    print(f"[SUCCESS] Analysis started!")
    print(f"[INFO] Analysis ID: {analysis_id}")

    return analysis_id

def wait_for_completion(analysis_id: str, timeout: int = 300):
    """解析完了を待機"""
    print(f"\n[INFO] Waiting for analysis completion (timeout: {timeout}s)...")

    url = f"{API_BASE}/analysis/{analysis_id}/status"
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"[WARN] Failed to get status: {response.status_code}")
            time.sleep(5)
            continue

        data = response.json()
        status = data.get('status')
        progress = data.get('progress', 0)

        print(f"[PROGRESS] Status: {status}, Progress: {progress}%")

        if status == 'completed':
            print(f"[SUCCESS] Analysis completed!")
            return True
        elif status == 'failed':
            print(f"[FAIL] Analysis failed")
            print(f"[INFO] Error: {data.get('error_message')}")
            return False

        time.sleep(5)

    print(f"[FAIL] Timeout waiting for analysis completion")
    return False

def verify_contour(analysis_id: str):
    """Contourデータを検証"""
    print(f"\n[INFO] Verifying contour data...")

    url = f"{API_BASE}/analysis/{analysis_id}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"[FAIL] Failed to fetch analysis: {response.status_code}")
        return False

    data = response.json()

    # instrument_dataを確認
    instrument_data = data.get('instrument_data', [])
    if len(instrument_data) == 0:
        print(f"[FAIL] No instrument_data")
        return False

    first_frame = instrument_data[0]
    detections = first_frame.get('detections', [])
    if len(detections) == 0:
        print(f"[FAIL] No detections")
        return False

    first_detection = detections[0]
    contour = first_detection.get('contour', [])

    print(f"\n[TEST] Contour Validation:")
    print(f"   - Type: {type(contour)}")
    print(f"   - Length: {len(contour)}")

    if len(contour) == 0:
        print(f"[FAIL] Contour is empty (BUG NOT FIXED)")
        return False

    print(f"[PASS] Contour is not empty ({len(contour)} points)")

    # 構造を検証
    first_point = contour[0]
    if not isinstance(first_point, list) or len(first_point) != 2:
        print(f"[FAIL] Invalid contour structure")
        return False

    print(f"[PASS] Contour structure is valid")
    print(f"   - First point: [{first_point[0]:.2f}, {first_point[1]:.2f}]")

    # サンプル表示
    print(f"\n[INFO] Contour Sample (first 5 points):")
    for i, point in enumerate(contour[:5]):
        print(f"   [{i}]: [{point[0]:.2f}, {point[1]:.2f}]")

    # 複数フレームを確認
    frames_with_contour = sum(
        1 for frame in instrument_data[:10]
        for det in frame.get('detections', [])
        if det.get('contour') and len(det['contour']) > 0
    )

    print(f"\n[INFO] Frames with contour (first 10): {frames_with_contour}/10")

    if frames_with_contour == 0:
        print(f"[FAIL] No frames have contour data")
        return False

    print(f"\n" + "="*80)
    print(f"[SUCCESS] CONTOUR FIX VERIFIED!")
    print(f"="*80 + "\n")

    return True

def main():
    # 1. 新規解析を開始
    analysis_id = trigger_analysis()
    if not analysis_id:
        return 1

    # 2. 完了を待機
    success = wait_for_completion(analysis_id)
    if not success:
        return 1

    # 3. Contourを検証
    verified = verify_contour(analysis_id)
    if not verified:
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
