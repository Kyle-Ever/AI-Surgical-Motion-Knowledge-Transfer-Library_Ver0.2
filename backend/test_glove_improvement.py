"""青い手袋検出の改善テスト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
import time

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.glove_hand_detector import GloveHandDetector


def test_blue_glove_detection():
    """青い手袋検出の改善効果をテスト"""

    # テスト動画のパス
    video_paths = [
        Path("../data/uploads/Front_Angle.mp4"),
        Path("data/uploads/Front_Angle.mp4"),
        Path("test.mp4")  # ローカルテストファイル
    ]

    video_path = None
    for path in video_paths:
        if path.exists():
            video_path = path
            break

    if not video_path:
        print("Error: No test video found")
        print("Please ensure a video exists at one of these locations:")
        for path in video_paths:
            print(f"  - {path}")
        return

    print(f"Using test video: {video_path}")

    # 3つのディテクターを初期化
    print("\nInitializing detectors...")

    # 1. 標準版（手袋モード無効）
    standard_detector = HandSkeletonDetector(
        enable_glove_detection=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # 2. 改善版（手袋モード有効）
    improved_detector = HandSkeletonDetector(
        enable_glove_detection=True,
        min_detection_confidence=0.2,
        min_tracking_confidence=0.2
    )

    # 3. 高性能版
    advanced_detector = GloveHandDetector(
        use_color_enhancement=True,
        min_hand_confidence=0.2
    )

    cap = cv2.VideoCapture(str(video_path))

    # 結果を記録
    results = {
        'standard': {'detected': 0, 'hands_count': []},
        'improved': {'detected': 0, 'hands_count': []},
        'advanced': {'detected': 0, 'hands_count': []}
    }

    frame_count = 0
    max_frames = 100  # 最初の100フレームでテスト

    print(f"\nProcessing first {max_frames} frames...")
    print("Frame | Standard | Improved | Advanced")
    print("-" * 45)

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        # 各ディテクターでテスト
        standard_result = standard_detector.detect_from_frame(frame)
        improved_result = improved_detector.detect_from_frame(frame)
        advanced_result = advanced_detector.detect_from_frame(frame)

        # 結果を記録
        if standard_result["hands"]:
            results['standard']['detected'] += 1
            results['standard']['hands_count'].append(len(standard_result["hands"]))
        else:
            results['standard']['hands_count'].append(0)

        if improved_result["hands"]:
            results['improved']['detected'] += 1
            results['improved']['hands_count'].append(len(improved_result["hands"]))
        else:
            results['improved']['hands_count'].append(0)

        if advanced_result["hands"]:
            results['advanced']['detected'] += 1
            results['advanced']['hands_count'].append(len(advanced_result["hands"]))
        else:
            results['advanced']['hands_count'].append(0)

        # 10フレームごとに詳細表示
        if frame_count % 10 == 0:
            print(f"{frame_count:5} | {len(standard_result['hands']):8} | "
                  f"{len(improved_result['hands']):8} | {len(advanced_result['hands']):8}")

        frame_count += 1

    cap.release()

    # 結果の分析と表示
    print("\n" + "=" * 60)
    print("DETECTION PERFORMANCE COMPARISON")
    print("=" * 60)
    print(f"Total frames processed: {frame_count}")
    print("")

    # 検出率の計算
    for name, data in results.items():
        detection_rate = (data['detected'] / frame_count) * 100 if frame_count > 0 else 0
        avg_hands = np.mean(data['hands_count']) if data['hands_count'] else 0
        max_hands = max(data['hands_count']) if data['hands_count'] else 0

        print(f"{name.capitalize()} Detector:")
        print(f"  - Detection rate: {detection_rate:.1f}% ({data['detected']}/{frame_count} frames)")
        print(f"  - Average hands per frame: {avg_hands:.2f}")
        print(f"  - Max hands detected: {max_hands}")
        print("")

    # 改善率の計算
    print("Improvement Analysis:")
    print("-" * 30)

    standard_rate = (results['standard']['detected'] / frame_count) * 100 if frame_count > 0 else 0
    improved_rate = (results['improved']['detected'] / frame_count) * 100 if frame_count > 0 else 0
    advanced_rate = (results['advanced']['detected'] / frame_count) * 100 if frame_count > 0 else 0

    if standard_rate > 0:
        improved_gain = ((improved_rate - standard_rate) / standard_rate) * 100
        advanced_gain = ((advanced_rate - standard_rate) / standard_rate) * 100

        print(f"Improved vs Standard: {improved_gain:+.1f}% improvement")
        print(f"Advanced vs Standard: {advanced_gain:+.1f}% improvement")
    else:
        print("Standard detector failed to detect any hands")
        print(f"Improved detector: {improved_rate:.1f}% detection rate")
        print(f"Advanced detector: {advanced_rate:.1f}% detection rate")

    # 特定フレームでの詳細比較
    print("\n" + "=" * 60)
    print("SAMPLE FRAME ANALYSIS (Frame 50)")
    print("=" * 60)

    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 50)
    ret, frame = cap.read()

    if ret:
        # 時間計測も含む
        start = time.time()
        standard_result = standard_detector.detect_from_frame(frame)
        standard_time = time.time() - start

        start = time.time()
        improved_result = improved_detector.detect_from_frame(frame)
        improved_time = time.time() - start

        start = time.time()
        advanced_result = advanced_detector.detect_from_frame(frame)
        advanced_time = time.time() - start

        print(f"Standard: {len(standard_result['hands'])} hands detected in {standard_time:.3f}s")
        print(f"Improved: {len(improved_result['hands'])} hands detected in {improved_time:.3f}s")
        print(f"Advanced: {len(advanced_result['hands'])} hands detected in {advanced_time:.3f}s")

        if advanced_result['hands']:
            print(f"\nAdvanced detection method: {advanced_result.get('detection_method', 'unknown')}")

    cap.release()

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)
    print("\nRecommendations:")

    # 推奨事項の表示
    if advanced_rate > improved_rate * 1.2:
        print("✓ Advanced detector shows significant improvement.")
        print("  Recommend enabling USE_ADVANCED_GLOVE_DETECTION in production.")
    elif improved_rate > standard_rate * 1.2:
        print("✓ Improved detector shows good performance.")
        print("  Current configuration should handle blue gloves well.")
    else:
        print("⚠ Detection rates are still low.")
        print("  May need further tuning or different approach.")


if __name__ == "__main__":
    test_blue_glove_detection()