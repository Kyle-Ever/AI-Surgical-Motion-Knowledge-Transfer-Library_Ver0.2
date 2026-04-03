"""
Contour生成修正の検証テスト

目的:
  - `convert_numpy_types` → `compress` の順序バグ修正を検証
  - 既存の解析データでcontour配列を確認

検証項目:
  1. 最新の解析 (ca14493f) でcontourが空でないか確認
  2. contourの構造が正しいか検証 (配列の配列、座標値)
  3. バックエンドログで [CONTOUR_DEBUG] を確認
"""

import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8001/api/v1"

def test_analysis_contour(analysis_id: str):
    """
    指定された解析IDのcontourデータを検証
    """
    print(f"\n{'='*60}")
    print(f"Testing Analysis: {analysis_id}")
    print(f"{'='*60}\n")

    # 解析結果を取得
    url = f"{API_BASE}/analysis/{analysis_id}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"[FAIL] Failed to fetch analysis: {response.status_code}")
        return False

    data = response.json()

    # 基本情報を表示
    print(f"[INFO] Analysis Info:")
    print(f"   - ID: {data.get('id')}")
    print(f"   - Status: {data.get('status')}")
    print(f"   - Video Type: {data.get('video_type')}")
    print(f"   - Created: {data.get('created_at')}")

    # instrument_dataの存在確認
    if 'instrument_data' not in data:
        print(f"[FAIL] Missing 'instrument_data' field")
        return False

    instrument_data = data['instrument_data']
    if not isinstance(instrument_data, list):
        print(f"[FAIL] 'instrument_data' is not a list: {type(instrument_data)}")
        return False

    if len(instrument_data) == 0:
        print(f"[FAIL] 'instrument_data' is empty")
        return False

    print(f"\n[PASS] instrument_data exists: {len(instrument_data)} frames")

    # 最初のフレームを検証
    first_frame = instrument_data[0]
    print(f"\n[INFO] First Frame:")
    print(f"   - Frame Number: {first_frame.get('frame_number')}")
    print(f"   - Timestamp: {first_frame.get('timestamp')}")
    print(f"   - Detections Count: {len(first_frame.get('detections', []))}")

    detections = first_frame.get('detections', [])
    if len(detections) == 0:
        print(f"[FAIL] No detections in first frame")
        return False

    first_detection = detections[0]
    print(f"\n[INFO] First Detection:")
    print(f"   - ID: {first_detection.get('id')}")
    print(f"   - Name: {first_detection.get('name')}")
    print(f"   - BBox: {first_detection.get('bbox')}")
    print(f"   - Confidence: {first_detection.get('confidence')}")

    # Contour検証 (修正の核心部分)
    if 'contour' not in first_detection:
        print(f"[FAIL] Missing 'contour' field in detection")
        return False

    contour = first_detection['contour']
    print(f"\n[TEST] Contour Validation:")
    print(f"   - Type: {type(contour)}")
    print(f"   - Length: {len(contour) if isinstance(contour, list) else 'N/A'}")

    if not isinstance(contour, list):
        print(f"[FAIL] Contour is not a list")
        return False

    if len(contour) == 0:
        print(f"[FAIL] Contour is empty (BUG NOT FIXED)")
        return False

    print(f"[PASS] Contour is not empty ({len(contour)} points)")

    # Contourの構造を検証
    first_point = contour[0]
    print(f"\n[INFO] First Contour Point:")
    print(f"   - Type: {type(first_point)}")
    print(f"   - Value: {first_point}")

    if not isinstance(first_point, list):
        print(f"[FAIL] Contour point is not a list")
        return False

    if len(first_point) != 2:
        print(f"[FAIL] Contour point does not have 2 coordinates: {len(first_point)}")
        return False

    if not all(isinstance(coord, (int, float)) for coord in first_point):
        print(f"[FAIL] Contour coordinates are not numbers")
        return False

    print(f"[PASS] Contour structure is valid")
    print(f"   - Point format: [x, y]")
    print(f"   - First point: [{first_point[0]:.2f}, {first_point[1]:.2f}]")

    # サンプルポイントを表示
    print(f"\n[INFO] Contour Sample (first 5 points):")
    for i, point in enumerate(contour[:5]):
        print(f"   [{i}]: [{point[0]:.2f}, {point[1]:.2f}]")

    # 複数フレームでも検証
    print(f"\n[INFO] Checking Multiple Frames:")
    frames_with_contour = 0
    frames_without_contour = 0

    for frame in instrument_data[:10]:  # 最初の10フレームをチェック
        for detection in frame.get('detections', []):
            if detection.get('contour') and len(detection['contour']) > 0:
                frames_with_contour += 1
            else:
                frames_without_contour += 1

    print(f"   - Frames with contour: {frames_with_contour}")
    print(f"   - Frames without contour: {frames_without_contour}")

    if frames_with_contour == 0:
        print(f"[FAIL] No frames have contour data")
        return False

    print(f"\n{'='*60}")
    print(f"[PASS] TEST PASSED: Contour fix is working!")
    print(f"{'='*60}\n")

    return True


def main():
    print("\n" + "="*80)
    print("Contour Fix Verification Test")
    print("="*80)

    # テスト対象の解析ID (最新のもの)
    test_analysis_ids = [
        "ca14493f-b8e0-4aa8-a060-04ab7c962d5c",  # 最新の解析
    ]

    all_passed = True
    for analysis_id in test_analysis_ids:
        try:
            passed = test_analysis_contour(analysis_id)
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"[ERROR] Error testing {analysis_id}: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print("\n" + "="*80)
    if all_passed:
        print("[SUCCESS] ALL TESTS PASSED")
    else:
        print("[FAILED] SOME TESTS FAILED")
    print("="*80 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
