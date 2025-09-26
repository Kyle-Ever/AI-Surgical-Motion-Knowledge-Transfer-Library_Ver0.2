"""SAMを直接テスト"""

import cv2
import numpy as np
from pathlib import Path
import base64
from app.ai_engine.processors.sam_tracker import SAMTracker

def test_sam_directly():
    """SAMを直接テストして器具選択機能を確認"""

    # テスト動画を読み込み
    video_path = "../data/uploads/VID_20250926_123049.mp4"
    if not Path(video_path).exists():
        print(f"Video not found: {video_path}")
        return

    print(f"Loading video: {video_path}")

    # 最初のフレームを抽出
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Failed to read video frame")
        return

    print(f"Frame shape: {frame.shape}")

    # SAMトラッカーを初期化
    print("\nInitializing SAM tracker...")
    tracker = SAMTracker(
        model_type="vit_b",
        checkpoint_path="sam_b.pt",
        device="cpu",
        use_mock=False
    )

    # 画像をセット
    tracker.set_image(frame)

    # 1. ポイント選択テスト
    print("\n" + "="*50)
    print("1. Testing point selection...")

    # 画像の中央付近にポイントを配置
    h, w = frame.shape[:2]
    point_coords = [(w//2, h//2), (w//2 + 50, h//2 + 30)]
    point_labels = [1, 1]  # すべてforeground

    result = tracker.segment_with_point(point_coords, point_labels)

    if result and 'mask' in result:
        print("[OK] Point selection successful!")
        print(f"  Mask shape: {result['mask'].shape}")
        print(f"  Score: {result.get('score', 'N/A')}")

        # 可視化を保存
        mask = result['mask']
        vis = frame.copy()
        vis[mask > 0] = vis[mask > 0] * 0.5 + np.array([0, 255, 0], dtype=np.uint8) * 0.5
        cv2.imwrite("sam_point_test.jpg", vis)
        print("  Visualization saved to sam_point_test.jpg")
    else:
        print("[FAILED] Point selection failed")

    # 2. ボックス選択テスト
    print("\n" + "="*50)
    print("2. Testing box selection...")

    # 画像の中央領域にボックスを配置
    box = (w//3, h//3, 2*w//3, 2*h//3)

    result = tracker.segment_with_box(box)

    if result and 'mask' in result:
        print("[OK] Box selection successful!")
        print(f"  Mask shape: {result['mask'].shape}")
        print(f"  Score: {result.get('score', 'N/A')}")

        # 可視化を保存
        mask = result['mask']
        vis = frame.copy()
        vis[mask > 0] = vis[mask > 0] * 0.5 + np.array([0, 0, 255], dtype=np.uint8) * 0.5
        cv2.rectangle(vis, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
        cv2.imwrite("sam_box_test.jpg", vis)
        print("  Visualization saved to sam_box_test.jpg")
    else:
        print("[FAILED] Box selection failed")

    # 3. 自動マスク生成テスト（オプション）
    print("\n" + "="*50)
    print("3. Automatic mask generation (skipped - not needed for instrument tracking)")

    print("\n" + "="*50)
    print("SAM direct testing completed!")

    # モック実装かどうか確認
    if tracker.use_mock:
        print("\n[WARNING] Using mock SAM implementation.")
        print("For real SAM, ensure:")
        print("1. segment-anything is installed: pip install segment-anything")
        print("2. SAM checkpoint file exists: sam_b.pt")
    else:
        print("\n[SUCCESS] SAM is working correctly!")

if __name__ == "__main__":
    test_sam_directly()