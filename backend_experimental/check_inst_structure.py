import sqlite3
import json

conn = sqlite3.connect('aimotion_experimental.db')
c = conn.cursor()
c.execute('SELECT instrument_data FROM analysis_results WHERE id=?',
          ('482f9643-71d0-417a-bb61-8e35298a65f2',))
row = c.fetchone()

if row and row[0]:
    inst = json.loads(row[0])
    print(f'Type: {type(inst)}')
    print(f'Length: {len(inst)}')

    if len(inst) > 0:
        print(f'\nFirst element type: {type(inst[0])}')
        print(f'First element keys: {list(inst[0].keys())}')
        print(f'First element: {inst[0]}')

    if len(inst) > 1:
        print(f'\nSecond element: {inst[1]}')

    # 検出があったフレームを確認
    detected_frames = [i for i, frame in enumerate(inst) if frame.get('detections')]
    print(f'\nFrames with detections: {len(detected_frames)}')
    if detected_frames:
        print(f'First detection frame index: {detected_frames[0]}')
        print(f'First detection: {inst[detected_frames[0]]}')
else:
    print('No instrument data')

conn.close()
