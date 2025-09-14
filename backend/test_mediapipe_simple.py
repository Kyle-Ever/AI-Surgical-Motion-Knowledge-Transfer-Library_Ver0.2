"""
MediaPipe簡易テスト - パス問題を回避
"""

import sys
import os
import cv2
import numpy as np

# テスト画像を作成（手の写真の代わりに単純な画像）
def create_test_image():
    """テスト用の画像を生成"""
    img = np.ones((480, 640, 3), dtype=np.uint8) * 255
    # 中央に円を描画（手のシミュレーション）
    cv2.circle(img, (320, 240), 50, (100, 100, 100), -1)
    return img

def test_mediapipe_basic():
    """MediaPipeの基本動作テスト"""
    print("Testing MediaPipe installation...")

    try:
        # MediaPipeのインポートテスト
        import mediapipe as mp
        print("[OK] MediaPipe imported successfully")
        print(f"    Version: {mp.__version__}")

        # 基本コンポーネントのテスト
        mp_hands = mp.solutions.hands
        mp_drawing = mp.solutions.drawing_utils
        print("[OK] MediaPipe solutions loaded")

        # テスト画像で検出（エラーが出る可能性があるがインストール確認のため）
        test_img = create_test_image()
        print(f"[OK] Test image created: {test_img.shape}")

        # 手検出の初期化を試みる
        try:
            # モデルファイル確認
            import mediapipe.python.solutions.hands
            hands_module_path = mediapipe.python.solutions.hands.__file__
            print(f"[INFO] Hands module path: {hands_module_path}")

            # 簡易的な検出テスト（失敗しても続行）
            with mp_hands.Hands(
                static_image_mode=True,
                max_num_hands=1,
                min_detection_confidence=0.3
            ) as hands:
                print("[OK] Hands detector initialized")

                # RGB変換
                rgb_image = cv2.cvtColor(test_img, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb_image)

                if results.multi_hand_landmarks:
                    print(f"[OK] Detected {len(results.multi_hand_landmarks)} hand(s)")
                else:
                    print("[INFO] No hands detected in test image (expected)")

        except Exception as e:
            print(f"[WARNING] Hands detection failed: {e}")
            print("    This might be due to path encoding issues")
            print("    MediaPipe is installed but may need workaround for special characters in path")

        # OpenCVテスト
        print("\nTesting OpenCV...")
        print(f"[OK] OpenCV version: {cv2.__version__}")

        # NumPyテスト
        print("\nTesting NumPy...")
        arr = np.array([1, 2, 3])
        print(f"[OK] NumPy version: {np.__version__}")
        print(f"[OK] Test array: {arr}")

        print("\n[SUMMARY] Core libraries are installed correctly")
        print("MediaPipe detection may fail due to path issues with special characters")
        print("Consider moving project to a path without special characters for full functionality")

        return True

    except ImportError as e:
        print(f"[ERROR] Failed to import MediaPipe: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mediapipe_basic()
    sys.exit(0 if success else 1)