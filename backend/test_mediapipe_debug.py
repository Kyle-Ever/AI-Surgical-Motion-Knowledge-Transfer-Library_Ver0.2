import cv2
import mediapipe as mp
import numpy as np
from pathlib import Path
import sys
import traceback

def test_mediapipe():
    try:
        print("=== MediaPipe Debug Test ===")

        # Use first uploaded video for testing
        upload_dir = Path('data/uploads')
        video_files = list(upload_dir.glob('*.mp4'))

        if not video_files:
            print("ERROR: No uploaded videos found")
            return

        test_path = video_files[0]
        print(f"Video file: {test_path}")
        print(f"File size: {test_path.stat().st_size / 1024 / 1024:.2f} MB")

        # Initialize MediaPipe
        print("\nInitializing MediaPipe...")
        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.3,  # Lower threshold
            min_tracking_confidence=0.3    # Lower threshold
        )
        print("MediaPipe initialized successfully")

        # Open video
        print("\nOpening video...")
        cap = cv2.VideoCapture(str(test_path))

        if not cap.isOpened():
            print("ERROR: Cannot open video")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"Video opened: {fps} fps, {frame_count} frames")

        # Test first 10 frames
        detected_count = 0
        for i in range(min(10, frame_count)):
            ret, frame = cap.read()
            if not ret:
                print(f"Frame {i}: Cannot read")
                break

            print(f"\nFrame {i}:")
            print(f"  Shape: {frame.shape}")
            print(f"  dtype: {frame.dtype}")

            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Process with MediaPipe
            print("  Processing with MediaPipe...")
            results = hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                detected_count += 1
                print(f"  [DETECTED] Hands found: {len(results.multi_hand_landmarks)}")
                for j, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    print(f"    Hand {j}: {len(hand_landmarks.landmark)} landmarks")
                    # Print first landmark as example
                    landmark = hand_landmarks.landmark[0]
                    print(f"      Wrist: x={landmark.x:.3f}, y={landmark.y:.3f}, z={landmark.z:.3f}")
            else:
                print("  [NOT DETECTED] No hands found")

        print(f"\n=== Summary ===")
        print(f"Frames tested: {min(10, frame_count)}")
        print(f"Frames with hands: {detected_count}")
        print(f"Detection rate: {detected_count/min(10, frame_count)*100:.1f}%")

        cap.release()
        hands.close()

    except Exception as e:
        print(f"\n=== ERROR ===")
        print(f"Error: {str(e)}")
        print(f"Type: {type(e).__name__}")
        traceback.print_exc()

if __name__ == "__main__":
    test_mediapipe()