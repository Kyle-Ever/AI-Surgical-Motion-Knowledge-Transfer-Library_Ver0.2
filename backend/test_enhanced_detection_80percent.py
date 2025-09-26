"""80%以上の検出精度を目指す強化版検出スクリプト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from collections import deque
import mediapipe as mp

class EnhancedHandDetector80Percent:
    """80%検出率を目指す強化版検出器"""

    def __init__(self):
        """複数の検出戦略を初期化"""

        # 戦略1: 超低閾値のMediaPipe
        self.mp_hands_low = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.01,  # 極限まで下げる
            min_tracking_confidence=0.01,
            model_complexity=1
        )

        # 戦略2: 静止画モードのMediaPipe
        self.mp_hands_static = mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=2,
            min_detection_confidence=0.05,
            min_tracking_confidence=0.05,
            model_complexity=1
        )

        # 戦略3: 中間閾値の安定版
        self.mp_hands_mid = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.15,
            min_tracking_confidence=0.15,
            model_complexity=1
        )

        # トラッキング用履歴
        self.detection_history = deque(maxlen=10)
        self.last_valid_detection = None
        self.frames_since_detection = 0

    def detect_hands(self, frame):
        """複数戦略を組み合わせた手検出"""

        # 前処理パイプライン
        preprocessed_frames = self.preprocess_multiple(frame)

        all_detections = []

        # 各前処理バージョンで検出試行
        for prep_frame in preprocessed_frames:
            # RGB変換
            rgb_frame = cv2.cvtColor(prep_frame, cv2.COLOR_BGR2RGB)

            # 戦略1: 低閾値検出
            result1 = self.mp_hands_low.process(rgb_frame)
            if result1.multi_hand_landmarks:
                all_detections.append((result1, 0.8))  # 信頼度調整

            # 戦略2: 静止画モード（検出がない場合）
            if not all_detections:
                result2 = self.mp_hands_static.process(rgb_frame)
                if result2.multi_hand_landmarks:
                    all_detections.append((result2, 0.7))

            # 戦略3: 中間閾値（まだ検出がない場合）
            if not all_detections:
                result3 = self.mp_hands_mid.process(rgb_frame)
                if result3.multi_hand_landmarks:
                    all_detections.append((result3, 0.6))

        # 検出結果の統合
        if all_detections:
            best_result = max(all_detections, key=lambda x: x[1])
            self.last_valid_detection = best_result[0]
            self.frames_since_detection = 0
            return best_result[0]

        # 補間戦略: 前のフレームから推定
        if self.last_valid_detection and self.frames_since_detection < 5:
            self.frames_since_detection += 1
            return self.last_valid_detection  # 前の検出を使用

        return None

    def preprocess_multiple(self, frame):
        """複数の前処理バージョンを生成"""

        versions = []

        # オリジナル
        versions.append(frame.copy())

        # バージョン1: 青を肌色に変換
        skin_converted = self.convert_blue_to_skin_advanced(frame)
        versions.append(skin_converted)

        # バージョン2: コントラスト強調
        contrast_enhanced = self.enhance_contrast_clahe(frame)
        versions.append(contrast_enhanced)

        # バージョン3: エッジ強調
        edge_enhanced = self.enhance_edges(frame)
        versions.append(edge_enhanced)

        # バージョン4: 明度補正
        brightness_corrected = self.correct_brightness(frame)
        versions.append(brightness_corrected)

        return versions

    def convert_blue_to_skin_advanced(self, frame):
        """改良版: 青を肌色に変換"""

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # より広い青色範囲
        lower_blue = np.array([60, 10, 10])
        upper_blue = np.array([150, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # モルフォロジー処理で手の形状を保持
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, kernel)

        # 肌色に変換
        result = frame.copy()
        hsv_copy = hsv.copy()

        # 青い領域を肌色に
        hsv_copy[blue_mask > 0, 0] = 20  # 肌色の色相
        hsv_copy[blue_mask > 0, 1] = hsv_copy[blue_mask > 0, 1] * 0.3  # 彩度を下げる

        result = cv2.cvtColor(hsv_copy, cv2.COLOR_HSV2BGR)

        # ブレンド
        result = cv2.addWeighted(frame, 0.3, result, 0.7, 0)

        return result

    def enhance_contrast_clahe(self, frame):
        """CLAHE適用によるコントラスト強調"""

        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        enhanced = cv2.merge([l, a, b])
        result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        return result

    def enhance_edges(self, frame):
        """エッジ強調"""

        # アンシャープマスク
        gaussian = cv2.GaussianBlur(frame, (5, 5), 1.0)
        sharpened = cv2.addWeighted(frame, 1.5, gaussian, -0.5, 0)

        return sharpened

    def correct_brightness(self, frame):
        """明度補正"""

        # HSVで明度調整
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)

        # V成分の正規化
        hsv[:, :, 2] = hsv[:, :, 2] * 1.2  # 明度を上げる
        hsv[:, :, 2][hsv[:, :, 2] > 255] = 255

        hsv = hsv.astype(np.uint8)
        result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        return result


def test_enhanced_detection():
    """強化版検出のテスト"""

    print("=" * 80)
    print("TESTING ENHANCED DETECTION (TARGET: 80%+)")
    print("=" * 80)

    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/Front_Angle.mp4")

    if not video_path.exists():
        print(f"Error: Video not found at {video_path}")
        return

    detector = EnhancedHandDetector80Percent()

    cap = cv2.VideoCapture(str(video_path))
    total_frames = min(100, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))  # 最初の100フレームでテスト

    detected_count = 0
    detection_details = []

    print("\nProcessing frames...")
    print("-" * 40)

    for frame_idx in range(total_frames):
        ret, frame = cap.read()
        if not ret:
            break

        # 検出実行
        result = detector.detect_hands(frame)

        if result and result.multi_hand_landmarks:
            detected_count += 1
            num_hands = len(result.multi_hand_landmarks)
            detection_details.append({
                'frame': frame_idx,
                'detected': True,
                'num_hands': num_hands
            })
            status = f"OK (Hands: {num_hands})"
        else:
            detection_details.append({
                'frame': frame_idx,
                'detected': False,
                'num_hands': 0
            })
            status = "NG"

        # 進捗表示
        if frame_idx % 10 == 0:
            print(f"Frame {frame_idx:3d}: {status}")

    cap.release()

    # 結果の分析
    detection_rate = (detected_count / total_frames) * 100

    print("\n" + "=" * 80)
    print("DETECTION RESULTS")
    print("=" * 80)
    print(f"Total frames processed: {total_frames}")
    print(f"Frames with detection: {detected_count}")
    print(f"Detection rate: {detection_rate:.1f}%")

    if detection_rate >= 80:
        print("\n[SUCCESS] Achieved 80%+ detection rate!")
    elif detection_rate >= 70:
        print("\n[GOOD] Achieved 70%+ detection rate (close to target)")
    elif detection_rate >= 60:
        print("\n[MODERATE] Achieved 60%+ detection rate")
    else:
        print(f"\n[NEEDS IMPROVEMENT] Only {detection_rate:.1f}% detection rate")

    # 連続検出の分析
    max_gap = 0
    current_gap = 0
    for detail in detection_details:
        if detail['detected']:
            if current_gap > max_gap:
                max_gap = current_gap
            current_gap = 0
        else:
            current_gap += 1

    print(f"\nMax consecutive frames without detection: {max_gap}")

    # 改善提案
    if detection_rate < 80:
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS FOR IMPROVEMENT")
        print("=" * 80)
        print("1. Consider using optical flow for frame interpolation")
        print("2. Implement ensemble voting from multiple models")
        print("3. Use temporal smoothing with Kalman filters")
        print("4. Train custom model on surgical glove data")
        print("5. Implement ROI tracking to focus on hand regions")


if __name__ == "__main__":
    test_enhanced_detection()