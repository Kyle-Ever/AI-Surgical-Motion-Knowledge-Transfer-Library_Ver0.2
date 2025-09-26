"""直接的な解析テスト"""

import asyncio
import sys
import os
sys.path.append('.')
os.environ["PYTHONPATH"] = "."

from pathlib import Path
from app.services.analysis_service import AnalysisService
from app.models.video import VideoType

async def test_direct_analysis():
    """直接解析をテスト"""

    video_path = "../data/uploads/Front_Angle.mp4"

    if not Path(video_path).exists():
        print(f"Error: Video not found at {video_path}")
        return

    print("\n" + "="*60)
    print("DIRECT ANALYSIS TEST WITH GLOVE DETECTION")
    print("="*60)

    # サービスのインスタンス化
    service = AnalysisService()
    service.analysis_id = "test-123"
    service.video_type = VideoType.EXTERNAL  # 外部カメラ = 手袋検出モード

    print("\n1. Extracting video info...")
    video_info = service._get_video_info(video_path)
    print(f"   Video: {video_info['width']}x{video_info['height']}, "
          f"{video_info['fps']} fps, {video_info['duration']:.1f} sec")

    print("\n2. Extracting frames...")
    frames = await service._extract_frames_with_progress(video_path, fps=5)
    print(f"   Extracted {len(frames)} frames")

    print("\n3. Detecting skeletons with glove mode...")
    skeleton_data = await service._detect_skeleton_with_progress(frames[:30])  # 最初の30フレーム

    # 統計を計算
    frames_with_detection = sum(1 for frame in skeleton_data if frame.get("hands"))
    total_frames = len(skeleton_data)

    print("\n" + "="*60)
    print("DETECTION RESULTS")
    print("="*60)
    print(f"Total frames: {total_frames}")
    print(f"Frames with detection: {frames_with_detection}")
    print(f"Detection rate: {frames_with_detection/total_frames*100:.1f}%")

    # フレームごとの詳細
    print("\nFirst 10 frames:")
    for frame_data in skeleton_data[:10]:
        hands = frame_data.get("hands", [])
        frame_num = frame_data.get("frame", 0)
        if hands:
            hand_info = []
            for hand in hands:
                hand_info.append(f"{hand.get('handedness', 'Unknown')}({hand.get('confidence', 0):.2f})")
            print(f"  Frame {frame_num}: {', '.join(hand_info)}")
        else:
            print(f"  Frame {frame_num}: No detection")

    # 成功したフレームの詳細
    if frames_with_detection > 0:
        print("\nSample successful detection:")
        for frame_data in skeleton_data:
            if frame_data.get("hands"):
                hand = frame_data["hands"][0]
                print(f"  Frame {frame_data['frame']}:")
                print(f"    - Handedness: {hand.get('handedness')}")
                print(f"    - Confidence: {hand.get('confidence', 0):.3f}")
                print(f"    - Landmarks: {len(hand.get('landmarks', []))} points")
                if hand.get('finger_angles'):
                    print(f"    - Finger angles detected: {list(hand['finger_angles'].keys())}")
                break

    print("\nTest completed!")

if __name__ == "__main__":
    print("Testing direct analysis with glove detection...")
    asyncio.run(test_direct_analysis())