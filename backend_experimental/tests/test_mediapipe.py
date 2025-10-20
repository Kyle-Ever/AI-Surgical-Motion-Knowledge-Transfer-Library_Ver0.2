"""
MediaPipe検出の直接テスト - 骨格検出が動作するか確認
"""
import sys
from pathlib import Path
import cv2

sys.path.insert(0, str(Path(__file__).parent))

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector

# テスト動画
video_path = Path("data/uploads/c9aefc43-a76e-4957-be43-f17bd4d85960.mp4")

if not video_path.exists():
    print(f"❌ Video not found: {video_path}")
    sys.exit(1)

print(f"=== MediaPipe Skeleton Detection Test ===")
print(f"Video: {video_path}")

# フレーム抽出
cap = cv2.VideoCapture(str(video_path))
frames = []
for i in range(10):  # 最初の10フレームをテスト
    ret, frame = cap.read()
    if not ret:
        break
    frames.append(frame)
cap.release()

print(f"\nExtracted {len(frames)} frames")

# MediaPipe検出
detector = HandSkeletonDetector(min_detection_confidence=0.1)
results = detector.detect_batch(frames)

print(f"\n=== Detection Results ===")
print(f"Total results: {len(results)}")

for i, result in enumerate(results[:5]):
    print(f"\nFrame {i}:")
    print(f"  Type: {type(result)}")
    print(f"  Content: {result}")

    if isinstance(result, dict):
        detected = result.get('detected')
        hands = result.get('hands', [])
        print(f"  - detected: {detected}")
        print(f"  - hands count: {len(hands)}")
        if hands:
            print(f"  - first hand: {hands[0]}")

# 検出数カウント
detected_count = sum(1 for r in results if isinstance(r, dict) and r.get('detected'))
print(f"\n=== Summary ===")
print(f"Detected in {detected_count}/{len(results)} frames")

if detected_count == 0:
    print("\n❌ WARNING: No hands detected!")
    print("Possible reasons:")
    print("1. Video has no hands visible")
    print("2. MediaPipe confidence threshold too high")
    print("3. MediaPipe installation issue")
else:
    print(f"\n✅ SUCCESS: Detected hands in {detected_count} frames")
