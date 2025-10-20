"""
マスクベース初期化機能のテスト
"""
import sys
import base64
import numpy as np
from PIL import Image
from io import BytesIO

# パスを追加
sys.path.insert(0, "c:/Users/ajksk/Desktop/Dev/AI Surgical Motion Knowledge Transfer Library_Ver0.2/backend")

from app.ai_engine.processors.sam_tracker_unified import SAMTrackerUnified

def create_test_mask_b64():
    """テスト用のマスクを作成してbase64エンコード"""
    # 100x100のテストマスク（中央に50x50の矩形）
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[25:75, 25:75] = 255

    # PNG形式でエンコード
    img = Image.fromarray(mask, mode='L')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    mask_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return mask_b64

def test_decode_mask():
    """_decode_mask()関数のテスト"""
    print("=" * 60)
    print("TEST 1: _decode_mask() の動作確認")
    print("=" * 60)

    tracker = SAMTrackerUnified(model_type="sam_vit_b")
    mask_b64 = create_test_mask_b64()

    try:
        mask = tracker._decode_mask(mask_b64)
        print(f"✅ マスクデコード成功")
        print(f"   Shape: {mask.shape}")
        print(f"   Non-zero pixels: {np.sum(mask)}")
        print(f"   Expected: 2500 (50x50)")

        if np.sum(mask) == 2500:
            print("✅ マスクの内容が正しい")
            return True
        else:
            print(f"❌ マスクの内容が不正: {np.sum(mask)} != 2500")
            return False

    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

def test_convert_instruments_format():
    """_convert_instruments_format()のテスト"""
    print("\n" + "=" * 60)
    print("TEST 2: _convert_instruments_format() の動作確認")
    print("=" * 60)

    from app.services.analysis_service_v2 import AnalysisService

    service = AnalysisService()
    mask_b64 = create_test_mask_b64()

    # テストデータ
    instruments = [{
        "name": "Test Instrument",
        "bbox": [10, 20, 50, 60],  # x, y, w, h
        "mask": mask_b64,
        "frame_number": 0
    }]

    try:
        converted = service._convert_instruments_format(instruments)
        print(f"✅ 変換成功")
        print(f"   変換後の数: {len(converted)}")
        print(f"   Type: {converted[0]['selection']['type']}")

        if converted[0]['selection']['type'] == 'mask':
            print("✅ マスクタイプが正しく設定されている")
            print(f"   Mask data length: {len(converted[0]['selection']['data'])} chars")
            return True
        else:
            print(f"❌ マスクタイプが不正: {converted[0]['selection']['type']}")
            return False

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_initialize_with_mask():
    """initialize_instruments()でマスクタイプが動作するかテスト"""
    print("\n" + "=" * 60)
    print("TEST 3: initialize_instruments() with mask type")
    print("=" * 60)

    tracker = SAMTrackerUnified(model_type="sam_vit_b")

    # テストフレーム（ランダムな画像）
    test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    mask_b64 = create_test_mask_b64()

    instruments = [{
        "id": 0,
        "name": "Test Instrument",
        "selection": {
            "type": "mask",
            "data": mask_b64
        },
        "color": "#FF0000"
    }]

    try:
        tracker.initialize_instruments(test_frame, instruments)
        print(f"✅ 初期化成功")
        print(f"   Tracked instruments: {len(tracker.tracked_instruments)}")

        if len(tracker.tracked_instruments) == 1:
            inst = tracker.tracked_instruments[0]
            print(f"   Instrument ID: {inst['id']}")
            print(f"   Instrument name: {inst['name']}")
            print(f"   BBox: {inst['last_bbox']}")
            print(f"   Score: {inst['last_score']}")
            print("✅ マスクベース初期化が正しく動作")
            return True
        else:
            print(f"❌ 初期化された器具数が不正: {len(tracker.tracked_instruments)}")
            return False

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("マスクベース初期化機能テスト")
    print("=" * 60)

    results = []

    # Test 1: マスクデコード
    results.append(("Mask Decode", test_decode_mask()))

    # Test 2: 形式変換
    results.append(("Convert Format", test_convert_instruments_format()))

    # Test 3: SAM初期化
    results.append(("SAM Initialize", test_initialize_with_mask()))

    # 結果サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result for _, result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 すべてのテストが成功しました！")
    else:
        print("⚠️ 一部のテストが失敗しました")
    print("=" * 60)
