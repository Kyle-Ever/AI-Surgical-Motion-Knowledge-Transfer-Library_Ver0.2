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
import pytz

from app.models import SessionLocal
from sqlalchemy.orm import Session
from app.models.analysis import AnalysisResult, AnalysisStatus, get_jst_now
from app.models.video import Video, VideoType
from app.core.websocket import manager
from app.core.config import settings
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
from app.ai_engine.processors.sam2_tracker import SAM2Tracker
from app.ai_engine.processors.sam2_tracker_video import SAM2TrackerVideo  # 実験版
from app.ai_engine.processors.gaze_analyzer import GazeAnalyzer  # 視線解析
from .data_converter import convert_numpy_types, extract_mask_contour
from .gaze_analysis_service import GazeAnalysisService
from .metrics_calculator import MetricsCalculator
from .frame_extraction_service import FrameExtractionService, ExtractionConfig, ExtractionResult
from .realtime_metrics_service import RealtimeMetricsService
from .waste_metrics_calculator import WasteMetricsCalculator
from .metrics import SixMetricsService

logger = logging.getLogger(__name__)



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
        # フレーム抽出サービス
        self.frame_extraction_service = FrameExtractionService(
            ExtractionConfig(
                target_fps=getattr(settings, 'FRAME_EXTRACTION_FPS', 15),
                use_round=True  # round()を使用してframe_skip計算
            )
        )
        self.extraction_result: Optional[ExtractionResult] = None  # 抽出結果を保持
        # 視線解析サービス
        self.gaze_service = GazeAnalysisService()

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

            # 2.1 視線解析の場合は専用パイプラインへ（既存機能と完全分離）
            if video_type == VideoType.EYE_GAZE:
                logger.info(f"[ANALYSIS] Routing to eye gaze analysis pipeline")
                return await self._analyze_eye_gaze(video, analysis_result, analysis_id, db)

            # 3. 動画情報の取得（既存機能はここから継続）
            logger.info(f"[ANALYSIS] Getting video info...")
            await self._update_status(analysis_result, "initialization", db, progress=5)
            self.video_info = self._get_video_info(str(video_path))
            logger.info(f"[ANALYSIS] Video info retrieved")
            await self._update_status(analysis_result, "initialization", db, progress=10)
            logger.info(f"[ANALYSIS] Status updated to initialization")

            # 4. フレーム抽出（新しいFrameExtractionServiceを使用）
            logger.info(f"[ANALYSIS] Starting frame extraction...")
            await self._update_status(analysis_result, "frame_extraction", db, progress=15)

            # 新しいサービスでフレーム抽出
            loop = asyncio.get_event_loop()
            self.extraction_result = await loop.run_in_executor(
                None,
                self.frame_extraction_service.extract_frames,
                str(video_path)
            )

            frames = self.extraction_result.frames
            logger.info(f"[ANALYSIS] {self.extraction_result}")
            logger.info(f"[ANALYSIS] Extracted {len(frames)} frames, "
                       f"effective_fps={self.extraction_result.effective_fps:.2f}, "
                       f"frame_skip={self.extraction_result.frame_skip}")
            await self._update_status(analysis_result, "frame_extraction", db, progress=30)

            # 5. 検出処理の実行
            logger.info(f"[ANALYSIS] Starting detection...")
            await self._update_status(analysis_result, "skeleton_detection", db, progress=35)
            detection_results = await self._run_detection(
                frames, video_type, video_id, instruments, video_path
            )
            logger.info(f"[ANALYSIS] Detection completed with {len(detection_results) if detection_results else 0} results")
            await self._update_status(analysis_result, "instrument_detection", db, progress=60)

            # 6. メトリクス計算
            await self._update_status(analysis_result, "motion_analysis", db, progress=70)
            metrics = await self._calculate_metrics(detection_results)
            await self._update_status(analysis_result, "motion_analysis", db, progress=80)

            # 7. スコアリング
            await self._update_status(analysis_result, "report_generation", db, progress=85)
            scores = await self._calculate_scores(metrics, detection_results)

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
            # デバッグ用: エラーメッセージにトレースバック末尾を含める
            tb_short = error_traceback.strip().split('\n')[-3:]
            error_msg_with_tb = f"{str(e)} | TB: {' | '.join(tb_short)}"

            if analysis_result:
                # Phase 2.2: エラー情報を詳細に記録
                analysis_result.status = AnalysisStatus.FAILED
                analysis_result.error_message = error_msg_with_tb

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
                    await manager.send_progress(analysis_id, {
                        "type": "error",
                        "error_type": type(e).__name__,
                        "message": str(e),
                        "warnings_count": len(self.warnings),
                        "tracking_stats": self.tracking_stats
                    })
                except Exception:
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

    # _extract_frames メソッドは削除 - FrameExtractionServiceを使用

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
            # 🆕 pointsリストからbboxを計算
            elif "points" in inst and inst["points"]:
                points = inst["points"]
                if len(points) >= 2:  # 最低2点必要
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    x_min, y_min = min(xs), min(ys)
                    x_max, y_max = max(xs), max(ys)
                    bbox_xyxy = [x_min, y_min, x_max, y_max]
                    logger.info(f"[ANALYSIS] Instrument {idx} using points-to-box conversion ({len(points)} points)")
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
                    logger.warning(f"[ANALYSIS] Instrument {idx} has insufficient points ({len(points)})")
            else:
                logger.warning(f"[ANALYSIS] Instrument {idx} has no valid bbox, mask, or points, skipping")
                continue

        logger.info(f"[ANALYSIS] Converted {len(converted)} instruments from saved format to SAM format")
        return converted

    async def _run_detection(
        self,
        frames: List[np.ndarray],
        video_type: VideoType,
        video_id: str,
        instruments: Optional[List[Dict]],
        video_path: Path
    ) -> Dict[str, Any]:
        """
        動画タイプに基づく検出処理の実行

        Args:
            frames: フレームリスト
            video_type: 動画タイプ
            video_id: 動画ID
            instruments: 器具定義
            video_path: 動画ファイルパス（絶対パス）

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

            # 実験版: SAM2 Video APIを使用するか確認
            use_video_api = getattr(settings, 'USE_SAM2_VIDEO_API', False)

            if self.use_sam2 and use_video_api:
                # 🧪 実験版: SAM2 Video API
                logger.info(f"[EXPERIMENTAL] SAM2 Video API: {settings.SAM2_VIDEO_MODEL_TYPE}, device={device}")

                # Configから自動的にモデルを読み込む（🆕 Phase 3: model_type指定）
                sam_detector = SAM2TrackerVideo(
                    model_type=settings.SAM2_VIDEO_MODEL_TYPE,
                    device=device
                )
                logger.info("[EXPERIMENTAL] SAM2 Video API: Memory Bank + Temporal Context enabled")

                # Video APIは全フレームを一度に処理
                if instruments and len(instruments) > 0 and len(frames) > 0:
                    # 保存形式からSAM形式に変換
                    instruments_converted = self._convert_instruments_format(instruments)
                    logger.info(f"[EXPERIMENTAL] Tracking {len(instruments_converted)} instruments across {len(frames)} frames...")

                    # 🆕 器具初期化内容を詳細にログ
                    for idx, inst in enumerate(instruments_converted):
                        logger.info(f"[INSTRUMENT INIT] [{idx}] id={inst['id']}, name={inst['name']}, selection_type={inst['selection']['type']}")

                    # Video APIで追跡（video_pathは既に絶対パス）
                    logger.info(f"[SAM2 VIDEO] Starting video tracking: path={video_path}")
                    logger.info(f"[SAM2 VIDEO] Video total frames: {self.video_info.get('total_frames', 'unknown')}")
                    logger.info(f"[SAM2 VIDEO] Video duration: {self.video_info.get('duration', 'unknown')}s")
                    logger.info(f"[SAM2 VIDEO] Instruments: {len(instruments_converted)}")

                    try:
                        tracking_result = await sam_detector.track_video(
                            str(video_path),
                            instruments_converted
                        )
                        logger.info(f"[SAM2 VIDEO] Tracking completed successfully")
                    except Exception as e:
                        logger.error(f"[SAM2 VIDEO] Tracking failed: {e}")
                        import traceback
                        logger.error(f"[SAM2 VIDEO] Traceback: {traceback.format_exc()}")
                        raise

                    # 結果をフレーム単位の形式に変換
                    # 重要: extraction_resultを使用して正確なフレーム数とインデックスマッピング
                    if self.extraction_result:
                        instrument_results = self._convert_video_api_result(
                            tracking_result,
                            total_frames=len(frames),
                            extraction_result=self.extraction_result
                        )
                    else:
                        # フォールバック
                        instrument_results = self._convert_video_api_result(tracking_result, len(frames))
                    logger.info(f"[EXPERIMENTAL] SAM2 Video API completed: {len(instrument_results)} frames processed")
                else:
                    logger.warning("[EXPERIMENTAL] No instruments provided for Video API tracking")
                    instrument_results = []

            elif self.use_sam2:
                # 既存のSAM2（フレーム単位処理）
                logger.info(f"[ANALYSIS] Creating SAM2Tracker with model=small, device={device}")
                sam_detector = SAM2Tracker(model_type="small", device=device)
                logger.info("[ANALYSIS] SAM2 enabled for higher accuracy (+2% Dice, -21% HD95)")

                self.detectors['sam'] = sam_detector
                instruments_converted = []

                # 器具の初期化
                if instruments and len(instruments) > 0 and len(frames) > 0:
                    try:
                        # 保存形式からSAM形式に変換
                        instruments_converted = self._convert_instruments_format(instruments)
                        logger.info(f"[ANALYSIS] Initializing {len(instruments_converted)} instruments from user selection")
                        sam_detector.initialize_instruments(frames[0], instruments_converted)
                    except Exception as e:
                        logger.error(f"[ANALYSIS] Failed to initialize instruments from user selection: {e}")
                        logger.warning("[ANALYSIS] SAM2 auto-detection is not supported in this version. Skipping.")
                elif len(frames) > 0:
                    logger.info("[ANALYSIS] No user selection. SAM2 auto-detection is not supported in this version.")
                else:
                    logger.warning("[ANALYSIS] No frames available for instrument initialization")

                logger.info(f"[ANALYSIS] Running SAM detect_batch on {len(frames)} frames...")
                # 修正: instruments引数を渡す
                instrument_results = sam_detector.detect_batch(frames, instruments_converted)
                logger.info(f"[ANALYSIS] SAM detection completed, got {len(instrument_results)} results")
            else:
                # SAM1（既存実装）
                logger.info(f"[ANALYSIS] Creating SAMTrackerUnified with model=vit_h, device={device}, instruments={len(instruments) if instruments else 0}, fps={fps}, target_fps={target_fps}")
                sam_detector = SAMTrackerUnified(model_type="vit_h", device=device)

                self.detectors['sam'] = sam_detector

                # 器具の初期化
                if instruments and len(instruments) > 0 and len(frames) > 0:
                    try:
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
        """
        骨格検出結果をフォーマット（フロントエンド互換形式）

        extraction_resultのframe_indicesとtimestampsを使用して正確なマッピング
        """
        from collections import defaultdict

        # extraction_resultがない場合のフォールバック
        if not self.extraction_result:
            logger.error("[ANALYSIS] extraction_result not available, using fallback")
            fps = self.video_info.get('fps', 30)
            target_fps = getattr(settings, 'FRAME_EXTRACTION_FPS', 15)
            frame_skip = max(1, int(fps / target_fps))

            frames_dict = defaultdict(list)
            for result in raw_results:
                if not isinstance(result, dict):
                    continue
                if result.get('detected'):
                    if 'frame_index' not in result:
                        raise ValueError(f"Missing frame_index in skeleton result")
                    frame_idx = result['frame_index']
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

            formatted = []
            for frame_number in sorted(frames_dict.keys()):
                timestamp = frame_number / fps if fps > 0 else frame_number / 30.0
                formatted.append({
                    'frame': frame_number,
                    'frame_number': frame_number,
                    'timestamp': timestamp,
                    'hands': frames_dict[frame_number]
                })
            return formatted

        # 新しいロジック: extraction_resultを使用
        logger.info(f"[ANALYSIS] _format_skeleton_data using extraction_result: "
                   f"{len(self.extraction_result.frame_indices)} frame_indices, "
                   f"{len(self.extraction_result.timestamps)} timestamps")

        frames_dict = defaultdict(list)
        for result in raw_results:
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

                # extraction_resultから正確な値を取得
                if frame_idx >= len(self.extraction_result.frame_indices):
                    logger.warning(f"[ANALYSIS] Frame {frame_idx} exceeds extraction_result length")
                    continue

                actual_frame_number = self.extraction_result.frame_indices[frame_idx]
                timestamp = self.extraction_result.timestamps[frame_idx]

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
            # extraction_resultから対応するタイムスタンプを取得
            frame_idx = self.extraction_result.frame_indices.index(frame_number) if frame_number in self.extraction_result.frame_indices else None
            if frame_idx is not None:
                timestamp = self.extraction_result.timestamps[frame_idx]
            else:
                # フォールバック
                fps = self.video_info.get('fps', 30)
                timestamp = frame_number / fps

            formatted.append({
                'frame': frame_number,
                'frame_number': frame_number,
                'timestamp': timestamp,
                'hands': frames_dict[frame_number]
            })

        logger.info(f"Formatted {len(formatted)} skeleton frames with hands data")
        return formatted

    def _format_instrument_data(self, raw_results: List[Dict]) -> List[Dict]:
        """
        器具検出結果をフォーマット

        extraction_resultのframe_indicesとtimestampsを使用して正確なマッピング
        """
        formatted = []

        # extraction_resultがない場合のフォールバック
        if not self.extraction_result:
            logger.error("[ANALYSIS] extraction_result not available for instrument data, using fallback")
            fps = self.video_info.get('fps', 30)
            target_fps = getattr(settings, 'FRAME_EXTRACTION_FPS', 15)
            frame_skip = max(1, int(fps / target_fps))

            for frame_idx, result in enumerate(raw_results):
                if not isinstance(result, dict):
                    continue
                actual_frame_number = frame_idx * frame_skip
                timestamp = actual_frame_number / fps if fps > 0 else frame_idx / 30.0
                instruments = result.get('instruments', result.get('detections', []))
                formatted.append({
                    'frame_number': actual_frame_number,
                    'timestamp': timestamp,
                    'detections': instruments
                })
            return formatted

        # 新しいロジック: extraction_resultを使用
        logger.info(f"[ANALYSIS] _format_instrument_data using extraction_result: "
                   f"{len(self.extraction_result.frame_indices)} frame_indices")

        for frame_idx, result in enumerate(raw_results):
            if not isinstance(result, dict):
                logger.warning(f"[ANALYSIS] Skipping non-dict instrument result: type={type(result)}")
                continue

            if frame_idx >= len(self.extraction_result.frame_indices):
                logger.warning(f"[ANALYSIS] Instrument frame {frame_idx} exceeds extraction_result length")
                break

            # extraction_resultから正確な値を取得
            actual_frame_number = self.extraction_result.frame_indices[frame_idx]
            timestamp = self.extraction_result.timestamps[frame_idx]

            # SAM2 Video APIは'instruments'キー、SAMTrackerUnifiedは'detections'キーを使う
            instruments = result.get('instruments', result.get('detections', []))

            # デバッグ：最初と最後のフレームを確認
            if frame_idx == 0 or frame_idx >= 110:
                logger.info(f"[ANALYSIS] Instrument frame {frame_idx}: "
                          f"actual_frame={actual_frame_number}, "
                          f"timestamp={timestamp:.3f}s, "
                          f"instruments_count={len(instruments)}")

            formatted.append({
                'frame_number': actual_frame_number,
                'timestamp': timestamp,
                'detections': instruments
            })

        logger.info(f"Formatted {len(formatted)} instrument detections with correct timestamps")
        return formatted

    async def _calculate_metrics(self, detection_results: Dict) -> Dict:
        """メトリクス計算"""
        metrics = {}
        fps = self.video_info.get('fps', 30)

        # 骨格データのメトリクス
        if detection_results.get('skeleton_data'):
            calculator = MetricsCalculator(fps=fps)
            metrics['skeleton_metrics'] = calculator.calculate_all_metrics(
                detection_results['skeleton_data']
            )

        # ムダ指標の計算（旧版 — 後方互換性のため維持）
        if detection_results.get('skeleton_data'):
            waste_calc = WasteMetricsCalculator(fps=fps)
            metrics['waste_metrics'] = waste_calc.calculate_all_waste_metrics(
                detection_results['skeleton_data']
            )

        # 6指標計算（新版）
        if detection_results.get('skeleton_data'):
            six_svc = SixMetricsService(fps=fps)
            six_result = six_svc.calculate(detection_results['skeleton_data'])
            metrics['six_metrics'] = six_result.to_dict()
            metrics['six_metrics_timeline'] = six_svc.calculate_timeline(
                detection_results['skeleton_data'], interval_sec=0.5
            )

        # 器具データのメトリクス（将来的に実装）
        if detection_results.get('instrument_data'):
            metrics['instrument_metrics'] = {
                'total_detections': len(detection_results['instrument_data'])
            }

        logger.info(f"Calculated metrics: {list(metrics.keys())}")
        return metrics

    async def _calculate_scores(self, metrics: Dict, detection_results: Dict) -> Dict:
        """
        スコア計算

        Args:
            metrics: メトリクスデータ
            detection_results: 検出結果（skeleton_dataを含む）

        Returns:
            スコア辞書
        """
        scores = {
            'overall_score': 0,
            'speed_score': 0,
            'smoothness_score': 0,
            'accuracy_score': 0,
            'efficiency_score': 0
        }

        # 新しい3パラメータ計算（RealtimeMetricsService使用）
        skeleton_data = detection_results.get('skeleton_data', [])
        if skeleton_data:
            fps = self.video_info.get('fps', 30)
            realtime_service = RealtimeMetricsService(fps=fps)
            three_params = realtime_service.calculate_three_parameters(skeleton_data)

            scores['speed_score'] = three_params['speed_score']
            scores['smoothness_score'] = three_params['smoothness_score']
            scores['accuracy_score'] = three_params['accuracy_score']

            # 総合スコア（3パラメータの平均）
            scores['overall_score'] = (
                scores['speed_score'] +
                scores['smoothness_score'] +
                scores['accuracy_score']
            ) / 3.0

            logger.info(f"[SCORES] 3-parameter calculation: speed={scores['speed_score']:.2f}, smoothness={scores['smoothness_score']:.2f}, accuracy={scores['accuracy_score']:.2f}")
        else:
            logger.warning("[SCORES] No skeleton_data available, using fallback calculation")

            # 従来のフォールバック計算
            if 'skeleton_metrics' in metrics:
                skeleton_metrics = metrics['skeleton_metrics']

                if 'velocity' in skeleton_metrics:
                    avg_velocity = skeleton_metrics['velocity'].get('average', 0)
                    scores['efficiency_score'] = min(100, avg_velocity * 10)
                    scores['speed_score'] = scores['efficiency_score']

                if 'jerk' in skeleton_metrics:
                    avg_jerk = skeleton_metrics['jerk'].get('average', 0)
                    scores['smoothness_score'] = max(0, 100 - avg_jerk * 5)

                # 総合スコア
                scores['overall_score'] = (
                    scores['efficiency_score'] * 0.4 +
                    scores['smoothness_score'] * 0.6
                )

        # ムダスコアの追加
        if 'waste_metrics' in metrics:
            waste_calc = WasteMetricsCalculator(fps=self.video_info.get('fps', 30))
            waste_scores = waste_calc.calculate_waste_scores(metrics['waste_metrics'])
            scores.update(waste_scores)
            logger.info(f"[SCORES] Waste scores: waste={waste_scores['waste_score']:.1f}, "
                       f"idle={waste_scores['idle_time_score']:.1f}, "
                       f"volume={waste_scores['working_volume_score']:.1f}, "
                       f"movement={waste_scores['movement_count_score']:.1f}")

        logger.info(f"[SCORES] Final calculated scores: {scores}")
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

        # skeleton_dataは即座に型変換（圧縮不要）
        logger.info(f"[ANALYSIS] Converting skeleton_data numpy types...")
        skeleton_data = convert_numpy_types(skeleton_data)

        # instrument_dataは圧縮してから型変換（mask→contour変換が必要）
        if instrument_data:
            logger.info(f"[ANALYSIS] Compressing instrument_data (mask→contour)...")
            instrument_data = self._compress_instrument_data(instrument_data)
            compressed_size = len(json.dumps(instrument_data))
            logger.info(f"[ANALYSIS] Compressed instrument_data: {compressed_size} characters")

        # 圧縮後に型変換（残りのnumpy型をPython型に）
        logger.info(f"[ANALYSIS] Converting remaining numpy types...")
        instrument_data = convert_numpy_types(instrument_data)
        metrics = convert_numpy_types(metrics)
        scores = convert_numpy_types(scores)

        analysis_result.skeleton_data = skeleton_data
        analysis_result.instrument_data = instrument_data
        analysis_result.motion_analysis = metrics
        analysis_result.scores = scores
        analysis_result.total_frames = self.video_info.get('total_frames', 0)
        analysis_result.status = AnalysisStatus.COMPLETED
        # JST時刻で保存
        jst = pytz.timezone('Asia/Tokyo')
        analysis_result.completed_at = datetime.now(jst).replace(tzinfo=None)
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

        注意：このメソッドは_format_instrument_dataの出力を受け取る
        _format_instrument_dataは以下の形式で出力する：
        {
            'frame_number': int,
            'timestamp': float,
            'detections': [  # ← 'instruments'ではなく'detections'
                {
                    'id': int,
                    'name': str,
                    'center': [x, y],
                    'bbox': [x1, y1, x2, y2],
                    'confidence': float,
                    'mask': array (optional)
                }
            ]
        }

        Args:
            instrument_data: 器具追跡データのリスト

        Returns:
            圧縮された器具追跡データ
        """
        if not instrument_data:
            return []

        total_frames = len(instrument_data)
        logger.info(f"[ANALYSIS] Compressing {total_frames} frames of instrument data")

        # デバッグ：最初のフレームの構造を確認
        if total_frames > 0:
            first_frame = instrument_data[0]
            logger.info(f"[ANALYSIS] Compression input - First frame keys: {list(first_frame.keys())}")
            detections_key = 'detections' if 'detections' in first_frame else 'instruments'
            det_count = len(first_frame.get(detections_key, []))
            logger.info(f"[ANALYSIS] Compression input - First frame {detections_key} count: {det_count}")
            if det_count > 0:
                first_det = first_frame[detections_key][0]
                logger.info(f"[ANALYSIS] Compression input - First detection keys: {list(first_det.keys())}")

        # maskデータを除去して圧縮
        compressed_data = []

        # デバッグ: 圧縮開始時のログ
        logger.warning(f"[CONTOUR_DEBUG] Starting compression, total frames: {len(instrument_data)}")

        for frame_idx, frame_data in enumerate(instrument_data):
            # _format_instrument_dataが使用するキー名に対応
            compressed_frame = {
                'frame_number': frame_data.get('frame_number'),  # frame_index ではなく frame_number
                'timestamp': frame_data.get('timestamp', 0.0),
                'detections': []  # instruments ではなく detections
            }

            # SAM2 Video APIのデータ構造に対応
            detections = frame_data.get('detections', [])

            # デバッグ: 最初のフレームで必ずログ出力
            if frame_idx == 0:
                logger.warning(f"[CONTOUR_DEBUG] Frame 0 has {len(detections)} detections")

            for det_idx, det in enumerate(detections):
                # デバッグ: detectionの構造を確認（WARNINGレベルで確実に出力）
                if frame_idx == 0 and det_idx == 0:
                    logger.warning(f"[CONTOUR_DEBUG] First detection keys: {list(det.keys())}")
                    logger.warning(f"[CONTOUR_DEBUG] First detection has 'mask': {'mask' in det}")
                    if 'mask' in det:
                        mask_data = det.get('mask')
                        logger.warning(f"[CONTOUR_DEBUG] Mask type: {type(mask_data)}, is None: {mask_data is None}")
                        if isinstance(mask_data, np.ndarray):
                            logger.warning(f"[CONTOUR_DEBUG] Mask shape: {mask_data.shape}, dtype: {mask_data.dtype}, sum: {mask_data.sum()}")

                compressed_det = {
                    'id': det.get('id'),
                    'name': det.get('name', ''),
                    'center': det.get('center', []),
                    'bbox': det.get('bbox', []),
                    'confidence': det.get('confidence', 0.0),
                    'contour': self._extract_mask_contour(det.get('mask'))  # マスク輪郭を抽出
                    # mask配列は除外（588MB→数百KB）、代わりにcontour座標を保存
                }

                compressed_frame['detections'].append(compressed_det)

            compressed_data.append(compressed_frame)

        # 圧縮結果を確認
        frames_with_dets = sum(1 for f in compressed_data if len(f.get('detections', [])) > 0)
        logger.info(f"[ANALYSIS] After mask removal: {frames_with_dets}/{total_frames} frames have detections")

        # 500KB超過の場合、サンプリングで削減
        compressed_json = json.dumps(compressed_data)
        compressed_size = len(compressed_json)
        logger.info(f"[ANALYSIS] Compressed data size: {compressed_size} characters")

        if compressed_size > 500000:
            logger.warning(f"[ANALYSIS] Still too large ({compressed_size} chars), sampling frames...")
            summary_data = []

            # 最初の10フレーム
            summary_data.extend(compressed_data[:10])

            # 10フレームごとのサンプル
            for i in range(10, total_frames - 10, 10):
                summary_data.append(compressed_data[i])

            # 最後の10フレーム
            if total_frames > 20:
                summary_data.extend(compressed_data[-10:])

            sampled_frames_with_dets = sum(1 for f in summary_data if len(f.get('detections', [])) > 0)
            logger.info(f"[ANALYSIS] Sampled {len(summary_data)} frames from {total_frames} total")
            logger.info(f"[ANALYSIS] Sampled data: {sampled_frames_with_dets}/{len(summary_data)} frames have detections")
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

    def _convert_video_api_result(
        self,
        tracking_result: Dict[str, Any],
        total_frames: int,
        extraction_result: Optional[ExtractionResult] = None
    ) -> List[Dict[str, Any]]:
        """
        SAM2 Video APIの結果を既存フォーマット（フレーム単位）に変換

        Args:
            tracking_result: Video APIの結果
            total_frames: 抽出されたフレーム数
            extraction_result: フレーム抽出結果（frame_indicesマッピング用）

        Returns:
            フレーム単位の結果リスト
        """
        logger.info("[EXPERIMENTAL] Converting Video API result to frame-based format...")

        # フレームごとの結果を初期化
        frame_results = [
            {"detected": False, "instruments": []}
            for _ in range(total_frames)
        ]

        # 各器具の軌跡をフレーム単位に分配
        instruments_data = tracking_result.get("instruments", [])

        # extraction_resultがある場合、動画フレーム番号→抽出インデックスのマッピングを作成
        video_frame_to_extract_idx = {}
        if extraction_result:
            for idx, video_frame_num in enumerate(extraction_result.frame_indices):
                video_frame_to_extract_idx[video_frame_num] = idx
            logger.info(f"[EXPERIMENTAL] Created frame mapping: {len(video_frame_to_extract_idx)} video frames → extract indices")

        for inst_data in instruments_data:
            inst_id = inst_data["instrument_id"]
            inst_name = inst_data["name"]
            trajectory = inst_data["trajectory"]

            for point_idx, point in enumerate(trajectory):
                # SAM2 Video APIは動画内の実際のフレーム番号を返す
                video_frame_idx = point["frame_index"]

                # 抽出されたフレームのインデックスに変換
                if extraction_result and video_frame_idx in video_frame_to_extract_idx:
                    extract_idx = video_frame_to_extract_idx[video_frame_idx]
                else:
                    # 🐛 FIX: フォールバックを削除してスキップ
                    # 問題: SAM2が連続フレーム番号(0,1,2,3...)を返すのに対し、
                    #       extraction_resultには間引き後のフレーム(0,2,4,6...)のみ含まれる
                    # 結果: video_frame=1がextract_idx=1に配置され、video_frame=2も
                    #       extract_idx=1にマッピングされることで重複が発生していた
                    if point_idx < 5:  # 最初の数回のみログ出力
                        logger.info(f"[SKIP] Inst {inst_id}, Point {point_idx}: video_frame={video_frame_idx} not in extraction mapping, skipping")
                    continue  # このtrajectory pointをスキップ

                if 0 <= extract_idx < total_frames:
                    frame_results[extract_idx]["detected"] = True
                    frame_results[extract_idx]["instruments"].append({
                        "id": inst_id,
                        "name": inst_name,
                        "center": point["center"],
                        "bbox": point["bbox"],
                        "confidence": point["confidence"],
                        "mask": point.get("mask")
                    })

        # 検出があったフレーム数をカウント
        detected_frames = sum(1 for fr in frame_results if fr["detected"])
        logger.info(f"[EXPERIMENTAL] Converted to frame-based format: {detected_frames}/{total_frames} frames with detections")

        return frame_results

    def _extract_mask_contour(self, mask: np.ndarray) -> List[List[int]]:
        """マスクから輪郭座標を抽出（data_converterに委譲）"""
        return extract_mask_contour(mask)

    async def _analyze_eye_gaze(
        self,
        video: Video,
        analysis_result: AnalysisResult,
        analysis_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """視線解析パイプ���インをGazeAnalysisServiceに委譲"""
        return await self.gaze_service.analyze(video, analysis_result, analysis_id, db)