"""器具追跡API統合テスト"""

import asyncio
import aiohttp
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1"


async def test_instrument_tracking_api():
    """器具追跡APIのテスト"""

    async with aiohttp.ClientSession() as session:
        # 1. ビデオリストを取得
        print("\n" + "="*80)
        print("INSTRUMENT TRACKING API TEST")
        print("="*80)

        print("\n1. Getting video list...")
        async with session.get(f"{BASE_URL}/videos") as resp:
            if resp.status != 200:
                print(f"Failed to get videos: {resp.status}")
                return

            videos = await resp.json()
            if not videos:
                print("No videos found. Please upload a video first.")
                return

            video = videos[0]
            video_id = video['id']
            print(f"Using video: {video['filename']} (ID: {video_id})")

        # 2. 器具追跡の初期化
        print("\n2. Initializing instrument tracking...")

        # テスト用の選択領域（実際の本番環境では、フロントエンドから送信される）
        selections = [
            {
                "name": "Left Instrument",
                "type": "rectangle",
                "data": {
                    "x": 200,
                    "y": 150,
                    "width": 150,
                    "height": 200
                },
                "color": [0, 255, 0]  # Green
            },
            {
                "name": "Right Instrument",
                "type": "rectangle",
                "data": {
                    "x": 400,
                    "y": 150,
                    "width": 150,
                    "height": 200
                },
                "color": [0, 0, 255]  # Red
            }
        ]

        init_request = {
            "video_id": video_id,
            "selections": selections
        }

        async with session.post(
            f"{BASE_URL}/instrument-tracking/initialize",
            json=init_request
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                print(f"Failed to initialize tracking: {resp.status}")
                print(f"Error: {error_text}")
                return

            init_result = await resp.json()
            print(f"Initialization result: {json.dumps(init_result, indent=2)}")

            if not init_result.get('success'):
                print(f"Initialization failed: {init_result.get('error')}")
                return

            tracking_id = init_result['tracking_id']
            total_frames = init_result['total_frames']

        # 3. 単一フレームのテスト追跡
        print("\n3. Testing single frame tracking...")
        frame_request = {
            "tracking_id": tracking_id,
            "frame_number": 10  # 10フレーム目をテスト
        }

        async with session.post(
            f"{BASE_URL}/instrument-tracking/track-frame",
            json=frame_request
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                print(f"Failed to track frame: {resp.status}")
                print(f"Error: {error_text}")
            else:
                frame_result = await resp.json()
                print(f"Frame tracking result:")
                print(json.dumps(frame_result, indent=2))

        # 4. ビデオ全体の処理
        print("\n4. Processing entire video...")
        process_request = {
            "tracking_id": tracking_id,
            "output_video": True
        }

        async with session.post(
            f"{BASE_URL}/instrument-tracking/process-video",
            json=process_request
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                print(f"Failed to process video: {resp.status}")
                print(f"Error: {error_text}")
                return

            process_result = await resp.json()
            print(f"Processing started: {process_result}")

        # 5. ステータス確認（数回）
        print("\n5. Checking processing status...")
        for i in range(5):
            await asyncio.sleep(2)  # 2秒待機

            async with session.get(
                f"{BASE_URL}/instrument-tracking/tracking/{tracking_id}/status"
            ) as resp:
                if resp.status == 200:
                    status = await resp.json()
                    progress = status.get('progress', 0)
                    print(f"Progress: {progress:.1f}% - Frame {status.get('frame_count')}/{status.get('total_frames')}")

                    if progress >= 100:
                        print("Processing completed!")
                        break
                elif resp.status == 404:
                    print("Tracking session not found (might have been cleaned up)")
                    break

        # 6. クリーンアップ
        print("\n6. Cleaning up...")
        async with session.delete(
            f"{BASE_URL}/instrument-tracking/tracking/{tracking_id}"
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"Cleanup result: {result}")

        print("\n" + "="*80)
        print("TEST COMPLETED")
        print("="*80)


async def test_with_polygon_selection():
    """ポリゴン選択のテスト"""

    async with aiohttp.ClientSession() as session:
        print("\n" + "="*80)
        print("POLYGON SELECTION TEST")
        print("="*80)

        # ビデオ取得
        async with session.get(f"{BASE_URL}/videos") as resp:
            videos = await resp.json()
            if not videos:
                print("No videos found")
                return

            video_id = videos[0]['id']

        # ポリゴン選択で初期化
        selections = [
            {
                "name": "Complex Instrument",
                "type": "polygon",
                "data": {
                    "points": [
                        [200, 100],
                        [300, 120],
                        [350, 200],
                        [300, 280],
                        [200, 300],
                        [150, 200]
                    ]
                },
                "color": [255, 0, 255]  # Magenta
            }
        ]

        init_request = {
            "video_id": video_id,
            "selections": selections
        }

        async with session.post(
            f"{BASE_URL}/instrument-tracking/initialize",
            json=init_request
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"Polygon selection initialized:")
                print(json.dumps(result, indent=2))
            else:
                error = await resp.text()
                print(f"Failed: {error}")


if __name__ == "__main__":
    print("Starting Instrument Tracking API Test...")
    print("Make sure the backend server is running (start_both.bat)")

    try:
        # メインテスト
        asyncio.run(test_instrument_tracking_api())

        # ポリゴン選択テスト
        asyncio.run(test_with_polygon_selection())

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the backend server is running on http://localhost:8000")