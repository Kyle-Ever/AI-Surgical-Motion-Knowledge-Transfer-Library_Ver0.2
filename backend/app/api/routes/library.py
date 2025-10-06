"""Library endpoints for completed analyses."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
import csv
import io
from datetime import datetime

from app.models import get_db
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.models.video import Video
from app.schemas.analysis import AnalysisResultResponse

router = APIRouter()

@router.get(
    "/completed",
    response_model=List[AnalysisResultResponse],
    summary="Get completed analyses",
)
async def get_completed_analyses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get list of completed analyses with video information - sorted by created_at desc"""

    analyses = db.query(AnalysisResult).filter(
        AnalysisResult.status == AnalysisStatus.COMPLETED
    ).order_by(AnalysisResult.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for analysis in analyses:
        video = db.query(Video).filter(Video.id == analysis.video_id).first()

        analysis_dict = {
            "id": analysis.id,
            "video_id": analysis.video_id,
            "status": analysis.status,
            "skeleton_data": analysis.skeleton_data,
            "instrument_data": analysis.instrument_data,
            "motion_analysis": analysis.motion_analysis,
            "scores": analysis.scores,
            "avg_velocity": analysis.avg_velocity,
            "max_velocity": analysis.max_velocity,
            "total_distance": analysis.total_distance,
            "total_frames": analysis.total_frames,
            "created_at": analysis.created_at,
            "completed_at": analysis.completed_at,
            "video": {
                "id": video.id,
                "filename": video.filename,
                "original_filename": video.original_filename,
                "duration": video.duration,
                "file_size": video.file_size,
                "created_at": video.created_at
            } if video else None
        }
        result.append(analysis_dict)

    return result

@router.get(
    "/export/{analysis_id}",
    summary="Export analysis data as CSV",
)
async def export_analysis(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """Export analysis data as CSV"""

    analysis = db.query(AnalysisResult).filter(
        AnalysisResult.id == analysis_id
    ).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    video = db.query(Video).filter(Video.id == analysis.video_id).first()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Analysis Export Report"])
    writer.writerow(["Generated at", datetime.now().isoformat()])
    writer.writerow([])

    writer.writerow(["Basic Information"])
    writer.writerow(["Analysis ID", analysis.id])
    writer.writerow(["Video ID", analysis.video_id])
    writer.writerow(["Status", analysis.status])
    writer.writerow(["Created At", analysis.created_at])
    writer.writerow(["Completed At", analysis.completed_at or "N/A"])
    writer.writerow([])

    if video:
        writer.writerow(["Video Information"])
        writer.writerow(["Filename", video.original_filename])
        writer.writerow(["Duration", f"{video.duration:.2f} seconds" if video.duration else "N/A"])
        writer.writerow(["File Size", f"{video.file_size / (1024*1024):.2f} MB" if video.file_size else "N/A"])
        writer.writerow([])

    writer.writerow(["Analysis Metrics"])
    writer.writerow(["Average Velocity", analysis.avg_velocity or "N/A"])
    writer.writerow(["Max Velocity", analysis.max_velocity or "N/A"])
    writer.writerow(["Total Distance", analysis.total_distance or "N/A"])
    writer.writerow(["Total Frames", analysis.total_frames or "N/A"])
    writer.writerow([])

    if analysis.scores:
        writer.writerow(["Scores"])
        for key, value in analysis.scores.items():
            writer.writerow([key, value])
        writer.writerow([])

    if analysis.skeleton_data:
        writer.writerow(["Skeleton Data Summary"])
        writer.writerow(["Frame Count", len(analysis.skeleton_data)])
        writer.writerow([])

    if analysis.instrument_data:
        writer.writerow(["Instrument Data Summary"])
        writer.writerow(["Detection Count", len(analysis.instrument_data)])

    csv_content = output.getvalue()
    output.close()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=analysis_{analysis_id}.csv"
        }
    )