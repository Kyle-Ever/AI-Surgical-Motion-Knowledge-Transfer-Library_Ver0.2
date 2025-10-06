# データパイプライン開発ガイドライン

**目的**: データ処理ロジック変更時の品質保証とバグ再発防止

---

## 📋 データパイプライン変更チェックリスト

### フェーズ1: 設計・実装前

#### 1.1 上流データ確認
- [ ] 依存する関数の出力フォーマットを確認
- [ ] 必須フィールドをリストアップ
- [ ] 実際のデータサンプルをログ出力で確認

```python
# 良い例: 上流データの確認
upstream_output = detect_batch(frames)
logger.debug(f"Upstream output sample: {upstream_output[0] if upstream_output else 'empty'}")
logger.debug(f"Output keys: {upstream_output[0].keys() if upstream_output else 'N/A'}")
```

#### 1.2 バリデーション戦略設計
- [ ] Fail Fast原則でバリデーション計画
- [ ] デフォルト値使用の妥当性を検証
- [ ] エラーメッセージの明確性を確保

---

### フェーズ2: 実装

#### 2.1 Fail Fast実装（必須）
**原則**: データの存在を仮定せず、早期に大きく失敗する

```python
# ❌ 悪い例: サイレント失敗
frame_idx = result.get('frame_index', 0)  # 問題を隠蔽

# ✅ 良い例: Fail Fast
if 'frame_index' not in result:
    error_msg = f"Missing frame_index in result. Keys: {list(result.keys())}"
    logger.error(error_msg)
    raise ValueError(f"Upstream function must provide frame_index. {error_msg}")
frame_idx = result['frame_index']
```

#### 2.2 ロギング戦略
- [ ] 上流データの構造をDEBUGレベルでログ
- [ ] 異常値・欠損値をWARNINGレベルでログ
- [ ] エラー時に十分な診断情報を含める

```python
logger.debug(f"Processing {len(raw_results)} results from upstream")
logger.debug(f"First result structure: {raw_results[0].keys() if raw_results else 'empty'}")

if len(hands) > 10:
    logger.warning(f"Frame {frame_num} has {len(hands)} hands (expected 1-4)")
```

#### 2.3 データ構造妥当性検証
- [ ] 期待される範囲の値チェック
- [ ] 異常なデータ分布の検出
- [ ] データ型の検証

```python
# データ分布の妥当性チェック
if len(frames_dict) < expected_minimum:
    raise ValueError(f"Insufficient frames: {len(frames_dict)} < {expected_minimum}")

# 値の範囲チェック
for frame_num, hands in frames_dict.items():
    if len(hands) > 10:
        logger.warning(f"Abnormal: Frame {frame_num} has {len(hands)} hands")
```

---

### フェーズ3: テスト

#### 3.1 ユニットテスト（必須）
**場所**: `tests/unit/test_<module_name>.py`

**カバーすべき項目**:
- [ ] 正常系: 期待通りのデータ
- [ ] 異常系: 必須フィールド欠損時にエラー
- [ ] エッジケース: 空データ、境界値
- [ ] 複数パターン: 様々なデータ組み合わせ

```python
# 例: frame_index欠損時のテスト
def test_format_without_frame_index_fails():
    """frame_indexが欠損している場合はValueError"""
    raw_results = [
        {
            'detected': True,
            # 'frame_index': 0,  ← 意図的に欠如
            'hands': [...]
        }
    ]

    with pytest.raises(ValueError) as exc_info:
        service._format_skeleton_data(raw_results)

    assert "frame_index" in str(exc_info.value)
```

#### 3.2 統合テスト（重要）
**場所**: `tests/test_<feature>_comprehensive.py`

**重要**: 既存データではなく、新規データで新コードパスをテスト

```python
# ❌ 悪い例: 古いデータをテスト
def test_analysis():
    old_analysis_id = "existing-id-from-database"
    verify(old_analysis_id)  # 新コードを実行していない！

# ✅ 良い例: 新規解析を実行
def test_analysis():
    # 新しい動画をアップロード
    video_id = upload_test_video("test_video.mp4")

    # 新規解析実行（新しいコードパス）
    analysis_id = start_new_analysis(video_id, analysis_type="external")

    # データベース検証
    analysis = get_analysis(analysis_id)
    assert analysis['skeleton_frames'] > 100
    assert all(len(frame['hands']) < 5 for frame in analysis['skeleton_data'])
```

#### 3.3 E2Eテスト（推奨）
**場所**: `frontend/tests/e2e-*.spec.ts`

**カバーすべき項目**:
- [ ] データ構造の妥当性検証
- [ ] フロントエンド表示の確認
- [ ] エラーケースの動作確認

```typescript
// ❌ 不十分: キーの存在のみ
test('データ形式確認', async ({ request }) => {
  const data = await getAnalysisData(analysisId)
  expect(data).toHaveProperty('skeleton_data')
})

// ✅ 完全: 構造の妥当性も
test('骨格データ構造検証', async ({ request }) => {
  const data = await getAnalysisData(analysisId)

  // フレーム数の妥当性
  expect(data.skeleton_data.length).toBeGreaterThan(100)

  // 各フレームの手の数
  for (const frame of data.skeleton_data) {
    expect(frame.hands.length).toBeGreaterThan(0)
    expect(frame.hands.length).toBeLessThan(5)
  }

  // タイムスタンプの分散
  const timestamps = data.skeleton_data.map(f => f.timestamp)
  const uniqueTimestamps = new Set(timestamps)
  expect(uniqueTimestamps.size).toBeGreaterThan(100)
})
```

---

### フェーズ4: 検証

#### 4.1 サーバー再起動検証（重要）

**問題**: Uvicornの `--reload` が時々ファイル変更を検知しない

**検証手順**:

1. **コード変更直後**:
```bash
# バックエンドサーバーのログを確認
# "Reloading..." または "Application startup complete" が表示されるか
```

2. **リロードが検知されない場合**:
```bash
# 明示的に再起動
./restart_backend.bat
```

3. **再起動後の検証**:
```bash
# verify_fix.py で最新データをチェック
backend/venv311/Scripts/python.exe verify_fix.py

# または手動APIチェック
curl http://localhost:8000/api/v1/health
```

**検証チェックリスト**:
- [ ] バックエンドログに "Reloading..." 表示
- [ ] 新規解析を実行（既存データテストは不十分）
- [ ] データベースで新形式データ確認
- [ ] UIで期待通りの表示確認

#### 4.2 実際のUIテスト
- [ ] ブラウザで実際に動作確認
- [ ] 様々なデータパターンで表示確認
- [ ] エラー時の挙動確認

#### 4.3 データベース検証
```python
# データ構造の確認
analysis = db.query(AnalysisResult).filter(...).first()
skeleton_data = json.loads(analysis.skeleton_data)

print(f"Skeleton frames: {len(skeleton_data)}")
print(f"First frame structure: {skeleton_data[0].keys()}")
print(f"Hands in first frame: {len(skeleton_data[0]['hands'])}")
```

#### 4.4 ログ確認
```bash
# サーバーログで異常を確認
tail -f backend/logs/app.log | grep -E "WARNING|ERROR"
```

---

## 🚨 よくある落とし穴と対策

### 落とし穴1: デフォルト値による隠蔽
**症状**: 必須データが欠損していてもエラーにならず、おかしな動作になる

```python
# ❌ 問題のあるコード
frame_idx = result.get('frame_index', 0)  # 全て0になる

# ✅ 正しいコード
if 'frame_index' not in result:
    raise ValueError("frame_index is required")
frame_idx = result['frame_index']
```

### 落とし穴2: 古いデータでのテスト
**症状**: テストは通るが、新しいコードが実際には動かない

```python
# ❌ 問題のあるテスト
def test_analysis():
    # 古い解析データ（コード変更前のデータ）
    analysis = get_analysis("old-analysis-id")
    assert analysis['status'] == 'completed'  # 新コードをテストしていない

# ✅ 正しいテスト
def test_analysis():
    # 新しいデータで新コードを実行
    video_id = upload_test_video()
    analysis_id = start_new_analysis(video_id)
    verify_structure(analysis_id)
```

### 落とし穴3: フォーマットのみの検証
**症状**: データキーは存在するが、内容がおかしい（例: 1フレームに213個の手）

```typescript
// ❌ 不十分な検証
expect(data).toHaveProperty('skeleton_data')

// ✅ 完全な検証
expect(data.skeleton_data.length).toBeGreaterThan(100)
expect(data.skeleton_data[0].hands.length).toBeLessThan(5)
```

### 落とし穴4: ログ不足
**症状**: エラーが起きても原因特定に時間がかかる

```python
# ❌ ログ不足
result = process_data(data)

# ✅ 十分なログ
logger.debug(f"Input data keys: {data.keys()}")
result = process_data(data)
logger.debug(f"Output data structure: {result.keys() if result else 'None'}")
logger.info(f"Processed {len(result)} items")
```

---

## 📊 テスト戦略マトリクス

| テストレベル | タイミング | 検証内容 | 実行頻度 |
|------------|-----------|---------|---------|
| **ユニット** | 関数作成・修正時 | エッジケース、異常系、欠損データ | 各コミット前 |
| **統合** | データパイプライン変更時 | 新規データで新コードパス実行 | PR作成前 |
| **E2E** | フロントエンド連携時 | データ構造妥当性、UI表示 | リリース前 |
| **手動** | 重要な変更時 | 実際のUI動作、UX確認 | リリース前 |

---

## 🔄 変更後のレビューポイント

### コードレビュー時
- [ ] 上流依存のバリデーションコード確認
- [ ] Fail Fast原則の適用確認
- [ ] ログ出力の適切性確認
- [ ] エラーメッセージの明確性確認

### テストレビュー時
- [ ] ユニットテストの異常系カバレッジ
- [ ] 統合テストの新規データ使用確認
- [ ] E2Eテストの構造検証確認

---

## 📚 関連ドキュメント

- [POST_MORTEM: 骨格検出フレームインデックス](../POST_MORTEM_SKELETON_FRAME_INDEX.md) - 実際のバグ事例
- [CLAUDE.md - データパイプライン品質保証](../../CLAUDE.md#データパイプライン品質保証)
- [アーキテクチャ設計](../01_architecture/01_architecture_design.md)

---

## ✅ 最終チェックリスト

データパイプラインの変更をコミットする前に、以下を確認:

### 実装
- [ ] Fail Fast原則でバリデーション実装
- [ ] 上流データ構造の確認コード追加
- [ ] 十分なログ出力
- [ ] エラーメッセージが診断可能

### テスト
- [ ] ユニットテストで異常系カバー
- [ ] 統合テストで新規データ使用
- [ ] E2Eテストで構造検証
- [ ] 実際のUIで動作確認

### ドキュメント
- [ ] コード内コメント追加
- [ ] 重要な変更はPOST_MORTEM参照
- [ ] 設計ドキュメント更新（必要な場合）

---

**原則**: "データの存在を仮定せず、早期に大きく失敗する" - Fail Fast
