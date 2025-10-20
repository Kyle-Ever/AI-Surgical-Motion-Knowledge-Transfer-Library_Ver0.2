#!/usr/bin/env python3
"""
存在しない動画ファイルを特定するスクリプト
"""
import sqlite3
from pathlib import Path
import json

def check_missing_videos():
    """データベース内の動画レコードで、実際のファイルが存在しないものを特定"""

    # データベース接続
    conn = sqlite3.connect('aimotion.db')
    cursor = conn.cursor()

    # 全動画レコードを取得
    cursor.execute('''
        SELECT id, filename, file_path, created_at, video_type
        FROM videos
        ORDER BY created_at DESC
    ''')

    videos = cursor.fetchall()

    print(f"[DATABASE] Total videos in database: {len(videos)}")
    print("=" * 80)

    missing_videos = []
    existing_videos = []

    for video in videos:
        video_id, filename, file_path, created_at, video_type = video

        # ファイルパスを確認（Windows/Unix パスの両方に対応）
        if file_path:
            # Windowsパス区切りをUnixに変換
            normalized_path = file_path.replace('\\', '/')
            full_path = Path(normalized_path)
        else:
            full_path = Path('data/uploads') / filename

        if full_path.exists():
            existing_videos.append({
                'id': video_id,
                'filename': filename,
                'path': str(full_path),
                'created_at': created_at,
                'type': video_type
            })
        else:
            missing_videos.append({
                'id': video_id,
                'filename': filename,
                'path': str(full_path),
                'created_at': created_at,
                'type': video_type
            })
            print(f"[MISSING] Video ID: {video_id}")
            print(f"   Filename: {filename}")
            print(f"   Path: {full_path}")
            print(f"   Created: {created_at}")
            print(f"   Type: {video_type}")

            # この動画を使用している分析を確認
            cursor.execute('''
                SELECT id, status, created_at
                FROM analysis_results
                WHERE video_id = ?
            ''', (video_id,))
            analyses = cursor.fetchall()

            if analyses:
                print(f"   [ANALYSES] {len(analyses)} related analyses:")
                for analysis in analyses:
                    print(f"      - {analysis[0]} ({analysis[1]}) - {analysis[2]}")

            # この動画を使用している基準モデルを確認
            cursor.execute('''
                SELECT rm.id, rm.name, a.id as analysis_id
                FROM reference_models rm
                JOIN analysis_results a ON rm.analysis_id = a.id
                WHERE a.video_id = ?
            ''', (video_id,))
            ref_models = cursor.fetchall()

            if ref_models:
                print(f"   [REFERENCE MODELS] {len(ref_models)} models:")
                for ref_model in ref_models:
                    print(f"      - {ref_model[0]} ({ref_model[1]}) - Analysis: {ref_model[2]}")

            print()

    print("=" * 80)
    print(f"[EXISTING] Files found: {len(existing_videos)}")
    print(f"[MISSING] Files not found: {len(missing_videos)}")

    # 結果をJSONファイルに保存
    result = {
        'total_videos': len(videos),
        'existing_count': len(existing_videos),
        'missing_count': len(missing_videos),
        'missing_videos': missing_videos
    }

    with open('missing_videos_report.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n[REPORT] Detailed report saved: missing_videos_report.json")

    conn.close()

    return missing_videos

if __name__ == '__main__':
    missing = check_missing_videos()

    if missing:
        print("\n[WARNING] Missing video files found!")
        print("[NEXT STEP] Run cleanup_missing_videos.py to clean up the database")
    else:
        print("\n[SUCCESS] All video files exist")
