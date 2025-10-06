# POST MORTEM: 骨格検出フレームインデックスバグ

**日付**: 2025-10-05
**影響度**: 🔴 Critical
**検出者**: ユーザー報告
**修正者**: Claude (AI Assistant)

---

## 📋 概要

### 問題の症状
- ダッシュボードで骨格検出が表示されない
- 新規解析を実行しても同じ問題が繰り返し発生
- データベースには1フレームのみ、213個の手が全て集約

### 根本原因
`skeleton_detector.py`の`detect_batch()`メソッドが`frame_index`を結果に追加していなかったため、下流の`_format_skeleton_data()`がデフォルト値0を使用し、全フレームのデータがframe 0に集約された。

### 影響範囲
- **影響を受けた機能**: 骨格検出表示（EXTERNAL, EXTERNAL_WITH_INSTRUMENTS）
- **影響期間**: Phase 5.4コード変更後から修正まで（約20分間）
- **影響を受けた解析**: 2件（旧形式データ含む）

---

## 🔍 詳細な技術分析

### バグの連鎖

#### 1. 上流の欠陥（skeleton_detector.py Line 556-560）
```python
# 問題のコード
def detect_batch(self, frames: List[np.ndarray]) -> List[Dict[str, Any]]:
    results = []
    for frame in frames:  # ← frame_indexを追加していない
        result = self.detect_from_frame(frame)
        results.append(result)
    return results
```

**問題点**: `enumerate()`を使わず、`frame_index`キーを結果に追加していない

#### 2. 下流のサイレント失敗（analysis_service_v2.py Line 519）
```python
# 問題のコード
frame_idx = result.get('frame_index', 0)  # ← デフォルト値0
```

**問題点**:
- `frame_index`が存在しない場合、エラーを出さず0にフォールバック
- 全てのフレームが`actual_frame_number = 0`と計算される
- `frames_dict[0]`に全ての手（213個）が集約

#### 3. 結果の異常

**正常な場合（期待）**:
```json
{
  "skeleton_data": [
    {"frame": 0, "timestamp": 0.0, "hands": [{"hand_type": "Left", ...}]},
    {"frame": 6, "timestamp": 0.2, "hands": [{"hand_type": "Right", ...}]},
    ...  // 213フレーム
  ]
}
```

**バグ発生時（実際）**:
```json
{
  "skeleton_data": [
    {
      "frame": 0,
      "timestamp": 0.0,
      "hands": [
        {"hand_type": "Left", ...},   // 手1
        {"hand_type": "Right", ...},  // 手2
        ...  // 213個の手が全てここに！
      ]
    }
  ]
}
```

### フロントエンドへの影響

```typescript
// VideoPlayer.tsx Line 88-122
const getCurrentData = (timestamp: number) => {
  let currentSkeletons = skeletonData.filter(
    data => Math.abs(data.timestamp - adjustedTimestamp) < 0.04
  )
  // ...
}
```

**問題の流れ**:
1. `skeletonData`には`timestamp: 0.0`のフレーム1つのみ
2. ビデオ再生中（例: timestamp 1.5秒）→ フィルタに一致するデータなし
3. 最近接フレーム検索 → `timestamp: 0.0`が最近接だが、差が1.5秒
4. 閾値0.01秒を超えているため、データが取得されない
5. **結果**: 骨格が表示されない

---

## 🛠️ 修正内容

### 修正1: frame_index追加（skeleton_detector.py）
```python
# 修正後
def detect_batch(self, frames: List[np.ndarray]) -> List[Dict[str, Any]]:
    results = []
    for idx, frame in enumerate(frames):  # ← enumerate追加
        result = self.detect_from_frame(frame)
        result['frame_index'] = idx  # ← frame_index追加
        results.append(result)
    return results
```

### 修正2: Fail Fast実装（analysis_service_v2.py）
```python
# 修正後
if result.get('detected'):
    # Fail Fast: frame_indexが存在しない場合はエラー
    if 'frame_index' not in result:
        error_msg = f"Missing frame_index in skeleton detection result. Result keys: {list(result.keys())}"
        logger.error(error_msg)
        raise ValueError(f"skeleton_detector.detect_batch() must include frame_index in results. {error_msg}")

    frame_idx = result['frame_index']
    # ...
```

### 修正3: ユニットテスト作成
```python
# tests/unit/test_format_skeleton_data.py
def test_format_without_frame_index_fails():
    """異常系: frame_indexが欠損している場合はValueError"""
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

**テスト結果**: 7 passed ✅

---

## 📊 根本原因分析（5 Whys）

### なぜ骨格が表示されなかったのか？
→ データベースに1フレームしか存在せず、timestamp 0.0のみだったから

### なぜ1フレームしかなかったのか？
→ 全ての手が`frames_dict[0]`に集約されたから

### なぜ全てがframe 0に集約されたのか？
→ `frame_idx = result.get('frame_index', 0)`でデフォルト値0が使われたから

### なぜframe_indexが存在しなかったのか？
→ `detect_batch()`が`frame_index`を結果に追加していなかったから

### なぜ追加していなかったのか？
→ **Phase 5.4で`_format_skeleton_data()`を書き直した際、上流の`detect_batch()`の出力を確認せず、`frame_index`が存在すると仮定したから**

---

## 🚨 テスト戦略の失敗

### 失敗1: ユニットテストの欠如
- `_format_skeleton_data()`のユニットテストが存在しなかった
- エッジケース（frame_index欠損）が検証されなかった

### 失敗2: 統合テストの不備
- `test_phase5_comprehensive.py`は**古いデータ**をテスト
- 新規解析を実行せず、新しいコードパスを検証していなかった

```python
# ❌ 実際のテスト（問題あり）
analysis_id = "3493e268-6b94-471b-b21b-fe95f2a6cc59"  # 古いデータ
verify(analysis_id)  # Phase 5.4コード変更前のデータ

# ✅ あるべきテスト
video_id = upload_test_video()
analysis_id = start_new_analysis(video_id)  # 新しいコード実行
verify(analysis_id)
```

### 失敗3: E2Eテストの不完全性
- Playwright E2Eテストは**フォーマットのみ検証**
- データ構造の妥当性を検証していなかった

```typescript
// ❌ 実際のテスト（不十分）
expect(firstFrame).toHaveProperty('frame')
expect(firstFrame).toHaveProperty('hands')

// ✅ あるべきテスト
expect(data.skeleton_data.length).toBeGreaterThan(100)  // フレーム数
expect(firstFrame.hands.length).toBeLessThan(5)  // 手の数の妥当性
```

---

## 💡 学んだ教訓

### 1. Fail Fast原則の重要性
**サイレント失敗は致命的**
- ❌ `result.get('frame_index', 0)` - 問題を隠蔽
- ✅ `if 'frame_index' not in result: raise ValueError()` - 問題を表面化

### 2. 上流依存の検証義務
**新しいコードが既存関数に依存する場合**:
1. まず上流の出力を確認
2. 必須フィールドの存在を検証
3. バリデーションを追加

### 3. 3層テスト戦略の徹底

| テストレベル | 目的 | 今回の失敗 | 改善策 |
|------------|------|-----------|--------|
| **ユニット** | エッジケース検証 | 存在しなかった | `test_format_skeleton_data.py`作成 |
| **統合** | 新コードパス実行 | 古いデータのみテスト | 新規解析実行を追加 |
| **E2E** | データ構造妥当性 | フォーマットのみ検証 | 構造検証を追加 |

### 4. 新規コードパス検証義務
**データ処理ロジックを変更した場合**:
- 既存データのテストは不十分
- 必ず新しいデータで新しいコードを実行
- 実際のUIで動作確認

---

## 🎯 再発防止策

### 即時対応（完了）
- [x] `skeleton_detector.py`に`frame_index`追加
- [x] `analysis_service_v2.py`にFail Fast実装
- [x] ユニットテスト作成（7テストケース）
- [x] CLAUDE.md更新（Fail Fast原則、3層テスト戦略）

### 中期対応（推奨）
- [ ] 統合テストで新規解析実行パターンに更新
- [ ] E2Eテストにデータ構造妥当性検証追加
- [ ] 開発ガイドラインに「データパイプライン変更時のチェックリスト」追加

### 長期対応（組織的学習）
- [ ] コードレビュー時のFail Fastチェック
- [ ] データパイプライン変更時の必須検証ステップ文書化
- [ ] CI/CDパイプラインにデータ構造検証テスト追加

---

## 📚 関連ドキュメント

- [POST_MORTEM: ファイルアップロードボタン](POST_MORTEM_FILE_UPLOAD_BUTTON.md)
- [CLAUDE.md - データパイプライン品質保証](../CLAUDE.md#データパイプライン品質保証)
- [アーキテクチャ設計](01_architecture/01_architecture_design.md)
- [開発環境セットアップ](06_development/06_development_setup.md)

---

## 🔄 タイムライン

| 時刻 | イベント |
|------|---------|
| 2025-10-05 03:02 | Phase 5.4実装: `_format_skeleton_data()`書き直し |
| 2025-10-05 03:02 | 古い解析データでテスト実施（旧形式） |
| 2025-10-05 03:05 | ユーザー: 新規解析実行（バグのあるコード使用） |
| 2025-10-05 03:06 | ユーザー報告: 骨格検出が表示されない（1回目） |
| 2025-10-05 03:08 | サーバー手動再起動 |
| 2025-10-05 03:09 | ユーザー報告: 問題が繰り返される（2回目） |
| 2025-10-05 03:12 | 根本原因特定: `frame_index`欠損 |
| 2025-10-05 03:15 | 修正計画立案 |
| 2025-10-05 03:20 | Phase 1-2完了: `frame_index`追加 + Fail Fast実装 |
| 2025-10-05 03:25 | Phase 3完了: ユニットテスト7件作成・全パス |
| 2025-10-05 03:30 | Phase 5完了: CLAUDE.md更新、POST_MORTEM作成 |

---

## ✅ チェックリスト（今後のデータパイプライン変更時）

新しいデータ処理ロジックを実装する際、以下を確認:

### 実装前
- [ ] 上流関数の出力フォーマットを確認
- [ ] 必須フィールドをリストアップ
- [ ] バリデーション戦略を設計

### 実装中
- [ ] Fail Fast原則でバリデーション実装
- [ ] デフォルト値による隠蔽を避ける
- [ ] ロギングで上流データを可視化

### テスト
- [ ] ユニットテスト: 異常系・欠損データをカバー
- [ ] 統合テスト: **新規データで新コードパス実行**
- [ ] E2Eテスト: データ構造の妥当性検証
- [ ] 実際のUIで動作確認

### レビュー
- [ ] 上流依存の検証コード確認
- [ ] エラーハンドリングの適切性確認
- [ ] テストカバレッジ確認（異常系含む）

---

**教訓**: "データの存在を仮定せず、早期に大きく失敗する" - Fail Fast原則の徹底が再発防止の鍵
