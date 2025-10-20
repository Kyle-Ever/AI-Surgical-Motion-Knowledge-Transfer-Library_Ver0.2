"""
instruments形式変換のテスト
"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from app.services.analysis_service_v2 import AnalysisServiceV2

# テスト用の保存形式instruments
saved_format = [
    {
        "name": "器具1",
        "bbox": [359, 158, 470, 398],  # [x, y, w, h]
        "frame_number": 0,
        "mask": "base64_data_here"
    },
    {
        "name": "器具2",
        "bbox": [100, 200, 150, 250],
        "frame_number": 0,
        "mask": "base64_data_here"
    }
]

print("=== Test: Instruments Format Conversion ===\n")
print("Input (saved format):")
print(json.dumps(saved_format, indent=2, ensure_ascii=False))
print()

# AnalysisServiceV2インスタンス作成
service = AnalysisServiceV2()

# 変換実行
converted = service._convert_instruments_format(saved_format)

print("Output (SAM format):")
print(json.dumps(converted, indent=2, ensure_ascii=False))
print()

# 検証
print("=== Validation ===")
for i, inst in enumerate(converted):
    print(f"\nInstrument {i}:")
    print(f"  - ID: {inst['id']}")
    print(f"  - Name: {inst['name']}")
    print(f"  - Selection type: {inst['selection']['type']}")
    print(f"  - BBox (x1,y1,x2,y2): {inst['selection']['data']}")
    print(f"  - Color: {inst['color']}")

    # bbox変換の検証
    original_bbox = saved_format[i]['bbox']
    x, y, w, h = original_bbox
    expected_xyxy = [x, y, x + w, y + h]
    actual_xyxy = inst['selection']['data']

    if expected_xyxy == actual_xyxy:
        print(f"  ✅ BBox conversion correct: [x,y,w,h]={original_bbox} → [x1,y1,x2,y2]={actual_xyxy}")
    else:
        print(f"  ❌ BBox conversion error: expected {expected_xyxy}, got {actual_xyxy}")

print("\n=== Test Complete ===")
