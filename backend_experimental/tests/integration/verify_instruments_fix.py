# -*- coding: utf-8 -*-
import inspect
from app.services.analysis_service_v2 import AnalysisServiceV2

# _format_instrument_dataメソッドのソースを確認
source = inspect.getsource(AnalysisServiceV2._format_instrument_data)

if "instruments = result.get('instruments', result.get('detections', []))" in source:
    print("[OK] Fixed code is loaded! Variable name changed to 'instruments'")
    print("[OK] Detection key fallback logic present")
else:
    print("[ERROR] Old code still loaded! Variable still named 'detections'")

# 関連する行を表示
for i, line in enumerate(source.split('\n'), 1):
    if 'instruments' in line.lower() or 'detections' in line.lower():
        print(f"Line {i}: {line.strip()}")
