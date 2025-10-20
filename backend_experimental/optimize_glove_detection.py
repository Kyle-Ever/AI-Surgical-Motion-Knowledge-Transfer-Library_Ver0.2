"""青い手袋検出の最適化設定を見つけるスクリプト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector


def test_different_settings(video_path: Path):
    """異なる設定で検出率を比較"""

    print("Testing different detection settings for optimal blue glove detection...")
    print("=" * 70)

    cap = cv2.VideoCapture(str(video_path))

    # テスト用フレームを取得（30フレームごと）
    test_frames = []
    for i in range(0, 180, 30):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            test_frames.append((i, frame))

    cap.release()

    # 異なる設定のテスト
    test_configs = [
        {
            'name': 'Current (0.2 confidence)',
            'min_detection_confidence': 0.2,
            'min_tracking_confidence': 0.2,
            'static_image_mode': False
        },
        {
            'name': 'Lower threshold (0.1)',
            'min_detection_confidence': 0.1,
            'min_tracking_confidence': 0.1,
            'static_image_mode': False
        },
        {
            'name': 'Static mode + Low threshold',
            'min_detection_confidence': 0.1,
            'min_tracking_confidence': 0.1,
            'static_image_mode': True  # 各フレーム独立処理
        },
        {
            'name': 'Very low threshold (0.05)',
            'min_detection_confidence': 0.05,
            'min_tracking_confidence': 0.05,
            'static_image_mode': False
        },
        {
            'name': 'Static mode + Standard',
            'min_detection_confidence': 0.2,
            'min_tracking_confidence': 0.2,
            'static_image_mode': True
        }
    ]

    results = []

    for config in test_configs:
        print(f"\nTesting: {config['name']}")
        print("-" * 40)

        detector = HandSkeletonDetector(
            enable_glove_detection=True,
            min_detection_confidence=config['min_detection_confidence'],
            min_tracking_confidence=config['min_tracking_confidence'],
            static_image_mode=config['static_image_mode'],
            max_num_hands=2
        )

        total_detected = 0
        total_hands = 0
        confidence_sum = 0

        for frame_idx, frame in test_frames:
            result = detector.detect_from_frame(frame)
            hands = result.get("hands", [])

            if hands:
                total_detected += 1
                total_hands += len(hands)
                confidence_sum += sum(h['confidence'] for h in hands)
                print(f"  Frame {frame_idx}: {len(hands)} hands detected")
            else:
                print(f"  Frame {frame_idx}: No detection")

        detection_rate = (total_detected / len(test_frames)) * 100
        avg_confidence = confidence_sum / total_hands if total_hands > 0 else 0

        results.append({
            'config': config['name'],
            'detection_rate': detection_rate,
            'total_hands': total_hands,
            'avg_confidence': avg_confidence
        })

        print(f"  Detection rate: {detection_rate:.1f}%")
        print(f"  Total hands: {total_hands}")
        print(f"  Avg confidence: {avg_confidence:.3f}")

        # クリーンアップ
        del detector

    # 結果の比較
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)
    print(f"{'Configuration':<30} {'Detection%':>12} {'Hands':>8} {'Confidence':>12}")
    print("-" * 70)

    for r in results:
        print(f"{r['config']:<30} {r['detection_rate']:>11.1f}% {r['total_hands']:>8} {r['avg_confidence']:>12.3f}")

    # 最適な設定を特定
    best = max(results, key=lambda x: x['detection_rate'])
    print(f"\nBEST CONFIGURATION: {best['config']}")
    print(f"  Detection rate: {best['detection_rate']:.1f}%")

    return best


def test_preprocessing_variations(video_path: Path):
    """前処理のバリエーションをテスト"""

    print("\n" + "=" * 70)
    print("TESTING PREPROCESSING VARIATIONS")
    print("=" * 70)

    cap = cv2.VideoCapture(str(video_path))

    # テストフレーム取得
    cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Failed to read frame")
        return

    # 前処理のバリエーション
    def preprocess_v1(img):
        """現在の前処理"""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([70, 20, 20])
        upper_blue = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        result = img.copy()
        if np.any(mask > 0):
            result[mask > 0] = [180, 150, 120]
        return result

    def preprocess_v2(img):
        """より広い青色範囲"""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([60, 10, 10])  # さらに広い
        upper_blue = np.array([150, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        result = img.copy()
        if np.any(mask > 0):
            # より自然な肌色変換
            result[mask > 0] = [200, 170, 140]
        return result

    def preprocess_v3(img):
        """適応的変換"""
        # 青色領域の明度を保持しながら変換
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        # 青色範囲のマスク
        blue_mask = (h >= 60) & (h <= 150)

        # 色相を肌色に変換（20度前後）
        h[blue_mask] = 20
        # 彩度を下げる
        s[blue_mask] = s[blue_mask] * 0.5

        hsv_modified = cv2.merge([h, s, v])
        return cv2.cvtColor(hsv_modified, cv2.COLOR_HSV2BGR)

    preprocessors = [
        ('Current method', preprocess_v1),
        ('Wider blue range', preprocess_v2),
        ('Adaptive conversion', preprocess_v3)
    ]

    detector = HandSkeletonDetector(
        enable_glove_detection=False,  # 前処理のみテスト
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3,
        max_num_hands=2
    )

    print("\nTesting on frame 30:")
    print("-" * 40)

    for name, preprocess_func in preprocessors:
        processed_frame = preprocess_func(frame)
        result = detector.detect_from_frame(processed_frame)
        hands = result.get("hands", [])

        print(f"{name:20}: {len(hands)} hands detected")
        if hands:
            for i, hand in enumerate(hands):
                print(f"  Hand {i+1}: {hand['handedness']} (conf: {hand['confidence']:.3f})")

        # 処理後の画像を保存（最初のもののみ）
        if name == 'Adaptive conversion':
            cv2.imwrite(f'preprocessed_{name.replace(" ", "_")}.jpg', processed_frame)

    print("\nPreprocessed images saved for inspection")


if __name__ == "__main__":
    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")

    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
    else:
        # 1. 最適な検出設定を見つける
        best_config = test_different_settings(video_path)

        # 2. 前処理のバリエーションをテスト
        test_preprocessing_variations(video_path)