"""
Test both hands detection with MediaPipe
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from pathlib import Path
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector

def create_test_video_with_both_hands():
    """Create a simple test video with both hands visible"""
    output_path = Path("test_both_hands.mp4")

    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, 30.0, (640, 480))

    # Create frames with simulated hand positions
    for frame_num in range(90):  # 3 seconds at 30fps
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 255  # White background

        # Add text
        cv2.putText(frame, f"Frame {frame_num}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.putText(frame, "Place both hands in front of camera", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Draw circles to represent hands
        # Left hand position
        left_x = 200
        left_y = 240
        cv2.circle(frame, (left_x, left_y), 50, (255, 0, 0), -1)  # Blue for left
        cv2.putText(frame, "LEFT", (left_x-20, left_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Right hand position
        right_x = 440
        right_y = 240
        cv2.circle(frame, (right_x, right_y), 50, (0, 0, 255), -1)  # Red for right
        cv2.putText(frame, "RIGHT", (right_x-25, right_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        out.write(frame)

    out.release()
    print(f"Test video created: {output_path}")
    return output_path

def test_both_hands_detection():
    """Test detection of both hands"""

    # Find the test video
    uploads_dir = Path("data/uploads")
    test_video = None

    # First, look for our test both hands video
    test_both_hands = uploads_dir / "test_both_hands_real.mp4"
    if test_both_hands.exists():
        test_video = test_both_hands
        print("Using real both hands test video")
    else:
        # Look for the larger video file (Simple Hand Motion)
        for f in uploads_dir.glob("*.mp4"):
            if f.stat().st_size > 15 * 1024 * 1024:  # Larger than 15MB
                test_video = f
                break

    if not test_video:
        print("Simple Hand Motion video not found, creating test video...")
        test_video = create_test_video_with_both_hands()

    print(f"\nTesting with video: {test_video}")

    # Initialize detector with same settings as reference code
    print("\nInitializing HandSkeletonDetector with settings from reference code...")
    print("static_image_mode=False, max_num_hands=2, confidence=0.5")
    detector = HandSkeletonDetector(
        static_image_mode=False,  # Use tracking mode like reference
        max_num_hands=2,          # Detect both hands
        min_detection_confidence=0.5,  # Same as reference code
        min_tracking_confidence=0.5,   # Same as reference code
        flip_handedness=False     # Don't flip for testing
    )

    # Open video
    cap = cv2.VideoCapture(str(test_video))
    if not cap.isOpened():
        print(f"Failed to open video: {test_video}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\nVideo info:")
    print(f"  FPS: {fps:.2f}")
    print(f"  Total frames: {total_frames}")

    # Process frames and track both hands
    frame_interval = max(1, int(fps / 5))  # Sample at 5 fps

    frames_with_left = 0
    frames_with_right = 0
    frames_with_both = 0
    frames_processed = 0

    print("\nProcessing frames...")
    print("-" * 60)

    for frame_idx in range(0, min(total_frames, 200), frame_interval):
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

            # Detailed output for frames with both hands
            if len(detection_result["hands"]) == 2:
                print(f"Frame {frame_idx}: BOTH HANDS DETECTED!")
                for i, hand in enumerate(detection_result["hands"]):
                    hand_type = hand.get('handedness', hand.get('label', 'Unknown'))
                    confidence = hand.get('confidence', 0)
                    print(f"  Hand {i+1}: {hand_type} (confidence: {confidence:.3f})")
            elif len(detection_result["hands"]) == 1:
                hand = detection_result["hands"][0]
                hand_type = hand.get('handedness', hand.get('label', 'Unknown'))
                print(f"Frame {frame_idx}: Single hand - {hand_type}")

    cap.release()

    # Summary
    print("-" * 60)
    print(f"\n=== Detection Summary ===")
    print(f"Total frames processed: {frames_processed}")
    print(f"Frames with LEFT hand:  {frames_with_left} ({frames_with_left/frames_processed*100:.1f}%)")
    print(f"Frames with RIGHT hand: {frames_with_right} ({frames_with_right/frames_processed*100:.1f}%)")
    print(f"Frames with BOTH hands: {frames_with_both} ({frames_with_both/frames_processed*100:.1f}%)")

    if frames_with_both == 0:
        print("\nWARNING: No frames detected with both hands simultaneously!")
        print("This could indicate:")
        print("  1. The video doesn't show both hands at the same time")
        print("  2. Detection confidence is too high")
        print("  3. Hands are too close together or overlapping")
    else:
        print(f"\nSuccessfully detected both hands in {frames_with_both} frames!")

if __name__ == "__main__":
    test_both_hands_detection()