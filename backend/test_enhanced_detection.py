"""強化版手検出のテスト"""

import sys
sys.path.append('.')

import cv2
from pathlib import Path
from app.ai_engine.processors.enhanced_hand_detector import EnhancedHandDetector
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector

def test_enhanced_detection():
    """強化版検出のテスト"""

    video_path = Path("../data/uploads/Front_Angle.mp4")
    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    # 両方のディテクターを初期化
    print("Initializing detectors...")
    enhanced_detector = EnhancedHandDetector(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.2,
        min_tracking_confidence=0.2,
        enable_preprocessing=True
    )

    standard_detector = HandSkeletonDetector(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    )

    cap = cv2.VideoCapture(str(video_path))

    frame_count = 0
    enhanced_detected = 0
    standard_detected = 0
    preprocessing_used = 0

    print("\nProcessing first 60 frames...")
    while frame_count < 60:
        ret, frame = cap.read()
        if not ret:
            break

        # 強化版検出
        enhanced_result = enhanced_detector.detect_from_frame(frame)
        if enhanced_result["hands"]:
            enhanced_detected += 1
            if enhanced_result.get("preprocessing_applied"):
                preprocessing_used += 1

        # 標準検出
        standard_result = standard_detector.detect_from_frame(frame)
        if standard_result["hands"]:
            standard_detected += 1

        frame_count += 1

        if frame_count % 10 == 0:
            print(f"Frame {frame_count}: Enhanced={len(enhanced_result['hands'])} hands, "
                  f"Standard={len(standard_result['hands'])} hands, "
                  f"Preprocessing={'Yes' if enhanced_result.get('preprocessing_applied') else 'No'}")

    print("\n" + "="*60)
    print("DETECTION COMPARISON")
    print("="*60)
    print(f"Frames processed: {frame_count}")
    print(f"Standard MediaPipe: {standard_detected}/{frame_count} frames ({standard_detected/frame_count*100:.1f}%)")
    print(f"Enhanced detection: {enhanced_detected}/{frame_count} frames ({enhanced_detected/frame_count*100:.1f}%)")
    print(f"Preprocessing used: {preprocessing_used}/{frame_count} frames ({preprocessing_used/frame_count*100:.1f}%)")

    if enhanced_detected > standard_detected:
        improvement = ((enhanced_detected - standard_detected) / max(standard_detected, 1)) * 100
        print(f"\nImprovement: +{improvement:.1f}%")

    # 特定のフレームで詳細テスト
    cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
    ret, frame = cap.read()

    if ret:
        print("\n" + "="*60)
        print("FRAME 30 DETAILED ANALYSIS")
        print("="*60)

        enhanced_result = enhanced_detector.detect_from_frame(frame)
        standard_result = standard_detector.detect_from_frame(frame)

        print(f"Standard detection: {len(standard_result['hands'])} hands")
        print(f"Enhanced detection: {len(enhanced_result['hands'])} hands")
        print(f"Preprocessing applied: {enhanced_result.get('preprocessing_applied', False)}")

        if enhanced_result["hands"]:
            for i, hand in enumerate(enhanced_result["hands"]):
                print(f"\nHand {i+1}:")
                print(f"  - Confidence: {hand.get('confidence', 0):.3f}")
                print(f"  - Handedness: {hand.get('handedness', 'Unknown')}")
                print(f"  - Preprocessing method: {hand.get('preprocessing_method', 'none')}")
                print(f"  - Landmarks: {len(hand.get('landmarks', []))} points")
                if hand.get('palm_center'):
                    print(f"  - Palm center: ({hand['palm_center']['x']:.1f}, {hand['palm_center']['y']:.1f})")
                if hand.get('finger_angles'):
                    print(f"  - Finger angles: {list(hand['finger_angles'].keys())}")

        # 結果を画像として保存
        if enhanced_result["hands"]:
            annotated = enhanced_detector.draw_landmarks(frame, enhanced_result)
            cv2.imwrite("enhanced_detection_result.jpg", annotated)
            print("\nAnnotated frame saved as enhanced_detection_result.jpg")

        # 前処理された画像も保存
        if enhanced_result.get("preprocessing_applied"):
            # 各前処理手法の結果を保存
            methods = [
                ("blue_to_skin", enhanced_detector._convert_blue_to_skin),
                ("enhance_contrast", enhanced_detector._enhance_contrast),
                ("adaptive", enhanced_detector._adaptive_preprocessing)
            ]

            for method_name, method_func in methods:
                processed = method_func(frame)
                cv2.imwrite(f"preprocessed_{method_name}.jpg", processed)
                print(f"Preprocessed image saved as preprocessed_{method_name}.jpg")

    cap.release()
    print("\nTest completed!")

if __name__ == "__main__":
    print("Testing enhanced hand detection for gloved hands...")
    test_enhanced_detection()