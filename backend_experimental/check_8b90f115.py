import sqlite3
import json

conn = sqlite3.connect('aimotion_experimental.db')
c = conn.cursor()

# 解析結果を取得
c.execute('SELECT id, status, progress, error_message, skeleton_data, instrument_data FROM analysis_results WHERE id=?',
          ('8b90f115-d0eb-4441-b210-2bae194f8897',))
row = c.fetchone()

if row:
    analysis_id, status, progress, error_msg, skel_data, inst_data = row

    print(f"=== Analysis {analysis_id[:8]} ===")
    print(f"Status: {status}")
    print(f"Progress: {progress}%")
    print(f"Error: {error_msg if error_msg else 'None'}")
    print()

    # Skeleton data
    if skel_data:
        skel = json.loads(skel_data)
        print(f"Skeleton frames: {len(skel)}")
    else:
        print("Skeleton data: None")

    # Instrument data
    if inst_data:
        inst = json.loads(inst_data)
        print(f"Instrument data length: {len(inst)}")

        if len(inst) > 0:
            print(f"First frame keys: {list(inst[0].keys())}")

            # 検出があったフレームを確認
            detected_frames = [i for i, frame in enumerate(inst) if frame.get('detections') and len(frame['detections']) > 0]
            print(f"Frames with detections: {len(detected_frames)}/{len(inst)}")

            if detected_frames:
                print(f"\n✅ SUCCESS! First detection frame {detected_frames[0]}:")
                print(f"   Detections: {inst[detected_frames[0]]['detections']}")

                # 最後の検出フレームも確認
                if len(detected_frames) > 1:
                    print(f"\n   Last detection frame {detected_frames[-1]}:")
                    print(f"   Total detection frames: {len(detected_frames)}")
            else:
                print("\n❌ FAILED: No detections found")
    else:
        print("Instrument data: None")
else:
    print('Analysis not found')

conn.close()
