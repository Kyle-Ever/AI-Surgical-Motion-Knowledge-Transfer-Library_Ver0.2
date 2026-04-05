"""
Data conversion utilities for analysis results.

Pure functions extracted from AnalysisServiceV2 for reuse and testability.
"""
import logging
from typing import Dict, List, Any, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def convert_numpy_types(obj):
    """
    Convert numpy types to Python native types for JSON serialization.

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
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    return obj


def extract_mask_contour(mask: Optional[np.ndarray]) -> List[List[int]]:
    """
    Extract contour coordinates from a binary mask (lightweight representation).

    Args:
        mask: numpy mask array (H, W), or None

    Returns:
        List of contour points [[x, y], ...]
    """
    if mask is None:
        return []

    if not isinstance(mask, np.ndarray):
        return []

    try:
        if mask.dtype in (np.float32, np.float64):
            binary_mask = (mask > 0.5).astype(np.uint8)
        else:
            binary_mask = mask.astype(np.uint8)

        if binary_mask.sum() == 0:
            return []

        contours, _ = cv2.findContours(
            binary_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if len(contours) == 0:
            return []

        largest_contour = max(contours, key=cv2.contourArea)
        epsilon = 0.003 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)

        return approx.reshape(-1, 2).tolist()

    except Exception as e:
        logger.warning(f"[CONTOUR] Failed to extract contour: {e}")
        return []


def get_video_info(video_path: str) -> Dict:
    """
    Get video metadata (resolution, fps, duration).

    Args:
        video_path: Path to the video file

    Returns:
        Dict with width, height, fps, total_frames, duration
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    try:
        info = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': 0,
        }
        if info['fps'] <= 0:
            logger.warning(f"Invalid FPS ({info['fps']}), using default 30fps")
            info['fps'] = 30.0
        info['duration'] = info['total_frames'] / info['fps']
        return info
    finally:
        cap.release()
