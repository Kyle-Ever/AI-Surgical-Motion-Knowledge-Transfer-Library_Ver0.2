#!/usr/bin/env python
"""Test analysis processing directly"""

import asyncio
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.models.video import Video
from app.api.routes.analysis import process_video_analysis
import uuid

async def test_analysis():
    # Connect to database
    engine = create_engine(settings.DATABASE_URL, connect_args={'check_same_thread': False})
    Session = sessionmaker(bind=engine)
    db = Session()

    # Get a video to test with
    video = db.query(Video).first()
    if not video:
        print("No videos in database")
        return

    print(f"Testing with video: {video.id} - {video.original_filename}")

    # Create a test analysis
    analysis_id = str(uuid.uuid4())
    analysis = AnalysisResult(
        id=analysis_id,
        video_id=video.id,
        status=AnalysisStatus.PENDING,
        progress=0
    )

    db.add(analysis)
    db.commit()
    print(f"Created analysis: {analysis_id}")

    # Run the analysis processing
    print("Starting analysis processing...")
    try:
        await process_video_analysis(
            analysis_id=analysis_id,
            video_id=video.id,
            instruments=[],
            sampling_rate=5
        )
        print("Analysis processing completed")
    except Exception as e:
        print(f"Analysis processing failed: {e}")
        import traceback
        traceback.print_exc()

    # Check the final status
    db.refresh(analysis)
    print(f"Final analysis status: {analysis.status}")
    print(f"Final progress: {analysis.progress}")

    db.close()

if __name__ == "__main__":
    asyncio.run(test_analysis())