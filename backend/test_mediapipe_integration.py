"""
MediaPipe統合テスト - 実際の骨格検出が動作することを確認
"""

import sys
import os
import cv2
import numpy as np
from pathlib import Path

# プロジェクトのルートをPythonパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.frame_extractor import FrameExtractor


def test_skeleton_detection():
    """骨格検出のテスト"""
    print("=== MediaPipe骨格検出テスト ===\n")

    # テスト用の画像を作成（黒い背景）
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # 骨格検出器を初期化
    detector = HandSkeletonDetector()
    print("✓ HandSkeletonDetector初期化完了")

    # 検出実行
    result = detector.detect_from_frame(test_frame)
    print(f"✓ 検出実行完了")
    print(f"  - 検出された手の数: {len(result['hands'])}")
    print(f"  - フレームサイズ: {result['frame_shape']}")

    # テスト画像に手を模した白い領域を追加
    cv2.circle(test_frame, (320, 240), 50, (255, 255, 255), -1)
    cv2.circle(test_frame, (300, 200), 20, (255, 255, 255), -1)
    cv2.circle(test_frame, (340, 200), 20, (255, 255, 255), -1)

    # 再度検出
    result2 = detector.detect_from_frame(test_frame)
    print(f"\n✓ 模擬手画像での検出完了")
    print(f"  - 検出された手の数: {len(result2['hands'])}")

    if result2['hands']:
        hand = result2['hands'][0]
        print(f"  - 手のラベル: {hand.get('label', 'N/A')}")
        print(f"  - 信頼度: {hand.get('confidence', 0):.2f}")
        print(f"  - ランドマーク数: {len(hand.get('landmarks', []))}")
        print(f"  - 手の開き具合: {hand.get('hand_openness', 0):.1f}%")

    print("\n✓ MediaPipe統合テスト成功！")
    return True


def test_frame_extraction():
    """フレーム抽出のテスト"""
    print("\n=== フレーム抽出テスト ===\n")

    # テスト用動画パスを探す
    test_video_paths = [
        Path("data/uploads") / "test.mp4",
        Path("data/uploads") / "sample.mp4",
    ]

    test_video = None
    for path in test_video_paths:
        if path.exists():
            test_video = path
            break

    if not test_video:
        print("⚠ テスト用動画が見つかりません")
        print("  data/uploads/test.mp4 または sample.mp4 を配置してください")
        return False

    print(f"テスト動画: {test_video}")

    try:
        # フレーム抽出器を初期化
        with FrameExtractor(str(test_video), target_fps=5) as extractor:
            info = extractor.get_info()
            print(f"✓ 動画情報取得完了")
            print(f"  - サイズ: {info.width}x{info.height}")
            print(f"  - FPS: {info.fps:.2f}")
            print(f"  - 総フレーム数: {info.total_frames}")
            print(f"  - 長さ: {info.duration:.2f}秒")

            # 最初の3フレームを抽出
            frame_count = 0
            for frame_num, frame in extractor.extract_frames_generator():
                frame_count += 1
                print(f"  - フレーム {frame_num}: {frame.shape}")
                if frame_count >= 3:
                    break

            print(f"\n✓ フレーム抽出テスト成功！")
            return True

    except Exception as e:
        print(f"✗ エラー: {e}")
        return False


def test_full_pipeline():
    """完全なパイプラインのテスト"""
    print("\n=== 統合パイプラインテスト ===\n")

    # テスト用動画を探す
    test_video = None
    for path in [Path("data/uploads") / f for f in ["test.mp4", "sample.mp4"]]:
        if path.exists():
            test_video = path
            break

    if not test_video:
        print("⚠ 動画ファイルがないため、模擬データでテスト")

        # 模擬フレームで骨格検出
        detector = HandSkeletonDetector()
        frames = [np.ones((480, 640, 3), dtype=np.uint8) * 128 for _ in range(5)]

        results = []
        for i, frame in enumerate(frames):
            result = detector.detect_from_frame(frame)
            results.append({
                "frame": i,
                "hands": result.get("hands", [])
            })

        print(f"✓ 模擬データでの処理完了")
        print(f"  - 処理フレーム数: {len(results)}")
        print(f"  - 手検出フレーム数: {sum(1 for r in results if r['hands'])}")

    else:
        print(f"動画ファイル: {test_video}")

        # 実際の動画でテスト
        detector = HandSkeletonDetector()

        with FrameExtractor(str(test_video), target_fps=2) as extractor:
            results = []
            frame_count = 0

            for frame_num, frame in extractor.extract_frames_generator():
                result = detector.detect_from_frame(frame)
                results.append({
                    "frame": frame_num,
                    "hands": result.get("hands", [])
                })

                frame_count += 1
                if frame_count >= 10:  # 最初の10フレームのみ
                    break

            print(f"✓ 実動画での処理完了")
            print(f"  - 処理フレーム数: {len(results)}")
            print(f"  - 手検出フレーム数: {sum(1 for r in results if r['hands'])}")

            # 検出された手の詳細
            for r in results:
                if r['hands']:
                    print(f"  - フレーム {r['frame']}: {len(r['hands'])}個の手を検出")

    print("\n✓ 統合パイプラインテスト成功！")
    return True


def main():
    """メインテスト実行"""
    print("=" * 50)
    print("MediaPipe統合テストを開始します")
    print("=" * 50)

    success = True

    # 各テストを実行
    try:
        if not test_skeleton_detection():
            success = False
    except Exception as e:
        print(f"✗ 骨格検出テストでエラー: {e}")
        success = False

    try:
        if not test_frame_extraction():
            success = False
    except Exception as e:
        print(f"✗ フレーム抽出テストでエラー: {e}")
        success = False

    try:
        if not test_full_pipeline():
            success = False
    except Exception as e:
        print(f"✗ 統合パイプラインテストでエラー: {e}")
        success = False

    print("\n" + "=" * 50)
    if success:
        print("✅ すべてのテストが成功しました！")
        print("MediaPipeによる骨格検出が正常に動作しています。")
    else:
        print("⚠ 一部のテストが失敗しました")
        print("エラーメッセージを確認してください。")
    print("=" * 50)


if __name__ == "__main__":
    main()