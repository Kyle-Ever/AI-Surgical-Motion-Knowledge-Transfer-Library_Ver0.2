"""White_Glove.mp4のシンプルな検出テスト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
import mediapipe as mp

def test_simple_detection():
    """基本的な手検出テスト"""

    print("=" * 80)
    print("SIMPLE WHITE GLOVE DETECTION TEST")
    print("=" * 80)

    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/White_Glove.mp4")

    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    # 複数の設定でMediaPipeを試す
    configs = [
        {"name": "Ultra Low (0.01)", "min_detection": 0.01, "min_tracking": 0.01},
        {"name": "Low (0.1)", "min_detection": 0.1, "min_tracking": 0.1},
        {"name": "Medium (0.3)", "min_detection": 0.3, "min_tracking": 0.3},
        {"name": "Default (0.5)", "min_detection": 0.5, "min_tracking": 0.5},
    ]

    cap = cv2.VideoCapture(str(video_path))

    # 最初の10フレームをサンプル
    sample_frames = []
    for i in range(10):
        ret, frame = cap.read()
        if ret:
            sample_frames.append(frame)

    # 100フレーム目もサンプル
    cap.set(cv2.CAP_PROP_POS_FRAMES, 100)
    for i in range(10):
        ret, frame = cap.read()
        if ret:
            sample_frames.append(frame)

    cap.release()

    print(f"\nTesting {len(sample_frames)} sample frames with different configurations...")
    print("-" * 40)

    results = {}

    for config in configs:
        print(f"\nTesting: {config['name']}")

        mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=config['min_detection'],
            min_tracking_confidence=config['min_tracking'],
            model_complexity=1
        )

        detected_count = 0
        total_hands = 0

        for idx, frame in enumerate(sample_frames):
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = mp_hands.process(rgb_frame)

            if result.multi_hand_landmarks:
                detected_count += 1
                num_hands = len(result.multi_hand_landmarks)
                total_hands += num_hands

                if idx < 3:  # 最初の3フレームの詳細
                    h, w = frame.shape[:2]
                    for hand_landmarks in result.multi_hand_landmarks:
                        # 手の位置を確認
                        wrist = hand_landmarks.landmark[0]
                        wrist_x = int(wrist.x * w)
                        wrist_y = int(wrist.y * h)
                        print(f"  Frame {idx}: Hand at ({wrist_x}, {wrist_y})")

        detection_rate = (detected_count / len(sample_frames)) * 100
        avg_hands = total_hands / detected_count if detected_count > 0 else 0

        results[config['name']] = {
            'detected': detected_count,
            'total_hands': total_hands,
            'rate': detection_rate,
            'avg_hands': avg_hands
        }

        print(f"  Detection rate: {detection_rate:.1f}%")
        print(f"  Average hands: {avg_hands:.2f}")

        mp_hands.close()

    # 結果のサマリー
    print("\n" + "=" * 80)
    print("DETECTION SUMMARY")
    print("=" * 80)

    for name, res in results.items():
        print(f"{name:20} : {res['rate']:5.1f}% detection, {res['avg_hands']:.1f} hands/frame")

    # 最初のフレームを保存して確認
    if sample_frames:
        output_path = "white_glove_first_frame.jpg"
        cv2.imwrite(output_path, sample_frames[0])
        print(f"\nFirst frame saved to {output_path}")

        # フレーム100も保存
        if len(sample_frames) > 10:
            output_path2 = "white_glove_frame_100.jpg"
            cv2.imwrite(output_path2, sample_frames[10])
            print(f"Frame 100 saved to {output_path2}")


if __name__ == "__main__":
    test_simple_detection()