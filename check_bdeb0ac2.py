import sqlite3
import json

conn = sqlite3.connect('aimotion.db')
cursor = conn.cursor()

# 解析情報を取得
cursor.execute('''
    SELECT ar.id, ar.created_at, ar.status, v.video_type,
           json_extract(ar.result_data, '$.instrument_data') as instrument_data
    FROM analysis_results ar
    JOIN videos v ON ar.video_id = v.id
    WHERE ar.id = 'bdeb0ac2-4ff2-4614-97aa-5407f1395e8e'
''')

row = cursor.fetchone()

if row:
    analysis_id, created_at, status, video_type, instrument_data = row

    print("=" * 70)
    print("解析情報")
    print("=" * 70)
    print(f"解析ID: {analysis_id}")
    print(f"作成日時: {created_at}")
    print(f"ステータス: {status}")
    print(f"ビデオタイプ: {video_type}")
    print()

    # instrument_dataを解析
    if instrument_data and instrument_data != 'null':
        data = json.loads(instrument_data)
        print("=" * 70)
        print("器具検出結果")
        print("=" * 70)
        print(f"総フレーム数: {len(data)}")

        # フレームごとの検出数をカウント
        detection_counts = {}
        for frame in data:
            detections = frame.get('detections', [])
            count = len(detections)
            detection_counts[count] = detection_counts.get(count, 0) + 1

        print("\n検出数の分布:")
        for count in sorted(detection_counts.keys()):
            print(f"  {count}個検出: {detection_counts[count]}フレーム")

        # 最初のフレームの詳細
        if len(data) > 0 and data[0].get('detections'):
            print("\n" + "=" * 70)
            print("最初のフレームの検出詳細")
            print("=" * 70)
            first_detection = data[0]['detections'][0]
            print(f"器具名: {first_detection.get('class_name', 'N/A')}")
            print(f"BBox: {first_detection.get('bbox', 'N/A')}")
            print(f"信頼度: {first_detection.get('confidence', 'N/A')}")
            print(f"Track ID: {first_detection.get('track_id', 'N/A')}")

            # 回転BBoxがあるか確認
            if 'rotated_bbox' in first_detection:
                print(f"✅ 回転BBox: あり")
                print(f"   回転角度: {first_detection.get('rotation_angle', 'N/A')}°")
                print(f"   面積削減: {first_detection.get('area_reduction', 'N/A')}%")
            else:
                print("❌ 回転BBox: なし")

        # 検出が0のフレームがあるか
        zero_detection_frames = sum(1 for frame in data if len(frame.get('detections', [])) == 0)
        if zero_detection_frames > 0:
            print(f"\n⚠️ 警告: {zero_detection_frames}フレームで器具が検出されていません")
        else:
            print(f"\n✅ すべてのフレームで器具が検出されています")
    else:
        print("❌ 器具検出データがありません")
else:
    print("❌ 解析が見つかりません")

conn.close()
