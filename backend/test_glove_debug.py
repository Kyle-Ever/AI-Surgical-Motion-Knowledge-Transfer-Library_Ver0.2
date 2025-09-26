"""手袋検出デバッグテスト"""

import sys
sys.path.append('.')

import cv2
from pathlib import Path
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector

def test_glove_detection_debug():
    """手袋検出のデバッグ"""

    video_path = Path("../data/uploads/Front_Angle.mp4")
    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    print("\n" + "="*60)
    print("GLOVE DETECTION DEBUG TEST")
    print("="*60)

    # 設定パターン
    test_configs = [
        {
            "name": "Standard (no glove mode)",
            "enable_glove_detection": False,
            "min_detection_confidence": 0.5,
            "min_tracking_confidence": 0.5
        },
        {
            "name": "Glove mode enabled",
            "enable_glove_detection": True,
            "min_detection_confidence": 0.5,  # 内部で0.2に下がる
            "min_tracking_confidence": 0.5
        },
        {
            "name": "Glove mode with very low threshold",
            "enable_glove_detection": True,
            "min_detection_confidence": 0.1,
            "min_tracking_confidence": 0.1
        }
    ]

    cap = cv2.VideoCapture(str(video_path))

    for config in test_configs:
        print(f"\n### Testing: {config['name']}")

        detector = HandSkeletonDetector(
            enable_glove_detection=config["enable_glove_detection"],
            min_detection_confidence=config["min_detection_confidence"],
            min_tracking_confidence=config["min_tracking_confidence"],
            static_image_mode=False,
            max_num_hands=2
        )

        # 最初の30フレームをテスト
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        detections = []

        for i in range(30):
            ret, frame = cap.read()
            if not ret:
                break

            result = detector.detect_from_frame(frame)
            hands = result.get("hands", [])
            detections.append(len(hands))

            # 最初の検出成功フレームを報告
            if hands and len(detections) <= 5:
                print(f"  Frame {i}: {len(hands)} hand(s) detected")
                for hand in hands:
                    print(f"    - {hand.get('handedness')} (conf: {hand.get('confidence', 0):.3f})")

        # 統計
        frames_with_detection = sum(1 for d in detections if d > 0)
        total_hands = sum(detections)
        detection_rate = frames_with_detection / len(detections) * 100

        print(f"  Results:")
        print(f"    - Detection rate: {detection_rate:.1f}%")
        print(f"    - Total hands: {total_hands}")
        print(f"    - Detections per frame: {detections[:10]}")

    # 特定フレームで詳細テスト
    print("\n" + "="*60)
    print("FRAME 30 PREPROCESSING TEST")
    print("="*60)

    cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
    ret, frame = cap.read()

    if ret:
        # 標準検出
        detector_std = HandSkeletonDetector(enable_glove_detection=False)
        result_std = detector_std.detect_from_frame(frame)

        # 手袋モード検出
        detector_glove = HandSkeletonDetector(enable_glove_detection=True)
        result_glove = detector_glove.detect_from_frame(frame)

        print(f"Standard mode: {len(result_std.get('hands', []))} hands")
        print(f"Glove mode: {len(result_glove.get('hands', []))} hands")

        # 前処理された画像を保存
        if detector_glove.enable_glove_detection:
            preprocessed = detector_glove._preprocess_for_gloves(frame)
            cv2.imwrite("debug_preprocessed.jpg", preprocessed)
            cv2.imwrite("debug_original.jpg", frame)
            print("\nSaved debug images:")
            print("  - debug_original.jpg")
            print("  - debug_preprocessed.jpg")

    cap.release()
    print("\nDebug test completed!")

if __name__ == "__main__":
    test_glove_detection_debug()