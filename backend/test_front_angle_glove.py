"""Front_Angle.mp4での青い手袋検出の詳細テスト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
import json
from datetime import datetime

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.glove_hand_detector import GloveHandDetector


def analyze_video_full(video_path: Path):
    """動画全体を分析して手袋検出の統計を取得"""

    print("=" * 80)
    print(f"VIDEO ANALYSIS: {video_path.name}")
    print("=" * 80)

    # 動画情報を取得
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"\nVideo Info:")
    print(f"  Resolution: {width}x{height}")
    print(f"  FPS: {fps:.2f}")
    print(f"  Total frames: {total_frames}")
    print(f"  Duration: {total_frames/fps:.2f} seconds")

    # 3つの検出器を初期化
    print("\nInitializing detectors...")

    # 1. 標準版（手袋モード無効）
    standard_detector = HandSkeletonDetector(
        enable_glove_detection=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        max_num_hands=2
    )

    # 2. 改善版（手袋モード有効）
    improved_detector = HandSkeletonDetector(
        enable_glove_detection=True,
        min_detection_confidence=0.2,
        min_tracking_confidence=0.2,
        max_num_hands=2
    )

    print("Detectors ready!\n")

    # 結果を記録
    results = {
        'standard': {
            'frames_with_detection': 0,
            'total_hands': 0,
            'left_hands': 0,
            'right_hands': 0,
            'confidence_sum': 0,
            'hand_counts': [],
            'frame_details': []
        },
        'improved': {
            'frames_with_detection': 0,
            'total_hands': 0,
            'left_hands': 0,
            'right_hands': 0,
            'confidence_sum': 0,
            'hand_counts': [],
            'frame_details': []
        }
    }

    # サンプリング（5フレームごと）
    sample_interval = 5
    frames_processed = 0

    print("Processing frames (every 5th frame)...")
    print("\nFrame | Standard (L/R) | Improved (L/R) | Confidence")
    print("-" * 60)

    for frame_idx in range(0, total_frames, sample_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        # 標準版で検出
        std_result = standard_detector.detect_from_frame(frame)
        std_hands = std_result.get("hands", [])

        # 改善版で検出
        imp_result = improved_detector.detect_from_frame(frame)
        imp_hands = imp_result.get("hands", [])

        # 標準版の結果を記録
        if std_hands:
            results['standard']['frames_with_detection'] += 1
            results['standard']['total_hands'] += len(std_hands)

            left_count = sum(1 for h in std_hands if h['handedness'] == 'Left')
            right_count = sum(1 for h in std_hands if h['handedness'] == 'Right')
            results['standard']['left_hands'] += left_count
            results['standard']['right_hands'] += right_count

            avg_conf = np.mean([h['confidence'] for h in std_hands])
            results['standard']['confidence_sum'] += avg_conf

            results['standard']['frame_details'].append({
                'frame': frame_idx,
                'hands': len(std_hands),
                'left': left_count,
                'right': right_count,
                'confidence': avg_conf
            })

        results['standard']['hand_counts'].append(len(std_hands))

        # 改善版の結果を記録
        if imp_hands:
            results['improved']['frames_with_detection'] += 1
            results['improved']['total_hands'] += len(imp_hands)

            left_count = sum(1 for h in imp_hands if h['handedness'] == 'Left')
            right_count = sum(1 for h in imp_hands if h['handedness'] == 'Right')
            results['improved']['left_hands'] += left_count
            results['improved']['right_hands'] += right_count

            avg_conf = np.mean([h['confidence'] for h in imp_hands])
            results['improved']['confidence_sum'] += avg_conf

            results['improved']['frame_details'].append({
                'frame': frame_idx,
                'hands': len(imp_hands),
                'left': left_count,
                'right': right_count,
                'confidence': avg_conf
            })

        results['improved']['hand_counts'].append(len(imp_hands))

        # 進捗表示（20フレームごと）
        if frame_idx % 20 == 0:
            std_l = sum(1 for h in std_hands if h['handedness'] == 'Left')
            std_r = sum(1 for h in std_hands if h['handedness'] == 'Right')
            imp_l = sum(1 for h in imp_hands if h['handedness'] == 'Left')
            imp_r = sum(1 for h in imp_hands if h['handedness'] == 'Right')

            imp_conf = np.mean([h['confidence'] for h in imp_hands]) if imp_hands else 0

            print(f"{frame_idx:5} | {std_l}/{std_r:13} | {imp_l}/{imp_r:13} | {imp_conf:.2f}")

        frames_processed += 1

    cap.release()

    # 統計の計算と表示
    print("\n" + "=" * 80)
    print("DETECTION STATISTICS")
    print("=" * 80)

    for name, data in results.items():
        total = frames_processed
        detection_rate = (data['frames_with_detection'] / total * 100) if total > 0 else 0
        avg_hands = data['total_hands'] / total if total > 0 else 0
        avg_confidence = data['confidence_sum'] / data['frames_with_detection'] if data['frames_with_detection'] > 0 else 0

        print(f"\n{name.upper()} DETECTOR:")
        print(f"  Detection rate: {detection_rate:.1f}% ({data['frames_with_detection']}/{total} frames)")
        print(f"  Total hands detected: {data['total_hands']}")
        print(f"    - Left hands: {data['left_hands']}")
        print(f"    - Right hands: {data['right_hands']}")
        print(f"  Average hands per frame: {avg_hands:.2f}")
        print(f"  Average confidence: {avg_confidence:.3f}")

        # 最も検出が多かったフレーム
        if data['frame_details']:
            best_frame = max(data['frame_details'], key=lambda x: x['hands'])
            print(f"  Best frame: #{best_frame['frame']} with {best_frame['hands']} hands")

    # 改善率の計算
    print("\n" + "=" * 80)
    print("IMPROVEMENT ANALYSIS")
    print("=" * 80)

    std_rate = results['standard']['frames_with_detection'] / frames_processed * 100
    imp_rate = results['improved']['frames_with_detection'] / frames_processed * 100

    if std_rate > 0:
        improvement = ((imp_rate - std_rate) / std_rate) * 100
        print(f"Detection rate improvement: {improvement:+.1f}%")
    else:
        print(f"Standard detector: {std_rate:.1f}%")
        print(f"Improved detector: {imp_rate:.1f}%")
        print("Infinite improvement (standard detector failed completely)")

    hands_std = results['standard']['total_hands']
    hands_imp = results['improved']['total_hands']
    if hands_std > 0:
        hands_improvement = ((hands_imp - hands_std) / hands_std) * 100
        print(f"Total hands detected improvement: {hands_improvement:+.1f}%")
    else:
        print(f"Standard: {hands_std} hands")
        print(f"Improved: {hands_imp} hands")

    return results


def visualize_specific_frames(video_path: Path):
    """特定のフレームで視覚的な比較を行う"""

    print("\n" + "=" * 80)
    print("VISUAL COMPARISON OF SPECIFIC FRAMES")
    print("=" * 80)

    cap = cv2.VideoCapture(str(video_path))

    # テストするフレーム番号
    test_frames = [30, 60, 90, 120, 150]

    # 改善版検出器
    detector = HandSkeletonDetector(
        enable_glove_detection=True,
        min_detection_confidence=0.2,
        min_tracking_confidence=0.2,
        max_num_hands=2
    )

    for frame_idx in test_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue

        # 検出実行
        result = detector.detect_from_frame(frame)
        hands = result.get("hands", [])

        print(f"\nFrame {frame_idx}:")
        if hands:
            print(f"  Detected {len(hands)} hand(s):")
            for i, hand in enumerate(hands):
                print(f"    Hand {i+1}: {hand['handedness']} (confidence: {hand['confidence']:.3f})")
                print(f"      Palm center: ({hand['palm_center']['x']:.0f}, {hand['palm_center']['y']:.0f})")
                print(f"      Hand openness: {hand['hand_openness']:.1f}%")

                # 指の角度情報
                if hand.get('finger_angles'):
                    angles = hand['finger_angles']
                    print(f"      Finger angles:")
                    for finger, angle in angles.items():
                        print(f"        {finger}: {angle:.1f}°")
        else:
            print(f"  No hands detected")

        # 検出結果を画像として保存（最初のフレームのみ）
        if frame_idx == test_frames[0] and hands:
            vis_frame = frame.copy()

            for hand in hands:
                # ランドマークを描画
                if hand['landmarks']:
                    for landmark in hand['landmarks']:
                        x = int(landmark['x'])
                        y = int(landmark['y'])
                        cv2.circle(vis_frame, (x, y), 3, (0, 255, 0), -1)

                # バウンディングボックスを描画
                bbox = hand['bbox']
                cv2.rectangle(vis_frame,
                            (int(bbox['x_min']), int(bbox['y_min'])),
                            (int(bbox['x_max']), int(bbox['y_max'])),
                            (0, 255, 0), 2)

                # ラベルを追加
                label = f"{hand['handedness']} ({hand['confidence']:.2f})"
                cv2.putText(vis_frame, label,
                          (int(bbox['x_min']), int(bbox['y_min']) - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            output_path = f"front_angle_frame_{frame_idx}_detection.jpg"
            cv2.imwrite(output_path, vis_frame)
            print(f"\n  Visualization saved to: {output_path}")

    cap.release()


def main():
    """メイン実行関数"""

    # 動画パスの設定
    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")

    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    print("Starting analysis of Front_Angle.mp4 for blue glove detection...")
    print(f"Video path: {video_path}\n")

    # 1. 動画全体の分析
    results = analyze_video_full(video_path)

    # 2. 特定フレームの詳細分析
    visualize_specific_frames(video_path)

    # 3. 結果をJSONファイルに保存
    output_json = {
        'video': str(video_path),
        'timestamp': datetime.now().isoformat(),
        'results': results
    }

    with open('front_angle_analysis_results.json', 'w') as f:
        json.dump(output_json, f, indent=2)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("Results saved to: front_angle_analysis_results.json")
    print("Visualization saved to: front_angle_frame_30_detection.jpg")


if __name__ == "__main__":
    main()