"""
SAM Auto-Detection Direct Test
"""
import cv2
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified

def test_auto_detection():
    video_path = Path("data/uploads/test_video.mp4")
    if not video_path.exists():
        logger.error(f"Video not found: {video_path}")
        return False

    logger.info(f"Loading video: {video_path}")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error("Failed to open video")
        return False

    ret, frame = cap.read()
    if not ret:
        logger.error("Failed to read first frame")
        cap.release()
        return False

    logger.info(f"Frame shape: {frame.shape}")

    try:
        logger.info("Initializing SAMTrackerUnified...")
        tracker = SAMTrackerUnified(device='cpu')
        logger.info("Initialized successfully")
    except Exception as e:
        logger.error(f"Init failed: {e}")
        import traceback
        traceback.print_exc()
        cap.release()
        return False

    try:
        logger.info("Running auto_detect_instruments()...")
        tracker.auto_detect_instruments(frame, max_instruments=5)
        logger.info(f"Found {len(tracker.tracked_instruments)} instruments")

        for inst in tracker.tracked_instruments:
            logger.info(f"  Instrument {inst['id']}: {inst['name']}, bbox={inst['last_bbox']}, score={inst['last_score']:.4f}")
    except Exception as e:
        logger.error(f"Auto-detection failed: {e}")
        import traceback
        traceback.print_exc()
        cap.release()
        return False

    logger.info("\nTesting tracking on next 5 frames...")
    for i in range(1, 6):
        ret, frame = cap.read()
        if not ret:
            break

        detections = tracker.track_frame(frame)
        logger.info(f"Frame {i}: {len(detections)} detections")
        for det in detections:
            logger.info(f"  {det['class_name']}: conf={det['confidence']:.4f}")

    cap.release()
    stats = tracker.get_tracking_stats()
    logger.info(f"\nStats: {stats}")
    return True

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("SAM Auto-Detection Direct Test")
    logger.info("=" * 60)
    success = test_auto_detection()
    logger.info("\n" + ("✓ SUCCESS" if success else "✗ FAILED"))
    sys.exit(0 if success else 1)
