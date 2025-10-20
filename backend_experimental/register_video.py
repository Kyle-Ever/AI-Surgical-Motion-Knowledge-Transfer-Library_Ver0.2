#!/usr/bin/env python
"""Register a video file directly into the database"""
import sys
import cv2
import uuid
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.models.video import Video, VideoType

def register_video(video_path: str, video_type: str = "internal"):
    """Register video in database"""

    # Check file exists
    video_file = Path(video_path)
    if not video_file.exists():
        print(f"❌ File not found: {video_path}")
        return None

    # Get video metadata
    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        print(f"❌ Cannot open video: {video_path}")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()

    # Connect to database
    engine = create_engine('sqlite:///./aimotion.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check if video already registered
        existing = session.query(Video).filter(
            Video.file_path == str(video_file)
        ).first()

        if existing:
            print(f"✅ Video already registered: {existing.id}")
            print(f"   Filename: {existing.filename}")
            print(f"   Duration: {existing.duration}s")
            print(f"   FPS: {existing.fps}")
            return existing.id

        # Create new video record
        video_id = str(uuid.uuid4())
        video = Video(
            id=video_id,
            filename=video_file.name,
            file_path=str(video_file),
            duration=duration,
            fps=fps,
            frame_count=frame_count,
            width=width,
            height=height,
            video_type=VideoType(video_type),
            created_at=datetime.utcnow()
        )

        session.add(video)
        session.commit()

        print(f"✅ Video registered successfully!")
        print(f"   ID: {video_id}")
        print(f"   Filename: {video_file.name}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   FPS: {fps}")
        print(f"   Frames: {frame_count}")
        print(f"   Resolution: {width}x{height}")

        return video_id

    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        return None
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python register_video.py <video_path> [video_type]")
        sys.exit(1)

    video_path = sys.argv[1]
    video_type = sys.argv[2] if len(sys.argv) > 2 else "internal"

    register_video(video_path, video_type)
