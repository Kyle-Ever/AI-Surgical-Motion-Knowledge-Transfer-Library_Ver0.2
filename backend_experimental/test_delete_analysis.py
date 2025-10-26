#!/usr/bin/env python
"""解析削除APIのテストスクリプト"""

import requests
import sys

BASE_URL = "http://localhost:8001/api/v1"

def test_delete_analysis(analysis_id: str):
    """解析削除をテスト"""
    url = f"{BASE_URL}/analysis/{analysis_id}"

    print(f"DELETE {url}")
    print("-" * 80)

    try:
        response = requests.delete(url, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Status Text: {response.reason}")
        print(f"Headers: {dict(response.headers)}")
        print()

        if response.status_code == 200:
            print("✅ 削除成功")
            print(f"Response: {response.json()}")
        elif response.status_code == 404:
            print("❌ 解析が見つかりません")
            print(f"Response: {response.json()}")
        else:
            print(f"⚠️  予期しないステータスコード: {response.status_code}")
            print(f"Response Text: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ バックエンドに接続できません")
        print("サーバーが起動しているか確認してください")
    except requests.exceptions.Timeout:
        print("❌ タイムアウト")
    except Exception as e:
        print(f"❌ エラー: {e}")

    print("-" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_delete_analysis.py <analysis_id>")
        print()
        print("Example:")
        print("  python test_delete_analysis.py e5e8c0a3-0412-429e-9e81-4cbf7e2829b9")
        sys.exit(1)

    analysis_id = sys.argv[1]
    test_delete_analysis(analysis_id)
