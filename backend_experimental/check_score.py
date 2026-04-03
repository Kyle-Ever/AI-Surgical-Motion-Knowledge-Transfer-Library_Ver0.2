import sqlite3

conn = sqlite3.connect('aimotion.db')
cursor = conn.cursor()

# テーブル一覧を取得
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# 分析データを確認
analysis_id = 'f88cc4cf-54a8-4696-b8dc-71aa8e751009'

# analysis_resultsテーブルを確認
try:
    cursor.execute(f"SELECT * FROM analysis_results WHERE id = '{analysis_id}'")
    columns = [description[0] for description in cursor.description]
    result = cursor.fetchone()
    if result:
        print(f"\nAnalysis {analysis_id}:")
        for i, col in enumerate(columns):
            if 'score' in col.lower() or col in ['id', 'status']:
                print(f"  {col}: {result[i]}")
    else:
        print(f"\nNo analysis found with ID: {analysis_id}")
except Exception as e:
    print(f"Error querying analysis_results: {e}")

conn.close()
