#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基準モデルの動画ファイル存在確認スクリプト"""

import sqlite3
import sys
import io
from pathlib import Path

# UTF-8出力設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def verify_reference_videos():
    """基準モデルに紐づく動画ファイルの存在を確認"""

    conn = sqlite3.connect('aimotion.db')
    cursor = conn.cursor()

    # 基準モデル一覧を取得
    cursor.execute("""
        SELECT
            rm.id,
            rm.name,
            rm.surgeon_name,
            rm.analysis_id,
            ar.video_id,
            v.filename,
            v.file_path
        FROM reference_models rm
        LEFT JOIN analysis_results ar ON rm.analysis_id = ar.id
        LEFT JOIN videos v ON ar.video_id = v.id
        WHERE rm.is_active = 1
        ORDER BY rm.created_at DESC
    """)

    results = cursor.fetchall()

    print("=" * 80)
    print("基準モデルと動画ファイル存在確認")
    print("=" * 80)
    print()

    total = len(results)
    with_video = 0
    missing_video = 0

    for idx, (ref_id, name, surgeon, analysis_id, video_id, filename, file_path) in enumerate(results, 1):
        print(f"[{idx}/{total}] {name}")
        print(f"  術者: {surgeon or '未設定'}")
        print(f"  基準モデルID: {ref_id[:8]}...")
        print(f"  解析ID: {analysis_id[:8] if analysis_id else 'なし'}...")
        print(f"  動画ID: {video_id[:8] if video_id else 'なし'}...")

        if file_path:
            video_file = Path(file_path)
            if video_file.exists():
                size_mb = video_file.stat().st_size / (1024 * 1024)
                print(f"  ✅ 動画ファイル: {file_path} ({size_mb:.2f} MB)")
                with_video += 1
            else:
                print(f"  ❌ 動画ファイルが見つかりません: {file_path}")
                missing_video += 1
        else:
            print(f"  ❌ 動画ファイルパスがデータベースにありません")
            missing_video += 1

        print()

    print("=" * 80)
    print(f"📊 集計結果:")
    print(f"  合計基準モデル: {total}件")
    print(f"  ✅ 動画ファイルあり: {with_video}件")
    print(f"  ❌ 動画ファイルなし: {missing_video}件")
    print("=" * 80)

    conn.close()

if __name__ == '__main__':
    verify_reference_videos()
