"""
Test YOLOv8 for hand detection and pose estimation
"""

import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
import json

def test_yolo_hand_detection():
    """Test YOLOv8 pose model for hand detection"""

    print("Testing YOLOv8 for hand detection...")
    print("-" * 50)

    # Load YOLOv8 pose model (can detect human keypoints including hands)
    print("Loading YOLOv8 pose model...")
    model = YOLO('yolov8n-pose.pt')  # Will download if not available

    # Find test video
    video_path = Path("data/uploads/test_both_hands_real.mp4")
    if not video_path.exists():
        # Use any available video
        uploads_dir = Path("data/uploads")
        videos = list(uploads_dir.glob("*.mp4"))
        if videos:
            video_path = videos[0]
        else:
            print("No video files found")
            return

    print(f"Testing with video: {video_path}")

    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\nVideo info:")
    print(f"  FPS: {fps:.2f}")
    print(f"  Total frames: {total_frames}")

    # Process frames
    frame_interval = max(1, int(fps / 5))  # Sample at 5 fps
    detections = []

    print("\nProcessing frames...")

    for frame_idx in range(0, min(total_frames, 100), frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            break

        # Run YOLOv8 inference
        results = model(frame, verbose=False)

        # Process results
        for r in results:
            if r.keypoints is not None and r.keypoints.xy is not None:
                keypoints = r.keypoints.xy.cpu().numpy()

                # YOLOv8-pose detects full body, but we can extract wrist points
                # Keypoint indices: 9=left_wrist, 10=right_wrist
                for person_idx, person_kpts in enumerate(keypoints):
                    left_wrist = person_kpts[9] if len(person_kpts) > 9 else None
                    right_wrist = person_kpts[10] if len(person_kpts) > 10 else None

                    hands_detected = []
                    if left_wrist is not None and left_wrist[0] > 0:
                        hands_detected.append("Left")
                    if right_wrist is not None and right_wrist[0] > 0:
                        hands_detected.append("Right")

                    if hands_detected:
                        print(f"Frame {frame_idx}: Detected {hands_detected}")
                        detections.append({
                            "frame": frame_idx,
                            "hands": hands_detected,
                            "person_id": person_idx
                        })

    cap.release()

    # Summary
    print("\n" + "=" * 50)
    print("YOLO Detection Summary:")

    frames_with_both = sum(1 for d in detections if len(d["hands"]) == 2)
    frames_with_left = sum(1 for d in detections if "Left" in d["hands"])
    frames_with_right = sum(1 for d in detections if "Right" in d["hands"])

    print(f"Total detections: {len(detections)}")
    print(f"Frames with LEFT hand: {frames_with_left}")
    print(f"Frames with RIGHT hand: {frames_with_right}")
    print(f"Frames with BOTH hands: {frames_with_both}")

    return detections

def test_yolo_custom_hand_model():
    """Test YOLOv8 with custom hand detection model"""

    print("\n" + "=" * 50)
    print("Alternative: Custom Hand Detection with YOLOv8")
    print("-" * 50)

    print("For more accurate hand detection, consider:")
    print("1. Training YOLOv8 on hand-specific dataset")
    print("2. Using pre-trained hand detection models:")
    print("   - EgoHands dataset models")
    print("   - Oxford Hand dataset models")
    print("3. Combining YOLO detection with MediaPipe landmarks")
    print("\nHybrid approach:")
    print("- Use YOLO for robust hand detection (bounding boxes)")
    print("- Use MediaPipe for detailed landmark extraction within each box")

    # Example hybrid approach
    print("\nHybrid Detection Pseudocode:")
    print("""
    1. Detect hands with YOLO → Get bounding boxes
    2. For each bounding box:
       - Crop image region
       - Run MediaPipe on cropped region
       - Get 21 landmarks with high accuracy
    3. Combine results:
       - YOLO provides robust multi-hand detection
       - MediaPipe provides detailed landmarks
    """)

if __name__ == "__main__":
    try:
        # Test YOLO pose model
        test_yolo_hand_detection()

        # Show custom model options
        test_yolo_custom_hand_model()

    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: YOLOv8 requires ultralytics package")
        print("Install with: pip install ultralytics")