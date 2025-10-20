"""手袋検出モードが正しく有効化されているか確認するスクリプト"""

import sys
sys.path.append('.')

import asyncio
from pathlib import Path
from app.services.analysis_service import AnalysisService
from app.models.video import VideoType
import cv2
import numpy as np

async def test_glove_mode_activation():
    """手袋検出モードの有効化をテスト"""

    print("=" * 60)
    print("GLOVE DETECTION MODE VERIFICATION")
    print("=" * 60)

    # テスト用のダミーフレームを作成
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dummy_frame[:, :] = [255, 100, 0]  # 青色で塗りつぶし
    frames = [dummy_frame] * 5

    # 1. AnalysisServiceインスタンスを作成
    service = AnalysisService()

    # 各ビデオタイプでテスト
    video_types_to_test = [
        (VideoType.INTERNAL, False),  # 内部カメラ -> 手袋モード無効
        (VideoType.EXTERNAL, True),   # 外部カメラ -> 手袋モード有効
        (VideoType.EXTERNAL_NO_INSTRUMENTS, True),  # 外部（器具なし） -> 手袋モード有効
        (VideoType.EXTERNAL_WITH_INSTRUMENTS, True),  # 外部（器具あり） -> 手袋モード有効
        ("external", True),  # 文字列版 -> 手袋モード有効
        ("internal", False),  # 文字列版 -> 手袋モード無効
    ]

    print("\nTesting different video types:\n")

    for video_type, expected_glove_mode in video_types_to_test:
        # サービスをリセット
        service.skeleton_detector = None
        service.video_type = video_type

        # 骨格検出を実行（これにより検出器が初期化される）
        print(f"Video type: {video_type}")

        try:
            await service._detect_skeleton_with_progress(frames[:1])  # 1フレームのみテスト

            # 検出器の設定を確認
            if service.skeleton_detector:
                detector_name = type(service.skeleton_detector).__name__

                if hasattr(service.skeleton_detector, 'enable_glove_detection'):
                    glove_enabled = service.skeleton_detector.enable_glove_detection
                elif detector_name == "GloveHandDetector":
                    glove_enabled = True
                else:
                    glove_enabled = False

                status = "✓" if glove_enabled == expected_glove_mode else "✗"
                print(f"  Detector: {detector_name}")
                print(f"  Glove mode: {glove_enabled} (expected: {expected_glove_mode}) {status}")

                if glove_enabled != expected_glove_mode:
                    print(f"  WARNING: Glove mode mismatch!")
            else:
                print(f"  ERROR: Detector not initialized")

        except Exception as e:
            print(f"  ERROR: {e}")

        print()

    # 実際の動画でテスト（あれば）
    print("\n" + "=" * 60)
    print("TESTING WITH ACTUAL VIDEO")
    print("=" * 60)

    video_paths = [
        Path("../data/uploads/Front_Angle.mp4"),
        Path("data/uploads/Front_Angle.mp4"),
    ]

    video_path = None
    for path in video_paths:
        if path.exists():
            video_path = path
            break

    if video_path:
        print(f"\nUsing video: {video_path}")

        # ビデオから最初のフレームを取得
        cap = cv2.VideoCapture(str(video_path))
        ret, frame = cap.read()
        cap.release()

        if ret:
            # 外部動画として処理
            service.skeleton_detector = None
            service.video_type = VideoType.EXTERNAL

            result = await service._detect_skeleton_with_progress([frame])

            if result and result[0]['hands']:
                print(f"SUCCESS: Detected {len(result[0]['hands'])} hands with glove mode")
            else:
                print(f"No hands detected - may need to check additional frames")

            # 設定の確認
            if service.skeleton_detector:
                print(f"\nDetector used: {type(service.skeleton_detector).__name__}")
                if hasattr(service.skeleton_detector, 'enable_glove_detection'):
                    print(f"Glove detection enabled: {service.skeleton_detector.enable_glove_detection}")
                if hasattr(service.skeleton_detector, 'min_detection_confidence'):
                    print(f"Min detection confidence: {service.skeleton_detector.min_detection_confidence}")
    else:
        print("No test video found - skipping actual video test")

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_glove_mode_activation())