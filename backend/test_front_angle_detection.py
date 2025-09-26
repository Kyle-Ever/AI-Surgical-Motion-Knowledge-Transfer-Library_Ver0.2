"""Front_Angle.mp4での手検出テスト"""

import cv2
import mediapipe as mp
import numpy as np
from pathlib import Path

def test_detection_with_different_settings():
    """異なる設定で検出をテスト"""

    video_path = Path("../data/uploads/Front_Angle.mp4")
    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    cap = cv2.VideoCapture(str(video_path))

    # 複数の設定パターンをテスト
    test_configs = [
        {
            "name": "Default (0.5/0.5)",
            "static_image_mode": False,
            "max_num_hands": 2,
            "min_detection_confidence": 0.5,
            "min_tracking_confidence": 0.5
        },
        {
            "name": "Low Threshold (0.3/0.3)",
            "static_image_mode": False,
            "max_num_hands": 2,
            "min_detection_confidence": 0.3,
            "min_tracking_confidence": 0.3
        },
        {
            "name": "Very Low Threshold (0.1/0.1)",
            "static_image_mode": False,
            "max_num_hands": 2,
            "min_detection_confidence": 0.1,
            "min_tracking_confidence": 0.1
        },
        {
            "name": "Static Mode High (0.7/0.7)",
            "static_image_mode": True,
            "max_num_hands": 2,
            "min_detection_confidence": 0.7,
            "min_tracking_confidence": 0.7
        },
        {
            "name": "Static Mode Low (0.2/0.2)",
            "static_image_mode": True,
            "max_num_hands": 2,
            "min_detection_confidence": 0.2,
            "min_tracking_confidence": 0.2
        }
    ]

    # 各フレームの結果を保存
    results_by_config = {}

    for config in test_configs:
        print(f"\nTesting: {config['name']}")
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 最初に戻す

        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            static_image_mode=config["static_image_mode"],
            max_num_hands=config["max_num_hands"],
            min_detection_confidence=config["min_detection_confidence"],
            min_tracking_confidence=config["min_tracking_confidence"]
        )

        frame_results = []
        frame_count = 0
        detected_count = 0

        # 最初の60フレームをテスト
        while frame_count < 60:
            ret, frame = cap.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                num_hands = len(results.multi_hand_landmarks)
                detected_count += 1
                frame_results.append({
                    "frame": frame_count,
                    "hands_detected": num_hands,
                    "confidences": [h.classification[0].score for h in results.multi_handedness]
                })
            else:
                frame_results.append({
                    "frame": frame_count,
                    "hands_detected": 0,
                    "confidences": []
                })

            frame_count += 1

        hands.close()

        # 統計を計算
        total_hands = sum(r["hands_detected"] for r in frame_results)
        avg_confidence = np.mean([c for r in frame_results for c in r["confidences"]]) if total_hands > 0 else 0

        results_by_config[config["name"]] = {
            "frames_with_detection": detected_count,
            "total_frames": frame_count,
            "detection_rate": detected_count / frame_count * 100,
            "total_hands_detected": total_hands,
            "avg_confidence": avg_confidence,
            "details": frame_results[:10]  # 最初の10フレームの詳細
        }

    # 結果を表示
    print("\n" + "="*60)
    print("DETECTION RESULTS SUMMARY")
    print("="*60)

    for config_name, results in results_by_config.items():
        print(f"\n{config_name}:")
        print(f"  Detection rate: {results['detection_rate']:.1f}% ({results['frames_with_detection']}/{results['total_frames']} frames)")
        print(f"  Total hands: {results['total_hands_detected']}")
        print(f"  Avg confidence: {results['avg_confidence']:.3f}")
        print(f"  First 10 frames: {[d['hands_detected'] for d in results['details']]}")

    # 最良の設定を特定
    best_config = max(results_by_config.items(), key=lambda x: x[1]["detection_rate"])
    print(f"\nBest configuration: {best_config[0]}")
    print(f"   Detection rate: {best_config[1]['detection_rate']:.1f}%")

    cap.release()

    # 単一フレームでの詳細分析
    print("\n" + "="*60)
    print("SINGLE FRAME DETAILED ANALYSIS")
    print("="*60)

    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 30)  # 30フレーム目
    ret, frame = cap.read()

    if ret:
        # フレームを保存して視覚的に確認
        cv2.imwrite("test_frame_original.jpg", frame)
        print(f"\nOriginal frame saved as test_frame_original.jpg")

        # 前処理のバリエーションをテスト
        preprocessing_tests = [
            ("Original", frame),
            ("Histogram Equalization", apply_histogram_equalization(frame)),
            ("CLAHE", apply_clahe(frame)),
            ("Brightness +30", adjust_brightness(frame, 30)),
            ("Brightness -30", adjust_brightness(frame, -30)),
            ("Contrast 1.5", adjust_contrast(frame, 1.5))
        ]

        mp_hands = mp.solutions.hands
        mp_drawing = mp.solutions.drawing_utils

        for prep_name, processed_frame in preprocessing_tests:
            hands = mp_hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=0.2,
                min_tracking_confidence=0.2
            )

            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                annotated = processed_frame.copy()
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        annotated, hand_landmarks, mp_hands.HAND_CONNECTIONS
                    )
                cv2.imwrite(f"test_frame_{prep_name.replace(' ', '_').lower()}_detected.jpg", annotated)
                print(f"  {prep_name}: [OK] Detected {len(results.multi_hand_landmarks)} hand(s)")
            else:
                print(f"  {prep_name}: [FAIL] No hands detected")

            hands.close()

    cap.release()

def apply_histogram_equalization(image):
    """ヒストグラム平坦化"""
    yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)
    yuv[:,:,0] = cv2.equalizeHist(yuv[:,:,0])
    return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

def apply_clahe(image):
    """CLAHE (Contrast Limited Adaptive Histogram Equalization)"""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    lab[:,:,0] = clahe.apply(lab[:,:,0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

def adjust_brightness(image, value):
    """明度調整"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:,:,2] = np.clip(hsv[:,:,2] + value, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

def adjust_contrast(image, factor):
    """コントラスト調整"""
    return cv2.convertScaleAbs(image, alpha=factor, beta=0)

if __name__ == "__main__":
    print("Testing hand detection on Front_Angle.mp4...")
    test_detection_with_different_settings()