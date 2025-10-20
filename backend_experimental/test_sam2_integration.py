"""
SAM2統合テスト - JPEG一時保存方式の検証
"""
import sys
import os
import logging
import numpy as np
import cv2
from pathlib import Path

# プロジェクトルートをPYTHONPATHに追加
sys.path.insert(0, str(Path(__file__).parent))

from app.ai_engine.processors.sam2_tracker import SAM2Tracker
from app.utils.temp_frame_storage import TemporaryFrameStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_temporary_frame_storage():
    """一時フレームストレージのテスト"""
    print("\n" + "="*70)
    print("TEST 1: TemporaryFrameStorage")
    print("="*70)

    # ダミーフレームを作成
    frames = []
    for i in range(10):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        frames.append(frame)

    analysis_id = "test_sam2_001"
    storage = TemporaryFrameStorage(analysis_id)

    try:
        # JPEG保存
        print(f"\n[1/3] Saving {len(frames)} frames as JPEG...")
        jpeg_dir = storage.save_frames(frames, quality=95, parallel=True)
        print(f"[OK] JPEG folder created: {jpeg_dir}")

        # フレーム数確認
        frame_count = storage.get_frame_count()
        print(f"[OK] Frame count: {frame_count}")
        assert frame_count == len(frames), f"Frame count mismatch: {frame_count} != {len(frames)}"

        # サイズ確認
        total_size_mb = storage.get_total_size_mb()
        print(f"[OK] Total size: {total_size_mb:.2f} MB")

        # クリーンアップ
        print(f"\n[2/3] Cleaning up temporary files...")
        success = storage.cleanup()
        assert success, "Cleanup failed"
        print(f"[OK] Cleanup completed")

        # 削除確認
        print(f"\n[3/3] Verifying deletion...")
        assert not jpeg_dir.exists(), f"Directory still exists: {jpeg_dir}"
        print(f"[OK] Directory deleted successfully")

        print("\n" + "="*70)
        print("TEST 1 PASSED: TemporaryFrameStorage works correctly")
        print("="*70)

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        storage.cleanup(ignore_errors=True)
        raise


def test_sam2_basic_initialization():
    """SAM2Trackerの基本初期化テスト"""
    print("\n" + "="*70)
    print("TEST 2: SAM2Tracker Basic Initialization")
    print("="*70)

    try:
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"\n[1/2] Initializing SAM2Tracker (device={device})...")

        tracker = SAM2Tracker(model_type="small", device=device)
        print(f"[OK] SAM2Tracker initialized")
        print(f"     Model: sam2.1_hiera_small")
        print(f"     Device: {tracker.device}")

        print(f"\n[2/2] Verifying model files...")
        model_path = Path("sam2.1_hiera_small.pt")
        config_path = Path("configs/sam2.1/sam2.1_hiera_s.yaml")

        assert model_path.exists(), f"Model file not found: {model_path}"
        assert config_path.exists(), f"Config file not found: {config_path}"

        print(f"[OK] Model file: {model_path} ({model_path.stat().st_size / 1024 / 1024:.1f} MB)")
        print(f"[OK] Config file: {config_path}")

        print("\n" + "="*70)
        print("TEST 2 PASSED: SAM2Tracker initialized successfully")
        print("="*70)

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise


def test_sam2_detect_batch():
    """SAM2Tracker.detect_batch()のテスト"""
    print("\n" + "="*70)
    print("TEST 3: SAM2Tracker detect_batch()")
    print("="*70)

    try:
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # SAM2Tracker初期化
        print(f"\n[1/4] Initializing SAM2Tracker...")
        tracker = SAM2Tracker(model_type="small", device=device)
        print(f"[OK] Initialized")

        # ダミーフレームとinstruments作成
        print(f"\n[2/4] Creating dummy frames and instruments...")
        frames = []
        for i in range(5):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            # 赤い矩形を描画（検出対象）
            cv2.rectangle(frame, (100, 100), (200, 200), (0, 0, 255), -1)
            frames.append(frame)

        instruments = [
            {"bbox": [100, 100, 200, 200]}  # 赤い矩形の位置
        ]
        print(f"[OK] Created {len(frames)} frames, {len(instruments)} instruments")

        # detect_batch実行
        print(f"\n[3/4] Running detect_batch()...")
        results = tracker.detect_batch(frames, instruments)
        print(f"[OK] detect_batch completed")

        # 結果検証
        print(f"\n[4/4] Verifying results...")
        assert "instrument_data" in results, "Missing 'instrument_data' key"
        instrument_data = results["instrument_data"]
        assert len(instrument_data) == len(frames), f"Frame count mismatch: {len(instrument_data)} != {len(frames)}"

        # 最初のフレームを確認
        first_frame = instrument_data[0]
        assert "frame_number" in first_frame, "Missing 'frame_number'"
        assert "detections" in first_frame, "Missing 'detections'"

        print(f"[OK] Results structure is valid")
        print(f"     Frames: {len(instrument_data)}")
        print(f"     First frame detections: {len(first_frame['detections'])}")

        # 一時フォルダが削除されたか確認
        temp_base = Path("temp_frames")
        if temp_base.exists():
            remaining = list(temp_base.iterdir())
            if len(remaining) > 0:
                print(f"[WARNING] Temporary folders not cleaned up: {remaining}")
            else:
                print(f"[OK] Temporary folders cleaned up")
        else:
            print(f"[OK] Temporary base directory does not exist")

        print("\n" + "="*70)
        print("TEST 3 PASSED: detect_batch works correctly")
        print("="*70)

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """全テストを実行"""
    print("\n" + "="*70)
    print("SAM2 Integration Test Suite")
    print("="*70)

    try:
        # Test 1: TemporaryFrameStorage
        test_temporary_frame_storage()

        # Test 2: SAM2Tracker basic initialization
        test_sam2_basic_initialization()

        # Test 3: SAM2Tracker.detect_batch()
        test_sam2_detect_batch()

        print("\n" + "="*70)
        print("ALL TESTS PASSED")
        print("="*70)
        print("\nNext steps:")
        print("1. Set USE_SAM2=true in backend/.env to enable SAM2")
        print("2. Restart backend: restart_backend.bat")
        print("3. Run actual video analysis test")
        print("="*70)

    except Exception as e:
        print("\n" + "="*70)
        print("TEST SUITE FAILED")
        print("="*70)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
