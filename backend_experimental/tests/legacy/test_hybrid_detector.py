"""
Test Hybrid Hand Detector with Simple Hand Motion video
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from pathlib import Path
from app.ai_engine.processors.hybrid_hand_detector import HybridHandDetector


def test_hybrid_detection():
    """Test hybrid hand detection with real video"""

    print("=" * 60)
    print("Hybrid Hand Detection Test (YOLO + MediaPipe)")
    print("=" * 60)

    # Find test video
    uploads_dir = Path("data/uploads")
    test_video = None

    # Look for Simple Hand Motion video
    for f in uploads_dir.glob("*.mp4"):
        if "Simple Hand Motion" in f.name or f.stat().st_size > 15 * 1024 * 1024:
            test_video = f
            break

    if not test_video:
        print("Error: Test video not found")
        return

    print(f"\nTesting with video: {test_video}")
    print("-" * 60)

    # Initialize hybrid detector
    print("\nInitializing Hybrid Hand Detector...")
    print("- YOLO: Detection of hand regions")
    print("- MediaPipe: 21-point landmark extraction")

    try:
        detector = HybridHandDetector(
            yolo_model_path="yolov8n-pose.pt",  # Will auto-download if needed
            confidence_threshold=0.5,
            flip_handedness=False  # Internal camera
        )
        print("[OK] Detector initialized successfully")
    except Exception as e:
        print(f"[ERROR] Failed to initialize detector: {e}")
        return

    # Open video
    cap = cv2.VideoCapture(str(test_video))
    if not cap.isOpened():
        print(f"Error: Failed to open video")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\nVideo Info:")
    print(f"- FPS: {fps:.2f}")
    print(f"- Total frames: {total_frames}")

    # Process frames
    frame_interval = max(1, int(fps / 5))  # Sample at 5 fps

    frames_with_left = 0
    frames_with_right = 0
    frames_with_both = 0
    frames_processed = 0

    print("\nProcessing frames...")
    print("-" * 60)

    for frame_idx in range(0, min(total_frames, 100), frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            break

        # Detect hands using hybrid approach
        try:
            detection_result = detector.detect_from_frame(frame)
            frames_processed += 1

            if detection_result["has_left"]:
                frames_with_left += 1
            if detection_result["has_right"]:
                frames_with_right += 1
            if detection_result["has_left"] and detection_result["has_right"]:
                frames_with_both += 1

            # Log frames with both hands detected
            if detection_result["num_hands"] == 2:
                print(f"Frame {frame_idx}: [BOTH] BOTH HANDS DETECTED!")
                for hand in detection_result["hands"]:
                    print(f"  - {hand['handedness']} hand (confidence: {hand['confidence']:.3f})")
            elif detection_result["num_hands"] == 1:
                hand = detection_result["hands"][0]
                print(f"Frame {frame_idx}: [SINGLE] {hand['handedness']} hand detected")

        except Exception as e:
            print(f"Frame {frame_idx}: Error - {e}")

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
        print("The hybrid approach is working correctly.")
    else:
        print("\n[WARNING] No frames with both hands detected")
        print("Possible issues:")
        print("1. Both hands may not be visible in the video")
        print("2. YOLO may need fine-tuning for hand detection")
        print("3. Consider using YOLO pose model for better results")

    print("\n" + "=" * 60)
    print("Next Steps:")
    print("1. If successful, update analysis.py to use HybridHandDetector")
    print("2. If not, try yolov8n-pose.pt for better body part detection")
    print("=" * 60)


if __name__ == "__main__":
    test_hybrid_detection()