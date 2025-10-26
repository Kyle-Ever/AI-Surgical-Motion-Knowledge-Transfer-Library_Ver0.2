#!/usr/bin/env python3
"""
自動器具検出機能の統合テスト
"""
import requests
import json
import sys
from pathlib import Path

API_URL = "http://localhost:8000/api/v1"

def test_instrument_detection():
    """器具検出エンドポイントのテスト"""
    print("\n=== 1. 器具検出テスト ===")

    # まず既存の動画IDを取得
    print("既存の動画を取得中...")
    response = requests.get(f"{API_URL}/videos")
    if response.status_code != 200:
        print(f"[ERROR] 動画取得失敗: {response.status_code}")
        return None

    videos = response.json()
    if not videos:
        print("[ERROR] テスト用の動画がありません")
        return None

    video = videos[-1]  # 最新の動画を使用
    video_id = video['id']
    print(f"[OK] 動画ID: {video_id}")
    print(f"   動画名: {video.get('title', 'N/A')}")

    # 器具検出を実行
    print("\n器具検出を実行中...")
    detect_payload = {"frame_number": 0}
    response = requests.post(
        f"{API_URL}/videos/{video_id}/detect-instruments",
        json=detect_payload
    )

    if response.status_code != 200:
        print(f"[ERROR] 検出失敗: {response.status_code}")
        print(f"   エラー: {response.text}")
        return None

    detection_result = response.json()
    print(f"[OK] 検出成功!")
    print(f"   検出器具数: {len(detection_result.get('instruments', []))}")
    print(f"   モデル情報: {detection_result.get('model_info', {})}")

    # 検出された器具の詳細
    instruments = detection_result.get('instruments', [])
    for inst in instruments:
        print(f"\n   器具 #{inst['id']}:")
        print(f"     - クラス: {inst['class_name']}")
        print(f"     - 推奨名: {inst['suggested_name']}")
        print(f"     - 信頼度: {inst['confidence']:.2%}")
        print(f"     - Bbox: {inst['bbox']}")
        print(f"     - 中心: ({inst['center']['x']:.0f}, {inst['center']['y']:.0f})")

    return video_id, instruments


def test_segmentation_from_detection(video_id, instruments):
    """検出からのセグメンテーションテスト"""
    print("\n\n=== 2. 検出ベースのセグメンテーションテスト ===")

    if not instruments:
        print("[WARN]  検出された器具がないためスキップ")
        return False

    # 最初の器具でセグメンテーションを実行
    first_inst = instruments[0]
    print(f"器具 #{first_inst['id']} ({first_inst['suggested_name']}) でセグメンテーション実行中...")

    segment_payload = {
        "bbox": first_inst['bbox'],
        "detection_id": first_inst['id'],
        "frame_number": 0
    }

    response = requests.post(
        f"{API_URL}/videos/{video_id}/segment-from-detection",
        json=segment_payload
    )

    if response.status_code != 200:
        print(f"[ERROR] セグメンテーション失敗: {response.status_code}")
        print(f"   エラー: {response.text}")
        return False

    segment_result = response.json()
    print(f"[OK] セグメンテーション成功!")
    print(f"   Bbox: {segment_result.get('bbox')}")
    print(f"   スコア: {segment_result.get('score', 0):.4f}")
    print(f"   エリア: {segment_result.get('area', 0)} pixels")
    print(f"   マスクサイズ: {len(segment_result.get('mask', ''))} bytes (Base64)")

    return True


def test_full_workflow():
    """完全なワークフローテスト: 検出 → セグメンテーション → 登録"""
    print("\n\n=== 3. 完全ワークフローテスト ===")

    # ステップ1: 検出
    result = test_instrument_detection()
    if not result:
        print("\n[ERROR] テスト失敗: 器具検出")
        return False

    video_id, instruments = result

    # ステップ2: セグメンテーション
    if not test_segmentation_from_detection(video_id, instruments):
        print("\n[ERROR] テスト失敗: セグメンテーション")
        return False

    print("\n[OK] 完全ワークフローテスト合格!")
    return True


def main():
    """メインテスト実行"""
    print("=" * 60)
    print("自動器具検出機能 統合テスト")
    print("=" * 60)

    try:
        # バックエンドの疎通確認
        print("\nバックエンド接続確認...")
        response = requests.get(f"{API_URL}/videos", timeout=5)
        if response.status_code != 200:
            print(f"[ERROR] バックエンドに接続できません: {response.status_code}")
            return 1
        print("[OK] バックエンド接続OK")

        # 完全なワークフローテスト
        if test_full_workflow():
            print("\n" + "=" * 60)
            print("[OK] 全テスト合格!")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("[ERROR] テスト失敗")
            print("=" * 60)
            return 1

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] エラー: バックエンドサーバーに接続できません")
        print("   backend_experimental サーバーが起動しているか確認してください")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
