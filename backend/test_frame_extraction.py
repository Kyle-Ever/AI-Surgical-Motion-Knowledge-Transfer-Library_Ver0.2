"""
フレーム抽出機能のテストスクリプト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ai_engine.processors.frame_extractor import FrameExtractor, get_video_info
import glob

def test_frame_extraction():
    """フレーム抽出機能をテスト"""

    # テスト用動画を探す
    video_files = glob.glob("data/uploads/*.mp4")

    if not video_files:
        print("[ERROR] No test videos found in data/uploads/")
        return False

    test_video = video_files[0]
    print(f"[OK] Found test video: {test_video}")

    try:
        # 動画情報取得テスト
        print("\n1. Testing get_video_info()...")
        info = get_video_info(test_video)
        print(f"   Video Info: {info}")

        # フレーム抽出テスト
        print("\n2. Testing frame extraction...")
        with FrameExtractor(test_video, target_fps=5) as extractor:
            # 最初の10フレームを抽出
            frames = []
            for i, (frame_num, frame) in enumerate(extractor.extract_frames_generator()):
                frames.append((frame_num, frame))
                if i >= 9:  # 10フレーム取得したら終了
                    break

            print(f"   [OK] Extracted {len(frames)} frames")
            print(f"   Frame numbers: {[f[0] for f in frames]}")
            print(f"   Frame shapes: {[f[1].shape for f in frames[:3]]}")

        # キーフレーム抽出テスト
        print("\n3. Testing keyframe extraction...")
        with FrameExtractor(test_video) as extractor:
            keyframes = extractor.extract_keyframes(interval_seconds=2.0)
            print(f"   [OK] Extracted {len(keyframes)} keyframes")
            print(f"   Timestamps: {[f[0] for f in keyframes[:5]]}")

        print("\n[SUCCESS] All frame extraction tests passed!")
        return True

    except Exception as e:
        print(f"\n[ERROR] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_frame_extraction()
    sys.exit(0 if success else 1)