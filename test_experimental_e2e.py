#!/usr/bin/env python3
"""
Experimental Backend E2E Test
Tests the complete workflow: upload -> analyze -> get analysis ID
"""

import requests
import json
import time
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8001/api/v1"
VIDEO_PATH = Path(__file__).parent / "backend_experimental" / "data" / "uploads" / "5d83bfd5-42dd-40e7-a0a9-c383cecd06b9.mp4"

def test_health():
    """Test if backend is healthy"""
    print("=== Checking Backend Health ===")
    response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/api/v1/health")
    print(f"Health Status: {response.json()}")
    return response.status_code == 200

def upload_video():
    """Upload a test video"""
    print("\n=== Uploading Video ===")

    if not VIDEO_PATH.exists():
        print(f"ERROR: Video file not found: {VIDEO_PATH}")
        return None

    print(f"Video file: {VIDEO_PATH}")
    print(f"File size: {VIDEO_PATH.stat().st_size / 1024 / 1024:.2f} MB")

    # Prepare upload
    with open(VIDEO_PATH, 'rb') as video_file:
        files = {
            'file': (VIDEO_PATH.name, video_file, 'video/mp4')
        }
        data = {
            'video_type': 'external_with_instruments',
            'surgery_name': 'E2E Test Surgery',
            'surgeon_name': 'Test Surgeon',
            'memo': 'Automated E2E test'
        }

        print(f"Uploading to: {BASE_URL}/videos/upload")
        response = requests.post(
            f"{BASE_URL}/videos/upload",
            files=files,
            data=data,
            timeout=120
        )

    if response.status_code in [200, 201]:
        video_data = response.json()
        video_id = video_data.get('video_id')
        print(f"[OK] Upload successful!")
        print(f"  Video ID: {video_id}")
        return video_id
    else:
        print(f"[FAIL] Upload failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def start_analysis(video_id):
    """Start analysis for the uploaded video"""
    print(f"\n=== Starting Analysis for Video: {video_id} ===")

    response = requests.post(
        f"{BASE_URL}/analysis/{video_id}/analyze",
        json={"video_id": video_id}
    )

    if response.status_code in [200, 201]:
        analysis_data = response.json()
        analysis_id = analysis_data.get('id')
        print(f"[OK] Analysis started!")
        print(f"  Analysis ID: {analysis_id}")
        return analysis_id
    else:
        print(f"[FAIL] Analysis start failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def monitor_analysis(analysis_id, max_wait=120):
    """Monitor analysis progress"""
    print(f"\n=== Monitoring Analysis: {analysis_id} ===")

    start_time = time.time()
    last_status = None

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{BASE_URL}/analysis/{analysis_id}/status")

            if response.status_code == 200:
                status_data = response.json()
                current_status = status_data.get('status')
                progress = status_data.get('progress', 0)
                current_step = status_data.get('current_step', 'unknown')

                if current_status != last_status:
                    print(f"  Status: {current_status} | Step: {current_step} | Progress: {progress}%")
                    last_status = current_status

                # Check if completed or failed
                if current_status == 'completed':
                    print(f"\n[OK] Analysis completed successfully!")
                    return True
                elif current_status == 'failed':
                    error_msg = status_data.get('error_message', 'Unknown error')
                    print(f"\n[FAIL] Analysis failed: {error_msg}")
                    return False

                # Show progress updates
                if progress > 0 and progress % 10 == 0:
                    elapsed = time.time() - start_time
                    print(f"  Progress: {progress}% (elapsed: {elapsed:.1f}s)")

            time.sleep(3)

        except Exception as e:
            print(f"Error checking status: {e}")
            time.sleep(3)

    print(f"\n[WARN] Timeout after {max_wait}s (last status: {last_status})")
    return False

def get_analysis_results(analysis_id):
    """Get final analysis results"""
    print(f"\n=== Getting Analysis Results ===")

    response = requests.get(f"{BASE_URL}/analysis/{analysis_id}")

    if response.status_code == 200:
        results = response.json()
        print(f"[OK] Results retrieved")
        print(f"  Status: {results.get('status')}")
        print(f"  Total frames: {results.get('total_frames', 'N/A')}")
        print(f"  Duration: {results.get('duration', 'N/A')}s")
        return results
    else:
        print(f"[FAIL] Failed to get results: {response.status_code}")
        return None

def main():
    """Main test flow"""
    print("=" * 60)
    print("EXPERIMENTAL BACKEND E2E TEST")
    print("=" * 60)

    # 1. Health check
    if not test_health():
        print("\n[FAIL] Backend is not healthy!")
        sys.exit(1)

    # 2. Upload video
    video_id = upload_video()
    if not video_id:
        print("\n[FAIL] Video upload failed!")
        sys.exit(1)

    # 3. Start analysis
    analysis_id = start_analysis(video_id)
    if not analysis_id:
        print("\n[FAIL] Analysis start failed!")
        sys.exit(1)

    # 4. Monitor progress
    success = monitor_analysis(analysis_id, max_wait=120)

    # 5. Get results (even if not completed)
    results = get_analysis_results(analysis_id)

    # Final summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Video ID: {video_id}")
    print(f"Analysis ID: {analysis_id}")
    print(f"Dashboard URL: http://localhost:3000/dashboard/{analysis_id}")
    print(f"Status: {'[SUCCESS]' if success else '[INCOMPLETE/FAILED]'}")
    print("=" * 60)

    # Return analysis ID for manual inspection
    return analysis_id

if __name__ == "__main__":
    try:
        analysis_id = main()
        print(f"\n[SUCCESS] Analysis ID: {analysis_id}")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
