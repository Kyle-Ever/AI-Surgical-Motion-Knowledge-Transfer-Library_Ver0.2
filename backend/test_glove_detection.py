"""手袋検出テスト"""

import sys
sys.path.append('.')

import cv2
from pathlib import Path
from app.ai_engine.processors.glove_hand_detector import GloveHandDetector
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector

def test_glove_detection():
    """手袋検出のテスト"""

    video_path = Path("../data/uploads/Front_Angle.mp4")
    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    # 両方のディテクターを初期化
    print("Initializing detectors...")
    glove_detector = GloveHandDetector(use_color_enhancement=True)
    standard_detector = HandSkeletonDetector(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    )

    cap = cv2.VideoCapture(str(video_path))

    frame_count = 0
    glove_detected = 0
    standard_detected = 0

    print("\nProcessing first 60 frames...")
    while frame_count < 60:
        ret, frame = cap.read()
        if not ret:
            break

        # 手袋対応検出
        glove_result = glove_detector.detect_from_frame(frame)
        if glove_result["hands"]:
            glove_detected += 1

        # 標準検出
        standard_result = standard_detector.detect_from_frame(frame)
        if standard_result["hands"]:
            standard_detected += 1

        frame_count += 1

        if frame_count % 10 == 0:
            print(f"Frame {frame_count}: Glove={len(glove_result['hands'])} hands, "
                  f"Standard={len(standard_result['hands'])} hands, "
                  f"Method={glove_result.get('detection_method', 'none')}")

    print("\n" + "="*60)
    print("DETECTION COMPARISON")
    print("="*60)
    print(f"Frames processed: {frame_count}")
    print(f"Standard MediaPipe detection: {standard_detected}/{frame_count} frames ({standard_detected/frame_count*100:.1f}%)")
    print(f"Glove-aware detection: {glove_detected}/{frame_count} frames ({glove_detected/frame_count*100:.1f}%)")

    if glove_detected > standard_detected:
        improvement = ((glove_detected - standard_detected) / max(standard_detected, 1)) * 100
        print(f"\nImprovement: +{improvement:.1f}%")

    # 特定のフレームで詳細テスト
    cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
    ret, frame = cap.read()

    if ret:
        print("\n" + "="*60)
        print("FRAME 30 DETAILED ANALYSIS")
        print("="*60)

        glove_result = glove_detector.detect_from_frame(frame)
        standard_result = standard_detector.detect_from_frame(frame)

        print(f"Standard detection: {len(standard_result['hands'])} hands")
        print(f"Glove detection: {len(glove_result['hands'])} hands")
        print(f"Detection method: {glove_result.get('detection_method', 'none')}")

        if glove_result["hands"]:
            for i, hand in enumerate(glove_result["hands"]):
                print(f"\nHand {i+1}:")
                print(f"  - Method: {hand.get('detection_method', 'unknown')}")
                print(f"  - Confidence: {hand.get('confidence', 0):.3f}")
                print(f"  - Handedness: {hand.get('handedness', 'Unknown')}")
                print(f"  - Landmarks: {len(hand.get('landmarks', []))} points")
                if hand.get('palm_center'):
                    print(f"  - Palm center: ({hand['palm_center']['x']:.1f}, {hand['palm_center']['y']:.1f})")

        # 結果を画像として保存
        if glove_result["hands"]:
            annotated = frame.copy()
            for hand in glove_result["hands"]:
                if hand.get("bbox"):
                    bbox = hand["bbox"]
                    cv2.rectangle(annotated,
                                (int(bbox["x_min"]), int(bbox["y_min"])),
                                (int(bbox["x_max"]), int(bbox["y_max"])),
                                (0, 255, 0), 2)

                    label = f"{hand.get('detection_method', 'unknown')} ({hand.get('confidence', 0):.2f})"
                    cv2.putText(annotated, label,
                              (int(bbox["x_min"]), int(bbox["y_min"]) - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                if hand.get("landmarks"):
                    for landmark in hand["landmarks"]:
                        x = int(landmark["x"])
                        y = int(landmark["y"])
                        cv2.circle(annotated, (x, y), 3, (255, 0, 0), -1)

            cv2.imwrite("glove_detection_result.jpg", annotated)
            print("\nAnnotated frame saved as glove_detection_result.jpg")

    cap.release()
    print("\nTest completed!")

if __name__ == "__main__":
    print("Testing glove hand detection...")
    test_glove_detection()