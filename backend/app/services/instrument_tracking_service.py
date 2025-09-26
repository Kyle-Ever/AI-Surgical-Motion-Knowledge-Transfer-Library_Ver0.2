"""器具追跡サービス

ユーザーが選択した器具領域を追跡するサービス
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class InstrumentTrackingService:
    """器具追跡サービス

    ユーザーが選択した器具をOptical Flowで追跡
    """

    def __init__(self):
        # Optical Flow パラメータ
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

        # トラッキング状態
        self.tracking_states: Dict[str, Any] = {}

    def extract_features_from_selection(
        self,
        frame: np.ndarray,
        selection: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """選択領域から特徴点を抽出

        Args:
            frame: ビデオフレーム
            selection: 選択情報 {
                'type': 'rectangle' | 'polygon' | 'mask',
                'data': 選択データ
            }

        Returns:
            特徴点の配列
        """
        # マスク作成
        mask = self._create_mask_from_selection(frame.shape[:2], selection)

        if mask is None:
            return None

        # グレースケール変換
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 特徴点抽出
        corners = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=50,
            qualityLevel=0.01,
            minDistance=10,
            mask=mask
        )

        return corners

    def _create_mask_from_selection(
        self,
        shape: Tuple[int, int],
        selection: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """選択情報からマスクを作成

        Args:
            shape: フレームの形状 (height, width)
            selection: 選択情報

        Returns:
            マスク画像
        """
        mask = np.zeros(shape, dtype=np.uint8)

        sel_type = selection.get('type')
        data = selection.get('data')

        if sel_type == 'rectangle':
            # 矩形選択
            x, y, w, h = data['x'], data['y'], data['width'], data['height']
            mask[y:y+h, x:x+w] = 255

        elif sel_type == 'polygon':
            # ポリゴン選択
            points = np.array(data['points'], np.int32)
            cv2.fillPoly(mask, [points], 255)

        elif sel_type == 'mask':
            # マスク直接指定
            mask = np.array(data['mask'], dtype=np.uint8)

        else:
            logger.error(f"Unknown selection type: {sel_type}")
            return None

        return mask

    async def initialize_tracking(
        self,
        video_path: str,
        selections: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """追跡の初期化

        Args:
            video_path: ビデオファイルパス
            selections: 器具選択情報のリスト

        Returns:
            初期化結果
        """
        cap = cv2.VideoCapture(video_path)
        ret, first_frame = cap.read()

        if not ret:
            return {
                'success': False,
                'error': 'Cannot read video'
            }

        # 各選択領域から特徴点を抽出
        instruments = []

        for i, selection in enumerate(selections):
            features = self.extract_features_from_selection(first_frame, selection)

            if features is not None and len(features) > 0:
                instrument = {
                    'id': selection.get('id', f'instrument_{i}'),
                    'name': selection.get('name', f'Instrument {i+1}'),
                    'initial_features': features,
                    'current_features': features.copy(),
                    'color': selection.get('color', (0, 255, 0)),
                    'lost': False,
                    'tracking_history': []
                }
                instruments.append(instrument)

                logger.info(f"Initialized {instrument['name']} with {len(features)} features")

        # トラッキング状態を保存
        tracking_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.tracking_states[tracking_id] = {
            'video_path': video_path,
            'cap': cap,
            'first_frame': first_frame,
            'instruments': instruments,
            'frame_count': 0,
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        }

        cap.release()

        return {
            'success': True,
            'tracking_id': tracking_id,
            'instruments_count': len(instruments),
            'total_frames': self.tracking_states[tracking_id]['total_frames']
        }

    async def track_frame(
        self,
        tracking_id: str,
        frame_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """特定フレームで追跡

        Args:
            tracking_id: 追跡ID
            frame_number: フレーム番号（Noneの場合は次のフレーム）

        Returns:
            追跡結果
        """
        if tracking_id not in self.tracking_states:
            return {'success': False, 'error': 'Invalid tracking ID'}

        state = self.tracking_states[tracking_id]

        # ビデオキャプチャを再オープン（必要な場合）
        if state.get('cap') is None:
            state['cap'] = cv2.VideoCapture(state['video_path'])

        cap = state['cap']

        # フレーム位置設定
        if frame_number is not None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        # フレーム読み込み
        ret, frame = cap.read()
        if not ret:
            return {'success': False, 'error': 'Cannot read frame'}

        # グレースケール変換
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 前フレームのグレースケール取得
        if state['frame_count'] == 0:
            prev_gray = cv2.cvtColor(state['first_frame'], cv2.COLOR_BGR2GRAY)
        else:
            prev_gray = state.get('prev_gray')

        # 各器具を追跡
        tracking_results = []

        for instrument in state['instruments']:
            if instrument['lost']:
                continue

            # Optical Flow計算
            loop = asyncio.get_event_loop()
            next_points, status, error = await loop.run_in_executor(
                None,
                cv2.calcOpticalFlowPyrLK,
                prev_gray, gray, instrument['current_features'], None, **self.lk_params
            )

            if next_points is not None:
                good_points = next_points[status == 1]

                if len(good_points) > 5:
                    # 追跡成功
                    instrument['current_features'] = good_points.reshape(-1, 1, 2)

                    # 重心計算
                    center = np.mean(good_points, axis=0)

                    # 履歴に追加
                    instrument['tracking_history'].append({
                        'frame': state['frame_count'],
                        'center': center.tolist(),
                        'points_count': len(good_points)
                    })

                    tracking_results.append({
                        'id': instrument['id'],
                        'name': instrument['name'],
                        'center': center.tolist(),
                        'points': good_points.tolist(),
                        'active': True
                    })
                else:
                    # 追跡失敗
                    instrument['lost'] = True
                    tracking_results.append({
                        'id': instrument['id'],
                        'name': instrument['name'],
                        'active': False,
                        'reason': 'Too few points'
                    })

        # 状態更新
        state['prev_gray'] = gray
        state['frame_count'] += 1

        return {
            'success': True,
            'frame_number': state['frame_count'],
            'tracking_results': tracking_results
        }

    async def process_video(
        self,
        tracking_id: str,
        output_path: Optional[str] = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """ビデオ全体を処理

        Args:
            tracking_id: 追跡ID
            output_path: 出力ビデオパス
            progress_callback: 進捗コールバック

        Returns:
            処理結果
        """
        if tracking_id not in self.tracking_states:
            return {'success': False, 'error': 'Invalid tracking ID'}

        state = self.tracking_states[tracking_id]

        # ビデオキャプチャを再オープン
        cap = cv2.VideoCapture(state['video_path'])
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = state['total_frames']

        # 出力設定
        out = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        # リセット
        state['frame_count'] = 0
        for instrument in state['instruments']:
            instrument['current_features'] = instrument['initial_features'].copy()
            instrument['lost'] = False
            instrument['tracking_history'] = []

        # 最初のフレーム処理
        ret, first_frame = cap.read()
        if not ret:
            return {'success': False, 'error': 'Cannot read first frame'}

        prev_gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)

        # 処理ループ
        successful_tracks = 0

        for frame_idx in range(1, total_frames):
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            vis_frame = frame.copy() if output_path else None

            active_count = 0

            # 各器具を追跡
            for instrument in state['instruments']:
                if instrument['lost']:
                    continue

                # Optical Flow（同期実行）
                next_points, status, error = cv2.calcOpticalFlowPyrLK(
                    prev_gray, gray, instrument['current_features'], None, **self.lk_params
                )

                if next_points is not None:
                    good_points = next_points[status == 1]

                    if len(good_points) > 5:
                        active_count += 1
                        instrument['current_features'] = good_points.reshape(-1, 1, 2)

                        # 可視化
                        if vis_frame is not None:
                            for point in good_points:
                                cv2.circle(vis_frame, tuple(point.astype(int)), 3, instrument['color'], -1)

                            # 凸包描画
                            if len(good_points) > 8:
                                hull = cv2.convexHull(good_points.astype(np.int32))
                                cv2.polylines(vis_frame, [hull], True, instrument['color'], 2)
                    else:
                        instrument['lost'] = True

            if active_count > 0:
                successful_tracks += 1

            # 出力
            if out and vis_frame is not None:
                # ステータス表示
                cv2.putText(vis_frame, f"Frame: {frame_idx}/{total_frames}",
                          (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(vis_frame, f"Active: {active_count}/{len(state['instruments'])}",
                          (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                out.write(vis_frame)

            prev_gray = gray

            # 進捗通知
            if progress_callback and frame_idx % 10 == 0:
                await progress_callback({
                    'frame': frame_idx,
                    'total': total_frames,
                    'progress': (frame_idx / total_frames) * 100,
                    'active_instruments': active_count
                })

        # クリーンアップ
        cap.release()
        if out:
            out.release()

        success_rate = (successful_tracks / total_frames) * 100 if total_frames > 0 else 0

        return {
            'success': True,
            'frames_processed': total_frames,
            'success_rate': success_rate,
            'output_path': output_path
        }

    def cleanup(self, tracking_id: str):
        """トラッキング状態のクリーンアップ

        Args:
            tracking_id: 追跡ID
        """
        if tracking_id in self.tracking_states:
            state = self.tracking_states[tracking_id]
            if state.get('cap'):
                state['cap'].release()
            del self.tracking_states[tracking_id]