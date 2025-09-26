"""自動器具選択・追跡テスト（デモ用）"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoInstrumentSelector:
    """自動で器具領域を選択して追跡デモ"""

    def __init__(self, video_path: str):
        self.video_path = Path(video_path)
        self.cap = cv2.VideoCapture(str(video_path))

        ret, self.first_frame = self.cap.read()
        if not ret:
            raise ValueError("Cannot read video")

        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

    def auto_select_instruments(self):
        """自動で器具領域を選択（デモ用）"""
        h, w = self.first_frame.shape[:2]

        # デモ用の選択領域（実際の器具がある位置）
        selections = [
            {
                'name': 'Left Instrument',
                'rect': (int(w * 0.3), int(h * 0.4), int(w * 0.2), int(h * 0.3)),
                'color': (0, 255, 0)  # 緑
            },
            {
                'name': 'Right Instrument',
                'rect': (int(w * 0.5), int(h * 0.4), int(w * 0.2), int(h * 0.3)),
                'color': (0, 0, 255)  # 赤
            }
        ]

        results = []

        for selection in selections:
            x, y, width, height = selection['rect']

            # マスク作成
            mask = np.zeros(self.first_frame.shape[:2], dtype=np.uint8)
            mask[y:y+height, x:x+width] = 255

            # 特徴点抽出
            gray = cv2.cvtColor(self.first_frame, cv2.COLOR_BGR2GRAY)
            corners = cv2.goodFeaturesToTrack(
                gray,
                maxCorners=30,
                qualityLevel=0.01,
                minDistance=10,
                mask=mask
            )

            if corners is not None and len(corners) > 0:
                results.append({
                    'name': selection['name'],
                    'points': corners,
                    'color': selection['color'],
                    'rect': selection['rect']
                })

                logger.info(f"{selection['name']}: {len(corners)} tracking points")

        return results

    def track_all(self, selections):
        """選択した全器具を追跡"""
        fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/auto_selection_{timestamp}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        # 最初のフレームに選択領域を描画
        vis_frame = self.first_frame.copy()

        for sel in selections:
            # 矩形を描画
            x, y, w, h = sel['rect']
            cv2.rectangle(vis_frame, (x, y), (x+w, y+h), sel['color'], 2)
            cv2.putText(vis_frame, sel['name'], (x, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, sel['color'], 2)

            # 特徴点を描画
            for point in sel['points']:
                px, py = point[0]
                cv2.circle(vis_frame, (int(px), int(py)), 3, sel['color'], -1)

        out.write(vis_frame)

        # トラッキング開始
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 1)
        prev_gray = cv2.cvtColor(self.first_frame, cv2.COLOR_BGR2GRAY)

        # 各選択の追跡状態
        tracking_states = []
        for sel in selections:
            tracking_states.append({
                'name': sel['name'],
                'points': sel['points'].copy(),
                'color': sel['color'],
                'lost': False
            })

        frame_count = 1
        successful_tracks = 0

        logger.info("Starting tracking...")

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            vis_frame = frame.copy()

            active_instruments = 0

            for state in tracking_states:
                if state['lost']:
                    continue

                # Optical Flow
                next_points, status, error = cv2.calcOpticalFlowPyrLK(
                    prev_gray, gray, state['points'], None, **self.lk_params
                )

                if next_points is not None:
                    good_points = next_points[status == 1]

                    if len(good_points) > 5:
                        # 追跡成功
                        active_instruments += 1

                        # 点を描画
                        for point in good_points:
                            px, py = point
                            cv2.circle(vis_frame, (int(px), int(py)), 3, state['color'], -1)

                        # 凸包を描画
                        if len(good_points) > 8:
                            hull = cv2.convexHull(good_points.astype(np.int32))
                            cv2.polylines(vis_frame, [hull], True, state['color'], 2)

                        # ラベル
                        center = np.mean(good_points, axis=0)
                        cv2.putText(vis_frame, state['name'],
                                   (int(center[0]-30), int(center[1]-20)),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, state['color'], 2)

                        # 状態更新
                        state['points'] = good_points.reshape(-1, 1, 2)
                    else:
                        state['lost'] = True
                        logger.warning(f"{state['name']} lost at frame {frame_count}")

            if active_instruments > 0:
                successful_tracks += 1

            # ステータス表示
            cv2.putText(vis_frame, f"Frame: {frame_count}/{total_frames}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(vis_frame, f"Active: {active_instruments}/2",
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            out.write(vis_frame)

            prev_gray = gray
            frame_count += 1

            if frame_count % 50 == 0:
                progress = (frame_count / total_frames) * 100
                logger.info(f"Progress: {progress:.1f}% | Active: {active_instruments}")

        self.cap.release()
        out.release()

        success_rate = (successful_tracks / frame_count) * 100
        logger.info(f"\nTracking completed!")
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info(f"Output saved to: {output_path}")

        return output_path, success_rate

    def simulate_user_selection(self):
        """ユーザー選択をシミュレート（実際にはMediaPipeで手の位置を検出）"""
        import mediapipe as mp

        mp_hands = mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=2,
            min_detection_confidence=0.3
        )

        rgb_frame = cv2.cvtColor(self.first_frame, cv2.COLOR_BGR2RGB)
        hands_result = mp_hands.process(rgb_frame)

        selections = []

        if hands_result.multi_hand_landmarks:
            h, w = self.first_frame.shape[:2]

            for i, hand_landmarks in enumerate(hands_result.multi_hand_landmarks):
                # 手の周辺に器具があると仮定
                hand_points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

                # バウンディングボックス
                x_coords = [p[0] for p in hand_points]
                y_coords = [p[1] for p in hand_points]

                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)

                # 器具は手の延長にあると仮定
                width = x_max - x_min
                height = y_max - y_min

                # 選択領域を手の近くに設定
                selection_rect = (
                    x_min - width // 2,
                    y_min - height // 2,
                    width * 2,
                    height * 2
                )

                # マスク作成
                mask = np.zeros(self.first_frame.shape[:2], dtype=np.uint8)
                x, y, w, h = selection_rect
                x = max(0, x)
                y = max(0, y)
                w = min(w, self.first_frame.shape[1] - x)
                h = min(h, self.first_frame.shape[0] - y)
                mask[y:y+h, x:x+w] = 255

                # 特徴点抽出
                gray = cv2.cvtColor(self.first_frame, cv2.COLOR_BGR2GRAY)
                corners = cv2.goodFeaturesToTrack(
                    gray,
                    maxCorners=30,
                    qualityLevel=0.01,
                    minDistance=10,
                    mask=mask
                )

                if corners is not None and len(corners) > 5:
                    selections.append({
                        'name': f'Instrument {i+1}',
                        'points': corners,
                        'color': (0, 255, 0) if i == 0 else (0, 0, 255),
                        'rect': (x, y, w, h)
                    })

                    logger.info(f"Auto-selected Instrument {i+1}: {len(corners)} points")

        mp_hands.close()
        return selections


def main():
    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")

    if not video_path.exists():
        logger.error(f"Video not found: {video_path}")
        return

    print("\n" + "="*80)
    print("AUTOMATIC INSTRUMENT SELECTION & TRACKING TEST")
    print("="*80)

    selector = AutoInstrumentSelector(str(video_path))

    # MediaPipeベースの自動選択を試みる
    print("\nTrying MediaPipe-based auto selection...")
    selections = selector.simulate_user_selection()

    if not selections:
        print("MediaPipe selection failed, using manual regions...")
        selections = selector.auto_select_instruments()

    if selections:
        print(f"\nSelected {len(selections)} instruments")
        print("Starting tracking...")

        output_path, success_rate = selector.track_all(selections)

        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Output video: {output_path}")

        return output_path, success_rate
    else:
        print("No instruments selected!")
        return None, 0


if __name__ == "__main__":
    main()