"""
detect_batchがなぜ空の結果を返すのかデバッグ
"""
import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified

# テスト動画
video_path = Path("data/uploads/952c451c-8695-456f-996a-8a482a3afa9e.mp4")
cap = cv2.VideoCapture(str(video_path))

# 最初のフレーム読み込み
ret, frame = cap.read()
if not ret:
    print("ERROR: Failed to read frame")
    sys.exit(1)

print(f"Frame shape: {frame.shape}")
print()

# ケース1: 初期化なしでdetect_batch
print("=== Test 1: detect_batch WITHOUT initialization ===")
tracker1 = SAMTrackerUnified(device='cpu')
print(f"tracked_instruments: {len(tracker1.tracked_instruments)}")
results1 = tracker1.detect_batch([frame])
print(f"Results: {results1}")
print()

# ケース2: auto_detect後にdetect_batch
print("=== Test 2: detect_batch WITH auto_detect ===")
tracker2 = SAMTrackerUnified(device='cpu')
tracker2.auto_detect_instruments(frame, max_instruments=5)
print(f"tracked_instruments after auto_detect: {len(tracker2.tracked_instruments)}")
for inst in tracker2.tracked_instruments:
    print(f"  - {inst['name']}: bbox={inst['last_bbox']}, score={inst['last_score']:.4f}")
results2 = tracker2.detect_batch([frame])
print(f"Results: {len(results2[0]['detections'])} detections")
for det in results2[0]['detections']:
    print(f"  - {det['class_name']}: bbox={det['bbox']}, conf={det['confidence']:.4f}")

cap.release()
