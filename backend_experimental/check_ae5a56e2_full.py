# -*- coding: utf-8 -*-
import sqlite3
import json

conn = sqlite3.connect('aimotion_experimental.db')
c = conn.cursor()

c.execute('SELECT instrument_data FROM analysis_results WHERE id=?',
          ('ae5a56e2-d3f7-4945-a22b-6bf0d7b8003b',))
row = c.fetchone()

if row and row[0]:
    inst = json.loads(row[0])
    print(f"Total frames: {len(inst)}")

    if len(inst) > 0:
        print(f"\nFirst frame:")
        print(f"  Keys: {list(inst[0].keys())}")
        print(f"  frame_number: {inst[0].get('frame_number')}")
        print(f"  timestamp: {inst[0].get('timestamp')}")
        print(f"  detections: {inst[0].get('detections')}")

        # Count frames with detections
        with_det = sum(1 for f in inst if f.get('detections'))
        print(f"\nFrames with 'detections' key: {with_det}")

        # Check actual detection data
        has_data = sum(1 for f in inst if f.get('detections') and len(f['detections']) > 0)
        print(f"Frames with actual detection data: {has_data}")

        if has_data > 0:
            # Find first frame with data
            for i, frame in enumerate(inst):
                if frame.get('detections') and len(frame['detections']) > 0:
                    print(f"\nFirst detection at frame {i}:")
                    print(f"  Detection: {frame['detections'][0]}")
                    break
        else:
            print("\n[ERROR] All detection arrays are empty!")
            print(f"Sample frame 0: {inst[0]}")
            if len(inst) > 1:
                print(f"Sample frame 1: {inst[1]}")
else:
    print("No instrument data")

conn.close()
