"""Script to add mock instrument data to existing analysis for demonstration"""
import json
from app.models import SessionLocal, AnalysisResult

def add_mock_instrument_data(analysis_id: str):
    """Add mock instrument data to demonstrate instrument tracking overlay"""
    db = SessionLocal()

    try:
        # Get the analysis
        analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()

        if not analysis:
            print(f"Analysis {analysis_id} not found")
            return

        print(f"Found analysis: {analysis.id}")
        print(f"Video ID: {analysis.video_id}")
        print(f"Total frames: {analysis.total_frames}")

        # Generate mock instrument data
        instrument_data = []
        total_frames = analysis.total_frames or 100

        for i in range(0, total_frames, 5):  # Every 5th frame
            timestamp = i / 30.0  # Assuming 30 fps

            # Mock forceps detection
            detections = []
            if i % 10 < 7:  # Instrument appears 70% of the time
                x = 200 + (i % 50) * 2
                y = 150 + (i % 30)
                detections.append({
                    "class_name": "forceps",
                    "confidence": 0.85 + (i % 20) * 0.005,
                    "bbox": [x, y, x + 80, y + 40]  # [x1, y1, x2, y2] format
                })

            # Add scissors occasionally
            if i % 20 < 5:
                x = 350 + (i % 40)
                y = 200 + (i % 25) * 2
                detections.append({
                    "class_name": "scissors",
                    "confidence": 0.80 + (i % 15) * 0.01,
                    "bbox": [x, y, x + 70, y + 35]  # [x1, y1, x2, y2] format
                })

            instrument_data.append({
                "frame": i,
                "timestamp": timestamp,
                "detections": detections
            })

        # Update the analysis with instrument data
        analysis.instrument_data = instrument_data

        db.commit()
        print(f"Successfully added {len(instrument_data)} frames of instrument data")
        print(f"First frame with instruments: {instrument_data[0] if instrument_data else 'None'}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # The analysis ID from the URL
    analysis_id = "d8e933f7-8818-4443-8115-d846608a0276"
    add_mock_instrument_data(analysis_id)