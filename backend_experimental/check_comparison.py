#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""比較データの確認スクリプト"""

import sqlite3
import json
from pathlib import Path
import sys
import io

# Windows環境でUTF-8出力を強制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# データベースファイルのパス
db_path = Path(__file__).parent / "aimotion.db"

if not db_path.exists():
    print(f"❌ データベースが見つかりません: {db_path}")
    exit(1)

def check_comparison(comparison_id: str):
    """比較データを確認"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 80)
    print(f"比較データ確認: {comparison_id}")
    print("=" * 80)

    # 比較データを取得
    cursor.execute("""
        SELECT
            id,
            reference_model_id,
            learner_analysis_id,
            overall_score,
            created_at
        FROM comparison_results
        WHERE id = ?
    """, (comparison_id,))

    comparison = cursor.fetchone()

    if not comparison:
        print(f"\n❌ 比較データが見つかりません: {comparison_id}")
        conn.close()
        return

    comp_id, ref_model_id, learner_analysis_id, score, created = comparison
    print(f"\n✅ 比較データが見つかりました")
    print(f"  ID: {comp_id}")
    print(f"  基準モデルID: {ref_model_id}")
    print(f"  学習者解析ID: {learner_analysis_id}")
    print(f"  総合スコア: {score}")
    print(f"  作成日時: {created}")

    # 基準モデルの解析IDから動画IDを取得
    cursor.execute("""
        SELECT ar.video_id
        FROM reference_models rm
        JOIN analysis_results ar ON rm.analysis_id = ar.id
        WHERE rm.id = ?
    """, (ref_model_id,))
    ref_model = cursor.fetchone()
    ref_vid = ref_model[0] if ref_model else None

    # 学習者解析から動画IDを取得
    cursor.execute("""
        SELECT video_id
        FROM analysis_results
        WHERE id = ?
    """, (learner_analysis_id,))
    learner_analysis = cursor.fetchone()
    eval_vid = learner_analysis[0] if learner_analysis else None

    print(f"\n  基準動画ID: {ref_vid}")
    print(f"  評価動画ID: {eval_vid}")

    # 基準動画を確認
    print(f"\n--- 基準動画 ({ref_vid}) ---")
    cursor.execute("""
        SELECT id, filename, original_filename, file_path, video_type
        FROM videos
        WHERE id = ?
    """, (ref_vid,))
    ref_video = cursor.fetchone()

    if ref_video:
        vid, fname, orig_fname, fpath, vtype = ref_video
        print(f"  ファイル名: {fname}")
        print(f"  元ファイル名: {orig_fname}")
        print(f"  ファイルパス: {fpath}")
        print(f"  タイプ: {vtype}")

        # ファイルが存在するか確認
        video_path = Path(fpath)
        if video_path.exists():
            size_mb = video_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ ファイル存在: {size_mb:.2f} MB")
        else:
            print(f"  ❌ ファイルが見つかりません: {fpath}")
    else:
        print(f"  ❌ 動画データが見つかりません")

    # 評価動画を確認
    print(f"\n--- 評価動画 ({eval_vid}) ---")
    cursor.execute("""
        SELECT id, filename, original_filename, file_path, video_type
        FROM videos
        WHERE id = ?
    """, (eval_vid,))
    eval_video = cursor.fetchone()

    if eval_video:
        vid, fname, orig_fname, fpath, vtype = eval_video
        print(f"  ファイル名: {fname}")
        print(f"  元ファイル名: {orig_fname}")
        print(f"  ファイルパス: {fpath}")
        print(f"  タイプ: {vtype}")

        # ファイルが存在するか確認
        video_path = Path(fpath)
        if video_path.exists():
            size_mb = video_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ ファイル存在: {size_mb:.2f} MB")
        else:
            print(f"  ❌ ファイルが見つかりません: {fpath}")
    else:
        print(f"  ❌ 動画データが見つかりません")

    conn.close()
    print("=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_comparison.py <comparison_id>")
        print()
        print("Example:")
        print("  python check_comparison.py af35d155-a0b8-4ebf-a37f-efd5c702b1c4")
        sys.exit(1)

    comparison_id = sys.argv[1]
    check_comparison(comparison_id)
