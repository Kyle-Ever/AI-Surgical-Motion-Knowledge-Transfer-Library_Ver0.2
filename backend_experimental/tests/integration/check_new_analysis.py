#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新規解析の進捗を監視"""

import sys
import io
import time
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ANALYSIS_ID = "82126be4-1b46-463e-b853-0fe147f2d72c"
BASE_URL = "http://localhost:8000/api/v1"

print(f"🔍 解析進捗監視開始: {ANALYSIS_ID}\n")

for i in range(60):  # 最大5分
    try:
        response = requests.get(f"{BASE_URL}/analysis/{ANALYSIS_ID}/status")
        data = response.json()

        status = data.get('status', 'unknown')
        progress = data.get('progress', 0)
        current_step = data.get('current_step', '')
        error_message = data.get('error_message', '')

        print(f"[{i+1}/60] 進捗: {progress}% - {status} - {current_step}")

        if status in ['completed', 'COMPLETED']:
            print("\n✅ 解析完了！")

            # 解析結果を取得
            detail_response = requests.get(f"{BASE_URL}/analysis/{ANALYSIS_ID}")
            if detail_response.ok:
                detail = detail_response.json()

                # 器具データを確認
                if detail.get('instrument_data'):
                    print(f"\n📊 器具データ: {len(detail['instrument_data'])} フレーム")

                    # 回転BBoxをチェック
                    rotated_count = 0
                    total_reduction = 0
                    reduction_count = 0

                    for frame in detail['instrument_data'][:10]:  # 最初の10フレーム
                        if frame.get('instruments'):
                            for inst in frame['instruments']:
                                if inst.get('rotated_bbox'):
                                    rotated_count += 1
                                    if inst.get('area_reduction', 0) > 0:
                                        total_reduction += inst['area_reduction']
                                        reduction_count += 1

                    if rotated_count > 0:
                        print(f"✅ 回転BBox検出: {rotated_count} 個")
                        if reduction_count > 0:
                            avg = total_reduction / reduction_count
                            print(f"📐 平均面積削減率: {avg:.1f}%")
                    else:
                        print("⚠️  回転BBoxが検出されませんでした")

            break

        if status in ['failed', 'FAILED']:
            print(f"\n❌ 解析失敗: {error_message}")
            break

        time.sleep(5)

    except Exception as e:
        print(f"エラー: {e}")
        time.sleep(5)

print(f"\n📋 ダッシュボードURL: http://localhost:3000/dashboard/{ANALYSIS_ID}")
