"""
Test improved MediaPipe hand detection with split processing
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from pathlib import Path
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector


def test_improved_detection():
    """Test improved hand detection"""

    print("=" * 60)
    print("Improved MediaPipe Hand Detection Test")
    print("=" * 60)

    # Find test video
    uploads_dir = Path("data/uploads")
    test_video = None

    for f in uploads_dir.glob("*.mp4"):
        if "Simple Hand Motion" in f.name or f.stat().st_size > 15 * 1024 * 1024:
            test_video = f
            break

    if not test_video:
        print("Test video not found")
        return

    print(f"Video: {test_video}")
    print("-" * 60)

    # Initialize improved detector
    print("\nInitializing improved HandSkeletonDetector...")
    print("- Normal detection first")
    print("- Split processing if only 1 hand detected")
    print("- Left/right half independent processing")

    detector = HandSkeletonDetector(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        flip_handedness=False
    )

    # Open video
    cap = cv2.VideoCapture(str(test_video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\nVideo: {fps:.0f} fps, {total_frames} frames")
    print("\nProcessing frames...")
    print("-" * 60)

    frame_interval = max(1, int(fps / 5))
    frames_with_left = 0
    frames_with_right = 0
    frames_with_both = 0
    frames_processed = 0

    for frame_idx in range(0, min(100, total_frames), frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            break

        # Detect hands
        detection_result = detector.detect_from_frame(frame)
        frames_processed += 1

        if detection_result["hands"]:
            left_detected = False
            right_detected = False

            for hand in detection_result["hands"]:
                hand_type = hand.get('handedness', hand.get('label', 'Unknown'))
                if hand_type == 'Left':
                    left_detected = True
                elif hand_type == 'Right':
                    right_detected = True

            if left_detected:
                frames_with_left += 1
            if right_detected:
                frames_with_right += 1
            if left_detected and right_detected:
                frames_with_both += 1

            # Log frames with both hands
            if len(detection_result["hands"]) == 2:
                print(f"Frame {frame_idx}: [BOTH] Both hands detected!")
                for hand in detection_result["hands"]:
                    print(f"  - {hand['handedness']} (confidence: {hand['confidence']:.3f})")
            elif len(detection_result["hands"]) == 1:
                hand = detection_result["hands"][0]
                print(f"Frame {frame_idx}: [SINGLE] {hand['handedness']} hand")

    cap.release()

    # Summary
    print("\n" + "=" * 60)
    print("DETECTION SUMMARY")
    print("=" * 60)
    print(f"Total frames processed: {frames_processed}")
    print(f"Frames with LEFT hand:  {frames_with_left} ({frames_with_left/max(1,frames_processed)*100:.1f}%)")
    print(f"Frames with RIGHT hand: {frames_with_right} ({frames_with_right/max(1,frames_processed)*100:.1f}%)")
    print(f"Frames with BOTH hands: {frames_with_both} ({frames_with_both/max(1,frames_processed)*100:.1f}%)")

    if frames_with_both > 0:
        print(f"\n[SUCCESS] Both hands detected in {frames_with_both} frames!")
        print("The improved split processing is working.")
    else:
        print("\n[INFO] No frames with both hands detected")
        print("The video may not show both hands simultaneously")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_improved_detection()