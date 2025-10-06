#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2.5: 回転BBox実装検証スクリプト

既存の解析データに回転BBoxを追加して、実装が正しく動作するか確認
"""

import sys
import io
import json
import sqlite3
import numpy as np
from pathlib import Path

# Windows環境での文字コード問題を回避
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified

def verify_rotated_bbox_implementation():
    """回転BBox実装を検証"""

    print("🔍 Phase 2.5: 回転BBox実装検証\n")

    # データベースから最新の器具検出データを取得
    conn = sqlite3.connect('aimotion.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, video_id, instrument_data
        FROM analysis_results
        WHERE status = 'COMPLETED'
          AND instrument_data IS NOT NULL
          AND instrument_data != '[]'
        ORDER BY created_at DESC
        LIMIT 1
    """)

    row = cursor.fetchone()

    if not row:
        print("❌ 器具検出データが見つかりません")
        conn.close()
        return False

    analysis_id, video_id, instrument_data_json = row
    print(f"📊 解析ID: {analysis_id}")
    print(f"📹 動画ID: {video_id}")

    instrument_data = json.loads(instrument_data_json)
    print(f"✅ 器具データ取得: {len(instrument_data)} フレーム\n")

    # SAMTrackerインスタンスを作成
    tracker = SAMTrackerUnified(
        model_type="vit_b",
        checkpoint_path="sam_b.pt",
        device="cpu"
    )

    print("🔧 回転BBox計算テスト開始...\n")

    # テスト用のマスクデータを作成
    test_cases = [
        {
            "name": "垂直器具",
            "mask": create_vertical_mask(150, 150),
            "expected_reduction": 0  # ほぼ0%
        },
        {
            "name": "水平器具",
            "mask": create_horizontal_mask(150, 150),
            "expected_reduction": 0  # ほぼ0%
        },
        {
            "name": "45度斜め器具",
            "mask": create_diagonal_mask(150, 150),
            "expected_reduction": 30  # 30%以上
        }
    ]

    all_passed = True

    for idx, test_case in enumerate(test_cases, 1):
        print(f"[{idx}] {test_case['name']}:")

        # 回転BBoxを計算
        result = tracker._get_rotated_bbox_from_mask(test_case['mask'])

        # 結果を検証
        if not result['rotated_bbox']:
            print(f"   ❌ 回転BBoxが計算されませんでした")
            all_passed = False
            continue

        rotated_bbox = result['rotated_bbox']
        rotation_angle = result['rotation_angle']
        area_reduction = result['area_reduction']

        # 回転BBoxの形式チェック
        if len(rotated_bbox) != 4:
            print(f"   ❌ 回転BBoxの点数が不正: {len(rotated_bbox)} (期待: 4)")
            all_passed = False
            continue

        for point in rotated_bbox:
            if len(point) != 2:
                print(f"   ❌ 点の座標が不正: {point}")
                all_passed = False
                continue

        # 面積削減率のチェック
        expected = test_case['expected_reduction']
        if expected > 0:
            if area_reduction < expected:
                print(f"   ⚠️  面積削減率が期待値を下回る: {area_reduction:.1f}% (期待: >{expected}%)")
                all_passed = False
            else:
                print(f"   ✅ 面積削減率: {area_reduction:.1f}% (期待: >{expected}%)")
        else:
            print(f"   ✅ 面積削減率: {area_reduction:.1f}%")

        print(f"   ✅ 回転角度: {rotation_angle:.1f}°")
        print(f"   ✅ 回転BBox: {rotated_bbox[0]} → {rotated_bbox[2]}\n")

    # 実際の器具データで検証
    print("🔬 実際の器具データで検証...\n")

    frames_with_instruments = [f for f in instrument_data if f.get('instruments')]

    if not frames_with_instruments:
        print("⚠️  器具データが見つかりません（既存データには含まれない可能性）")
    else:
        sample_frame = frames_with_instruments[0]
        print(f"サンプルフレーム {sample_frame['frame_number']}:")

        for inst in sample_frame['instruments']:
            if 'rotated_bbox' in inst:
                print(f"   ✅ 回転BBoxフィールドが存在")
                print(f"      回転角度: {inst.get('rotation_angle', 'N/A')}°")
                print(f"      面積削減: {inst.get('area_reduction', 'N/A')}%")
            else:
                print(f"   ℹ️  回転BBoxフィールドなし（既存データのため正常）")

    conn.close()

    if all_passed:
        print("\n🎉 回転BBox実装検証: 成功！")
        print("✅ すべてのテストケースがパスしました")
        return True
    else:
        print("\n❌ 回転BBox実装検証: 失敗")
        print("⚠️  一部のテストケースが期待値を満たしていません")
        return False


def create_vertical_mask(height, width):
    """垂直器具のマスクを生成"""
    mask = np.zeros((height, width), dtype=np.uint8)
    # 中央に垂直な細長い領域
    mask[20:130, 70:80] = 255
    return mask


def create_horizontal_mask(height, width):
    """水平器具のマスクを生成"""
    mask = np.zeros((height, width), dtype=np.uint8)
    # 中央に水平な細長い領域
    mask[70:80, 20:130] = 255
    return mask


def create_diagonal_mask(height, width):
    """45度斜め器具のマスクを生成"""
    mask = np.zeros((height, width), dtype=np.uint8)
    # 対角線上にマスクを描画
    for i in range(20, 130):
        x = i
        y = i
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if 0 <= x+dx < width and 0 <= y+dy < height:
                    mask[y+dy, x+dx] = 255
    return mask


if __name__ == "__main__":
    success = verify_rotated_bbox_implementation()
    sys.exit(0 if success else 1)
