"""
Analysis Service V2 - Clean architecture implementation
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import numpy as np
import json
import pytz

from app.models import SessionLocal
from sqlalchemy.orm import Session
from app.models.analysis import AnalysisResult, AnalysisStatus, get_jst_now
from app.models.video import Video, VideoType
from app.core.websocket import manager
from app.core.config import settings
from .data_converter import convert_numpy_types, extract_mask_contour, get_video_info
from .result_formatter import (
    format_skeleton_data,
    format_instrument_data,
    compress_instrument_data,
    convert_video_api_result,
    convert_instruments_format,
    collect_tracking_stats,
)
from .detection_pipeline import run_detection as _run_detection_pipeline
from .gaze_analysis_service import GazeAnalysisService
from .metrics_calculator import MetricsCalculator
from .frame_extraction_service import FrameExtractionService, ExtractionConfig, ExtractionResult
from .realtime_metrics_service import RealtimeMetricsService
from .waste_metrics_calculator import WasteMetricsCalculator
from .metrics import EventDetector, SixMetricsService

logger = logging.getLogger(__name__)


@dataclass
class AnalysisContext:
    """
    リクエストスコープの解析コンテキスト。

    analyze_video()呼び出しごとに生成され、解析実行中の状態を保持する。
    これにより、AnalysisServiceV2インスタンスがステートレスになり、
    同時リクエスト間の状態干渉を防ぐ。
    """
    warnings: List[str] = field(default_factory=list)
    tracking_stats: Dict = field(default_factory=dict)
    extraction_result: Optional[ExtractionResult] = None
    detectors: Dict = field(default_factory=dict)
    video_info: Dict = field(default_factory=dict)
    use_sam2: bool = False

    def cleanup(self):
        """検出器のクリーンアップ"""
        for detector in self.detectors.values():
            if hasattr(detector, 'close'):
                detector.close()


class AnalysisServiceV2:
    """
    クリーンアーキテクチャに基づく解析サービス（オーケストレータ）

    リクエストごとにAnalysisContextを生成し、状態を管理する。
    検出・フォーマット・メトリクス計算は各専門モジュールに委譲。
    """

    def __init__(self):
        # SAM2使用フラグ（環境変数 USE_SAM2=true で有効化）
        self._use_sam2 = getattr(settings, 'USE_SAM2', False)
        # フレーム抽出サービス
        self.frame_extraction_service = FrameExtractionService(
            ExtractionConfig(
                target_fps=getattr(settings, 'FRAME_EXTRACTION_FPS', 15),
                use_round=True  # round()を使用してframe_skip計算
            )
        )
        # 視線解析サービス
        self.gaze_service = GazeAnalysisService()

        # 後方互換性: インスタンス変数としてもアクセス可能にする
        # analyze_video()実行中のみ有効。_ctxから委譲。
        self._ctx: Optional[AnalysisContext] = None

    # --- 後方互換性プロパティ ---
    @property
    def detectors(self) -> Dict:
        return self._ctx.detectors if self._ctx else {}

    @detectors.setter
    def detectors(self, value: Dict):
        if self._ctx:
            self._ctx.detectors = value

    @property
    def video_info(self) -> Dict:
        return self._ctx.video_info if self._ctx else {}

    @video_info.setter
    def video_info(self, value: Dict):
        if self._ctx:
            self._ctx.video_info = value

    @property
    def warnings(self) -> List[str]:
        return self._ctx.warnings if self._ctx else []

    @warnings.setter
    def warnings(self, value: List[str]):
        if self._ctx:
            self._ctx.warnings = value

    @property
    def tracking_stats(self) -> Dict:
        return self._ctx.tracking_stats if self._ctx else {}

    @tracking_stats.setter
    def tracking_stats(self, value: Dict):
        if self._ctx:
            self._ctx.tracking_stats = value

    @property
    def extraction_result(self) -> Optional[ExtractionResult]:
        return self._ctx.extraction_result if self._ctx else None

    @extraction_result.setter
    def extraction_result(self, value: Optional[ExtractionResult]):
        if self._ctx:
            self._ctx.extraction_result = value

    @property
    def use_sam2(self) -> bool:
        return self._ctx.use_sam2 if self._ctx else self._use_sam2

    @use_sam2.setter
    def use_sam2(self, value: bool):
        if self._ctx:
            self._ctx.use_sam2 = value

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

        # リクエストスコープのコンテキストを生成
        self._ctx = AnalysisContext(use_sam2=self._use_sam2)

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
            if self._ctx:
                self._ctx.cleanup()
                self._ctx = None

    def _get_video_info(self, video_path: str) -> Dict:
        """動画情報を取得（data_converterに委譲）"""
        info = get_video_info(video_path)
        logger.info(f"[ANALYSIS] Video info: {info}")
        return info

    # _extract_frames メソッドは削除 - FrameExtractionServiceを使用

    def _convert_instruments_format(self, instruments: List[Dict]) -> List[Dict]:
        """保存されたinstruments形式をSAMTrackerUnified用に変換（result_formatterに委譲）"""
        return convert_instruments_format(instruments)

    async def _run_detection(
        self,
        frames: List[np.ndarray],
        video_type: VideoType,
        video_id: str,
        instruments: Optional[List[Dict]],
        video_path: Path
    ) -> Dict[str, Any]:
        """動画タイプに基づく検出処理の実行（detection_pipelineに委譲）"""
        detection_result = await _run_detection_pipeline(
            frames=frames,
            video_type=video_type,
            video_info=self.video_info,
            instruments=instruments,
            video_path=video_path,
            extraction_result=self.extraction_result,
            use_sam2=self.use_sam2,
        )

        # 検出器をオーケストレータに登録（クリーンアップ用）
        self.detectors.update(detection_result.detectors)

        # 結果をフォーマット
        results = {
            'skeleton_data': [],
            'instrument_data': []
        }

        if detection_result.skeleton_results:
            results['skeleton_data'] = self._format_skeleton_data(detection_result.skeleton_results)
            logger.info(f"[ANALYSIS] Formatted {len(results['skeleton_data'])} skeleton data points")

        if detection_result.instrument_results:
            results['instrument_data'] = self._format_instrument_data(detection_result.instrument_results)
            logger.info(f"[ANALYSIS] Formatted instrument data: {len(results['instrument_data'])} frames with detections")

            # Phase 2.2: トラッキング統計を収集
            sam_detector = self.detectors.get('sam')
            if sam_detector:
                self._collect_tracking_stats(sam_detector, detection_result.instrument_results)

        return results

    def _format_skeleton_data(self, raw_results: List[Dict]) -> List[Dict]:
        """骨格検出結果をフォーマット（result_formatterに委譲）"""
        return format_skeleton_data(raw_results, self.extraction_result, self.video_info)

    def _format_instrument_data(self, raw_results: List[Dict]) -> List[Dict]:
        """器具検出結果をフォーマット（result_formatterに委譲）"""
        return format_instrument_data(raw_results, self.extraction_result, self.video_info)

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

        # Review Deck 用イベント検出 (fail-soft: 失敗しても解析全体は成功扱い)
        try:
            fps = float(self.video_info.get('fps', 30.0)) or 30.0
            detector = EventDetector(fps=fps)
            events = detector.detect(analysis_result.id, skeleton_data)
            analysis_result.events = convert_numpy_types(events)
            analysis_result.events_version = detector.version
            logger.info(
                f"[ANALYSIS] Review Deck events: {len(events)} events "
                f"(version={detector.version})"
            )
        except Exception as evt_err:
            logger.warning(f"[ANALYSIS] Event detection failed: {evt_err}")
            analysis_result.events = None
            analysis_result.events_version = None
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
        """トラッキング統計を収集する（result_formatterに委譲）"""
        self.tracking_stats = collect_tracking_stats(detector, instrument_results, self.tracking_stats)

    def _compress_instrument_data(self, instrument_data: List[Dict]) -> List[Dict]:
        """大容量の器具追跡データを圧縮（result_formatterに委譲）"""
        return compress_instrument_data(instrument_data)

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
        """SAM2 Video APIの結果を既存フォーマットに変換（result_formatterに委譲）"""
        return convert_video_api_result(tracking_result, total_frames, extraction_result)

    def _extract_mask_contour(self, mask: np.ndarray) -> List[List[int]]:
        """マスクから輪郭座標を抽出（data_converterに委譲）（後方互換性のため維持）"""
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