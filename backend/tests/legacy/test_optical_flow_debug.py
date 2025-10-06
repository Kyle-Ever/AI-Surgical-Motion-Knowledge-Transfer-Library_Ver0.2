"""Optical Flowトラッキングのデバッグ"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path

def analyze_tracking_video():
    """生成された動画を分析"""

    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/optical_flow_20250926_135149.mp4")

    if not video_path.exists():
        print("Error: Video not found")
        return

    cap = cv2.VideoCapture(str(video_path))

    print("=" * 80)
    print("OPTICAL FLOW TRACKING VIDEO ANALYSIS")
    print("=" * 80)

    # いくつかのフレームをサンプリング
    sample_frames = [0, 50, 100, 150, 200, 300, 400, 500]

    for frame_idx in sample_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            print(f"Frame {frame_idx}: Could not read")
            continue

        # フレームを保存
        output_path = f"debug_frame_{frame_idx}.jpg"
        cv2.imwrite(output_path, frame)
        print(f"Frame {frame_idx}: Saved to {output_path}")

        # 画像の分析
        # 緑と赤の点を検出
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 緑色の範囲
        green_lower = np.array([40, 40, 40])
        green_upper = np.array([80, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)

        # 赤色の範囲
        red_lower1 = np.array([0, 40, 40])
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([170, 40, 40])
        red_upper2 = np.array([180, 255, 255])
        red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
        red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        green_pixels = np.sum(green_mask > 0)
        red_pixels = np.sum(red_mask > 0)

        print(f"  Green pixels: {green_pixels}")
        print(f"  Red pixels: {red_pixels}")

        # 黄色とピンクの点も検出（握り部と先端）
        yellow_lower = np.array([20, 100, 100])
        yellow_upper = np.array([40, 255, 255])
        yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)

        pink_lower = np.array([140, 40, 100])
        pink_upper = np.array([170, 255, 255])
        pink_mask = cv2.inRange(hsv, pink_lower, pink_upper)

        yellow_pixels = np.sum(yellow_mask > 0)
        pink_pixels = np.sum(pink_mask > 0)

        print(f"  Yellow (grip) pixels: {yellow_pixels}")
        print(f"  Pink (tip) pixels: {pink_pixels}")
        print()

    cap.release()

    # 最初のフレームを詳細分析
    print("\nDetailed analysis of first frame:")
    first_frame = cv2.imread("debug_frame_0.jpg")

    if first_frame is not None:
        h, w = first_frame.shape[:2]
        print(f"Frame size: {w}x{h}")

        # 上部40ピクセルを確認（情報パネル）
        panel_area = first_frame[0:40, :]
        panel_mean = np.mean(panel_area)
        print(f"Panel area mean intensity: {panel_mean:.1f}")

        # 主要エリアを確認
        main_area = first_frame[40:, :]
        main_mean = np.mean(main_area)
        print(f"Main area mean intensity: {main_mean:.1f}")

if __name__ == "__main__":
    analyze_tracking_video()