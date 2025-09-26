"""
Create a real test video with both hands visible for testing MediaPipe detection
This script uses webcam to record a video with both hands
"""

import cv2
import numpy as np
from pathlib import Path
import time

def create_synthetic_both_hands_video():
    """Create a synthetic video with simulated hand movements"""
    output_path = Path("data/uploads/test_both_hands_synthetic.mp4")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Video settings
    width, height = 640, 480
    fps = 30
    duration = 10  # seconds
    total_frames = fps * duration

    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    print(f"Creating synthetic both hands video...")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    print(f"Duration: {duration} seconds")

    for frame_num in range(total_frames):
        # Create white background
        frame = np.ones((height, width, 3), dtype=np.uint8) * 255

        # Calculate time-based positions for hand movement
        t = frame_num / fps

        # Left hand (blue) - moves in a circle
        left_x = int(200 + 50 * np.cos(2 * np.pi * t / 3))
        left_y = int(240 + 50 * np.sin(2 * np.pi * t / 3))

        # Right hand (red) - moves in opposite circle
        right_x = int(440 - 50 * np.cos(2 * np.pi * t / 3))
        right_y = int(240 - 50 * np.sin(2 * np.pi * t / 3))

        # Draw hands as circles with finger-like extensions
        # Left hand (blue)
        cv2.circle(frame, (left_x, left_y), 30, (255, 100, 0), -1)  # Palm
        for angle in range(0, 360, 72):  # 5 fingers
            fx = left_x + int(40 * np.cos(np.radians(angle)))
            fy = left_y + int(40 * np.sin(np.radians(angle)))
            cv2.line(frame, (left_x, left_y), (fx, fy), (255, 100, 0), 5)
            cv2.circle(frame, (fx, fy), 8, (255, 150, 50), -1)

        # Right hand (red)
        cv2.circle(frame, (right_x, right_y), 30, (0, 100, 255), -1)  # Palm
        for angle in range(0, 360, 72):  # 5 fingers
            fx = right_x + int(40 * np.cos(np.radians(angle + 36)))
            fy = right_y + int(40 * np.sin(np.radians(angle + 36)))
            cv2.line(frame, (right_x, right_y), (fx, fy), (0, 100, 255), 5)
            cv2.circle(frame, (fx, fy), 8, (50, 150, 255), -1)

        # Add labels
        cv2.putText(frame, "LEFT HAND", (left_x - 40, left_y - 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        cv2.putText(frame, "RIGHT HAND", (right_x - 45, right_y - 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Add frame info
        cv2.putText(frame, f"Frame {frame_num}/{total_frames}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.putText(frame, "Both Hands Test Video", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 128, 0), 2)

        # Distance between hands
        distance = int(np.sqrt((right_x - left_x)**2 + (right_y - left_y)**2))
        cv2.putText(frame, f"Distance: {distance}px", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 1)

        out.write(frame)

        if frame_num % 30 == 0:
            print(f"Progress: {frame_num}/{total_frames} frames")

    out.release()
    print(f"\nVideo created successfully: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    return output_path

def record_real_hands_from_webcam():
    """Record real hands from webcam (if available)"""
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Webcam not available. Creating synthetic video instead...")
        return create_synthetic_both_hands_video()

    output_path = Path("data/uploads/test_both_hands_real.mp4")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get webcam properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = 30

    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    print("Recording from webcam...")
    print("Show both hands to the camera!")
    print("Press 'q' to stop recording")

    start_time = time.time()
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Add instructions overlay
        cv2.putText(frame, "Show BOTH HANDS to camera", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, "Press 'q' to stop", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        elapsed = time.time() - start_time
        cv2.putText(frame, f"Recording: {elapsed:.1f}s", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        # Show preview
        cv2.imshow('Recording - Press Q to stop', frame)

        # Write frame
        out.write(frame)
        frame_count += 1

        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q') or elapsed > 10:
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()

    print(f"\nVideo recorded: {output_path}")
    print(f"Duration: {frame_count/fps:.1f} seconds")
    print(f"File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    return output_path

if __name__ == "__main__":
    print("Creating both hands test video...")
    print("-" * 50)

    # Try webcam first, fall back to synthetic
    try:
        video_path = record_real_hands_from_webcam()
    except Exception as e:
        print(f"Webcam recording failed: {e}")
        print("Creating synthetic video instead...")
        video_path = create_synthetic_both_hands_video()

    print("\nVideo creation complete!")
    print(f"Test video saved at: {video_path}")
    print("\nYou can now upload this video to test both hands detection.")