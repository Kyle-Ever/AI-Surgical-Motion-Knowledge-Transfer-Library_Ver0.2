"""インタラクティブな器具選択・追跡テストスクリプト"""

import sys
sys.path.append('.')

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InteractiveInstrumentSelector:
    """マウスで器具を選択して追跡"""

    def __init__(self, video_path: str):
        self.video_path = Path(video_path)
        self.cap = cv2.VideoCapture(str(video_path))

        # 最初のフレームを読み込み
        ret, self.first_frame = self.cap.read()
        if not ret:
            raise ValueError("Cannot read video")

        self.display_frame = self.first_frame.copy()
        self.original_frame = self.first_frame.copy()

        # 選択状態
        self.selection_mode = None  # 'rectangle', 'polygon', 'paint'
        self.selecting = False
        self.selection_points = []
        self.selection_mask = None

        # 矩形選択用
        self.rect_start = None
        self.rect_end = None

        # ペイント選択用
        self.paint_mask = np.zeros(self.first_frame.shape[:2], dtype=np.uint8)
        self.brush_size = 10

        # トラッキング用
        self.tracking_points = None
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

    def mouse_callback(self, event, x, y, flags, param):
        """マウスイベントハンドラ"""

        if self.selection_mode == 'rectangle':
            self.handle_rectangle_selection(event, x, y)
        elif self.selection_mode == 'polygon':
            self.handle_polygon_selection(event, x, y)
        elif self.selection_mode == 'paint':
            self.handle_paint_selection(event, x, y, flags)

    def handle_rectangle_selection(self, event, x, y):
        """矩形選択"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.rect_start = (x, y)
            self.rect_end = (x, y)
            self.selecting = True

        elif event == cv2.EVENT_MOUSEMOVE and self.selecting:
            self.rect_end = (x, y)
            self.display_frame = self.original_frame.copy()
            cv2.rectangle(self.display_frame, self.rect_start, self.rect_end, (0, 255, 0), 2)

        elif event == cv2.EVENT_LBUTTONUP:
            self.selecting = False
            self.rect_end = (x, y)

            # マスク作成
            self.selection_mask = np.zeros(self.first_frame.shape[:2], dtype=np.uint8)
            x1, y1 = min(self.rect_start[0], self.rect_end[0]), min(self.rect_start[1], self.rect_end[1])
            x2, y2 = max(self.rect_start[0], self.rect_end[0]), max(self.rect_start[1], self.rect_end[1])
            self.selection_mask[y1:y2, x1:x2] = 255

            print(f"Rectangle selected: ({x1},{y1}) to ({x2},{y2})")

    def handle_polygon_selection(self, event, x, y):
        """ポリゴン選択"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.selection_points.append((x, y))

            # 点を描画
            self.display_frame = self.original_frame.copy()
            for i, point in enumerate(self.selection_points):
                cv2.circle(self.display_frame, point, 3, (0, 255, 0), -1)
                if i > 0:
                    cv2.line(self.display_frame, self.selection_points[i-1], point, (0, 255, 0), 2)

            # 最初の点と最後の点を結ぶ（閉じる）
            if len(self.selection_points) > 2:
                cv2.line(self.display_frame, self.selection_points[-1],
                        self.selection_points[0], (0, 255, 0), 1)

        elif event == cv2.EVENT_RBUTTONDOWN:  # 右クリックで確定
            if len(self.selection_points) > 2:
                # マスク作成
                self.selection_mask = np.zeros(self.first_frame.shape[:2], dtype=np.uint8)
                points = np.array(self.selection_points, np.int32)
                cv2.fillPoly(self.selection_mask, [points], 255)

                print(f"Polygon selected with {len(self.selection_points)} points")

    def handle_paint_selection(self, event, x, y, flags):
        """ペイント選択"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.selecting = True

        elif event == cv2.EVENT_MOUSEMOVE and self.selecting:
            # ブラシで塗る
            cv2.circle(self.paint_mask, (x, y), self.brush_size, 255, -1)

            # 表示更新
            self.display_frame = self.original_frame.copy()
            colored_mask = np.zeros_like(self.display_frame)
            colored_mask[:, :, 1] = self.paint_mask  # 緑で表示
            self.display_frame = cv2.addWeighted(self.display_frame, 0.7, colored_mask, 0.3, 0)

        elif event == cv2.EVENT_LBUTTONUP:
            self.selecting = False
            self.selection_mask = self.paint_mask.copy()

            print(f"Paint selection completed")

        elif event == cv2.EVENT_MOUSEWHEEL:  # マウスホイールでブラシサイズ変更
            if flags > 0:
                self.brush_size = min(50, self.brush_size + 2)
            else:
                self.brush_size = max(2, self.brush_size - 2)
            print(f"Brush size: {self.brush_size}")

    def extract_tracking_points(self):
        """選択領域から追跡点を抽出"""
        if self.selection_mask is None:
            print("No selection made!")
            return False

        # 特徴点を検出
        # 1. マスク内のエッジを検出
        gray = cv2.cvtColor(self.first_frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        masked_edges = cv2.bitwise_and(edges, self.selection_mask)

        # 2. Harris コーナー検出
        corners = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=50,
            qualityLevel=0.01,
            minDistance=10,
            mask=self.selection_mask
        )

        if corners is not None and len(corners) > 0:
            self.tracking_points = corners
            print(f"Extracted {len(corners)} tracking points")

            # 追跡点を表示
            for corner in corners:
                x, y = corner[0]
                cv2.circle(self.display_frame, (int(x), int(y)), 3, (255, 0, 0), -1)

            return True
        else:
            print("No tracking points found in selection!")
            return False

    def track_instrument(self):
        """選択した器具を全フレームで追跡"""
        if self.tracking_points is None:
            print("No tracking points to track!")
            return

        # 出力動画の設定
        fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/results/interactive_test_{timestamp}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        # 最初のフレームを書き込み
        vis_frame = self.first_frame.copy()
        for point in self.tracking_points:
            x, y = point[0]
            cv2.circle(vis_frame, (int(x), int(y)), 3, (0, 255, 0), -1)
        out.write(vis_frame)

        # トラッキング開始
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 1)  # 2フレーム目から
        prev_gray = cv2.cvtColor(self.first_frame, cv2.COLOR_BGR2GRAY)
        prev_points = self.tracking_points.copy()

        frame_count = 1
        lost_count = 0

        print("\nTracking started...")

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Optical Flow
            next_points, status, error = cv2.calcOpticalFlowPyrLK(
                prev_gray, gray, prev_points, None, **self.lk_params
            )

            if next_points is not None:
                # 有効な点のみ保持
                good_points = next_points[status == 1]

                if len(good_points) > 3:  # 最低3点必要
                    # 可視化
                    vis_frame = frame.copy()

                    # 点を描画
                    for point in good_points:
                        x, y = point
                        cv2.circle(vis_frame, (int(x), int(y)), 3, (0, 255, 0), -1)

                    # 凸包を描画（器具の輪郭として）
                    if len(good_points) > 5:
                        hull = cv2.convexHull(good_points.astype(np.int32))
                        cv2.polylines(vis_frame, [hull], True, (0, 255, 255), 2)

                    # ステータス表示
                    cv2.putText(vis_frame, f"Frame: {frame_count}/{total_frames}",
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(vis_frame, f"Points: {len(good_points)}",
                               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    out.write(vis_frame)

                    # 次フレーム用に更新
                    prev_gray = gray
                    prev_points = good_points.reshape(-1, 1, 2)
                else:
                    lost_count += 1
                    print(f"Lost tracking at frame {frame_count} (only {len(good_points)} points)")
                    out.write(frame)

            frame_count += 1

            # 進捗表示
            if frame_count % 50 == 0:
                progress = (frame_count / total_frames) * 100
                print(f"Progress: {progress:.1f}%")

        self.cap.release()
        out.release()

        success_rate = (frame_count - lost_count) / frame_count * 100
        print(f"\nTracking completed!")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Output saved to: {output_path}")

    def run(self):
        """メインループ"""
        cv2.namedWindow('Instrument Selection')
        cv2.setMouseCallback('Instrument Selection', self.mouse_callback)

        print("\n" + "="*80)
        print("INTERACTIVE INSTRUMENT SELECTION")
        print("="*80)
        print("\nInstructions:")
        print("1. Press 'r' for Rectangle selection (drag to select)")
        print("2. Press 'p' for Polygon selection (click points, right-click to finish)")
        print("3. Press 'm' for Paint/Mask selection (draw with mouse)")
        print("4. Press 'c' to clear selection")
        print("5. Press 'SPACE' to confirm selection and start tracking")
        print("6. Press 'ESC' to exit")
        print("\nFor paint mode: Use mouse wheel to change brush size")
        print("="*80)

        while True:
            cv2.imshow('Instrument Selection', self.display_frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('r'):
                self.selection_mode = 'rectangle'
                self.reset_selection()
                print("\nRectangle selection mode")

            elif key == ord('p'):
                self.selection_mode = 'polygon'
                self.reset_selection()
                print("\nPolygon selection mode")

            elif key == ord('m'):
                self.selection_mode = 'paint'
                self.reset_selection()
                print("\nPaint selection mode (brush size: {})".format(self.brush_size))

            elif key == ord('c'):
                self.reset_selection()
                print("\nSelection cleared")

            elif key == 32:  # SPACE
                if self.extract_tracking_points():
                    cv2.imshow('Instrument Selection', self.display_frame)
                    cv2.waitKey(1000)  # 追跡点を1秒表示

                    print("\nStarting tracking...")
                    cv2.destroyAllWindows()
                    self.track_instrument()
                    break

            elif key == 27:  # ESC
                print("\nExiting...")
                break

        cv2.destroyAllWindows()

    def reset_selection(self):
        """選択をリセット"""
        self.display_frame = self.original_frame.copy()
        self.selection_points = []
        self.selection_mask = None
        self.paint_mask = np.zeros(self.first_frame.shape[:2], dtype=np.uint8)
        self.rect_start = None
        self.rect_end = None
        self.selecting = False


def main():
    video_path = Path("C:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/data/uploads/VID_20250926_123049.mp4")

    if not video_path.exists():
        logger.error(f"Video not found: {video_path}")
        return

    selector = InteractiveInstrumentSelector(str(video_path))
    selector.run()


if __name__ == "__main__":
    main()