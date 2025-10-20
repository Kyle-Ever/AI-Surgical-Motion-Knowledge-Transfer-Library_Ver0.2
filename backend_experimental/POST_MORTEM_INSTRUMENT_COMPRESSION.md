# POST MORTEM: 器具検出データの圧縮処理によるデータ損失問題

**日時**: 2025-10-13
**影響範囲**: SAM2 Video API使用時の全ての器具トラッキング解析
**深刻度**: Critical（データが完全に失われる）

## 問題の概要

SAM2 Video APIを使用した器具トラッキング解析で、データベースに保存される器具検出結果が全て空配列になる問題が発生していた。ログでは「563フレームをトラッキング成功」「113/113フレームに検出あり」と表示されるが、データベースには`detections: []`（空配列）のみが保存される状態が継続していた。

## 根本原因

### 1. データ構造の不整合（主原因）

`_format_instrument_data`（フォーマット処理）と`_compress_instrument_data`（圧縮処理）の間でキー名が不一致だった。

**フォーマット処理の出力**:
```python
{
    'frame_number': 0,      # ← キー名
    'timestamp': 0.0,
    'detections': [{        # ← キー名
        'id': 0,
        'name': '1',
        'center': [x, y],
        'bbox': [x1, y1, x2, y2],
        'confidence': 0.076,
        'mask': <array>
    }]
}
```

**圧縮処理が期待していた構造**:
```python
{
    'frame_index': 0,       # ← 存在しないキー
    'timestamp': 0.0,
    'instruments': [{       # ← 存在しないキー
        'class_name': '',
        'track_id': -1,
        'bbox': [],
        'confidence': 0.0
    }]
}
```

### 2. データ損失のメカニズム

```python
# _compress_instrument_data の旧コード（Line 880, 885）
compressed_frame = {
    'frame_index': frame_data.get('frame_index', 0),  # → 常に0（キーが存在しない）
    'instruments': []
}

for inst in frame_data.get('instruments', []):  # → 常に空配列（キーが'detections'）
    # このループは一度も実行されない
```

結果：
- `frame_data.get('frame_index', 0)` → 常に**デフォルト値の0**
- `frame_data.get('instruments', [])` → 常に**空配列**
- 全フレームが `{frame_index: 0, instruments: []}` となり、実データが完全消失
- データベース保存：113フレーム全てが空

### 3. 問題が繰り返された理由

データフローでキー名が行ったり来たりしていた：

1. **SAM2 Video API** → `'instruments'`キー
2. **`_convert_video_api_result`** → `'instruments'`キー（正常）
3. **`_format_instrument_data`** → `'detections'`キーに変換（キー名変更）
4. **`_compress_instrument_data`** → `'instruments'`キーを期待（**ミスマッチ！**）
5. **結果** → 圧縮処理でデータが完全に失われる

過去の修正で`_format_instrument_data`内のキー読み取りは修正したが、最終的な保存キー名は`'detections'`のまま、そして圧縮処理は`'instruments'`を探すため、データ損失が継続していた。

## 影響を受けた解析

- **解析 ae5a56e2**: データ変換成功、フォーマット成功、圧縮でデータ損失 → 空配列
- **解析 5cb40515**: データ変換成功、フォーマット成功、圧縮でデータ損失 → 空配列
- **解析 ec90e1a2**: データ変換成功、フォーマット成功、圧縮でデータ損失 → 空配列

## 修正内容

### ファイル: `backend_experimental/app/services/analysis_service_v2.py`

**修正箇所**: `_compress_instrument_data`メソッド（Line 859-958）

**主な変更点**:

1. **キー名の統一**:
   ```python
   # 修正前
   'frame_index': frame_data.get('frame_index', 0)
   'instruments': []
   for inst in frame_data.get('instruments', []):

   # 修正後
   'frame_number': frame_data.get('frame_number')  # frame_numberに統一
   'detections': []  # detectionsに統一
   for det in frame_data.get('detections', []):
   ```

2. **SAM2データ構造への対応**:
   ```python
   # 修正前（存在しないキー）
   'class_name': inst.get('class_name', '')
   'track_id': inst.get('track_id', -1)

   # 修正後（SAM2の実際のキー）
   'id': det.get('id')
   'name': det.get('name', '')
   'center': det.get('center', [])
   'bbox': det.get('bbox', [])
   'confidence': det.get('confidence', 0.0)
   # mask は除外（圧縮のため）
   ```

3. **デバッグログの追加**:
   ```python
   # 圧縮処理の入力データ構造を確認
   logger.info(f"Compression input - First frame keys: {list(first_frame.keys())}")
   logger.info(f"Compression input - First detection keys: {list(first_det.keys())}")

   # 圧縮後のデータ検証
   logger.info(f"After mask removal: {frames_with_dets}/{total_frames} frames have detections")
   ```

## 検証方法

### 1. コード検証スクリプト
```bash
cd backend_experimental
./venv311/Scripts/python.exe verify_compression_fix.py
```

期待される出力：
```
[SUCCESS] 全ての修正が正しく適用されています
```

### 2. 新規解析での検証

1. 新しい動画をアップロード
2. 解析タイプ：`external_with_instruments`を選択
3. **器具マスクを描画**（重要！）
4. 解析を実行
5. 結果を確認：
   - ダッシュボードで器具トラッキング結果が表示される
   - データベースで`detections`配列にデータが存在する

### 3. データベース確認
```python
import sqlite3, json
conn = sqlite3.connect('aimotion_experimental.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT instrument_data
    FROM analysis_results
    WHERE id = '<new_analysis_id>'
''')
data = json.loads(cursor.fetchone()[0])
print(f"Frames with detections: {sum(1 for f in data if len(f['detections']) > 0)}")
```

## 予防策

### 1. データ構造の明確化

各処理関数のdocstringに、入力/出力のデータ構造を明記する：

```python
def _compress_instrument_data(self, instrument_data: List[Dict]) -> List[Dict]:
    """
    注意：このメソッドは_format_instrument_dataの出力を受け取る
    期待される入力形式：
    {
        'frame_number': int,
        'timestamp': float,
        'detections': [...]
    }
    """
```

### 2. ユニットテストの追加

圧縮処理のユニットテストを作成：

```python
def test_compress_instrument_data():
    # フォーマット処理の実際の出力形式でテスト
    test_data = [{
        'frame_number': 0,
        'timestamp': 0.0,
        'detections': [{
            'id': 0,
            'name': '1',
            'center': [100, 200],
            'bbox': [50, 100, 150, 300],
            'confidence': 0.95,
            'mask': np.zeros((480, 640))
        }]
    }]

    service = AnalysisServiceV2(...)
    compressed = service._compress_instrument_data(test_data)

    # 検証
    assert len(compressed) == 1
    assert len(compressed[0]['detections']) == 1
    assert 'mask' not in compressed[0]['detections'][0]
```

### 3. 統合テストの強化

新規解析を実行して、全データパイプラインを検証するテストを作成：

```python
def test_full_sam2_pipeline():
    # 1. 動画アップロード
    # 2. 器具選択（マスク保存）
    # 3. 解析実行
    # 4. データベース検証
    # 5. フロントエンド表示確認
```

### 4. Fail Fast原則の適用

デフォルト値で問題を隠蔽せず、早期に失敗する：

```python
# 悪い例
frame_number = frame_data.get('frame_number', 0)  # 問題を隠蔽

# 良い例
if 'frame_number' not in frame_data:
    raise ValueError(f"Missing frame_number: {frame_data.keys()}")
frame_number = frame_data['frame_number']
```

## 学んだ教訓

1. **キー名の一貫性**: データパイプライン全体でキー名を統一する
2. **データ構造の文書化**: 各処理関数の入出力形式を明確に文書化
3. **デバッグログの重要性**: データ構造の変化を追跡できるログを追加
4. **新規データでのテスト**: 既存データのテストだけでは不十分、新規解析でテスト
5. **Fail Fast原則**: デフォルト値で問題を隠さず、早期にエラーを検出

## タイムライン

- **2025-10-13 12:48**: 解析 5cb40515 実行 → 空配列
- **2025-10-13 17:31**: 解析 ec90e1a2 実行 → 空配列（ログは成功）
- **2025-10-13 17:45**: 根本原因を特定（圧縮処理のキー名ミスマッチ）
- **2025-10-13 18:00**: 修正完了、バックエンド再起動
- **2025-10-13 18:05**: 検証スクリプトで修正確認

## 次のステップ

1. ✅ 修正コードをデプロイ済み
2. ⏳ 新規解析で動作確認（ユーザー実行待ち）
3. ⏳ ユニットテスト追加
4. ⏳ 統合テスト強化
5. ⏳ ドキュメント更新
