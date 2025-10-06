"""
SAM2 基本動作確認テスト
SAM2Trackerの初期化と基本機能を検証
"""

import sys
sys.path.insert(0, "C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend")

import cv2
import numpy as np
from app.ai_engine.processors.sam2_tracker import SAM2Tracker

def test_sam2_initialization():
    """SAM2Trackerの初期化テスト"""
    print("=== SAM2 Initialization Test ===")

    try:
        # SAM2Tracker初期化
        tracker = SAM2Tracker(
            model_type="small",
            checkpoint_path="sam2.1_hiera_small.pt",
            config_path="configs/sam2.1/sam2.1_hiera_s.yaml",
            device="cuda"
        )

        print("[OK] SAM2Tracker initialized successfully")
        print(f"   Model type: {tracker.model_type}")
        print(f"   Device: {tracker.device}")
        print(f"   Predictor loaded: {tracker.predictor is not None}")

        return tracker

    except Exception as e:
        print(f"[FAIL] SAM2Tracker initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_sam2_with_dummy_frames():
    """ダミーフレームでの動作テスト"""
    print("\n=== SAM2 Dummy Frames Test ===")

    tracker = test_sam2_initialization()
    if tracker is None:
        return False

    try:
        # ダミーフレーム生成（640x480 RGB）
        num_frames = 10
        frames = []
        for i in range(num_frames):
            # グラデーション背景
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:, :, 0] = i * 25  # Red channel
            frame[:, :, 1] = 128     # Green channel
            frame[:, :, 2] = 255 - i * 25  # Blue channel

            # ダミー器具（白い楕円）
            center_x = 320 + i * 10
            center_y = 240
            cv2.ellipse(frame, (center_x, center_y), (50, 100), 0, 0, 360, (255, 255, 255), -1)

            frames.append(frame)

        print(f"[OK] Generated {len(frames)} dummy frames")

        # ダミー器具選択（ポイントプロンプト）
        instruments = [{
            "id": 1,
            "name": "test_instrument",
            "selection": {
                "type": "point",
                "data": [[320, 240]]  # 中心点
            },
            "color": "#00FF00"
        }]

        print(f"[OK] Created {len(instruments)} instrument selection")

        # 器具の初期化
        tracker.initialize_from_frames(frames, instruments)
        print("[OK] Instruments initialized successfully")

        # 全フレーム追跡
        results = tracker.track_all_frames()
        print(f"[OK] Tracking completed: {len(results)} frames processed")

        # 結果検証
        if results and len(results) > 0:
            first_frame = results[0]
            print(f"\n   First frame detections: {len(first_frame.get('detections', []))}")

            if first_frame.get('detections'):
                first_det = first_frame['detections'][0]
                print(f"   - Class: {first_det.get('class_name')}")
                print(f"   - BBox: {first_det.get('bbox')}")
                print(f"   - Confidence: {first_det.get('confidence')}")
                print(f"   - Tip point: {first_det.get('tip_point')}")

        return True

    except Exception as e:
        print(f"[FAIL] Dummy frames test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting SAM2 basic tests...")
    print("=" * 50)

    success = test_sam2_with_dummy_frames()

    print("=" * 50)
    if success:
        print("[OK] All tests passed!")
    else:
        print("[FAIL] Some tests failed!")

    sys.exit(0 if success else 1)
