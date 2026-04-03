# -*- coding: utf-8 -*-
"""
圧縮処理の修正を検証するスクリプト

_compress_instrument_dataメソッドが正しく動作するかテストする
"""
import sys
import inspect
from app.services.analysis_service_v2 import AnalysisServiceV2

print("=" * 60)
print("圧縮処理修正の検証")
print("=" * 60)

# ソースコードを取得
source = inspect.getsource(AnalysisServiceV2._compress_instrument_data)

# 修正内容の確認
checks = {
    "frame_number対応": "frame_data.get('frame_number')" in source,
    "detections対応": "'detections': []" in source and "frame_data.get('detections', [])" in source,
    "SAM2キー対応 (id)": "det.get('id')" in source,
    "SAM2キー対応 (name)": "det.get('name'" in source,
    "SAM2キー対応 (center)": "det.get('center'" in source,
    "デバッグログ追加": "Compression input" in source,
    "圧縮後検証": "After mask removal" in source,
    "旧キー削除 (frame_index)": "frame_data.get('frame_index'" not in source,
    "旧キー削除 (instruments)": "'instruments': []" not in source or "'detections': []" in source,
    "旧キー削除 (class_name)": "inst.get('class_name'" not in source,
    "旧キー削除 (track_id)": "inst.get('track_id'" not in source,
}

all_passed = True
for check_name, result in checks.items():
    status = "[OK]" if result else "[FAILED]"
    print(f"{status} {check_name}")
    if not result:
        all_passed = False

print("\n" + "=" * 60)
if all_passed:
    print("[SUCCESS] 全ての修正が正しく適用されています")
    print("=" * 60)
    sys.exit(0)
else:
    print("[ERROR] 一部の修正が適用されていません")
    print("=" * 60)
    sys.exit(1)
