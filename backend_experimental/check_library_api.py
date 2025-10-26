#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Library API検証スクリプト"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import requests
import json

url = "http://localhost:8001/api/v1/library/completed?limit=300"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    print(f"✅ API Success! Total analyses: {len(data)}")

    if len(data) > 0:
        print(f"\nFirst 5 analyses:")
        for i, analysis in enumerate(data[:5]):
            print(f"  {i+1}. ID: {analysis['id'][:12]}... Status: {analysis['status']}")
            if analysis.get('video'):
                print(f"      Video: {analysis['video'].get('original_filename', 'N/A')}")

    # 284件期待
    if len(data) >= 284:
        print(f"\n🎉 SUCCESS: Found {len(data)} completed analyses (expected 284+)")
    else:
        print(f"\n⚠️  WARNING: Only {len(data)} analyses found (expected 284)")
else:
    print(f"❌ API Error: {response.status_code}")
    print(response.text)
