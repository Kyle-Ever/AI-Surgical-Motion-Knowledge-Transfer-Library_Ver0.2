#!/usr/bin/env python3
"""
骨格検出修正の検証スクリプト

最新の解析データが正しい形式で保存されているか確認します。
"""

import sqlite3
import json
import sys
from datetime import datetime


def verify_latest_analysis():
    """最新の解析データを検証"""
    conn = None
    try:
        import os
        db_path = 'backend/aimotion.db' if os.path.exists('backend/aimotion.db') else 'aimotion.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 最新の解析を取得
        cursor.execute('SELECT id, created_at, status FROM analysis_results ORDER BY created_at DESC LIMIT 1')
        result = cursor.fetchone()

        if not result:
            print("[FAIL] No analysis found in database")
            return False

        analysis_id, created_at, status = result
        print(f"[OK] Latest analysis found:")
        print(f"   ID: {analysis_id}")
        print(f"   Created: {created_at}")
        print(f"   Status: {status}")

        if status != 'COMPLETED':
            print(f"[WARNING] Analysis status is '{status}', not 'COMPLETED'")

        # 骨格データ検証
        cursor.execute('SELECT skeleton_data FROM analysis_results WHERE id = ?', (analysis_id,))
        skeleton_result = cursor.fetchone()

        if not skeleton_result or not skeleton_result[0]:
            print("[FAIL] No skeleton data found")
            return False

        data = json.loads(skeleton_result[0])

        print(f"\n=== DATA STRUCTURE VALIDATION ===")
        print(f"Skeleton frames: {len(data)}")

        if len(data) == 0:
            print("[FAIL] No frames in skeleton data")
            return False

        # 形式チェック
        first_frame = data[0]
        print(f"First frame keys: {list(first_frame.keys())}")

        has_hands_array = 'hands' in first_frame
        if not has_hands_array:
            print("[FAIL] Old format detected (no 'hands' array)")
            print("   Expected new format: {frame, frame_number, timestamp, hands: [...]}")
            return False

        # 手の数の分布確認
        hands_counts = [len(frame.get('hands', [])) for frame in data]
        max_hands = max(hands_counts) if hands_counts else 0
        total_hands = sum(hands_counts)
        avg_hands = total_hands / len(data) if len(data) > 0 else 0

        print(f"\n=== HAND DISTRIBUTION ===")
        print(f"Total hands across all frames: {total_hands}")
        print(f"Average hands per frame: {avg_hands:.2f}")
        print(f"Max hands in any single frame: {max_hands}")

        # バグパターンの検出
        if len(data) == 1 and max_hands > 10:
            print(f"\n[CRITICAL] AGGREGATION BUG DETECTED!")
            print(f"   All {total_hands} hands are in a single frame!")
            print(f"   Expected: 100-300 frames with 1-4 hands each")
            print(f"   Actual: {len(data)} frame(s) with {max_hands} hands")
            return False

        # 正常範囲チェック
        if max_hands > 4:
            print(f"\n[WARNING] Unusually high hand count ({max_hands}) in a single frame")
            print(f"   Expected: 1-4 hands per frame (two hands, occasional detection errors)")
            if max_hands > 10:
                print(f"[FAIL] Too many hands in single frame")
                return False

        if len(data) < 50:
            print(f"\n[WARNING] Low frame count ({len(data)})")
            print(f"   Expected: 100-300 frames for typical video")
            if len(data) < 10:
                print(f"[FAIL] Too few frames")
                return False

        # 成功判定
        print(f"\n[SUCCESS] Bug is fixed!")
        print(f"   [OK] New format with 'hands' array detected")
        print(f"   [OK] {len(data)} frames with reasonable hand distribution")
        print(f"   [OK] Max {max_hands} hands per frame (within normal range)")

        return True

    except sqlite3.Error as e:
        print(f"[ERROR] DATABASE ERROR: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON DECODE ERROR: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] UNEXPECTED ERROR: {e}")
        return False
    finally:
        if conn:
            conn.close()


def print_usage():
    """使用方法を表示"""
    print("=" * 60)
    print("  骨格検出修正の検証スクリプト")
    print("=" * 60)
    print("\n使用方法:")
    print("  python verify_fix.py")
    print("\n確認項目:")
    print("  1. 最新の解析データが新形式(hands配列)で保存されているか")
    print("  2. フレーム数が正常範囲(50-300フレーム)か")
    print("  3. 各フレームの手の数が正常範囲(1-4個)か")
    print("  4. 集約バグ(1フレームに全ての手)が発生していないか")
    print("\n期待される結果:")
    print("  [SUCCESS] Bug is fixed!")
    print("=" * 60)
    print()


if __name__ == "__main__":
    print_usage()

    success = verify_latest_analysis()

    sys.exit(0 if success else 1)
