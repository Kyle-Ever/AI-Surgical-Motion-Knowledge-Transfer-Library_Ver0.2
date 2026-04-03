#!/usr/bin/env python
"""
Phase 1 BBox精度検証スクリプト

Phase 1で実装した以下の改善を検証:
1. マルチポイントプロンプト生成
2. BBox精密化（ノイズ除去）
3. 細長い器具への対応

既存の解析データでBBox統計を確認し、精度が妥当かチェック
"""

import sqlite3
import json
import statistics

def verify_phase1_improvements():
    # データベース接続
    conn = sqlite3.connect('aimotion.db')
    cursor = conn.cursor()

    # 器具データを持つ解析を取得
    cursor.execute("""
        SELECT id, video_id, instrument_data
        FROM analysis_results
        WHERE instrument_data IS NOT NULL
        AND status = 'COMPLETED'
        ORDER BY created_at DESC
        LIMIT 5
    """)

    analyses = cursor.fetchall()
    print(f"[INFO] 器具データを持つ解析: {len(analyses)}件\n")

    for analysis_id, video_id, instrument_data_json in analyses:
        print(f"{'='*80}")
        print(f"解析ID: {analysis_id[:20]}...")
        print(f"ビデオID: {video_id[:20]}...")

        try:
            instrument_data = json.loads(instrument_data_json)
        except json.JSONDecodeError:
            print("[WARN] JSONデコードエラー - スキップ\n")
            continue

        if not instrument_data:
            print("[WARN] 器具データが空 - スキップ\n")
            continue

        print(f"フレーム数: {len(instrument_data)}\n")

        # BBox統計の収集
        bbox_areas = []
        bbox_widths = []
        bbox_heights = []
        aspect_ratios = []
        instruments_per_frame = []

        frames_with_instruments = 0

        for frame_data in instrument_data:
            if not isinstance(frame_data, dict):
                continue

            # Try both 'instruments' and 'detections' keys
            instruments = frame_data.get('instruments', frame_data.get('detections', []))
            if instruments:
                frames_with_instruments += 1
                instruments_per_frame.append(len(instruments))

            for instrument in instruments:
                bbox = instrument.get('bbox')
                if bbox and len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    width = x2 - x1
                    height = y2 - y1

                    # 妥当性チェック
                    if width > 0 and height > 0 and width < 10000 and height < 10000:
                        area = width * height
                        bbox_areas.append(area)
                        bbox_widths.append(width)
                        bbox_heights.append(height)

                        # アスペクト比（細長さの指標）
                        aspect_ratio = max(width / height, height / width)
                        aspect_ratios.append(aspect_ratio)

        # 統計計算
        if bbox_areas:
            print(f"[DETECT] 器具検出フレーム: {frames_with_instruments}/{len(instrument_data)} ({frames_with_instruments/len(instrument_data)*100:.1f}%)")

            if instruments_per_frame:
                print(f"[STATS] フレーム当たり器具数: 平均 {statistics.mean(instruments_per_frame):.1f}, 最大 {max(instruments_per_frame)}")

            print(f"\n[BBOX] BBox統計:")
            print(f"  サンプル数: {len(bbox_areas)}個")
            print(f"  面積:  平均 {statistics.mean(bbox_areas):.0f}px^2,  中央値 {statistics.median(bbox_areas):.0f}px^2")
            print(f"  幅:    平均 {statistics.mean(bbox_widths):.0f}px,  中央値 {statistics.median(bbox_widths):.0f}px")
            print(f"  高さ:  平均 {statistics.mean(bbox_heights):.0f}px,  中央値 {statistics.median(bbox_heights):.0f}px")
            print(f"  アスペクト比: 平均 {statistics.mean(aspect_ratios):.2f},  中央値 {statistics.median(aspect_ratios):.2f}")

            # Phase 1 検証ポイント
            print(f"\n[PHASE1] Phase 1 検証ポイント:")

            # 1. BBox精密化の検証（ノイズ除去後は適度なサイズになる）
            avg_area = statistics.mean(bbox_areas)
            frame_area = 720 * 480  # 仮定のフレームサイズ
            area_ratio = avg_area / frame_area

            print(f"  1. BBox精密化: ")
            print(f"     - BBox/フレーム比率: {area_ratio*100:.1f}%")
            if area_ratio < 0.5:
                print(f"     [OK] 正常範囲（<50%）- ノイズ除去が機能している可能性")
            else:
                print(f"     [WARN] 大きすぎる可能性（>50%）")

            # 2. 細長い器具への対応
            avg_aspect = statistics.mean(aspect_ratios)
            elongated_count = sum(1 for ar in aspect_ratios if ar > 1.5)

            print(f"  2. 細長い器具対応:")
            print(f"     - 平均アスペクト比: {avg_aspect:.2f}")
            print(f"     - 細長い器具（AR>1.5）: {elongated_count}/{len(aspect_ratios)} ({elongated_count/len(aspect_ratios)*100:.1f}%)")
            if avg_aspect > 1.5:
                print(f"     [OK] 細長い器具を検出 - マルチポイントプロンプト適用対象")
            else:
                print(f"     [INFO] 比較的正方形に近い器具")

            # 3. BBoxの安定性（標準偏差が小さければ安定）
            if len(bbox_areas) > 1:
                area_stdev = statistics.stdev(bbox_areas)
                cv = area_stdev / statistics.mean(bbox_areas) * 100  # 変動係数
                print(f"  3. BBox安定性:")
                print(f"     - 面積の標準偏差: {area_stdev:.0f}px^2")
                print(f"     - 変動係数: {cv:.1f}%")
                if cv < 50:
                    print(f"     [OK] 安定したトラッキング（CV<50%）")
                else:
                    print(f"     [WARN] 変動が大きい（CV>50%）")
        else:
            print("[WARN] 有効なBBoxデータなし")

        print()

    conn.close()

    print(f"\n{'='*80}")
    print("[SUMMARY] Phase 1 検証まとめ:")
    print("  - BBox精密化: ノイズ除去後の面積比率で確認")
    print("  - 細長い器具対応: アスペクト比 > 1.5 でマルチポイント適用")
    print("  - 安定性: 変動係数（CV）で確認")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    verify_phase1_improvements()
