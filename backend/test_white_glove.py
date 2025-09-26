"""白い手袋検出のテスト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector

def create_test_image_with_white_gloves():
    """白い手袋のテスト画像を作成（シミュレーション）"""

    # 480x640のテスト画像を作成
    img = np.ones((480, 640, 3), dtype=np.uint8) * 128  # グレーの背景

    # 白い手袋をシミュレート（左手）
    cv2.ellipse(img, (200, 240), (80, 120), 15, 0, 360, (250, 250, 250), -1)
    # 指のシミュレーション
    for i in range(5):
        angle = -30 + i * 15
        end_x = int(200 + 100 * np.cos(np.radians(angle)))
        end_y = int(240 - 100 * np.sin(np.radians(angle)))
        cv2.line(img, (200, 240), (end_x, end_y), (245, 245, 245), 15)

    # 白い手袋をシミュレート（右手）
    cv2.ellipse(img, (440, 240), (80, 120), -15, 0, 360, (240, 240, 240), -1)
    # 指のシミュレーション
    for i in range(5):
        angle = 180 + 30 - i * 15
        end_x = int(440 + 100 * np.cos(np.radians(angle)))
        end_y = int(240 - 100 * np.sin(np.radians(angle)))
        cv2.line(img, (440, 240), (end_x, end_y), (235, 235, 235), 15)

    return img

def test_white_glove_detection():
    """白い手袋検出のテスト"""

    print("\n" + "="*60)
    print("WHITE GLOVE DETECTION TEST")
    print("="*60)

    # テスト画像を作成
    test_image = create_test_image_with_white_gloves()
    cv2.imwrite("test_white_gloves_original.jpg", test_image)
    print("\n1. Created test image with white gloves: test_white_gloves_original.jpg")

    # 設定パターン
    test_configs = [
        {
            "name": "Standard (no glove mode)",
            "enable_glove_detection": False,
            "min_detection_confidence": 0.3
        },
        {
            "name": "Glove mode enabled",
            "enable_glove_detection": True,
            "min_detection_confidence": 0.3
        }
    ]

    for config in test_configs:
        print(f"\n2. Testing: {config['name']}")

        detector = HandSkeletonDetector(
            enable_glove_detection=config["enable_glove_detection"],
            min_detection_confidence=config["min_detection_confidence"],
            min_tracking_confidence=config["min_detection_confidence"],
            static_image_mode=True,
            max_num_hands=2
        )

        # 検出実行
        result = detector.detect_from_frame(test_image)
        hands = result.get("hands", [])

        print(f"   - Detected {len(hands)} hand(s)")
        for i, hand in enumerate(hands):
            print(f"     Hand {i+1}: {hand.get('handedness')} (conf: {hand.get('confidence', 0):.3f})")

        # 前処理された画像を保存
        if config["enable_glove_detection"]:
            preprocessed = detector._preprocess_for_gloves(test_image)
            cv2.imwrite("test_white_gloves_preprocessed.jpg", preprocessed)
            print(f"   - Saved preprocessed image: test_white_gloves_preprocessed.jpg")

    # 実際の動画でのテスト（Front_Angle.mp4の特定フレーム）
    print("\n3. Testing with real video frame...")
    video_path = Path("../data/uploads/Front_Angle.mp4")

    if video_path.exists():
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
        ret, frame = cap.read()

        if ret:
            detector_with_glove = HandSkeletonDetector(
                enable_glove_detection=True,
                min_detection_confidence=0.2,
                min_tracking_confidence=0.2,
                static_image_mode=True,
                max_num_hands=2
            )

            result = detector_with_glove.detect_from_frame(frame)
            hands = result.get("hands", [])

            print(f"   Real video frame: {len(hands)} hand(s) detected")

            # 前処理前後の色分析
            preprocessed = detector_with_glove._preprocess_for_gloves(frame)

            # HSV分析
            hsv_orig = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hsv_proc = cv2.cvtColor(preprocessed, cv2.COLOR_BGR2HSV)

            print("\n4. Color analysis:")
            print("   Original frame HSV ranges:")
            print(f"     H: {hsv_orig[:,:,0].min()}-{hsv_orig[:,:,0].max()}")
            print(f"     S: {hsv_orig[:,:,1].min()}-{hsv_orig[:,:,1].max()}")
            print(f"     V: {hsv_orig[:,:,2].min()}-{hsv_orig[:,:,2].max()}")

            print("   Preprocessed frame HSV ranges:")
            print(f"     H: {hsv_proc[:,:,0].min()}-{hsv_proc[:,:,0].max()}")
            print(f"     S: {hsv_proc[:,:,1].min()}-{hsv_proc[:,:,1].max()}")
            print(f"     V: {hsv_proc[:,:,2].min()}-{hsv_proc[:,:,2].max()}")

        cap.release()
    else:
        print("   Video file not found")

    print("\nTest completed!")

if __name__ == "__main__":
    print("Testing white glove detection...")
    test_white_glove_detection()