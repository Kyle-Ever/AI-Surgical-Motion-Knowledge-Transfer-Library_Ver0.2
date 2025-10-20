"""
Video Integrity Verification Tool

動画ファイルの読み込み整合性をテストし、どのフレームで読み込みが失敗するかを診断

使用方法:
    python tools/verify_video_integrity.py <video_path>
"""

import sys
import cv2
from pathlib import Path
from typing import List, Tuple, Dict
import argparse


def get_video_metadata(video_path: str) -> Dict:
    """動画のメタデータを取得"""
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    metadata = {
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        'fps': cap.get(cv2.CAP_PROP_FPS),
        'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'fourcc': int(cap.get(cv2.CAP_PROP_FOURCC)),
        'codec': '',
        'bitrate': int(cap.get(cv2.CAP_PROP_BITRATE))
    }

    # FourCCをデコード
    fourcc = metadata['fourcc']
    metadata['codec'] = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])

    cap.release()
    return metadata


def test_frame_reading(video_path: str, test_indices: List[int] = None) -> Tuple[bool, List[int], List[int]]:
    """
    指定したフレーム番号の読み込みをテスト

    Returns:
        (success: bool, failed_indices: List[int], succeeded_indices: List[int])
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # デフォルトのテストポイント
    if test_indices is None:
        test_indices = [
            0,  # 最初
            50, 100, 110, 111, 112, 113, 114, 115, 120, 150,  # 問題発生範囲
            200, 300, 400, 500,  # 中間
            total_frames - 1  # 最後
        ]

    failed_indices = []
    succeeded_indices = []

    for frame_idx in test_indices:
        if frame_idx >= total_frames:
            print(f"⚠️  Frame {frame_idx} exceeds total frames ({total_frames}), skipping")
            continue

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if ret and frame is not None:
            succeeded_indices.append(frame_idx)
            print(f"✅ Frame {frame_idx}: OK (shape={frame.shape})")
        else:
            failed_indices.append(frame_idx)
            print(f"❌ Frame {frame_idx}: FAILED")

            # 最初の失敗地点でデバッグ情報を表示
            if len(failed_indices) == 1:
                print(f"   Current position: {cap.get(cv2.CAP_PROP_POS_FRAMES)}")
                print(f"   Current timestamp: {cap.get(cv2.CAP_PROP_POS_MSEC)}ms")

    cap.release()

    all_success = len(failed_indices) == 0
    return all_success, failed_indices, succeeded_indices


def sequential_test(video_path: str, start: int = 0, end: int = None, skip: int = 1) -> Tuple[int, List[int]]:
    """
    連続的にフレームを読み込んでどこで失敗するかを特定

    Returns:
        (first_failure: int, all_failures: List[int])
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if end is None:
        end = total_frames

    print(f"\n🔍 Sequential test: frames {start} to {end} (skip={skip})")

    first_failure = None
    all_failures = []

    for frame_idx in range(start, end, skip):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret or frame is None:
            all_failures.append(frame_idx)
            if first_failure is None:
                first_failure = frame_idx
                print(f"❌ First failure at frame {frame_idx}")
                print(f"   Position: {cap.get(cv2.CAP_PROP_POS_FRAMES)}")
                print(f"   Timestamp: {cap.get(cv2.CAP_PROP_POS_MSEC)}ms")

        if frame_idx % 100 == 0:
            status = "✅" if (ret and frame is not None) else "❌"
            print(f"{status} Frame {frame_idx}")

    cap.release()

    if first_failure is None:
        print(f"✅ All frames readable from {start} to {end}")
    else:
        print(f"❌ {len(all_failures)} failures, first at frame {first_failure}")

    return first_failure, all_failures


def analyze_failure_pattern(failed_indices: List[int], total_frames: int) -> Dict:
    """失敗パターンを分析"""
    if not failed_indices:
        return {"pattern": "no_failures"}

    analysis = {
        "total_failures": len(failed_indices),
        "first_failure": min(failed_indices),
        "last_failure": max(failed_indices),
        "failure_rate": len(failed_indices) / total_frames * 100,
        "pattern": "unknown"
    }

    # パターン検出
    if len(failed_indices) == 1:
        analysis["pattern"] = "single_frame"
    elif failed_indices == list(range(min(failed_indices), max(failed_indices) + 1)):
        analysis["pattern"] = "continuous_from_" + str(min(failed_indices))
    elif all(failed_indices[i] < failed_indices[i+1] for i in range(len(failed_indices)-1)):
        analysis["pattern"] = "scattered_increasing"
    else:
        analysis["pattern"] = "scattered_random"

    return analysis


def main():
    parser = argparse.ArgumentParser(description='Verify video file integrity')
    parser.add_argument('video_path', help='Path to video file')
    parser.add_argument('--sequential', action='store_true', help='Run sequential test')
    parser.add_argument('--start', type=int, default=0, help='Start frame for sequential test')
    parser.add_argument('--end', type=int, default=None, help='End frame for sequential test')
    parser.add_argument('--skip', type=int, default=1, help='Frame skip for sequential test')

    args = parser.parse_args()

    video_path = Path(args.video_path)

    if not video_path.exists():
        print(f"❌ Video file not found: {video_path}")
        sys.exit(1)

    print(f"📹 Video: {video_path.name}")
    print(f"   Path: {video_path.absolute()}\n")

    # メタデータ取得
    try:
        metadata = get_video_metadata(str(video_path))
        print("📊 Video Metadata:")
        print(f"   Resolution: {metadata['width']}x{metadata['height']}")
        print(f"   FPS: {metadata['fps']:.2f}")
        print(f"   Total frames: {metadata['total_frames']}")
        print(f"   Duration: {metadata['total_frames'] / metadata['fps']:.2f}s")
        print(f"   Codec: {metadata['codec']}")
        print(f"   Bitrate: {metadata['bitrate']}")
        print()
    except Exception as e:
        print(f"❌ Failed to get metadata: {e}")
        sys.exit(1)

    # フレーム読み込みテスト
    if args.sequential:
        first_failure, all_failures = sequential_test(
            str(video_path),
            start=args.start,
            end=args.end,
            skip=args.skip
        )

        if first_failure is not None:
            analysis = analyze_failure_pattern(all_failures, metadata['total_frames'])
            print(f"\n📈 Failure Analysis:")
            print(f"   Pattern: {analysis['pattern']}")
            print(f"   Total failures: {analysis['total_failures']}")
            print(f"   First failure: {analysis['first_failure']}")
            print(f"   Last failure: {analysis['last_failure']}")
            print(f"   Failure rate: {analysis['failure_rate']:.1f}%")
    else:
        success, failed, succeeded = test_frame_reading(str(video_path))

        print(f"\n📊 Test Results:")
        print(f"   Total tested: {len(failed) + len(succeeded)}")
        print(f"   Succeeded: {len(succeeded)}")
        print(f"   Failed: {len(failed)}")

        if not success:
            analysis = analyze_failure_pattern(failed, metadata['total_frames'])
            print(f"\n📈 Failure Analysis:")
            print(f"   Pattern: {analysis['pattern']}")
            if analysis['pattern'].startswith('continuous_from_'):
                print(f"   ⚠️  Video appears corrupted from frame {analysis['first_failure']} onwards")

            # 失敗フレームの詳細
            if len(failed) <= 20:
                print(f"   Failed frames: {failed}")
            else:
                print(f"   Failed frames (first 10): {failed[:10]}")
                print(f"   Failed frames (last 10): {failed[-10:]}")

            sys.exit(1)
        else:
            print("✅ All tested frames are readable")
            sys.exit(0)


if __name__ == "__main__":
    main()
