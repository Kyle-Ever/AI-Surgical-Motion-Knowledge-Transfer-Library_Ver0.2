"""
Test MediaPipe hand tracking with Simple Hand Motion video
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import json
from pathlib import Path
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector

def test_hand_tracking():
    # Test video path
    video_path = Path("data/uploads/Simple Hand Motion.mp4")

    # Find the actual video file
    uploads_dir = Path("data/uploads")
    matching_files = list(uploads_dir.glob("*.mp4"))

    print(f"Looking for video files in {uploads_dir}")
    print(f"Found {len(matching_files)} video files:")
    for f in matching_files:
        print(f"  - {f.name} ({f.stat().st_size / 1024 / 1024:.2f} MB)")

    # Find Simple Hand Motion video
    simple_hand_motion = None
    for f in matching_files:
        if f.stat().st_size > 15 * 1024 * 1024:  # Larger than 15MB
            simple_hand_motion = f
            print(f"\nUsing video: {f.name}")
            break

    if not simple_hand_motion:
        print("Could not find Simple Hand Motion video")
        return

    # Initialize detector
    print("\nInitializing HandSkeletonDetector...")
    detector = HandSkeletonDetector(
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    )

    # Open video
    cap = cv2.VideoCapture(str(simple_hand_motion))
    if not cap.isOpened():
        print(f"Failed to open video: {simple_hand_motion}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\nVideo info:")
    print(f"  FPS: {fps:.2f}")
    print(f"  Total frames: {total_frames}")
    print(f"  Duration: {total_frames/fps:.2f} seconds")

    # Process some frames
    print("\nProcessing frames...")
    frame_interval = max(1, int(fps / 10))  # Sample at 10 fps

    frames_processed = 0
    hands_detected = 0
    results = []

    for frame_idx in range(0, min(total_frames, 100), frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            break

        # Detect hands
        detection_result = detector.detect_from_frame(frame)

        frames_processed += 1
        if detection_result["hands"]:
            hands_detected += 1

            print(f"\nFrame {frame_idx}:")
            for hand in detection_result["hands"]:
                # Check the structure of the hand data
                print(f"  Hand keys: {hand.keys()}")
                print(f"  Hand type: {hand.get('handedness', hand.get('label', 'Unknown'))}")
                print(f"  Confidence: {hand.get('confidence', 0):.3f}")
                print(f"  Landmarks: {len(hand.get('landmarks', []))} points")

                # Check finger angles
                if 'finger_angles' in hand:
                    print(f"  Finger angles:")
                    for finger, angle in hand['finger_angles'].items():
                        print(f"    {finger}: {angle:.1f}°")

                # Store result
                results.append({
                    "frame": frame_idx,
                    "timestamp": frame_idx / fps,
                    "hand_type": hand.get('handedness', hand.get('label', 'Unknown')),
                    "confidence": hand.get('confidence', 0),
                    "num_landmarks": len(hand.get('landmarks', [])),
                    "hand_openness": hand.get('hand_openness', 0)
                })

    cap.release()

    # Summary
    print(f"\n=== Summary ===")
    print(f"Frames processed: {frames_processed}")
    print(f"Frames with hands detected: {hands_detected}")
    print(f"Detection rate: {hands_detected/frames_processed*100:.1f}%")

    # Save results
    output_file = Path("test_hand_tracking_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_file}")

if __name__ == "__main__":
    test_hand_tracking()