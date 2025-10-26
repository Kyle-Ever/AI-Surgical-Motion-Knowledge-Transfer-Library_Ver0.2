#!/usr/bin/env python3
"""
YOLO vs SAM2 自動マスク生成の比較テスト
"""
import requests
import json
import sys

API_URL = "http://localhost:8000/api/v1"

def compare_detection_methods():
    """YOLOとSAM2の検出を比較"""
    print("=" * 80)
    print("YOLO vs SAM2 自動検出比較テスト")
    print("=" * 80)

    # 既存の動画を取得
    response = requests.get(f"{API_URL}/videos/")
    if response.status_code != 200:
        print("[ERROR] 動画取得失敗")
        return False

    videos = response.json()
    if not videos:
        print("[ERROR] テスト用動画がありません")
        return False

    # 最新の動画を使用
    video_id = videos[-1]['id']
    print(f"\nテスト動画ID: {video_id}")
    print(f"動画名: {videos[-1].get('original_filename', 'N/A')}")

    # 動画が実際に存在するか確認
    response = requests.get(f"{API_URL}/videos/{video_id}")
    if response.status_code != 200:
        print(f"[ERROR] 動画 {video_id} が見つかりません")
        return False

    # ========================================
    # 1. YOLO検出
    # ========================================
    print("\n" + "=" * 80)
    print("1. YOLO検出")
    print("=" * 80)

    response = requests.post(
        f"{API_URL}/videos/{video_id}/detect-instruments",
        json={"frame_number": 0}
    )

    if response.status_code != 200:
        print(f"[ERROR] YOLO検出失敗: {response.status_code}")
        yolo_instruments = []
    else:
        yolo_result = response.json()
        yolo_instruments = yolo_result.get('instruments', [])
        print(f"\n検出数: {len(yolo_instruments)}")
        print(f"モデル情報: {yolo_result.get('model_info', {})}")

        for inst in yolo_instruments:
            print(f"\n  器具 #{inst['id']}:")
            print(f"    - 名前: {inst['suggested_name']}")
            print(f"    - 信頼度: {inst['confidence']:.2%}")
            print(f"    - Bbox: {inst['bbox']}")
            print(f"    - 面積: N/A")

    # ========================================
    # 2. SAM2自動マスク生成
    # ========================================
    print("\n" + "=" * 80)
    print("2. SAM2 自動マスク生成")
    print("=" * 80)

    response = requests.post(
        f"{API_URL}/videos/{video_id}/detect-instruments-sam2",
        json={
            "frame_number": 0,
            "min_confidence": 0.5,
            "max_results": 10
        }
    )

    if response.status_code != 200:
        print(f"[ERROR] SAM2検出失敗: {response.status_code}")
        print(f"エラー: {response.text}")
        sam2_instruments = []
    else:
        sam2_result = response.json()
        sam2_instruments = sam2_result.get('instruments', [])
        print(f"\n検出数: {len(sam2_instruments)}")
        print(f"モデル情報: {sam2_result.get('model_info', {})}")

        for inst in sam2_instruments:
            print(f"\n  器具 #{inst['id']}:")
            print(f"    - 名前: {inst['suggested_name']}")
            print(f"    - 信頼度: {inst['confidence']:.2%}")
            print(f"    - Bbox: {inst['bbox']}")
            print(f"    - 面積: {inst['area']} pixels")
            print(f"    - アスペクト比: {inst['aspect_ratio']:.2f}")

    # ========================================
    # 3. 比較結果
    # ========================================
    print("\n" + "=" * 80)
    print("3. 比較結果")
    print("=" * 80)

    print(f"\n検出数:")
    print(f"  YOLO:  {len(yolo_instruments)} 個")
    print(f"  SAM2:  {len(sam2_instruments)} 個")

    if yolo_instruments:
        avg_yolo_conf = sum(i['confidence'] for i in yolo_instruments) / len(yolo_instruments)
        print(f"\n平均信頼度:")
        print(f"  YOLO:  {avg_yolo_conf:.2%}")
    else:
        print(f"\n平均信頼度:")
        print(f"  YOLO:  N/A（検出なし）")

    if sam2_instruments:
        avg_sam2_conf = sum(i['confidence'] for i in sam2_instruments) / len(sam2_instruments)
        print(f"  SAM2:  {avg_sam2_conf:.2%}")
    else:
        print(f"  SAM2:  N/A（検出なし）")

    print(f"\n特徴:")
    print(f"  YOLO:")
    print(f"    - COCOデータセットベース")
    print(f"    - クラス分類あり（一般物体）")
    print(f"    - 学習データに依存")
    print(f"  SAM2:")
    print(f"    - 形状ベースの検出")
    print(f"    - セグメンテーション精度が高い")
    print(f"    - 細長い物体の検出に優れる")

    print("\n" + "=" * 80)
    print("[OK] 比較テスト完了")
    print("=" * 80)

    return True


def main():
    try:
        # バックエンド疎通確認
        response = requests.get(f"{API_URL}/videos/", timeout=5)
        if response.status_code != 200:
            print("[ERROR] バックエンドに接続できません")
            return 1

        if compare_detection_methods():
            return 0
        else:
            return 1

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] バックエンドサーバーに接続できません")
        print("backend_experimentalサーバーが起動しているか確認してください")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
