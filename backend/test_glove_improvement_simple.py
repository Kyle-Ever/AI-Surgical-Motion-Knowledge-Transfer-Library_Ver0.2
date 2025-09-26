"""青い手袋検出の改善テスト（シンプル版）"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
import time

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector


def test_blue_glove_detection():
    """青い手袋検出の改善効果をテスト（YOLOを使わないバージョン）"""

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

    # 2つのディテクターを初期化（YOLOを使わない）
    print("\nInitializing detectors...")

    # 1. 標準版（手袋モード無効）
    print("  - Creating standard detector (no glove mode)...")
    standard_detector = HandSkeletonDetector(
        enable_glove_detection=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # 2. 改善版（手袋モード有効）
    print("  - Creating improved detector (with glove mode)...")
    improved_detector = HandSkeletonDetector(
        enable_glove_detection=True,
        min_detection_confidence=0.2,
        min_tracking_confidence=0.2
    )

    print("Detectors initialized successfully!")

    cap = cv2.VideoCapture(str(video_path))

    # 結果を記録
    results = {
        'standard': {'detected': 0, 'hands_count': [], 'times': []},
        'improved': {'detected': 0, 'hands_count': [], 'times': []}
    }

    frame_count = 0
    max_frames = 60  # 最初の60フレームでテスト

    print(f"\nProcessing first {max_frames} frames...")
    print("Frame | Standard | Improved | Time (ms)")
    print("-" * 50)

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        # 標準版でテスト
        start = time.time()
        standard_result = standard_detector.detect_from_frame(frame)
        standard_time = (time.time() - start) * 1000

        # 改善版でテスト
        start = time.time()
        improved_result = improved_detector.detect_from_frame(frame)
        improved_time = (time.time() - start) * 1000

        # 結果を記録
        if standard_result["hands"]:
            results['standard']['detected'] += 1
            results['standard']['hands_count'].append(len(standard_result["hands"]))
        else:
            results['standard']['hands_count'].append(0)
        results['standard']['times'].append(standard_time)

        if improved_result["hands"]:
            results['improved']['detected'] += 1
            results['improved']['hands_count'].append(len(improved_result["hands"]))
        else:
            results['improved']['hands_count'].append(0)
        results['improved']['times'].append(improved_time)

        # 10フレームごとに詳細表示
        if frame_count % 10 == 0:
            print(f"{frame_count:5} | {len(standard_result['hands']):8} | "
                  f"{len(improved_result['hands']):8} | "
                  f"S:{standard_time:6.1f} I:{improved_time:6.1f}")

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
        avg_time = np.mean(data['times']) if data['times'] else 0

        print(f"{name.capitalize()} Detector:")
        print(f"  - Detection rate: {detection_rate:.1f}% ({data['detected']}/{frame_count} frames)")
        print(f"  - Average hands per frame: {avg_hands:.2f}")
        print(f"  - Max hands detected: {max_hands}")
        print(f"  - Average processing time: {avg_time:.1f}ms")
        print("")

    # 改善率の計算
    print("Improvement Analysis:")
    print("-" * 30)

    standard_rate = (results['standard']['detected'] / frame_count) * 100 if frame_count > 0 else 0
    improved_rate = (results['improved']['detected'] / frame_count) * 100 if frame_count > 0 else 0

    if standard_rate > 0:
        improvement = ((improved_rate - standard_rate) / standard_rate) * 100
        print(f"Detection rate improvement: {improvement:+.1f}%")
        print(f"  - Standard: {standard_rate:.1f}%")
        print(f"  - Improved: {improved_rate:.1f}%")
    else:
        print("Standard detector failed to detect any hands")
        print(f"Improved detector: {improved_rate:.1f}% detection rate")

    avg_hands_standard = np.mean(results['standard']['hands_count'])
    avg_hands_improved = np.mean(results['improved']['hands_count'])
    if avg_hands_standard > 0:
        hands_improvement = ((avg_hands_improved - avg_hands_standard) / avg_hands_standard) * 100
        print(f"\nAverage hands detected improvement: {hands_improvement:+.1f}%")
        print(f"  - Standard: {avg_hands_standard:.2f} hands/frame")
        print(f"  - Improved: {avg_hands_improved:.2f} hands/frame")

    # 処理時間の比較
    avg_time_standard = np.mean(results['standard']['times'])
    avg_time_improved = np.mean(results['improved']['times'])
    time_overhead = ((avg_time_improved - avg_time_standard) / avg_time_standard) * 100
    print(f"\nProcessing time overhead: {time_overhead:+.1f}%")
    print(f"  - Standard: {avg_time_standard:.1f}ms")
    print(f"  - Improved: {avg_time_improved:.1f}ms")

    # 特定フレームでの詳細比較
    print("\n" + "=" * 60)
    print("SAMPLE FRAME ANALYSIS (Frame 30)")
    print("=" * 60)

    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
    ret, frame = cap.read()

    if ret:
        # フレーム30で詳細テスト
        standard_result = standard_detector.detect_from_frame(frame)
        improved_result = improved_detector.detect_from_frame(frame)

        print(f"Standard detector: {len(standard_result['hands'])} hands detected")
        if standard_result['hands']:
            for i, hand in enumerate(standard_result['hands']):
                print(f"  Hand {i}: {hand['handedness']} (confidence: {hand['confidence']:.2f})")

        print(f"\nImproved detector: {len(improved_result['hands'])} hands detected")
        if improved_result['hands']:
            for i, hand in enumerate(improved_result['hands']):
                print(f"  Hand {i}: {hand['handedness']} (confidence: {hand['confidence']:.2f})")

        # 可視化（オプション）
        if improved_result['hands']:
            # 検出結果を描画
            vis_frame = frame.copy()
            for hand in improved_result['hands']:
                # バウンディングボックスを描画
                bbox = hand['bbox']
                cv2.rectangle(vis_frame,
                            (int(bbox['x_min']), int(bbox['y_min'])),
                            (int(bbox['x_max']), int(bbox['y_max'])),
                            (0, 255, 0), 2)

                # ラベルを追加
                label = f"{hand['handedness']} ({hand['confidence']:.2f})"
                cv2.putText(vis_frame, label,
                          (int(bbox['x_min']), int(bbox['y_min']) - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # 結果を保存
            output_path = "glove_detection_result.jpg"
            cv2.imwrite(output_path, vis_frame)
            print(f"\nVisualization saved to: {output_path}")

    cap.release()

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)
    print("\nRecommendations:")

    # 推奨事項の表示
    if improved_rate > standard_rate * 1.5:
        print("✅ Improved detector shows significant enhancement!")
        print("   The glove detection mode is working effectively.")
    elif improved_rate > standard_rate * 1.2:
        print("✓ Improved detector shows good performance.")
        print("   Glove detection mode provides moderate improvement.")
    elif improved_rate > standard_rate:
        print("📊 Improved detector shows slight improvement.")
        print("   Consider enabling advanced detection for better results.")
    else:
        print("⚠ No significant improvement detected.")
        print("  The video may not contain blue gloves, or further tuning needed.")

    # 処理時間について
    if time_overhead < 50:
        print("\n⚡ Processing overhead is acceptable.")
    else:
        print("\n⚠ Processing overhead is significant.")
        print("  Consider using it only when necessary.")


if __name__ == "__main__":
    test_blue_glove_detection()