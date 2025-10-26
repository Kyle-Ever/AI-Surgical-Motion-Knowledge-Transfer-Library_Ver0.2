#!/usr/bin/env python
"""解析データの確認スクリプト"""

import sqlite3
from pathlib import Path

# データベースファイルのパス
db_path = Path(__file__).parent / "aimotion.db"

if not db_path.exists():
    print(f"❌ データベースが見つかりません: {db_path}")
    exit(1)

# データベース接続
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 80)
print("解析データ確認")
print("=" * 80)

# 解析データを取得
cursor.execute("""
    SELECT
        id,
        status,
        created_at,
        video_id,
        total_frames
    FROM analysis_results
    ORDER BY created_at DESC
    LIMIT 20
""")

analyses = cursor.fetchall()

if not analyses:
    print("\n解析データが見つかりません")
else:
    print(f"\n最新の解析データ（{len(analyses)}件）:")
    print("-" * 80)
    for idx, (aid, status, created_at, vid, frames) in enumerate(analyses, 1):
        print(f"{idx}. ID: {aid}")
        print(f"   Status: {status}")
        print(f"   Frames: {frames}")
        print(f"   Video ID: {vid}")
        print(f"   Created: {created_at}")
        print()

# 各statusの件数
print("-" * 80)
print("ステータス別集計:")
cursor.execute("""
    SELECT status, COUNT(*) as count
    FROM analysis_results
    GROUP BY status
""")
status_counts = cursor.fetchall()
for status, count in status_counts:
    print(f"  {status}: {count}件")

conn.close()
print("=" * 80)
