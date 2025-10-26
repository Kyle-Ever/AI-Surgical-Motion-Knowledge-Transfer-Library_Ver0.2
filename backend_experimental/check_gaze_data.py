import sqlite3
import json

# 両方のデータベースをチェック
for db_name in ['aimotion.db', 'aimotion_experimental.db']:
    print(f"\n{'='*60}")
    print(f"Database: {db_name}")
    print('='*60)

    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # スキーマ確認
        print("\n[analysis_results schema]")
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")

        # 指定された解析データを確認
        analysis_id = '3c1dd5c5-6f09-465f-8a6a-de3b1b8483fc'
        print(f"\n[Analysis {analysis_id}]")

        # gaze_dataカラムが存在するか確認
        column_names = [col[1] for col in columns]
        if 'gaze_data' in column_names:
            cursor.execute('''
                SELECT a.id, v.video_type, a.status,
                       CASE WHEN a.gaze_data IS NULL THEN 'NULL' ELSE 'EXISTS' END as gaze_data_status,
                       a.created_at
                FROM analysis_results a
                JOIN videos v ON v.id = a.video_id
                WHERE a.id = ?
            ''', (analysis_id,))
        else:
            print("  ⚠️ gaze_data column does NOT exist")
            cursor.execute('''
                SELECT a.id, v.video_type, a.status, a.created_at
                FROM analysis_results a
                JOIN videos v ON v.id = a.video_id
                WHERE a.id = ?
            ''', (analysis_id,))

        result = cursor.fetchone()
        if result:
            print(f"  Found: {result}")

            # gaze_dataの内容を確認（存在する場合）
            if 'gaze_data' in column_names:
                cursor.execute('SELECT gaze_data FROM analysis_results WHERE id = ?', (analysis_id,))
                gaze_data_raw = cursor.fetchone()
                if gaze_data_raw and gaze_data_raw[0]:
                    gaze_data = json.loads(gaze_data_raw[0])
                    print(f"\n  gaze_data structure:")
                    print(f"    - frames: {len(gaze_data.get('frames', []))} frames")
                    if gaze_data.get('frames'):
                        first_frame = gaze_data['frames'][0]
                        print(f"    - first frame keys: {list(first_frame.keys())}")
                        print(f"    - fixations count: {len(first_frame.get('fixations', []))}")
                    if gaze_data.get('summary'):
                        print(f"    - summary: {gaze_data['summary']}")
                else:
                    print("  gaze_data is NULL")
        else:
            print(f"  Not found in this database")

        conn.close()

    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*60)
