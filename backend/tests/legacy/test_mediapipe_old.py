"""
MediaPipe骨格検出機能のテストスクリプト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.frame_extractor import FrameExtractor
import glob
import numpy as np

def test_mediapipe_detection():
    """MediaPipe手の骨格検出をテスト"""

    # テスト用動画を探す
    video_files = glob.glob("data/uploads/*.mp4")

    if not video_files:
        print("[ERROR] No test videos found in data/uploads/")
        return False

    test_video = video_files[0]
    print(f"[OK] Found test video: {test_video}")

    try:
        # MediaPipe検出器を初期化
        print("\n1. Initializing HandSkeletonDetector...")
        detector = HandSkeletonDetector(
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        print("   [OK] Detector initialized")

        # 動画からフレームを抽出
        print("\n2. Extracting frames from video...")
        with FrameExtractor(test_video, target_fps=5) as extractor:
            frames = []
            for i, (frame_num, frame) in enumerate(extractor.extract_frames_generator()):
                frames.append((frame_num, frame))
                if i >= 4:  # 5フレーム取得
                    break

        print(f"   [OK] Extracted {len(frames)} frames")

        # 各フレームで手の検出
        print("\n3. Detecting hands in frames...")
        detection_results = []

        for frame_num, frame in frames:
            hands = detector.detect(frame)

            if hands:
                print(f"   Frame {frame_num}: Detected {len(hands)} hand(s)")
                for i, hand in enumerate(hands):
                    landmarks = hand.get('landmarks', [])
                    print(f"      Hand {i+1}: {len(landmarks)} landmarks")
                    # 最初の3つのランドマーク座標を表示
                    for j, lm in enumerate(landmarks[:3]):
                        print(f"         Landmark {j}: x={lm['x']:.3f}, y={lm['y']:.3f}, z={lm['z']:.3f}")
            else:
                print(f"   Frame {frame_num}: No hands detected")

            detection_results.append({
                'frame': frame_num,
                'hands_detected': len(hands) if hands else 0
            })

        # 統計情報
        print("\n4. Detection Statistics:")
        total_detections = sum(r['hands_detected'] for r in detection_results)
        frames_with_detections = sum(1 for r in detection_results if r['hands_detected'] > 0)

        print(f"   Total hands detected: {total_detections}")
        print(f"   Frames with detections: {frames_with_detections}/{len(detection_results)}")
        print(f"   Detection rate: {frames_with_detections/len(detection_results)*100:.1f}%")

        # 可視化テスト（画像として保存）
        print("\n5. Testing visualization...")
        if frames and detection_results[0]['hands_detected'] > 0:
            frame_num, frame = frames[0]
            hands = detector.detect(frame)
            visualized = detector.visualize(frame.copy(), hands)
            print(f"   [OK] Visualization created with shape: {visualized.shape}")

            # 保存（オプション）
            import cv2
            output_path = "test_mediapipe_output.jpg"
            cv2.imwrite(output_path, visualized)
            print(f"   [OK] Saved visualization to {output_path}")

        print("\n[SUCCESS] All MediaPipe tests passed!")
        return True

    except Exception as e:
        print(f"\n[ERROR] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mediapipe_detection()
    sys.exit(0 if success else 1)