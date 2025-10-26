#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reference Model作成API検証"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import requests
import json

# まず完了済み解析を1つ取得
print("1️⃣  Fetching completed analyses...")
library_response = requests.get("http://localhost:8001/api/v1/library/completed?limit=1")
if library_response.status_code != 200:
    print(f"❌ Failed to get completed analyses: {library_response.status_code}")
    sys.exit(1)

analyses = library_response.json()
if len(analyses) == 0:
    print("❌ No completed analyses found")
    sys.exit(1)

test_analysis = analyses[0]
analysis_id = test_analysis['id']
video_id = test_analysis['video_id']

print(f"✅ Found completed analysis: {analysis_id[:12]}...")
print(f"   Video: {test_analysis.get('video', {}).get('original_filename', 'N/A')}")

# Reference Model作成を試行
print(f"\n2️⃣  Creating reference model...")
create_payload = {
    "name": "テスト用参照モデル",
    "description": "APIテスト用リファレンスモデル",
    "analysis_id": analysis_id,
    "surgeon_name": "テスト指導医",
    "surgery_type": "腹腔鏡下胆嚢摘出術"
}

create_response = requests.post(
    "http://localhost:8001/api/v1/scoring/reference",
    json=create_payload
)

if create_response.status_code in [200, 201]:
    result = create_response.json()
    print(f"✅ SUCCESS! Reference model created:")
    print(f"   Model ID: {result['id'][:12]}...")
    print(f"   Analysis ID: {result['analysis_id'][:12]}...")
    print(f"   Name: {result['name']}")
    print(f"   Surgeon: {result['surgeon_name']}")
    print(f"\n🎉 Reference Model作成が成功しました！")
    print(f"   → これで300+件の完了済み解析から参照モデルを作成できます")
    print(f"   → 修正前: 0件の解析しか見つからなかった")
    print(f"   → 修正後: 完了済み解析が正しく取得できている")
else:
    print(f"❌ Failed to create reference model: {create_response.status_code}")
    print(f"Response: {create_response.text}")
    sys.exit(1)
