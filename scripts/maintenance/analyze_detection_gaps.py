"""検出が途切れる原因を分析するスクリプト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from collections import defaultdict

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector


def analyze_detection_gaps(video_path: Path):
    """検出の途切れパターンを分析"""

    print("=" * 80)
    print("ANALYZING DETECTION GAPS IN VIDEO")
    print("=" * 80)

    # 検出器を初期化
    detector = HandSkeletonDetector(
        enable_glove_detection=True,
        min_detection_confidence=0.1,
        min_tracking_confidence=0.1,
        max_num_hands=2,
        static_image_mode=False  # トラッキングモード
    )

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # 分析データ
    detection_timeline = []
    gap_reasons = defaultdict(list)
    frame_analysis = []

    print("\nAnalyzing each frame...")
    print("-" * 40)

    for frame_idx in range(total_frames):
        ret, frame = cap.read()
        if not ret:
            break

        # 検出実行
        result = detector.detect_from_frame(frame)
        hands = result.get("hands", [])

        # 検出の有無を記録
        detected = len(hands) > 0
        detection_timeline.append(detected)

        # フレームの特徴を分析
        frame_features = analyze_frame_features(frame, frame_idx)

        # 検出失敗の理由を推定
        if not detected:
            reasons = []

            # 明度をチェック
            if frame_features['brightness'] < 50:
                reasons.append('too_dark')
            elif frame_features['brightness'] > 200:
                reasons.append('too_bright')

            # コントラストをチェック
            if frame_features['contrast'] < 30:
                reasons.append('low_contrast')

            # 青色の量をチェック
            if frame_features['blue_ratio'] < 0.05:
                reasons.append('no_blue_glove')

            # モーションブラーをチェック
            if frame_features['blur_score'] > 100:
                reasons.append('motion_blur')

            # エッジの少なさをチェック
            if frame_features['edge_density'] < 0.05:
                reasons.append('no_clear_edges')

            if not reasons:
                reasons.append('unknown')

            for reason in reasons:
                gap_reasons[reason].append(frame_idx)

        frame_analysis.append({
            'frame': frame_idx,
            'detected': detected,
            'num_hands': len(hands),
            'features': frame_features
        })

        # 進捗表示
        if frame_idx % 30 == 0:
            status = "OK" if detected else "NG"
            print(f"Frame {frame_idx:3d}: {status} - Brightness: {frame_features['brightness']:.0f}, "
                  f"Blue: {frame_features['blue_ratio']:.2%}, Blur: {frame_features['blur_score']:.1f}")

    cap.release()

    # 検出ギャップの分析
    print("\n" + "=" * 80)
    print("DETECTION GAP ANALYSIS")
    print("=" * 80)

    # 連続検出/非検出のパターンを分析
    gaps = []
    detections = []
    current_gap = []
    current_detection = []

    for i, detected in enumerate(detection_timeline):
        if detected:
            if current_gap:
                gaps.append(len(current_gap))
                current_gap = []
            current_detection.append(i)
        else:
            if current_detection:
                detections.append(len(current_detection))
                current_detection = []
            current_gap.append(i)

    if current_gap:
        gaps.append(len(current_gap))
    if current_detection:
        detections.append(len(current_detection))

    # 統計情報
    total = len(detection_timeline)
    detected_count = sum(detection_timeline)
    detection_rate = (detected_count / total) * 100 if total > 0 else 0

    print(f"\nOverall Statistics:")
    print(f"  Total frames: {total}")
    print(f"  Detected frames: {detected_count} ({detection_rate:.1f}%)")
    print(f"  Failed frames: {total - detected_count} ({100 - detection_rate:.1f}%)")

    if gaps:
        print(f"\nGap Patterns:")
        print(f"  Number of gaps: {len(gaps)}")
        print(f"  Average gap length: {np.mean(gaps):.1f} frames")
        print(f"  Max gap length: {max(gaps)} frames")
        print(f"  Min gap length: {min(gaps)} frames")

    if detections:
        print(f"\nDetection Patterns:")
        print(f"  Number of detection sequences: {len(detections)}")
        print(f"  Average detection length: {np.mean(detections):.1f} frames")
        print(f"  Max detection length: {max(detections)} frames")
        print(f"  Min detection length: {min(detections)} frames")

    # 失敗理由の分析
    print(f"\n" + "=" * 80)
    print("FAILURE REASONS ANALYSIS")
    print("=" * 80)

    total_failures = total - detected_count
    for reason, frames in sorted(gap_reasons.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(frames)
        percentage = (count / total_failures * 100) if total_failures > 0 else 0
        print(f"  {reason:20}: {count:3d} frames ({percentage:5.1f}%)")

        # 最初の数フレームを例として表示
        example_frames = frames[:5]
        print(f"    Example frames: {example_frames}")

    # 特定の問題フレームの詳細分析
    print(f"\n" + "=" * 80)
    print("PROBLEMATIC FRAME EXAMPLES")
    print("=" * 80)

    # 最も長いギャップを特定
    if gaps:
        max_gap_idx = gaps.index(max(gaps))
        gap_start = sum(detections[:max_gap_idx]) + max_gap_idx * 1 if max_gap_idx > 0 else 0
        gap_end = gap_start + max(gaps)

        print(f"\nLongest gap: Frames {gap_start}-{gap_end} ({max(gaps)} frames)")

        # そのギャップの中間フレームを分析
        mid_frame = (gap_start + gap_end) // 2
        if mid_frame < len(frame_analysis):
            features = frame_analysis[mid_frame]['features']
            print(f"  Mid-frame {mid_frame} features:")
            print(f"    Brightness: {features['brightness']:.1f}")
            print(f"    Contrast: {features['contrast']:.1f}")
            print(f"    Blue ratio: {features['blue_ratio']:.3f}")
            print(f"    Blur score: {features['blur_score']:.1f}")
            print(f"    Edge density: {features['edge_density']:.3f}")

    return frame_analysis, gap_reasons


def analyze_frame_features(frame: np.ndarray, frame_idx: int) -> dict:
    """フレームの特徴を分析"""

    features = {}

    # 明度の計算
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    features['brightness'] = np.mean(gray)
    features['contrast'] = np.std(gray)

    # 青色の割合を計算
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([70, 30, 30])
    upper_blue = np.array([140, 255, 255])
    blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
    features['blue_ratio'] = np.sum(blue_mask > 0) / (frame.shape[0] * frame.shape[1])

    # モーションブラーの検出（ラプラシアンの分散）
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    features['blur_score'] = np.var(laplacian)

    # エッジ密度
    edges = cv2.Canny(gray, 50, 150)
    features['edge_density'] = np.sum(edges > 0) / (frame.shape[0] * frame.shape[1])

    # 手の可能性がある領域のサイズ
    # 青色マスクの連結成分を分析
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(blue_mask, connectivity=8)
    if num_labels > 1:  # 背景を除く
        # 最大の青色領域のサイズ
        max_area = max(stats[1:, cv2.CC_STAT_AREA]) if num_labels > 1 else 0
        features['max_blue_area'] = max_area
    else:
        features['max_blue_area'] = 0

    return features


def visualize_detection_timeline(frame_analysis: list):
    """検出タイムラインを視覚化"""

    frames = [fa['frame'] for fa in frame_analysis]
    detected = [1 if fa['detected'] else 0 for fa in frame_analysis]
    brightness = [fa['features']['brightness'] for fa in frame_analysis]
    blue_ratio = [fa['features']['blue_ratio'] * 100 for fa in frame_analysis]
    blur_score = [fa['features']['blur_score'] for fa in frame_analysis]

    fig, axes = plt.subplots(4, 1, figsize=(15, 10))

    # 検出状態
    axes[0].plot(frames, detected, 'g-', linewidth=2)
    axes[0].fill_between(frames, detected, alpha=0.3, color='green')
    axes[0].set_ylabel('Detection')
    axes[0].set_ylim(-0.1, 1.1)
    axes[0].set_title('Hand Detection Timeline')
    axes[0].grid(True, alpha=0.3)

    # 明度
    axes[1].plot(frames, brightness, 'b-', alpha=0.7)
    axes[1].set_ylabel('Brightness')
    axes[1].set_title('Frame Brightness')
    axes[1].axhline(y=50, color='r', linestyle='--', alpha=0.5, label='Too dark')
    axes[1].axhline(y=200, color='r', linestyle='--', alpha=0.5, label='Too bright')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    # 青色の割合
    axes[2].plot(frames, blue_ratio, 'cyan', alpha=0.7)
    axes[2].set_ylabel('Blue %')
    axes[2].set_title('Blue Color Ratio (Glove Detection)')
    axes[2].axhline(y=5, color='r', linestyle='--', alpha=0.5, label='Min threshold')
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()

    # ブラースコア
    axes[3].plot(frames, blur_score, 'orange', alpha=0.7)
    axes[3].set_ylabel('Blur Score')
    axes[3].set_xlabel('Frame')
    axes[3].set_title('Motion Blur Score (lower = more blur)')
    axes[3].axhline(y=100, color='r', linestyle='--', alpha=0.5, label='Blur threshold')
    axes[3].grid(True, alpha=0.3)
    axes[3].legend()

    plt.tight_layout()
    plt.savefig('detection_timeline_analysis.png', dpi=150)
    print(f"\nVisualization saved to: detection_timeline_analysis.png")
    plt.close()


if __name__ == "__main__":
    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")

    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
    else:
        frame_analysis, gap_reasons = analyze_detection_gaps(video_path)
        visualize_detection_timeline(frame_analysis)