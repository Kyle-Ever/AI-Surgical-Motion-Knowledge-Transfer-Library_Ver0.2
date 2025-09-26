"""White_Glove.mp4の誤検出（顔・耳）を分析"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
import mediapipe as mp

def analyze_misdetection():
    """誤検出の分析"""

    print("=" * 80)
    print("ANALYZING MISDETECTION IN WHITE GLOVE VIDEO")
    print("=" * 80)

    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/White_Glove.mp4")

    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    # MediaPipe初期化
    mp_hands = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3,
        model_complexity=1
    )

    mp_drawing = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(str(video_path))

    print("\nAnalyzing first 50 frames for misdetection...")
    print("-" * 40)

    misdetection_frames = []

    for frame_idx in range(50):
        ret, frame = cap.read()
        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = mp_hands.process(rgb_frame)

        if result.multi_hand_landmarks:
            h, w = frame.shape[:2]

            for hand_idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
                # 手首（landmark 0）の位置を確認
                wrist = hand_landmarks.landmark[0]
                wrist_x = int(wrist.x * w)
                wrist_y = int(wrist.y * h)

                # 中指のMCP（landmark 9）の位置
                middle_mcp = hand_landmarks.landmark[9]
                middle_x = int(middle_mcp.x * w)
                middle_y = int(middle_mcp.y * h)

                # 手のサイズを推定（手首から中指MCPまでの距離）
                hand_size = np.sqrt((wrist_x - middle_x)**2 + (wrist_y - middle_y)**2)

                # 手の中心位置
                center_x = sum([int(lm.landmark.x * w) for lm in hand_landmarks.landmark]) // 21
                center_y = sum([int(lm.landmark.y * h) for lm in hand_landmarks.landmark]) // 21

                # 顔・耳の可能性をチェック
                # 1. Y座標が画面上部1/3にある
                # 2. 手のサイズが異常に大きい（顔は手より大きい）
                is_face_area = center_y < h * 0.4
                is_large_size = hand_size > min(w, h) * 0.15

                # 手の形状の妥当性チェック
                # 親指と小指の距離
                thumb_tip = hand_landmarks.landmark[4]
                pinky_tip = hand_landmarks.landmark[20]
                spread = np.sqrt((thumb_tip.x - pinky_tip.x)**2 + (thumb_tip.y - pinky_tip.y)**2) * w

                # 手の縦横比
                landmarks_x = [lm.x for lm in hand_landmarks.landmark]
                landmarks_y = [lm.y for lm in hand_landmarks.landmark]
                width = (max(landmarks_x) - min(landmarks_x)) * w
                height = (max(landmarks_y) - min(landmarks_y)) * h
                aspect_ratio = height / width if width > 0 else 0

                if is_face_area or is_large_size:
                    misdetection_frames.append(frame_idx)
                    print(f"Frame {frame_idx}: Possible misdetection")
                    print(f"  - Position: ({center_x}, {center_y})")
                    print(f"  - Hand size: {hand_size:.1f}")
                    print(f"  - In face area: {is_face_area}")
                    print(f"  - Large size: {is_large_size}")
                    print(f"  - Aspect ratio: {aspect_ratio:.2f}")
                    print(f"  - Spread: {spread:.1f}")

                    # 最初の誤検出フレームを保存
                    if frame_idx == misdetection_frames[0]:
                        # 描画
                        mp_drawing.draw_landmarks(
                            frame,
                            hand_landmarks,
                            mp.solutions.hands.HAND_CONNECTIONS
                        )

                        # 誤検出の可能性を表示
                        cv2.putText(frame, "MISDETECTION?",
                                  (center_x - 50, center_y - 30),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                        output_path = "white_glove_misdetection_frame.jpg"
                        cv2.imwrite(output_path, frame)
                        print(f"\nSaved misdetection frame to {output_path}")

    cap.release()

    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total frames analyzed: 50")
    print(f"Frames with possible misdetection: {len(misdetection_frames)}")

    if misdetection_frames:
        print(f"Misdetected frames: {misdetection_frames[:10]}...")  # 最初の10フレーム
        print("\nRecommendations:")
        print("1. Filter detections in upper 1/3 of frame (face area)")
        print("2. Check hand size relative to frame")
        print("3. Validate hand shape using aspect ratio")
        print("4. Use pose detection to exclude face regions")
    else:
        print("No obvious misdetections found in first 50 frames")


if __name__ == "__main__":
    analyze_misdetection()