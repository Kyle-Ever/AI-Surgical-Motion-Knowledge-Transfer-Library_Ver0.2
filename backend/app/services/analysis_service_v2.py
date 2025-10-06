"""
Analysis Service V2 - Clean architecture implementation
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
import json

from app.models import SessionLocal
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.models.video import Video, VideoType
from app.core.websocket import manager
from app.core.config import settings
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
from app.ai_engine.processors.sam2_tracker import SAM2Tracker
from .metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)


def convert_numpy_types(obj):
    """
    Convert numpy types to Python native types for JSON serialization

    Args:
        obj: Object potentially containing numpy types

    Returns:
        Object with all numpy types converted to Python native types
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj


class AnalysisServiceV2:
    """
    クリーンアーキテクチャに基づく解析サービス
    責務の分離と拡張性を重視
    """

    def __init__(self):
        self.detectors = {}
        self.video_info = {}
        self.warnings = []  # Phase 2.2: 警告収集用
        self.tracking_stats = {}  # Phase 2.2: トラッキング統計収集用
        # SAM2使用フラグ（環境変数 USE_SAM2=true で有効化）
        self.use_sam2 = getattr(settings, 'USE_SAM2', False)

    async def analyze_video(
        self,
        video_id: str,
        analysis_id: str,
        instruments: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        動画解析のメインエントリーポイント

        Args:
            video_id: 動画ID
            analysis_id: 解析ID
            instruments: 器具定義（オプション）

        Returns:
            解析結果の辞書
        """
        logger.info(f"[ANALYSIS] === Starting V2 analysis ===")
        logger.info(f"[ANALYSIS] video_id: {video_id}")
        logger.info(f"[ANALYSIS] analysis_id: {analysis_id}")
        logger.info(f"[ANALYSIS] instruments: {instruments}")

        db = SessionLocal()
        try:
            # 1. 解析レコードと動画情報の取得
            analysis_result = db.query(AnalysisResult).filter(
                AnalysisResult.id == analysis_id
            ).first()

            if not analysis_result:
                raise ValueError(f"Analysis not found: {analysis_id}")

            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError(f"Video not found: {video_id}")

            # Convert relative path to absolute path from backend directory
            video_path = Path(video.file_path)
            if not video_path.is_absolute():
                # Assume file_path is relative to backend directory
                backend_dir = Path(__file__).parent.parent.parent  # backend/
                video_path = backend_dir / video_path

            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")

            # 2. 動画タイプに基づく処理戦略の決定
            video_type = video.video_type
            logger.info(f"[ANALYSIS] Video type: {video_type}")
            logger.info(f"[ANALYSIS] Video path: {video.file_path}")

            # 3. 動画情報の取得
            logger.info(f"[ANALYSIS] Getting video info...")
            await self._update_status(analysis_result, "initialization", db, progress=5)
            self.video_info = self._get_video_info(str(video_path))
            logger.info(f"[ANALYSIS] Video info retrieved")
            await self._update_status(analysis_result, "initialization", db, progress=10)
            logger.info(f"[ANALYSIS] Status updated to initialization")

            # 4. フレーム抽出
            logger.info(f"[ANALYSIS] Starting frame extraction...")
            await self._update_status(analysis_result, "frame_extraction", db, progress=15)
            frames = await self._extract_frames(video_path)
            logger.info(f"[ANALYSIS] Extracted {len(frames)} frames")
            await self._update_status(analysis_result, "frame_extraction", db, progress=30)

            # 5. 検出処理の実行
            logger.info(f"[ANALYSIS] Starting detection...")
            await self._update_status(analysis_result, "skeleton_detection", db, progress=35)
            detection_results = await self._run_detection(
                frames, video_type, video_id, instruments
            )
            logger.info(f"[ANALYSIS] Detection completed with {len(detection_results) if detection_results else 0} results")
            await self._update_status(analysis_result, "instrument_detection", db, progress=60)

            # 6. メトリクス計算
            await self._update_status(analysis_result, "motion_analysis", db, progress=70)
            metrics = await self._calculate_metrics(detection_results)
            await self._update_status(analysis_result, "motion_analysis", db, progress=80)

            # 7. スコアリング
            await self._update_status(analysis_result, "report_generation", db, progress=85)
            scores = await self._calculate_scores(metrics)

            # 8. 結果の保存
            await self._update_status(analysis_result, "report_generation", db, progress=90)
            await self._save_results(
                analysis_result, detection_results, metrics, scores, db
            )
            await self._update_status(analysis_result, "report_generation", db, progress=95)

            # 9. 完了通知
            await self._update_status(analysis_result, "completed", db, progress=100)

            return {
                'status': 'success',
                'video_id': video_id,
                'analysis_id': analysis_id,
                'detection_results': detection_results,
                'metrics': metrics,
                'scores': scores
            }

        except Exception as e:
            logger.error(f"[ANALYSIS] Analysis failed: {str(e)}")
            logger.error(f"[ANALYSIS] Error type: {type(e).__name__}")
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"[ANALYSIS] Traceback: {error_traceback}")

            if analysis_result:
                # Phase 2.2: エラー情報を詳細に記録
                analysis_result.status = AnalysisStatus.FAILED
                analysis_result.error_message = f"{type(e).__name__}: {str(e)}"

                # 収集した警告があれば保存
                if self.warnings:
                    analysis_result.warnings = json.dumps(self.warnings)
                    logger.info(f"[ANALYSIS] Saved {len(self.warnings)} warnings to DB")

                # トラッキング統計があれば保存
                if self.tracking_stats:
                    analysis_result.tracking_stats = json.dumps(self.tracking_stats)
                    logger.info(f"[ANALYSIS] Saved tracking stats to DB: {list(self.tracking_stats.keys())}")

                db.commit()

                # WebSocketで詳細エラー情報を送信
                try:
                    await manager.send_update(analysis_id, {
                        "type": "error",
                        "error_type": type(e).__name__,
                        "message": str(e),
                        "warnings_count": len(self.warnings),
                        "tracking_stats": self.tracking_stats
                    })
                except:
                    pass  # WebSocket送信失敗は無視

            raise
        finally:
            db.close()
            # 検出器のクリーンアップ
            for detector in self.detectors.values():
                if hasattr(detector, 'close'):
                    detector.close()

    def _get_video_info(self, video_path: str) -> Dict:
        """動画情報を取得"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        info = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': 0
        }

        # FPSが不正な場合のフォールバック
        if info['fps'] <= 0:
            logger.warning(f"[ANALYSIS] Invalid FPS ({info['fps']}), using default 30fps")
            info['fps'] = 30.0

        # 動画の長さを正確に計算
        info['duration'] = info['total_frames'] / info['fps']

        cap.release()
        logger.info(f"[ANALYSIS] Video info: {info}")
        return info

    async def _extract_frames(self, video_path: Path, target_fps: int = 5) -> List[np.ndarray]:
        """
        動画からフレームを抽出

        Args:
            video_path: 動画ファイルパス
            target_fps: 抽出するFPS（デフォルト5fps）

        Returns:
            フレームのリスト
        """
        logger.info(f"[ANALYSIS] _extract_frames started: video_path={video_path}, target_fps={target_fps}")
        frames = []
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            logger.error(f"[ANALYSIS] Cannot open video: {video_path}")
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(f"[ANALYSIS] Video: fps={fps}, total_frames={total_frames}")

        # フレームスキップ数を計算
        frame_skip = max(1, int(fps / target_fps))
        logger.info(f"[ANALYSIS] Frame skip: {frame_skip}")

        # フレームを直接指定位置から読み取る方式に変更
        frame_indices = list(range(0, total_frames, frame_skip))
        logger.info(f"[ANALYSIS] Will extract {len(frame_indices)} frames from total {total_frames} frames")  # Updated

        extracted_count = 0
        failed_frames = []

        for idx, frame_idx in enumerate(frame_indices):
            # 指定フレームにジャンプ
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if ret and frame is not None:
                frames.append(frame)
                extracted_count += 1

                # 進捗ログ（10フレームごと）
                if extracted_count % 10 == 0 or extracted_count == len(frame_indices):
                    progress = (idx + 1) / len(frame_indices) * 100
                    logger.info(f"[ANALYSIS] Extracted {extracted_count}/{len(frame_indices)} frames ({progress:.1f}%)")
            else:
                failed_frames.append(frame_idx)
                logger.warning(f"[ANALYSIS] Failed to read frame {frame_idx}")

        if failed_frames:
            logger.warning(f"[ANALYSIS] Failed to read {len(failed_frames)} frames: {failed_frames[:10]}...")

        cap.release()
        logger.info(f"[ANALYSIS] Frame extraction completed: {extracted_count} frames extracted")
        return frames

    def _convert_instruments_format(self, instruments: List[Dict]) -> List[Dict]:
        """
        保存されたinstruments形式をSAMTrackerUnified用に変換

        Input: [{"name": str, "bbox": [x,y,w,h], "frame_number": int, "mask": str}]
        Output: [{"id": int, "name": str, "selection": {"type": "mask"|"box", "data": ...}, "color": str}]

        Args:
            instruments: 保存されたinstruments形式のリスト

        Returns:
            SAMTrackerUnified用に変換されたinstrumentsリスト
        """
        converted = []
        colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"]

        for idx, inst in enumerate(instruments):
            # マスクデータがある場合は優先的に使用（最も正確）
            if "mask" in inst and inst["mask"]:
                logger.info(f"[ANALYSIS] Instrument {idx} using mask-based initialization")
                converted.append({
                    "id": idx,
                    "name": inst.get("name", f"Instrument {idx + 1}"),
                    "selection": {
                        "type": "mask",
                        "data": inst["mask"]  # base64エンコードされたマスク
                    },
                    "color": inst.get("color", colors[idx % len(colors)])
                })
            # マスクがない場合はbboxにフォールバック
            elif "bbox" in inst:
                x, y, w, h = inst["bbox"]
                bbox_xyxy = [x, y, x + w, y + h]
                logger.info(f"[ANALYSIS] Instrument {idx} using box-based initialization (fallback)")
                converted.append({
                    "id": idx,
                    "name": inst.get("name", f"Instrument {idx + 1}"),
                    "selection": {
                        "type": "box",
                        "data": bbox_xyxy
                    },
                    "color": inst.get("color", colors[idx % len(colors)])
                })
            elif "selection" in inst and inst["selection"].get("type") == "box":
                # 既に変換済みの場合はそのまま使用
                bbox_xyxy = inst["selection"]["data"]
                logger.info(f"[ANALYSIS] Instrument {idx} using pre-converted box format")
                converted.append({
                    "id": idx,
                    "name": inst.get("name", f"Instrument {idx + 1}"),
                    "selection": {
                        "type": "box",
                        "data": bbox_xyxy
                    },
                    "color": inst.get("color", colors[idx % len(colors)])
                })
            else:
                logger.warning(f"[ANALYSIS] Instrument {idx} has no valid bbox or mask, skipping")
                continue

        logger.info(f"[ANALYSIS] Converted {len(converted)} instruments from saved format to SAM format")
        return converted

    async def _run_detection(
        self,
        frames: List[np.ndarray],
        video_type: VideoType,
        video_id: str,
        instruments: Optional[List[Dict]]
    ) -> Dict[str, Any]:
        """
        動画タイプに基づく検出処理の実行

        Args:
            frames: フレームリスト
            video_type: 動画タイプ
            video_id: 動画ID
            instruments: 器具定義

        Returns:
            検出結果
        """
        logger.info(f"[ANALYSIS] _run_detection started: video_type={video_type}, frames={len(frames)}")
        results = {
            'skeleton_data': [],
            'instrument_data': []
        }

        # 動画タイプに基づく検出器の選択
        if video_type in [VideoType.EXTERNAL, VideoType.EXTERNAL_NO_INSTRUMENTS]:
            # 骨格検出のみ
            logger.info(f"[ANALYSIS] Running MediaPipe detection only (no instruments) for video_type: {video_type}")
            detector = HandSkeletonDetector(min_detection_confidence=0.1)
            self.detectors['mediapipe'] = detector

            logger.info(f"[ANALYSIS] Starting MediaPipe batch detection on {len(frames)} frames")
            skeleton_results = detector.detect_batch(frames)
            logger.info(f"[ANALYSIS] MediaPipe detection completed, got {len(skeleton_results)} results")

            # デバッグ：最初の結果を確認
            if skeleton_results and len(skeleton_results) > 0:
                first_result = skeleton_results[0]
                # 型を確認してからアクセス
                if isinstance(first_result, dict):
                    logger.info(f"[ANALYSIS] First skeleton result: detected={first_result.get('detected')}, hands={len(first_result.get('hands', []))}")
                else:
                    logger.warning(f"[ANALYSIS] First skeleton result is not dict: type={type(first_result)}")

            results['skeleton_data'] = self._format_skeleton_data(skeleton_results)
            logger.info(f"[ANALYSIS] Formatted {len(results['skeleton_data'])} skeleton data points")

        elif video_type == VideoType.EXTERNAL_WITH_INSTRUMENTS:
            # 骨格検出と器具検出の両方
            logger.info("[ANALYSIS] Running both MediaPipe and SAM detection")

            # MediaPipe検出
            mediapipe_detector = HandSkeletonDetector(min_detection_confidence=0.1)
            self.detectors['mediapipe'] = mediapipe_detector
            skeleton_results = mediapipe_detector.detect_batch(frames)

            # デバッグ：最初の結果を確認
            if skeleton_results and len(skeleton_results) > 0:
                first_result = skeleton_results[0]
                if isinstance(first_result, dict):
                    logger.info(f"[ANALYSIS] First skeleton result: detected={first_result.get('detected')}, hands={len(first_result.get('hands', []))}")
                else:
                    logger.warning(f"[ANALYSIS] First skeleton result is not dict: type={type(first_result)}")

            results['skeleton_data'] = self._format_skeleton_data(skeleton_results)

            # SAM検出（一本化実装）
            device = getattr(settings, 'SAM_DEVICE', 'cpu')
            if device == 'auto':
                import torch
                device = 'cuda' if torch.cuda.is_available() else 'cpu'

            fps = self.video_info.get('fps', 30.0)
            target_fps = 5.0  # フレーム抽出時のFPS

            # SAM2またはSAM1を選択
            if self.use_sam2:
                logger.info(f"[ANALYSIS] Creating SAM2Tracker with model=small, device={device}")
                sam_detector = SAM2Tracker(model_type="small", device=device)
                logger.info("[ANALYSIS] SAM2 enabled for higher accuracy (+2% Dice, -21% HD95)")
            else:
                logger.info(f"[ANALYSIS] Creating SAMTrackerUnified with model=vit_h, device={device}, instruments={len(instruments) if instruments else 0}, fps={fps}, target_fps={target_fps}")
                # GPU対応: vit_hモデルを使用（RTX 3060で高速・高精度）
                sam_detector = SAMTrackerUnified(model_type="vit_h", device=device)

            self.detectors['sam'] = sam_detector

            # 器具の初期化
            if instruments and len(instruments) > 0 and len(frames) > 0:
                try:
                    # 保存形式からSAM形式に変換
                    instruments_converted = self._convert_instruments_format(instruments)
                    logger.info(f"[ANALYSIS] Initializing {len(instruments_converted)} instruments from user selection")
                    sam_detector.initialize_instruments(frames[0], instruments_converted)
                except Exception as e:
                    logger.error(f"[ANALYSIS] Failed to initialize instruments from user selection: {e}")
                    logger.info("[ANALYSIS] Falling back to automatic instrument detection")
                    sam_detector.auto_detect_instruments(frames[0], max_instruments=5)
            elif len(frames) > 0:
                logger.info("[ANALYSIS] No user selection, using automatic instrument detection")
                sam_detector.auto_detect_instruments(frames[0], max_instruments=5)
            else:
                logger.warning("[ANALYSIS] No frames available for instrument initialization")

            logger.info(f"[ANALYSIS] Running SAM detect_batch on {len(frames)} frames...")
            instrument_results = sam_detector.detect_batch(frames)
            logger.info(f"[ANALYSIS] SAM detection completed, got {len(instrument_results)} results")

            # デバッグ：最初の結果を確認
            if instrument_results and len(instrument_results) > 0:
                first_result = instrument_results[0]
                # 型を確認してからアクセス
                if isinstance(first_result, dict):
                    logger.info(f"[ANALYSIS] First instrument result: detected={first_result.get('detected')}, instruments={len(first_result.get('instruments', []))}")
                else:
                    logger.warning(f"[ANALYSIS] First instrument result is not dict: type={type(first_result)}")

            results['instrument_data'] = self._format_instrument_data(instrument_results)
            logger.info(f"[ANALYSIS] Formatted instrument data: {len(results['instrument_data'])} frames with detections")

            # Phase 2.2: トラッキング統計を収集
            self._collect_tracking_stats(sam_detector, instrument_results)

        elif video_type == VideoType.INTERNAL:
            # 内視鏡：器具検出のみ
            logger.info("[ANALYSIS] Running SAM detection only (internal camera)")
            device = getattr(settings, 'SAM_DEVICE', 'cpu')
            if device == 'auto':
                import torch
                device = 'cuda' if torch.cuda.is_available() else 'cpu'

            fps = self.video_info.get('fps', 30.0)
            target_fps = 5.0  # フレーム抽出時のFPS

            # SAM2またはSAM1を選択
            if self.use_sam2:
                logger.info(f"[ANALYSIS] Creating SAM2Tracker with model=small, device={device}")
                detector = SAM2Tracker(model_type="small", device=device)
                logger.info("[ANALYSIS] SAM2 enabled for higher accuracy (+2% Dice, -21% HD95)")
            else:
                logger.info(f"[ANALYSIS] Creating SAMTrackerUnified with model=vit_h, device={device}")
                # GPU対応: vit_hモデルを使用（RTX 3060で高速・高精度）
                detector = SAMTrackerUnified(model_type="vit_h", device=device)

            self.detectors['sam'] = detector

            # 器具の初期化
            if instruments and len(instruments) > 0 and len(frames) > 0:
                try:
                    # 保存形式からSAM形式に変換
                    instruments_converted = self._convert_instruments_format(instruments)
                    logger.info(f"[ANALYSIS] Initializing {len(instruments_converted)} instruments from user selection")
                    detector.initialize_instruments(frames[0], instruments_converted)
                except Exception as e:
                    logger.error(f"[ANALYSIS] Failed to initialize instruments from user selection: {e}")
                    logger.info("[ANALYSIS] Falling back to automatic instrument detection")
                    detector.auto_detect_instruments(frames[0], max_instruments=5)
            elif len(frames) > 0:
                logger.info("[ANALYSIS] No user selection, using automatic instrument detection for INTERNAL video")
                detector.auto_detect_instruments(frames[0], max_instruments=5)
            else:
                logger.warning("[ANALYSIS] No frames available for instrument initialization")

            instrument_results = detector.detect_batch(frames)
            results['instrument_data'] = self._format_instrument_data(instrument_results)

            # Phase 2.2: トラッキング統計を収集
            self._collect_tracking_stats(detector, instrument_results)

        else:
            logger.warning(f"Unknown video type: {video_type}, defaulting to MediaPipe only")
            detector = HandSkeletonDetector(min_detection_confidence=0.1)
            self.detectors['mediapipe'] = detector

            skeleton_results = detector.detect_batch(frames)

            # デバッグ：最初の結果を確認
            if skeleton_results and len(skeleton_results) > 0:
                first_result = skeleton_results[0]
                if isinstance(first_result, dict):
                    logger.info(f"[ANALYSIS] First skeleton result: detected={first_result.get('detected')}, hands={len(first_result.get('hands', []))}")
                else:
                    logger.warning(f"[ANALYSIS] First skeleton result is not dict: type={type(first_result)}")

            results['skeleton_data'] = self._format_skeleton_data(skeleton_results)

        return results

    def _format_skeleton_data(self, raw_results: List[Dict]) -> List[Dict]:
        """骨格検出結果をフォーマット（フロントエンド互換形式）"""
        from collections import defaultdict

        # フレームごとにグループ化
        frames_dict = defaultdict(list)
        fps = self.video_info.get('fps', 30)
        target_fps = 5  # デフォルトの抽出レート
        frame_skip = max(1, int(fps / target_fps))

        for result in raw_results:
            # 型チェック
            if not isinstance(result, dict):
                logger.warning(f"Skipping non-dict result: type={type(result)}")
                continue
            if result.get('detected'):
                # Fail Fast: frame_indexが存在しない場合はエラー
                if 'frame_index' not in result:
                    error_msg = f"Missing frame_index in skeleton detection result. Result keys: {list(result.keys())}"
                    logger.error(error_msg)
                    raise ValueError(f"skeleton_detector.detect_batch() must include frame_index in results. {error_msg}")

                frame_idx = result['frame_index']
                # 実際のフレーム番号を計算
                actual_frame_number = frame_idx * frame_skip
                timestamp = actual_frame_number / fps if fps > 0 else frame_idx / 30.0

                for hand in result.get('hands', []):
                    hand_data = {
                        'hand_type': hand.get('hand_type', hand.get('label', 'Unknown')),
                        'landmarks': hand.get('landmarks', {}),
                        'palm_center': hand.get('palm_center', {}),
                        'finger_angles': hand.get('finger_angles', {}),
                        'hand_openness': hand.get('hand_openness', 0.0)
                    }
                    frames_dict[actual_frame_number].append(hand_data)

        # フロントエンド形式に変換: 1フレーム = 1レコード（複数の手を含む）
        formatted = []
        for frame_number in sorted(frames_dict.keys()):
            timestamp = frame_number / fps if fps > 0 else frame_number / 30.0
            formatted.append({
                'frame': frame_number,
                'frame_number': frame_number,
                'timestamp': timestamp,
                'hands': frames_dict[frame_number]
            })

        logger.info(f"Formatted {len(formatted)} skeleton frames with hands data")
        return formatted

    def _format_instrument_data(self, raw_results: List[Dict]) -> List[Dict]:
        """器具検出結果をフォーマット"""
        formatted = []
        fps = self.video_info.get('fps', 30)  # 実際の動画FPS
        target_fps = 5  # フレーム抽出時のFPS

        # フレームスキップを計算（skeleton_dataと同じロジック）
        frame_skip = max(1, int(fps / target_fps))

        # デバッグ：FPS情報を確認
        logger.info(f"[ANALYSIS] _format_instrument_data: fps={fps}, target_fps={target_fps}, frame_skip={frame_skip}")
        logger.info(f"[ANALYSIS] self.video_info: {self.video_info}")

        for frame_idx, result in enumerate(raw_results):
            # 型チェック
            if not isinstance(result, dict):
                logger.warning(f"[ANALYSIS] Skipping non-dict instrument result: type={type(result)}")
                continue

            # 実際のフレーム番号を計算（skeleton_dataと同様）
            actual_frame_number = frame_idx * frame_skip

            # 正しいタイムスタンプを計算（実際のFPSで割る）
            timestamp = actual_frame_number / fps if fps > 0 else frame_idx / 30.0

            # SAMTrackerUnified.detect_batchは{'detections': [...]}形式を返す
            detections = result.get('detections', [])

            # デバッグ：最初と最後のフレームを確認
            if frame_idx == 0 or frame_idx >= 110:
                logger.info(f"[ANALYSIS] Instrument frame {frame_idx}: actual_frame={actual_frame_number}, timestamp={timestamp:.2f}s, detections_count={len(detections)}")

            formatted.append({
                'frame_number': actual_frame_number,  # 実際のフレーム番号
                'timestamp': timestamp,  # 正しいタイムスタンプ
                'detections': detections  # SAMTrackerUnifiedから直接取得
            })

        logger.info(f"Formatted {len(formatted)} instrument detections with correct timestamps")
        return formatted

    async def _calculate_metrics(self, detection_results: Dict) -> Dict:
        """メトリクス計算"""
        metrics = {}

        # 骨格データのメトリクス
        if detection_results.get('skeleton_data'):
            calculator = MetricsCalculator(fps=self.video_info.get('fps', 30))
            metrics['skeleton_metrics'] = calculator.calculate_all_metrics(
                detection_results['skeleton_data']
            )

        # 器具データのメトリクス（将来的に実装）
        if detection_results.get('instrument_data'):
            metrics['instrument_metrics'] = {
                'total_detections': len(detection_results['instrument_data'])
            }

        logger.info(f"Calculated metrics: {list(metrics.keys())}")
        return metrics

    async def _calculate_scores(self, metrics: Dict) -> Dict:
        """スコア計算"""
        scores = {
            'overall_score': 0,
            'efficiency_score': 0,
            'smoothness_score': 0,
            'accuracy_score': 0
        }

        if 'skeleton_metrics' in metrics:
            skeleton_metrics = metrics['skeleton_metrics']

            # シンプルなスコア計算（将来的に改善）
            if 'velocity' in skeleton_metrics:
                avg_velocity = skeleton_metrics['velocity'].get('average', 0)
                scores['efficiency_score'] = min(100, avg_velocity * 10)

            if 'jerk' in skeleton_metrics:
                avg_jerk = skeleton_metrics['jerk'].get('average', 0)
                scores['smoothness_score'] = max(0, 100 - avg_jerk * 5)

            # 総合スコア
            scores['overall_score'] = (
                scores['efficiency_score'] * 0.4 +
                scores['smoothness_score'] * 0.6
            )

        logger.info(f"Calculated scores: {scores}")
        return scores

    async def _save_results(
        self,
        analysis_result: AnalysisResult,
        detection_results: Dict,
        metrics: Dict,
        scores: Dict,
        db
    ):
        """結果をデータベースに保存（numpy型変換とデータ圧縮付き）"""
        skeleton_data = detection_results.get('skeleton_data', [])
        instrument_data = detection_results.get('instrument_data', [])

        logger.info(f"[ANALYSIS] _save_results: skeleton_data length = {len(skeleton_data)}")
        logger.info(f"[ANALYSIS] _save_results: instrument_data length = {len(instrument_data)}")

        # numpy型をPython標準型に変換
        logger.info(f"[ANALYSIS] Converting numpy types...")
        skeleton_data = convert_numpy_types(skeleton_data)
        instrument_data = convert_numpy_types(instrument_data)
        metrics = convert_numpy_types(metrics)
        scores = convert_numpy_types(scores)

        # instrument_dataのサイズをチェックし、必要に応じて圧縮
        instrument_data_str = json.dumps(instrument_data)
        data_size = len(instrument_data_str)
        logger.info(f"[ANALYSIS] Instrument data size: {data_size} characters")

        if data_size > 500000:  # 500KB超過
            logger.warning(f"[ANALYSIS] Instrument data too large ({data_size} chars), compressing...")
            instrument_data = self._compress_instrument_data(instrument_data)
            compressed_size = len(json.dumps(instrument_data))
            logger.info(f"[ANALYSIS] Compressed to {compressed_size} characters ({100 * compressed_size / data_size:.1f}%)")

        analysis_result.skeleton_data = skeleton_data
        analysis_result.instrument_data = instrument_data
        analysis_result.motion_analysis = metrics
        analysis_result.scores = scores
        analysis_result.total_frames = self.video_info.get('total_frames', 0)
        analysis_result.status = AnalysisStatus.COMPLETED
        analysis_result.completed_at = datetime.now()
        analysis_result.progress = 100

        # Phase 2.2: トラッキング統計と警告を保存
        if self.tracking_stats:
            analysis_result.tracking_stats = json.dumps(self.tracking_stats)
            logger.info(f"[ANALYSIS] Saved tracking_stats: {list(self.tracking_stats.keys())}")

        if self.warnings:
            analysis_result.warnings = json.dumps(self.warnings)
            logger.info(f"[ANALYSIS] Saved {len(self.warnings)} warnings")

        db.commit()
        logger.info(f"[ANALYSIS] Results saved for analysis_id: {analysis_result.id}")

    def _collect_tracking_stats(self, detector, instrument_results: List[Dict]):
        """
        トラッキング統計を収集する（Phase 2.2）

        Args:
            detector: SAMTrackerUnifiedインスタンス
            instrument_results: 器具検出結果
        """
        try:
            # SAMTrackerUnifiedから統計情報を取得
            if hasattr(detector, 'get_tracking_stats'):
                tracker_stats = detector.get_tracking_stats()

                # 器具ごとの統計
                for inst_key, inst_stats in tracker_stats.get('instruments', {}).items():
                    if inst_key not in self.tracking_stats:
                        self.tracking_stats[inst_key] = {}

                    self.tracking_stats[inst_key]['max_lost_count'] = inst_stats.get('lost_frames', 0)
                    self.tracking_stats[inst_key]['last_score'] = inst_stats.get('last_score', 0.0)
                    self.tracking_stats[inst_key]['trajectory_length'] = inst_stats.get('trajectory_length', 0)

            # 再検出イベントをカウント
            re_detection_count = {}
            for frame_data in instrument_results:
                if isinstance(frame_data, dict):
                    detections = frame_data.get('detections', [])
                    for detection in detections:
                        if detection.get('redetected'):
                            track_id = detection.get('track_id', 0)
                            inst_key = f"instrument_{track_id}"

                            if inst_key not in re_detection_count:
                                re_detection_count[inst_key] = 0
                            re_detection_count[inst_key] += 1

            # 再検出カウントをtracking_statsに追加
            for inst_key, count in re_detection_count.items():
                if inst_key not in self.tracking_stats:
                    self.tracking_stats[inst_key] = {}
                self.tracking_stats[inst_key]['re_detections'] = count

            # 総フレーム数と検出フレーム数
            total_frames = len(instrument_results)
            detected_frames = sum(
                1 for frame_data in instrument_results
                if isinstance(frame_data, dict) and len(frame_data.get('detections', [])) > 0
            )

            self.tracking_stats['summary'] = {
                'total_frames': total_frames,
                'detected_frames': detected_frames,
                'detection_rate': detected_frames / total_frames if total_frames > 0 else 0
            }

            logger.info(f"[ANALYSIS] Collected tracking stats: {list(self.tracking_stats.keys())}")

        except Exception as e:
            logger.warning(f"[ANALYSIS] Failed to collect tracking stats: {e}")

    def _compress_instrument_data(self, instrument_data: List[Dict]) -> List[Dict]:
        """
        大容量の器具追跡データを圧縮

        Args:
            instrument_data: 器具追跡データのリスト

        Returns:
            圧縮された器具追跡データ
        """
        if not instrument_data:
            return []

        total_frames = len(instrument_data)
        logger.info(f"[ANALYSIS] Compressing {total_frames} frames of instrument data")

        # trajectoryデータを最新50点に制限
        compressed_data = []
        for frame_data in instrument_data:
            compressed_frame = {
                'detected': frame_data.get('detected', False),
                'frame_index': frame_data.get('frame_index', 0),
                'timestamp': frame_data.get('timestamp', 0.0),
                'instruments': []
            }

            for inst in frame_data.get('instruments', []):
                compressed_inst = {
                    'class_name': inst.get('class_name', ''),
                    'bbox': inst.get('bbox', []),
                    'confidence': inst.get('confidence', 0.0),
                    'track_id': inst.get('track_id', -1)
                }

                # trajectoryがある場合は最新50点のみ
                if 'trajectory' in inst and inst['trajectory']:
                    trajectory = inst['trajectory']
                    if len(trajectory) > 50:
                        compressed_inst['trajectory'] = trajectory[-50:]
                    else:
                        compressed_inst['trajectory'] = trajectory

                compressed_frame['instruments'].append(compressed_inst)

            compressed_data.append(compressed_frame)

        # 500KB超過の場合、サンプリングで削減
        if len(json.dumps(compressed_data)) > 500000:
            logger.warning(f"[ANALYSIS] Still too large, sampling frames...")
            summary_data = []

            # 最初の10フレーム
            summary_data.extend(compressed_data[:10])

            # 10フレームごとのサンプル
            for i in range(10, total_frames - 10, 10):
                summary_data.append(compressed_data[i])

            # 最後の10フレーム
            if total_frames > 20:
                summary_data.extend(compressed_data[-10:])

            logger.info(f"[ANALYSIS] Sampled {len(summary_data)} frames from {total_frames} total")
            return summary_data

        return compressed_data

    async def _update_status(
        self,
        analysis_result: AnalysisResult,
        status: str,
        db,
        progress: int = None
    ):
        """ステータス更新とWebSocket通知（強化版）"""
        analysis_result.current_step = status
        if progress is not None:
            analysis_result.progress = progress

        # ステータスをDBのstatusフィールドにも反映
        if status == "completed":
            analysis_result.status = AnalysisStatus.COMPLETED
        elif status in ["initialization", "frame_extraction", "skeleton_detection",
                       "instrument_detection", "motion_analysis", "report_generation"]:
            analysis_result.status = AnalysisStatus.PROCESSING

        db.commit()

        # WebSocket通知（詳細情報付き）
        await manager.send_progress(
            analysis_result.id,
            {
                'type': 'status_update',
                'status': status,
                'current_step': status,
                'progress': progress or analysis_result.progress,
                'message': self._get_step_message(status, progress)
            }
        )

        logger.info(f"Updated status: {status}, progress: {progress}")

    def _get_step_message(self, step: str, progress: int = None) -> str:
        """各ステップの説明メッセージを返す"""
        messages = {
            "initialization": "動画情報を取得しています...",
            "frame_extraction": "フレームを抽出しています...",
            "skeleton_detection": "骨格を検出しています...",
            "instrument_detection": "器具を認識しています...",
            "motion_analysis": "モーションを解析しています...",
            "report_generation": "レポートを生成しています...",
            "completed": "解析が完了しました！"
        }
        return messages.get(step, f"処理中... ({progress}%)" if progress else "処理中...")