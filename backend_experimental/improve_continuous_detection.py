"""継続的な検出を改善するスクリプト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from collections import deque

from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector


class ContinuousHandDetector:
    """継続的な手検出を実現するクラス"""

    def __init__(self, history_size: int = 5):
        """
        初期化

        Args:
            history_size: トラッキング履歴のサイズ
        """
        # 複数の検出器を用意（異なる設定）
        self.primary_detector = HandSkeletonDetector(
            enable_glove_detection=True,
            min_detection_confidence=0.05,  # 超低閾値
            min_tracking_confidence=0.05,
            static_image_mode=False,
            max_num_hands=2
        )

        self.backup_detector = HandSkeletonDetector(
            enable_glove_detection=True,
            min_detection_confidence=0.1,
            min_tracking_confidence=0.1,
            static_image_mode=True,  # 静止画モード
            max_num_hands=2
        )

        # トラッキング履歴
        self.detection_history = deque(maxlen=history_size)
        self.last_valid_detection = None
        self.frames_since_last_detection = 0

    def detect_with_interpolation(self, frame: np.ndarray) -> dict:
        """
        検出と補間を組み合わせた処理

        Args:
            frame: 入力フレーム

        Returns:
            検出結果（補間を含む）
        """
        # 前処理の強化
        enhanced_frame = self.enhance_frame(frame)

        # 1. プライマリ検出器で試行
        result = self.primary_detector.detect_from_frame(enhanced_frame)

        # 2. 検出失敗時はバックアップ検出器
        if not result.get("hands"):
            result = self.backup_detector.detect_from_frame(enhanced_frame)

        # 3. それでも失敗時は異なる前処理で再試行
            if not result.get("hands"):
                alternative_frame = self.alternative_preprocessing(frame)
                result = self.primary_detector.detect_from_frame(alternative_frame)

        # 4. 履歴を更新
        self.detection_history.append(result)

        # 5. 補間処理
        if not result.get("hands") and self.last_valid_detection:
            result = self.interpolate_detection(result)
            self.frames_since_last_detection += 1
        else:
            if result.get("hands"):
                self.last_valid_detection = result
                self.frames_since_last_detection = 0

        return result

    def enhance_frame(self, frame: np.ndarray) -> np.ndarray:
        """フレームの前処理強化"""

        # 1. デノイジング（ブラー対策）
        denoised = cv2.fastNlMeansDenoisingColored(frame, None, 10, 10, 7, 21)

        # 2. シャープネス向上（エッジ強調）
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)

        # 3. ブレンド
        enhanced = cv2.addWeighted(denoised, 0.5, sharpened, 0.5, 0)

        # 4. 青色の強調
        hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([60, 20, 20])
        upper_blue = np.array([150, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # 青い部分をより肌色に近づける
        enhanced[blue_mask > 0] = self.convert_blue_to_skin(enhanced[blue_mask > 0])

        return enhanced

    def alternative_preprocessing(self, frame: np.ndarray) -> np.ndarray:
        """代替の前処理"""

        # ヒストグラム均等化
        yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
        yuv[:,:,0] = cv2.equalizeHist(yuv[:,:,0])
        equalized = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

        # エッジ保存スムージング
        smoothed = cv2.bilateralFilter(equalized, 9, 75, 75)

        return smoothed

    def convert_blue_to_skin(self, pixels: np.ndarray) -> np.ndarray:
        """青を肌色に変換（改良版）"""
        # HSV変換して色相だけ変更
        hsv_pixels = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV)

        # 色相を肌色範囲に変更（20度前後）
        hsv_pixels[:, :, 0] = 20
        # 彩度を下げる
        hsv_pixels[:, :, 1] = hsv_pixels[:, :, 1] * 0.4

        bgr_pixels = cv2.cvtColor(hsv_pixels, cv2.COLOR_HSV2BGR)
        return bgr_pixels.reshape(pixels.shape)

    def interpolate_detection(self, current_result: dict) -> dict:
        """前のフレームから検出を補間"""

        if self.frames_since_last_detection > 10:
            # 10フレーム以上検出なしの場合は補間しない
            return current_result

        if not self.last_valid_detection or not self.last_valid_detection.get("hands"):
            return current_result

        # 最後の有効な検出を使用（信頼度を下げて）
        interpolated_result = current_result.copy()
        interpolated_result["hands"] = []

        for hand in self.last_valid_detection["hands"]:
            interpolated_hand = hand.copy()
            # 信頼度を下げる
            interpolated_hand["confidence"] *= 0.8
            interpolated_hand["interpolated"] = True
            interpolated_result["hands"].append(interpolated_hand)

        return interpolated_result


def test_continuous_detection(video_path: Path):
    """継続的検出のテスト"""

    print("=" * 80)
    print("TESTING CONTINUOUS DETECTION IMPROVEMENTS")
    print("=" * 80)

    detector = ContinuousHandDetector(history_size=5)
    standard_detector = HandSkeletonDetector(
        enable_glove_detection=True,
        min_detection_confidence=0.1,
        min_tracking_confidence=0.1,
        max_num_hands=2
    )

    cap = cv2.VideoCapture(str(video_path))
    total_frames = min(100, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))

    # 比較用の結果
    continuous_detections = 0
    standard_detections = 0
    interpolated_count = 0

    print("\nProcessing frames...")
    print("-" * 40)

    for frame_idx in range(total_frames):
        ret, frame = cap.read()
        if not ret:
            break

        # 継続的検出
        continuous_result = detector.detect_with_interpolation(frame)
        if continuous_result.get("hands"):
            continuous_detections += 1
            if any(h.get("interpolated") for h in continuous_result["hands"]):
                interpolated_count += 1

        # 標準検出
        standard_result = standard_detector.detect_from_frame(frame)
        if standard_result.get("hands"):
            standard_detections += 1

        # 進捗表示
        if frame_idx % 20 == 0:
            cont_status = "OK" if continuous_result.get("hands") else "NG"
            std_status = "OK" if standard_result.get("hands") else "NG"
            interp = " (interpolated)" if continuous_result.get("hands") and any(h.get("interpolated") for h in continuous_result["hands"]) else ""
            print(f"Frame {frame_idx:3d}: Continuous={cont_status}{interp}, Standard={std_status}")

    cap.release()

    # 結果の比較
    print("\n" + "=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)

    continuous_rate = (continuous_detections / total_frames) * 100
    standard_rate = (standard_detections / total_frames) * 100
    interpolation_rate = (interpolated_count / total_frames) * 100

    print(f"Standard detection: {standard_detections}/{total_frames} ({standard_rate:.1f}%)")
    print(f"Continuous detection: {continuous_detections}/{total_frames} ({continuous_rate:.1f}%)")
    print(f"  - With interpolation: {interpolated_count} frames ({interpolation_rate:.1f}%)")
    print(f"  - Actual detection: {continuous_detections - interpolated_count} frames")

    improvement = continuous_rate - standard_rate
    print(f"\nImprovement: {improvement:+.1f} percentage points")

    if improvement > 10:
        print("SUCCESS: Significant improvement in detection continuity!")
    elif improvement > 0:
        print("Moderate improvement achieved")
    else:
        print("No significant improvement")


if __name__ == "__main__":
    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")

    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
    else:
        test_continuous_detection(video_path)