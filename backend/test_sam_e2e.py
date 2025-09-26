"""End-to-end test for SAM instrument tracking integration"""
import requests
import json
import base64
import time
from pathlib import Path

def test_sam_e2e():
    """Test the complete SAM instrument tracking flow"""
    base_url = "http://localhost:8000/api/v1"

    print("=" * 60)
    print("SAM Instrument Tracking - End-to-End Test")
    print("=" * 60)

    # 1. Upload video
    print("\n1. Uploading video...")
    test_video = Path("test.mp4")

    with open(test_video, "rb") as f:
        files = {"file": ("test.mp4", f, "video/mp4")}
        data = {
            "video_type": "internal",
            "surgery_name": "SAM E2E Test"
        }
        response = requests.post(f"{base_url}/videos/upload", files=files, data=data)

    if response.status_code != 201:
        print(f"Upload failed: {response.text}")
        return

    upload_result = response.json()
    video_id = upload_result["video_id"]
    print(f"[OK] Video uploaded: {video_id}")

    # 2. Get thumbnail
    print("\n2. Getting thumbnail...")
    response = requests.get(f"{base_url}/videos/{video_id}/thumbnail")

    if response.status_code == 200:
        print(f"[OK] Thumbnail retrieved: {len(response.content)} bytes")
    else:
        print(f"[ERROR] Thumbnail failed: {response.status_code}")

    # 3. Segment instrument using SAM
    print("\n3. Performing SAM segmentation...")
    segment_data = {
        "prompt_type": "box",
        "coordinates": [[200, 150, 440, 330]],
        "frame_number": 0
    }

    response = requests.post(
        f"{base_url}/videos/{video_id}/segment",
        json=segment_data
    )

    if response.status_code != 200:
        print(f"[ERROR] Segmentation failed: {response.text}")
        return

    result = response.json()
    print(f"[OK] Segmentation successful!")
    print(f"   - Score: {result['score']:.3f}")
    print(f"   - Area: {result['area']} pixels")

    # 4. Register instruments
    print("\n4. Registering instruments...")
    instruments_data = {
        "instruments": [
            {
                "name": "Surgical Forceps",
                "bbox": result["bbox"],
                "frame_number": 0,
                "mask": result["mask"]
            }
        ]
    }

    response = requests.post(
        f"{base_url}/videos/{video_id}/instruments",
        json=instruments_data
    )

    if response.status_code != 200:
        print(f"[ERROR] Registration failed: {response.text}")
        return

    reg_result = response.json()
    print(f"[OK] Instruments registered: {reg_result['instruments_count']} items")

    # 5. Verify instruments are saved
    print("\n5. Verifying saved instruments...")
    response = requests.get(f"{base_url}/videos/{video_id}/instruments")

    if response.status_code == 200:
        inst_result = response.json()
        print(f"[OK] Retrieved {len(inst_result['instruments'])} instruments:")
        for inst in inst_result['instruments']:
            print(f"   - {inst['name']} at bbox {inst['bbox']}")
    else:
        print(f"[ERROR] Get instruments failed: {response.text}")

    # 6. Start analysis with SAM tracking
    print("\n6. Starting analysis with SAM tracking...")
    analysis_data = {
        "video_id": video_id,
        "motion_type": "reaching",
        "description": "Test analysis with SAM tracking"
    }

    response = requests.post(
        f"{base_url}/analysis/{video_id}/analyze",
        json=analysis_data
    )

    if response.status_code not in [200, 201]:
        print(f"[ERROR] Analysis start failed: {response.text}")
        return

    analysis_result = response.json()
    analysis_id = analysis_result.get("analysis_id") or analysis_result.get("id")
    print(f"[OK] Analysis started: {analysis_id}")

    # 7. Monitor analysis progress
    print("\n7. Monitoring analysis progress...")
    max_attempts = 60  # 60 seconds timeout

    for attempt in range(max_attempts):
        response = requests.get(f"{base_url}/analysis/{analysis_id}/status")

        if response.status_code != 200:
            print(f"[ERROR] Status check failed: {response.text}")
            break

        status_data = response.json()
        # Debug: show available fields
        if attempt == 0:
            print(f"   Available fields: {list(status_data.keys())}")

        # Check different possible status field names
        status = status_data.get("status") or status_data.get("analysis_status", "unknown")
        progress = status_data.get("progress", 0)

        print(f"   [{attempt+1}/{max_attempts}] Status: {status}, Progress: {progress}%")

        if status == "completed":
            print(f"[OK] Analysis completed successfully!")
            break
        elif status == "failed":
            print(f"[ERROR] Analysis failed: {status_data.get('error')}")
            break

        time.sleep(1)

    # 8. Get final results
    print("\n8. Getting analysis results...")
    response = requests.get(f"{base_url}/analysis/{analysis_id}")

    if response.status_code == 200:
        final_result = response.json()
        print(f"[OK] Analysis results retrieved:")

        # Check if SAM tracking was used
        if "instrument_data" in final_result.get("result_data", {}):
            instrument_data = final_result["result_data"]["instrument_data"]
            frames_with_detections = len([d for d in instrument_data if d.get("detections")])
            print(f"   - Instruments detected in {frames_with_detections} frames")

            # Check if we have SAM-tracked instruments
            if instrument_data and instrument_data[0].get("detections"):
                first_detection = instrument_data[0]["detections"][0]
                if first_detection.get("class") == "Surgical Forceps":
                    print(f"   >>> SAM tracking confirmed! Detected: {first_detection['class']}")
                else:
                    print(f"   - Standard detection used: {first_detection['class']}")

        print(f"   - Final score: {final_result.get('final_score', 0):.1f}")
    else:
        print(f"[ERROR] Get results failed: {response.text}")

    print("\n" + "=" * 60)
    print("End-to-End Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    test_sam_e2e()