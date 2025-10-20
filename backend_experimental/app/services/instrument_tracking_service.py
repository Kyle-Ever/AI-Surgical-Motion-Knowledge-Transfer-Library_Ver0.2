"""器具追跡サービス（改善版）

ユーザーが選択した器具領域を追跡するサービス
- 特徴点の動的な再抽出
- 外れ値除去
- ロスト時のリカバリ機能
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime
import asyncio

from app.core.exceptions import AnalysisError, VideoProcessingError

logger = logging.getLogger(__name__)


class InstrumentTrackingService:
    """器具追跡サービス（改善版）

    ユーザーが選択した器具をOptical Flowで追跡
    特徴点の再抽出とロバストな追跡を実現
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

        # 追跡設定
        self.min_features = 5  # 最小特徴点数
        self.max_features = 100  # 最大特徴点数
        self.redetection_threshold = 30  # 再検出を行う特徴点数の閾値
        self.outlier_percentile = 75  # 外れ値検出用パーセンタイル
        self.roi_expansion = 100  # 再検出ROIの拡張サイズ

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
            特徴点座標 (N, 1, 2)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

        # マスク作成
        mask = np.zeros(gray.shape, dtype=np.uint8)

        if selection['type'] == 'rectangle':
            x, y, w, h = selection['data']
            mask[y:y+h, x:x+w] = 255
        elif selection['type'] == 'polygon':
            points = np.array(selection['data'], dtype=np.int32)
            cv2.fillPoly(mask, [points], 255)
        elif selection['type'] == 'mask':
            mask = selection['data']
        else:
            logger.error(f"Unknown selection type: {selection['type']}")
            return None

        # 特徴点抽出（適応的パラメータ）
        corners = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=self.max_features,
            qualityLevel=0.01,  # より多くの特徴点を取得
            minDistance=10,
            mask=mask,
            blockSize=7
        )

        return corners

    def initialize_tracking_state(
        self,
        video_path: str,
        instruments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """トラッキング状態を初期化

        Args:
            video_path: ビデオファイルパス
            instruments: 器具情報リスト [{
                'id': str,
                'name': str,
                'selection': dict,
                'color': tuple
            }]

        Returns:
            初期化された状態
        """
        cap = cv2.VideoCapture(video_path)
        ret, first_frame = cap.read()

        if not ret:
            cap.release()
            raise VideoProcessingError("Failed to read first frame")

        state = {
            'video_path': video_path,
            'frame_count': 0,
            'instruments': [],
            'prev_gray': cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
        }

        # 各器具の初期特徴点を抽出
        for inst in instruments:
            features = self.extract_features_from_selection(first_frame, inst['selection'])

            if features is not None and len(features) > self.min_features:
                state['instruments'].append({
                    'id': inst['id'],
                    'name': inst['name'],
                    'color': inst.get('color', (255, 0, 0)),
                    'initial_features': features.copy(),
                    'current_features': features,
                    'lost': False,
                    'tracking_history': [],
                    'reinitialized_count': 0,
                    'lost_frames': 0
                })
                logger.info(f"Initialized tracking for {inst['name']} with {len(features)} features")
            else:
                logger.warning(f"Failed to extract features for {inst['name']}")

        cap.release()
        return state

    def remove_outliers(self, points: np.ndarray, percentile: float = 75) -> np.ndarray:
        """外れ値を除去

        Args:
            points: 特徴点座標
            percentile: 外れ値検出用パーセンタイル

        Returns:
            外れ値除去後の特徴点
        """
        if len(points) < 4:
            return points

        # 中央値からの距離でフィルタリング
        median = np.median(points, axis=0)
        distances = np.linalg.norm(points - median, axis=1)
        threshold = np.percentile(distances, percentile) * 1.5

        return points[distances <= threshold]

    def redetect_features(
        self,
        gray: np.ndarray,
        instrument: Dict[str, Any],
        expand: int = 100
    ) -> Optional[np.ndarray]:
        """特徴点を再検出

        Args:
            gray: グレースケール画像
            instrument: 器具情報
            expand: ROI拡張サイズ

        Returns:
            新しい特徴点 or None
        """
        # 最後の既知位置からROIを設定
        if len(instrument['tracking_history']) == 0:
            return None

        last_center = instrument['tracking_history'][-1]['center']
        roi_x = max(0, int(last_center[0] - expand))
        roi_y = max(0, int(last_center[1] - expand))
        roi_w = min(expand * 2, gray.shape[1] - roi_x)
        roi_h = min(expand * 2, gray.shape[0] - roi_y)

        if roi_w <= 0 or roi_h <= 0:
            return None

        roi = gray[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]

        # 特徴点を再検出
        corners = cv2.goodFeaturesToTrack(
            roi,
            maxCorners=self.max_features,
            qualityLevel=0.01,
            minDistance=5,
            blockSize=7
        )

        if corners is not None and len(corners) > self.min_features:
            # ROI座標を画像座標に変換
            corners[:, 0, 0] += roi_x
            corners[:, 0, 1] += roi_y
            return corners

        return None

    async def track_frame(
        self,
        frame: np.ndarray,
        state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """1フレームを追跡

        Args:
            frame: 現在のフレーム
            state: トラッキング状態

        Returns:
            追跡結果リスト
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        prev_gray = state['prev_gray']
        state['frame_count'] += 1

        tracking_results = []

        for instrument in state['instruments']:
            # ロスト状態の場合、再検出を試みる
            if instrument['lost']:
                new_features = self.redetect_features(gray, instrument, self.roi_expansion)

                if new_features is not None:
                    instrument['current_features'] = new_features
                    instrument['lost'] = False
                    instrument['lost_frames'] = 0
                    instrument['reinitialized_count'] += 1
                    logger.info(f"Reinitialized {instrument['name']} with {len(new_features)} features")
                else:
                    instrument['lost_frames'] += 1
                    # ロスト状態でもデータは記録（UIでの連続性のため）
                    if len(instrument['tracking_history']) > 0:
                        last_entry = instrument['tracking_history'][-1]
                        tracking_results.append({
                            'id': instrument['id'],
                            'name': instrument['name'],
                            'center': last_entry['center'],  # 最後の既知位置を使用
                            'points': [],
                            'active': False,
                            'lost_frames': instrument['lost_frames']
                        })
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

                # 外れ値除去
                if len(good_points) > 3:
                    filtered_points = self.remove_outliers(good_points, self.outlier_percentile)
                    if len(filtered_points) >= self.min_features:
                        good_points = filtered_points

                if len(good_points) > self.min_features:
                    # 追跡成功
                    instrument['current_features'] = good_points.reshape(-1, 1, 2)
                    instrument['lost_frames'] = 0

                    # 特徴点が少なくなってきたら補充
                    if len(good_points) < self.redetection_threshold:
                        center = np.mean(good_points, axis=0)
                        roi_x = max(0, int(center[0] - 50))
                        roi_y = max(0, int(center[1] - 50))
                        roi_w = min(100, gray.shape[1] - roi_x)
                        roi_h = min(100, gray.shape[0] - roi_y)

                        if roi_w > 0 and roi_h > 0:
                            roi = gray[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
                            new_corners = cv2.goodFeaturesToTrack(
                                roi,
                                maxCorners=50,
                                qualityLevel=0.05,
                                minDistance=5,
                                blockSize=7
                            )

                            if new_corners is not None:
                                new_corners[:, 0, 0] += roi_x
                                new_corners[:, 0, 1] += roi_y
                                # 既存の特徴点と結合
                                combined = np.vstack([instrument['current_features'], new_corners])
                                # 重複を除去
                                unique_features = []
                                for feat in combined:
                                    is_unique = True
                                    for existing in unique_features:
                                        if np.linalg.norm(feat[0] - existing[0]) < 5:
                                            is_unique = False
                                            break
                                    if is_unique:
                                        unique_features.append(feat)
                                    if len(unique_features) >= self.max_features:
                                        break

                                instrument['current_features'] = np.array(unique_features)

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
                        'active': True,
                        'detected': True
                    })
                else:
                    # 追跡失敗（次フレームで再検出を試みる）
                    instrument['lost'] = True
                    instrument['lost_frames'] = 1

                    # 最後の既知位置を使用してデータを記録
                    if len(instrument['tracking_history']) > 0:
                        last_entry = instrument['tracking_history'][-1]
                        tracking_results.append({
                            'id': instrument['id'],
                            'name': instrument['name'],
                            'center': last_entry['center'],
                            'points': [],
                            'active': False,
                            'detected': False,
                            'reason': 'Tracking lost - will attempt recovery'
                        })

        # 状態更新
        state['prev_gray'] = gray

        return tracking_results

    async def process_video(
        self,
        video_id: str,
        video_path: str,
        instruments: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """ビデオ全体を処理

        Args:
            video_id: ビデオID
            video_path: ビデオファイルパス
            instruments: 器具情報リスト
            progress_callback: 進捗コールバック

        Returns:
            処理結果
        """
        try:
            # 状態初期化
            state = self.initialize_tracking_state(video_path, instruments)
            self.tracking_states[video_id] = state

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise VideoProcessingError(f"Failed to open video: {video_path}")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            results = []
            frame_idx = 0

            # 最初のフレームはスキップ（初期化済み）
            cap.read()
            frame_idx = 1

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # フレーム追跡
                frame_results = await self.track_frame(frame, state)

                # タイムスタンプ付きで結果を保存
                for result in frame_results:
                    result['frame'] = frame_idx
                    result['timestamp'] = frame_idx / fps
                    results.append(result)

                frame_idx += 1

                # 進捗通知
                if progress_callback and frame_idx % 10 == 0:
                    progress = (frame_idx / total_frames) * 100
                    await progress_callback({
                        'progress': progress,
                        'frame': frame_idx,
                        'total_frames': total_frames
                    })

            cap.release()

            # 統計情報を集計
            stats = self.calculate_statistics(state, results)

            return {
                'video_id': video_id,
                'total_frames': total_frames,
                'fps': fps,
                'instruments': len(state['instruments']),
                'tracking_data': results,
                'statistics': stats
            }

        except Exception as e:
            logger.error(f"Error in video processing: {str(e)}")
            raise AnalysisError(f"Failed to process video: {str(e)}")

    def calculate_statistics(
        self,
        state: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """統計情報を計算

        Args:
            state: トラッキング状態
            results: 追跡結果

        Returns:
            統計情報
        """
        stats = {
            'total_instruments': len(state['instruments']),
            'instrument_stats': []
        }

        for instrument in state['instruments']:
            inst_results = [r for r in results if r['id'] == instrument['id']]
            active_frames = [r for r in inst_results if r.get('active', False)]

            inst_stat = {
                'id': instrument['id'],
                'name': instrument['name'],
                'total_frames': len(inst_results),
                'active_frames': len(active_frames),
                'tracking_rate': len(active_frames) / len(inst_results) if inst_results else 0,
                'reinitialized_count': instrument['reinitialized_count'],
                'max_lost_frames': max([r.get('lost_frames', 0) for r in inst_results], default=0)
            }

            # 移動距離計算
            if len(instrument['tracking_history']) > 1:
                total_distance = 0
                for i in range(1, len(instrument['tracking_history'])):
                    prev = np.array(instrument['tracking_history'][i-1]['center'])
                    curr = np.array(instrument['tracking_history'][i]['center'])
                    total_distance += np.linalg.norm(curr - prev)
                inst_stat['total_movement'] = float(total_distance)
                inst_stat['avg_movement_per_frame'] = float(total_distance / len(instrument['tracking_history']))

            stats['instrument_stats'].append(inst_stat)

        return stats

    def visualize_tracking(
        self,
        frame: np.ndarray,
        tracking_results: List[Dict[str, Any]],
        instrument_colors: Optional[Dict[str, tuple]] = None
    ) -> np.ndarray:
        """追跡結果を可視化

        Args:
            frame: フレーム
            tracking_results: 追跡結果
            instrument_colors: 器具の色マッピング

        Returns:
            可視化されたフレーム
        """
        vis_frame = frame.copy()

        for result in tracking_results:
            if not result.get('active', False):
                continue

            color = (255, 0, 0)
            if instrument_colors and result['id'] in instrument_colors:
                color = instrument_colors[result['id']]

            # 特徴点を描画
            if 'points' in result and result['points']:
                points = np.array(result['points'])
                for point in points:
                    cv2.circle(vis_frame, tuple(point.astype(int)), 3, color, -1)

                # 凸包を描画（外れ値除去後）
                if len(points) > 8:
                    # 再度外れ値除去して安定した凸包を作成
                    filtered = self.remove_outliers(points, 80)
                    if len(filtered) > 5:
                        hull = cv2.convexHull(filtered.astype(np.int32))
                        cv2.polylines(vis_frame, [hull], True, color, 2)

            # 中心点とラベル
            if 'center' in result:
                center = tuple(np.array(result['center']).astype(int))
                cv2.circle(vis_frame, center, 5, color, -1)
                cv2.putText(vis_frame, result['name'],
                          (center[0] + 10, center[1] - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return vis_frame