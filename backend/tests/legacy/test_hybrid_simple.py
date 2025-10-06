"""
Simple test for YOLO + MediaPipe hybrid detection
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix PyTorch 2.6 weights_only issue
import torch
torch.load = lambda *args, **kwargs: torch.load(*args, **{**kwargs, 'weights_only': False}) if 'weights_only' not in kwargs else torch.load(*args, **kwargs)

import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
import mediapipe as mp


def test_hybrid():
    """Test hybrid detection with YOLO and MediaPipe"""

    print("=" * 60)
    print("Simplified Hybrid Hand Detection Test")
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

    # Initialize YOLO
    print("\nInitializing YOLO...")
    yolo = YOLO("yolov8n-pose.pt")

    # Initialize MediaPipe
    print("Initializing MediaPipe...")
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=True,
        max_num_hands=1,
        min_detection_confidence=0.3
    )

    # Open video
    cap = cv2.VideoCapture(str(test_video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\nVideo: {fps:.0f} fps, {total_frames} frames")
    print("\nProcessing frames...")
    print("-" * 60)

    frame_interval = max(1, int(fps / 5))
    both_hands_count = 0

    for frame_idx in range(0, min(100, total_frames), frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            break

        # Detect pose with YOLO
        results = yolo(frame, verbose=False)

        detected_hands = []

        for r in results:
            if r.keypoints is not None and r.keypoints.xy is not None:
                keypoints = r.keypoints.xy.cpu().numpy()

                for person_kpts in keypoints:
                    if len(person_kpts) > 10:
                        # Get wrist positions
                        left_wrist = person_kpts[9]  # Index 9: left wrist
                        right_wrist = person_kpts[10]  # Index 10: right wrist

                        # Process left hand
                        if left_wrist[0] > 0 and left_wrist[1] > 0:
                            h, w = frame.shape[:2]
                            size = int(min(w, h) * 0.15)
                            x1 = max(0, int(left_wrist[0] - size/2))
                            y1 = max(0, int(left_wrist[1] - size/2))
                            x2 = min(w, x1 + size)
                            y2 = min(h, y1 + size)

                            if x2 > x1 and y2 > y1:
                                roi = frame[y1:y2, x1:x2]
                                roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
                                result = hands.process(roi_rgb)

                                if result.multi_hand_landmarks:
                                    detected_hands.append("Left")

                        # Process right hand
                        if right_wrist[0] > 0 and right_wrist[1] > 0:
                            h, w = frame.shape[:2]
                            size = int(min(w, h) * 0.15)
                            x1 = max(0, int(right_wrist[0] - size/2))
                            y1 = max(0, int(right_wrist[1] - size/2))
                            x2 = min(w, x1 + size)
                            y2 = min(h, y1 + size)

                            if x2 > x1 and y2 > y1:
                                roi = frame[y1:y2, x1:x2]
                                roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
                                result = hands.process(roi_rgb)

                                if result.multi_hand_landmarks:
                                    detected_hands.append("Right")

        if len(detected_hands) == 2:
            both_hands_count += 1
            print(f"Frame {frame_idx}: BOTH hands detected!")
        elif len(detected_hands) == 1:
            print(f"Frame {frame_idx}: {detected_hands[0]} hand only")

    cap.release()
    hands.close()

    print("\n" + "=" * 60)
    print(f"Results: {both_hands_count} frames with both hands")
    print("=" * 60)


if __name__ == "__main__":
    test_hybrid()