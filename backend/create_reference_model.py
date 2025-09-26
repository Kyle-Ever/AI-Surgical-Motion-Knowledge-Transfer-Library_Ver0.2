"""
基準モデルを作成するスクリプト
エキスパートの手技を基準として登録する
"""

import sqlite3
import json
import uuid
from datetime import datetime

def create_reference_model():
    """サンプル基準モデルを作成"""
    conn = sqlite3.connect('aimotion.db')
    cursor = conn.cursor()

    # 利用可能な解析結果を確認
    cursor.execute("""
        SELECT id, video_id, status, total_frames
        FROM analysis_results
        WHERE status = 'COMPLETED'
        ORDER BY created_at DESC
        LIMIT 5
    """)

    analyses = cursor.fetchall()
    if not analyses:
        print("No completed analyses found")
        conn.close()
        return

    print("Available analyses:")
    for i, (aid, vid, status, frames) in enumerate(analyses):
        print(f"  {i+1}. Analysis ID: {aid[:8]}..., Video: {vid[:8]}..., Frames: {frames}")

    # 最初の解析結果を基準モデルとして使用
    analysis_id = analyses[0][0]

    # 既存の基準モデルをチェック
    cursor.execute("""
        SELECT COUNT(*) FROM reference_models
        WHERE analysis_id = ?
    """, (analysis_id,))

    if cursor.fetchone()[0] > 0:
        print(f"Reference model already exists for analysis {analysis_id}")

        # 既存の基準モデルを取得
        cursor.execute("""
            SELECT id, name FROM reference_models
            WHERE analysis_id = ?
        """, (analysis_id,))
        ref_id, ref_name = cursor.fetchone()
        print(f"Existing reference: ID={ref_id}, Name={ref_name}")
        conn.close()
        return ref_id

    # 新しい基準モデルを作成
    reference_id = str(uuid.uuid4())

    # スコアデータ（エキスパートレベルの高スコア）
    weights = {
        "speed": 0.25,
        "smoothness": 0.25,
        "stability": 0.25,
        "efficiency": 0.25
    }

    cursor.execute("""
        INSERT INTO reference_models (
            id, name, description, analysis_id,
            reference_type, surgeon_name, surgery_type,
            surgery_date, weights,
            avg_speed_score, avg_smoothness_score,
            avg_stability_score, avg_efficiency_score,
            created_at, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 1)
    """, (
        reference_id,
        "エキスパート基準モデル",
        "熟練外科医による標準的な手技動作",
        analysis_id,
        "expert",
        "山田太郎医師",
        "腹腔鏡手術",
        datetime.now().isoformat(),
        json.dumps(weights),
        95.0,  # 速度スコア
        92.0,  # 滑らかさスコア
        94.0,  # 安定性スコア
        90.0,  # 効率性スコア
    ))

    conn.commit()
    print(f"Successfully created reference model: {reference_id}")
    print(f"  Name: エキスパート基準モデル")
    print(f"  Analysis ID: {analysis_id}")
    print(f"  Scores: Speed=95, Smoothness=92, Stability=94, Efficiency=90")

    conn.close()
    return reference_id

def create_multiple_reference_models():
    """複数の基準モデルを作成（異なるレベル）"""
    conn = sqlite3.connect('aimotion.db')
    cursor = conn.cursor()

    # 利用可能な解析結果を取得
    cursor.execute("""
        SELECT id FROM analysis_results
        WHERE status = 'COMPLETED'
        ORDER BY created_at DESC
        LIMIT 3
    """)

    analyses = cursor.fetchall()
    if len(analyses) < 1:
        print("Not enough completed analyses")
        conn.close()
        return

    # 異なるレベルの基準モデルを作成
    reference_models = [
        {
            "name": "上級者基準モデル",
            "description": "10年以上の経験を持つ熟練医師",
            "scores": {"speed": 95, "smoothness": 92, "stability": 94, "efficiency": 90}
        },
        {
            "name": "中級者基準モデル",
            "description": "5年程度の経験を持つ医師",
            "scores": {"speed": 85, "smoothness": 82, "stability": 84, "efficiency": 80}
        },
        {
            "name": "初級者目標モデル",
            "description": "研修医が目指すべき基準",
            "scores": {"speed": 75, "smoothness": 70, "stability": 72, "efficiency": 68}
        }
    ]

    created_ids = []
    for i, model_data in enumerate(reference_models):
        if i >= len(analyses):
            break

        analysis_id = analyses[i % len(analyses)][0]

        # 既存チェック
        cursor.execute("""
            SELECT COUNT(*) FROM reference_models
            WHERE name = ?
        """, (model_data["name"],))

        if cursor.fetchone()[0] > 0:
            print(f"Reference model '{model_data['name']}' already exists")
            continue

        reference_id = str(uuid.uuid4())
        weights = {
            "speed": 0.25,
            "smoothness": 0.25,
            "stability": 0.25,
            "efficiency": 0.25
        }

        cursor.execute("""
            INSERT INTO reference_models (
                id, name, description, analysis_id,
                reference_type, surgeon_name, surgery_type,
                surgery_date, weights,
                avg_speed_score, avg_smoothness_score,
                avg_stability_score, avg_efficiency_score,
                created_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 1)
        """, (
            reference_id,
            model_data["name"],
            model_data["description"],
            analysis_id,
            "standard",
            f"標準モデル{i+1}",
            "腹腔鏡手術",
            datetime.now().isoformat(),
            json.dumps(weights),
            float(model_data["scores"]["speed"]),
            float(model_data["scores"]["smoothness"]),
            float(model_data["scores"]["stability"]),
            float(model_data["scores"]["efficiency"])
        ))

        created_ids.append(reference_id)
        print(f"Created: {model_data['name']} (ID: {reference_id})")

    conn.commit()
    conn.close()

    return created_ids

if __name__ == "__main__":
    print("Creating reference models...")

    # 単一の基準モデルを作成
    ref_id = create_reference_model()

    # 複数レベルの基準モデルを作成
    print("\nCreating multiple level reference models...")
    ref_ids = create_multiple_reference_models()

    print("\nReference models created successfully!")