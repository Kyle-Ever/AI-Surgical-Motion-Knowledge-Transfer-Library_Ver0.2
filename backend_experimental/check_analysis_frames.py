import sqlite3
import json

conn = sqlite3.connect('aimotion_experimental.db')
c = conn.cursor()
c.execute('SELECT skeleton_data, instrument_data FROM analysis_results WHERE id=?',
          ('482f9643-71d0-417a-bb61-8e35298a65f2',))
row = c.fetchone()

if row:
    skel = json.loads(row[0]) if row[0] else None
    inst = json.loads(row[1]) if row[1] else None

    print(f'Skeleton frames: {len(skel) if skel else 0}')
    print(f'Instrument data exists: {inst is not None}')

    if inst:
        print(f'Number of instruments: {len(inst)}')
        if len(inst) > 0:
            traj = inst[0].get('trajectory', [])
            print(f'First instrument trajectory frames: {len(traj)}')
            if len(traj) > 0:
                print(f'Sample frame keys: {list(traj[0].keys())}')
else:
    print('Analysis not found')

conn.close()
