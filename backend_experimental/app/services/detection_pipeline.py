"""
Detection pipeline strategies extracted from AnalysisServiceV2._run_detection.

Uses the Strategy pattern to encapsulate video-type-specific detection logic.
Each strategy handles detector creation, initialization, and batch detection.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

import numpy as np

from app.core.config import settings
from app.models.video import VideoType
from app.ai_engine.processors.skeleton_detector import HandSkeletonDetector
from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified
from app.ai_engine.processors.sam2_tracker import SAM2Tracker
from app.ai_engine.processors.sam2_tracker_video import SAM2TrackerVideo
from .result_formatter import convert_instruments_format, convert_video_api_result
from .frame_extraction_service import ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """検出パイプラインの結果を保持するデータクラス"""
    skeleton_results: list = field(default_factory=list)
    instrument_results: list = field(default_factory=list)
    detectors: Dict[str, Any] = field(default_factory=dict)
    tracking_stats: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def _get_device() -> str:
    """SAM用デバイスを決定する"""
    device = getattr(settings, 'SAM_DEVICE', 'cpu')
    if device == 'auto':
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    return device


def _log_first_skeleton_result(skeleton_results: list) -> None:
    """最初の骨格検出結果をデバッグログ出力する"""
    if skeleton_results and len(skeleton_results) > 0:
        first_result = skeleton_results[0]
        if isinstance(first_result, dict):
            logger.info(f"[ANALYSIS] First skeleton result: detected={first_result.get('detected')}, hands={len(first_result.get('hands', []))}")
        else:
            logger.warning(f"[ANALYSIS] First skeleton result is not dict: type={type(first_result)}")


def _log_first_instrument_result(instrument_results: list) -> None:
    """最初の器具検出結果をデバッグログ出力する"""
    if instrument_results and len(instrument_results) > 0:
        first_result = instrument_results[0]
        if isinstance(first_result, dict):
            logger.info(f"[ANALYSIS] First instrument result: detected={first_result.get('detected')}, instruments={len(first_result.get('instruments', []))}")
        else:
            logger.warning(f"[ANALYSIS] First instrument result is not dict: type={type(first_result)}")


def _init_and_detect_sam_instruments(
    detector,
    frames: List[np.ndarray],
    instruments: Optional[List[Dict]],
    allow_auto_detect: bool = True,
) -> list:
    """
    SAM系検出器の器具初期化とバッチ検出を行う共通ロジック。

    Args:
        detector: SAMTrackerUnifiedまたはSAM2Trackerインスタンス
        frames: フレームリスト
        instruments: 器具定義（None可）
        allow_auto_detect: 自動検出を許可するか（SAM2は非対応）

    Returns:
        器具検出結果リスト
    """
    instruments_converted = []

    if instruments and len(instruments) > 0 and len(frames) > 0:
        try:
            instruments_converted = convert_instruments_format(instruments)
            logger.info(f"[ANALYSIS] Initializing {len(instruments_converted)} instruments from user selection")
            detector.initialize_instruments(frames[0], instruments_converted)
        except Exception as e:
            logger.error(f"[ANALYSIS] Failed to initialize instruments from user selection: {e}")
            if allow_auto_detect:
                logger.info("[ANALYSIS] Falling back to automatic instrument detection")
                detector.auto_detect_instruments(frames[0], max_instruments=5)
            else:
                logger.warning("[ANALYSIS] SAM2 auto-detection is not supported in this version. Skipping.")
    elif len(frames) > 0:
        if allow_auto_detect:
            logger.info("[ANALYSIS] No user selection, using automatic instrument detection")
            detector.auto_detect_instruments(frames[0], max_instruments=5)
        else:
            logger.info("[ANALYSIS] No user selection. SAM2 auto-detection is not supported in this version.")
    else:
        logger.warning("[ANALYSIS] No frames available for instrument initialization")

    logger.info(f"[ANALYSIS] Running SAM detect_batch on {len(frames)} frames...")

    # SAM2Trackerはinstruments_convertedを受け取る
    is_sam2 = isinstance(detector, SAM2Tracker)
    if is_sam2:
        instrument_results = detector.detect_batch(frames, instruments_converted)
    else:
        instrument_results = detector.detect_batch(frames)

    logger.info(f"[ANALYSIS] SAM detection completed, got {len(instrument_results)} results")
    return instrument_results


class DetectionStrategy(ABC):
    """検出戦略の抽象基底クラス"""

    @abstractmethod
    async def detect(
        self,
        frames: List[np.ndarray],
        video_info: Dict[str, Any],
        instruments: Optional[List[Dict]],
        video_path: Path,
        extraction_result: Optional[ExtractionResult],
        use_sam2: bool,
    ) -> DetectionResult:
        """
        検出を実行する。

        Args:
            frames: フレームリスト
            video_info: 動画情報
            instruments: 器具定義
            video_path: 動画ファイルパス
            extraction_result: フレーム抽出結果
            use_sam2: SAM2を使用するか

        Returns:
            DetectionResult
        """
        ...


class SkeletonOnlyStrategy(DetectionStrategy):
    """骨格検出のみ（EXTERNAL / EXTERNAL_NO_INSTRUMENTS / 不明タイプ）"""

    async def detect(self, frames, video_info, instruments, video_path, extraction_result, use_sam2) -> DetectionResult:
        logger.info(f"[ANALYSIS] Running MediaPipe detection only (no instruments)")
        detector = HandSkeletonDetector(min_detection_confidence=0.1)

        logger.info(f"[ANALYSIS] Starting MediaPipe batch detection on {len(frames)} frames")
        skeleton_results = detector.detect_batch(frames)
        logger.info(f"[ANALYSIS] MediaPipe detection completed, got {len(skeleton_results)} results")

        _log_first_skeleton_result(skeleton_results)

        result = DetectionResult(skeleton_results=skeleton_results)
        result.detectors['mediapipe'] = detector
        return result


class SkeletonAndInstrumentStrategy(DetectionStrategy):
    """骨格検出＋器具検出（EXTERNAL_WITH_INSTRUMENTS）"""

    async def detect(self, frames, video_info, instruments, video_path, extraction_result, use_sam2) -> DetectionResult:
        logger.info("[ANALYSIS] Running both MediaPipe and SAM detection")
        result = DetectionResult()

        # MediaPipe検出
        mediapipe_detector = HandSkeletonDetector(min_detection_confidence=0.1)
        result.detectors['mediapipe'] = mediapipe_detector
        skeleton_results = mediapipe_detector.detect_batch(frames)
        _log_first_skeleton_result(skeleton_results)
        result.skeleton_results = skeleton_results

        # SAM検出
        device = _get_device()
        use_video_api = getattr(settings, 'USE_SAM2_VIDEO_API', False)

        if use_sam2 and use_video_api:
            instrument_results = await self._detect_sam2_video_api(
                frames, video_info, instruments, video_path, extraction_result, device
            )
        elif use_sam2:
            instrument_results, sam_detector = self._detect_sam2_frame(
                frames, instruments, device
            )
            result.detectors['sam'] = sam_detector
        else:
            instrument_results, sam_detector = self._detect_sam1(
                frames, instruments, device
            )
            result.detectors['sam'] = sam_detector

        _log_first_instrument_result(instrument_results)
        result.instrument_results = instrument_results
        return result

    async def _detect_sam2_video_api(
        self, frames, video_info, instruments, video_path, extraction_result, device
    ) -> list:
        """SAM2 Video APIで追跡"""
        logger.info(f"[EXPERIMENTAL] SAM2 Video API: {settings.SAM2_VIDEO_MODEL_TYPE}, device={device}")

        sam_detector = SAM2TrackerVideo(
            model_type=settings.SAM2_VIDEO_MODEL_TYPE,
            device=device
        )
        logger.info("[EXPERIMENTAL] SAM2 Video API: Memory Bank + Temporal Context enabled")

        if instruments and len(instruments) > 0 and len(frames) > 0:
            instruments_converted = convert_instruments_format(instruments)
            logger.info(f"[EXPERIMENTAL] Tracking {len(instruments_converted)} instruments across {len(frames)} frames...")

            for idx, inst in enumerate(instruments_converted):
                logger.info(f"[INSTRUMENT INIT] [{idx}] id={inst['id']}, name={inst['name']}, selection_type={inst['selection']['type']}")

            logger.info(f"[SAM2 VIDEO] Starting video tracking: path={video_path}")
            logger.info(f"[SAM2 VIDEO] Video total frames: {video_info.get('total_frames', 'unknown')}")
            logger.info(f"[SAM2 VIDEO] Video duration: {video_info.get('duration', 'unknown')}s")
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

            if extraction_result:
                instrument_results = convert_video_api_result(
                    tracking_result,
                    total_frames=len(frames),
                    extraction_result=extraction_result
                )
            else:
                instrument_results = convert_video_api_result(tracking_result, len(frames))

            logger.info(f"[EXPERIMENTAL] SAM2 Video API completed: {len(instrument_results)} frames processed")
        else:
            logger.warning("[EXPERIMENTAL] No instruments provided for Video API tracking")
            instrument_results = []

        return instrument_results

    def _detect_sam2_frame(self, frames, instruments, device) -> tuple:
        """SAM2（フレーム単位処理）"""
        logger.info(f"[ANALYSIS] Creating SAM2Tracker with model=small, device={device}")
        sam_detector = SAM2Tracker(model_type="small", device=device)
        logger.info("[ANALYSIS] SAM2 enabled for higher accuracy (+2% Dice, -21% HD95)")

        instrument_results = _init_and_detect_sam_instruments(
            sam_detector, frames, instruments, allow_auto_detect=False
        )
        return instrument_results, sam_detector

    def _detect_sam1(self, frames, instruments, device) -> tuple:
        """SAM1（既存実装）"""
        fps_info = f"instruments={len(instruments) if instruments else 0}"
        logger.info(f"[ANALYSIS] Creating SAMTrackerUnified with model=vit_h, device={device}, {fps_info}")
        sam_detector = SAMTrackerUnified(model_type="vit_h", device=device)

        instrument_results = _init_and_detect_sam_instruments(
            sam_detector, frames, instruments, allow_auto_detect=True
        )
        return instrument_results, sam_detector


class InstrumentOnlyStrategy(DetectionStrategy):
    """器具検出のみ（INTERNAL: 内視鏡映像）"""

    async def detect(self, frames, video_info, instruments, video_path, extraction_result, use_sam2) -> DetectionResult:
        logger.info("[ANALYSIS] Running SAM detection only (internal camera)")
        result = DetectionResult()
        device = _get_device()

        if use_sam2:
            logger.info(f"[ANALYSIS] Creating SAM2Tracker with model=small, device={device}")
            detector = SAM2Tracker(model_type="small", device=device)
            logger.info("[ANALYSIS] SAM2 enabled for higher accuracy (+2% Dice, -21% HD95)")
            allow_auto = False
        else:
            logger.info(f"[ANALYSIS] Creating SAMTrackerUnified with model=vit_h, device={device}")
            detector = SAMTrackerUnified(model_type="vit_h", device=device)
            allow_auto = True

        result.detectors['sam'] = detector

        # 内視鏡はINTERNAL専用のログメッセージ
        if not instruments and len(frames) > 0 and allow_auto:
            logger.info("[ANALYSIS] No user selection, using automatic instrument detection for INTERNAL video")

        instrument_results = _init_and_detect_sam_instruments(
            detector, frames, instruments, allow_auto_detect=allow_auto
        )
        result.instrument_results = instrument_results
        return result


# Strategy selection mapping
_STRATEGY_MAP: Dict[VideoType, DetectionStrategy] = {
    VideoType.EXTERNAL: SkeletonOnlyStrategy(),
    VideoType.EXTERNAL_NO_INSTRUMENTS: SkeletonOnlyStrategy(),
    VideoType.EXTERNAL_WITH_INSTRUMENTS: SkeletonAndInstrumentStrategy(),
    VideoType.INTERNAL: InstrumentOnlyStrategy(),
}

_FALLBACK_STRATEGY = SkeletonOnlyStrategy()


def get_detection_strategy(video_type: VideoType) -> DetectionStrategy:
    """
    動画タイプに応じた検出戦略を返す。

    Args:
        video_type: 動画タイプ

    Returns:
        対応するDetectionStrategyインスタンス
    """
    strategy = _STRATEGY_MAP.get(video_type)
    if strategy is None:
        logger.warning(f"Unknown video type: {video_type}, defaulting to MediaPipe only")
        return _FALLBACK_STRATEGY
    return strategy


async def run_detection(
    frames: List[np.ndarray],
    video_type: VideoType,
    video_info: Dict[str, Any],
    instruments: Optional[List[Dict]],
    video_path: Path,
    extraction_result: Optional[ExtractionResult],
    use_sam2: bool,
) -> DetectionResult:
    """
    動画タイプに基づく検出処理の実行（Strategy patternファサード）

    Args:
        frames: フレームリスト
        video_type: 動画タイプ
        video_info: 動画情報
        instruments: 器具定義
        video_path: 動画ファイルパス（絶対パス）
        extraction_result: フレーム抽出結果
        use_sam2: SAM2を使用するか

    Returns:
        DetectionResult
    """
    logger.info(f"[ANALYSIS] _run_detection started: video_type={video_type}, frames={len(frames)}")

    strategy = get_detection_strategy(video_type)
    return await strategy.detect(
        frames=frames,
        video_info=video_info,
        instruments=instruments,
        video_path=video_path,
        extraction_result=extraction_result,
        use_sam2=use_sam2,
    )
