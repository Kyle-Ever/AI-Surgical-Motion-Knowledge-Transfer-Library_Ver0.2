import sqlite3
import json

conn = sqlite3.connect('aimotion_experimental.db')
c = conn.cursor()
c.execute('SELECT skeleton_data, instrument_data FROM analysis_results WHERE id=?',
          ('8715fe07-a51e-4cfd-8ed1-f2af5eb1c93e',))
row = c.fetchone()

if row:
    skel = json.loads(row[0]) if row[0] else None
    inst = json.loads(row[1]) if row[1] else None

    print(f'Skeleton frames: {len(skel) if skel else 0}')
    print(f'Instrument data exists: {inst is not None}')

    if inst:
        print(f'Instrument data length: {len(inst)}')
        if len(inst) > 0:
            print(f'First element keys: {list(inst[0].keys())}')
            print(f'First element: {inst[0]}')

            # 検出があったフレームを確認
            detected_frames = [i for i, frame in enumerate(inst) if frame.get('detections') and len(frame['detections']) > 0]
            print(f'\nFrames with detections: {len(detected_frames)}/{len(inst)}')
            if detected_frames:
                print(f'First detection frame: {inst[detected_frames[0]]}')
else:
    print('Analysis not found')

conn.close()
