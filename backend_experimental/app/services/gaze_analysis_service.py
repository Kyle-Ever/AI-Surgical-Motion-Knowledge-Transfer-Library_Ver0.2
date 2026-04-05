"""
Gaze Analysis Service - Eye gaze analysis pipeline using DeepGaze III.

Extracted from AnalysisServiceV2 as an independent service.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisResult, AnalysisStatus, get_jst_now
from app.models.video import Video
from app.core.websocket import manager
from app.ai_engine.processors.gaze_analyzer import GazeAnalyzer
from .frame_extraction_service import FrameExtractionService, ExtractionConfig
from .data_converter import convert_numpy_types, get_video_info

logger = logging.getLogger(__name__)

# Default gaze analysis parameters
DEFAULT_GAZE_PARAMS = {
    'center_bias_weight': 0.6,
    'saccade_radius': 60,
    'ior_decay': 0.9,
    'add_corner_seeds': True,
    'num_fixations': 8,
    'gamma': 1.2,
    'blur_sigma': 5,
    'alpha': 0.6,
    'heat_threshold': 0.1,
    'circle_size': 6,
    'line_thickness': 2,
    'show_numbers': False,
}


class GazeAnalysisService:
    """Eye gaze analysis using DeepGaze III."""

    def __init__(self):
        self.gaze_analyzer: Optional[GazeAnalyzer] = None
        self.frame_extraction_service = FrameExtractionService(
            ExtractionConfig(target_fps=15, use_round=True)
        )

    def _get_video_info(self, video_path: str) -> Dict:
        """Get video metadata (data_converterに委譲)."""
        return get_video_info(video_path)

    async def _update_status(
        self,
        analysis_result: AnalysisResult,
        step: str,
        db: Session,
        progress: int = 0,
    ):
        """Update analysis progress in the database."""
        analysis_result.current_step = step
        analysis_result.progress = progress
        db.commit()

    async def analyze(
        self,
        video: Video,
        analysis_result: AnalysisResult,
        analysis_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Run the full eye gaze analysis pipeline.

        Args:
            video: Video model instance
            analysis_result: AnalysisResult to update
            analysis_id: Analysis ID for WebSocket progress
            db: Database session

        Returns:
            Result dict with status, gaze_data, etc.
        """
        logger.info(f"[GAZE] === Starting Eye Gaze Analysis ===")
        logger.info(f"[GAZE] video_id: {video.id}, analysis_id: {analysis_id}")

        try:
            # Resolve video path
            video_path = Path(video.file_path)
            if not video_path.is_absolute():
                backend_dir = Path(__file__).parent.parent.parent
                video_path = backend_dir / video_path
            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")

            # 1. Initialize GazeAnalyzer (lazy)
            await self._update_status(analysis_result, "initialization", db, progress=5)
            if self.gaze_analyzer is None:
                logger.info("[GAZE] Initializing GazeAnalyzer...")
                loop = asyncio.get_event_loop()
                self.gaze_analyzer = await loop.run_in_executor(
                    None, lambda: GazeAnalyzer(device="auto")
                )
                logger.info("[GAZE] GazeAnalyzer initialized")
            await self._update_status(analysis_result, "initialization", db, progress=10)

            # 2. Get original video resolution
            video_info = self._get_video_info(str(video_path))
            original_width = video_info['width']
            original_height = video_info['height']
            logger.info(f"[GAZE] Original resolution: {original_width}x{original_height}")

            # 3. Extract frames (use original FPS for gaze analysis)
            await self._update_status(analysis_result, "frame_extraction", db, progress=15)
            loop = asyncio.get_event_loop()
            extraction_result = await loop.run_in_executor(
                None,
                lambda: self.frame_extraction_service.extract_frames(
                    str(video_path), target_fps=video_info['fps']
                )
            )
            frames = extraction_result.frames
            if not frames:
                raise ValueError("No frames extracted from video")

            frame_height, frame_width = frames[0].shape[:2]
            logger.info(f"[GAZE] Extracted {len(frames)} frames at {frame_width}x{frame_height}")
            await self._update_status(analysis_result, "frame_extraction", db, progress=30)

            # 4. Analyze each frame
            await self._update_status(analysis_result, "gaze_detection", db, progress=35)
            gaze_results = []
            total_fixations = 0
            attention_hotspots: Dict[tuple, int] = {}
            scale_x = original_width / frame_width
            scale_y = original_height / frame_height
            gaze_params = dict(DEFAULT_GAZE_PARAMS)

            for idx, frame in enumerate(frames):
                progress = 35 + int((idx / len(frames)) * 50)
                if idx % 10 == 0:
                    await self._update_status(analysis_result, "gaze_detection", db, progress=progress)
                    await manager.send_progress(analysis_id, {
                        "type": "progress",
                        "step": "gaze_detection",
                        "progress": progress,
                        "message": f"視線解析中: {idx}/{len(frames)} フレーム",
                    })

                try:
                    result = await loop.run_in_executor(
                        None, self.gaze_analyzer.analyze_frame, frame, gaze_params
                    )
                    fixations = result['fixations']
                    fixations_scaled = [
                        (int(x * scale_x), int(y * scale_y)) for x, y in fixations
                    ]
                    total_fixations += len(fixations_scaled)

                    grid_size = int(20 * scale_x)
                    for fx, fy in fixations_scaled:
                        key = ((fx // grid_size) * grid_size, (fy // grid_size) * grid_size)
                        attention_hotspots[key] = attention_hotspots.get(key, 0) + 1

                    gaze_results.append({
                        'frame_index': idx,
                        'timestamp': extraction_result.timestamps[idx],
                        'fixations': [{'x': x, 'y': y} for x, y in fixations_scaled],
                        'stats': result['stats'],
                    })
                except Exception as e:
                    logger.warning(f"[GAZE] Frame {idx} analysis failed: {e}")
                    gaze_results.append({
                        'frame_index': idx,
                        'timestamp': extraction_result.timestamps[idx],
                        'fixations': [],
                        'stats': {'max_value': 0, 'mean_value': 0, 'high_attention_ratio': 0},
                    })

            await self._update_status(analysis_result, "gaze_detection", db, progress=85)
            logger.info(f"[GAZE] Analysis completed for {len(gaze_results)} frames")

            # 5. Generate summary
            await self._update_status(analysis_result, "report_generation", db, progress=90)
            top_hotspots = sorted(attention_hotspots.items(), key=lambda x: x[1], reverse=True)[:5]
            summary = {
                'total_frames': len(frames),
                'total_fixations': total_fixations,
                'average_fixations_per_frame': total_fixations / len(frames) if frames else 0,
                'attention_hotspots': [list(coord) for coord, _ in top_hotspots],
                'effective_fps': extraction_result.effective_fps,
                'total_duration': extraction_result.timestamps[-1] if extraction_result.timestamps else 0,
                'source_frame_resolution': [frame_width, frame_height],
                'target_video_resolution': [original_width, original_height],
                'scale_factor': round(scale_x, 2),
            }

            # 6. Save to database
            gaze_data = {
                'frames': convert_numpy_types(gaze_results),
                'summary': convert_numpy_types(summary),
                'params': convert_numpy_types(gaze_params),
            }
            analysis_result.gaze_data = convert_numpy_types(gaze_data)
            analysis_result.total_frames = len(frames)
            analysis_result.status = AnalysisStatus.COMPLETED
            analysis_result.completed_at = get_jst_now()
            db.commit()
            db.refresh(analysis_result)

            await self._update_status(analysis_result, "completed", db, progress=100)
            await manager.send_progress(analysis_id, {
                "type": "complete",
                "step": "completed",
                "progress": 100,
                "message": "視線解析が完了しました",
            })

            logger.info(f"[GAZE] === Eye Gaze Analysis Completed ===")
            logger.info(f"[GAZE] Total fixations: {total_fixations}")

            return {
                'status': 'success',
                'video_id': video.id,
                'analysis_id': analysis_id,
                'gaze_data': gaze_data,
            }

        except Exception as e:
            logger.error(f"[GAZE] Eye gaze analysis failed: {e}")
            import traceback
            logger.error(f"[GAZE] Traceback: {traceback.format_exc()}")

            analysis_result.status = AnalysisStatus.FAILED
            analysis_result.error_message = f"{type(e).__name__}: {str(e)}"
            db.commit()

            await manager.send_progress(analysis_id, {
                "type": "error",
                "step": "failed",
                "message": f"視線解析エラー: {str(e)}",
            })

            raise
