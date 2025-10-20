# -*- coding: utf-8 -*-
import sqlite3
import json

conn = sqlite3.connect('aimotion_experimental.db')
c = conn.cursor()

# Get analysis info
c.execute('''SELECT v.video_type, a.status, a.instrument_data
             FROM analysis_results a
             JOIN videos v ON a.video_id = v.id
             WHERE a.id=?''', ('5cb40515-b17a-48e0-b10f-f983a249a7b0',))
row = c.fetchone()

if row:
    video_type, status, inst_data = row
    print(f"Video type: {video_type}")
    print(f"Status: {status}")

    if inst_data:
        inst = json.loads(inst_data)
        print(f"Instrument data frames: {len(inst)}")

        if len(inst) > 0:
            # Check for detections
            has_data = sum(1 for f in inst if f.get('detections') and len(f['detections']) > 0)
            print(f"Frames with detections: {has_data}/{len(inst)}")

            if has_data > 0:
                for i, frame in enumerate(inst):
                    if frame.get('detections') and len(frame['detections']) > 0:
                        print(f"\n[SUCCESS] First detection at frame {i}:")
                        print(f"  Detection: {frame['detections'][0]}")
                        break
            else:
                print("\n[FAILED] No detections found")
                print(f"Sample frame 0: {inst[0]}")
    else:
        print("Instrument data: None (no instrument tracking)")
else:
    print("Analysis not found")

conn.close()
