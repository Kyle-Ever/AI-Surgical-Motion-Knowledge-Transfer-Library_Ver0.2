# レガシーコード削除・簡素化計画

## 🎯 目標
**複雑なレガシーコードを完全削除し、V2に一本化してデバッグ可能なシンプルな構造にする**

---

## 📋 現状分析

### レガシーコードの実態

#### 1. **旧SAM Tracker (`sam_tracker.py`)** 🔴 削除対象
- **場所**: `backend/app/ai_engine/processors/sam_tracker.py`
- **使用箇所**:
  - `app/api/routes/analysis.py` (Line 557, 560-598) - `process_with_mediapipe`関数内
  - `app/api/routes/videos.py` - 器具選択用
- **問題**:
  - `use_mock` フラグによる二重実装
  - OpenCVフォールバック混在
  - V2の`sam_tracker_unified.py`と機能重複

#### 2. **旧Analysis処理 (`analysis.py`内)** 🔴 削除対象
- **場所**: `app/api/routes/analysis.py` Line 500-700
- **関数**: `process_with_mediapipe()` - 巨大な処理関数
- **問題**:
  - MediaPipeとSAMを混在処理
  - フレームバッファリング、光学フロー、複雑なロジック
  - V2の`AnalysisServiceV2.analyze_video()`と完全重複

#### 3. **散乱したテストファイル** 🟡 整理対象
- **場所**: `backend/` ルート直下に18個のtest_*.py
- **問題**:
  - 何がアクティブで何が廃止か不明
  - デバッグ用の一時ファイルが残留
  - `backend/tests/` ディレクトリがあるのに未使用

#### 4. **重複した検出器実装** 🔴 統合対象
- `enhanced_hand_detector.py` - 改良版
- `skeleton_detector.py` - 標準版
- どちらを使うべきか不明確

---

## ✅ フェーズ別実行計画

### **Phase 0: 安全確認（15分）**
- [ ] 現在の全エンドポイントをテスト
- [ ] どのコードパスが実際に使われているか確認
- [ ] V2が全ての機能をカバーしているか検証

**テスト**:
```bash
# アップロード
curl -X POST http://localhost:8000/api/v1/videos/upload

# 解析開始（V2使用確認）
curl -X POST http://localhost:8000/api/v1/analysis/{video_id}/analyze

# 器具トラッキング
curl -X POST http://localhost:8000/api/v1/instrument-tracking/{video_id}/track
```

---

### **Phase 1: V2への完全移行確認（30分）**

#### 1.1 `analysis.py`の旧処理を無効化
**対象**: `process_with_mediapipe()` 関数 (Line 500-700)

**手順**:
1. 関数の先頭に明示的なエラーを追加
   ```python
   def process_with_mediapipe(...):
       raise NotImplementedError("DEPRECATED: Use AnalysisServiceV2 instead")
   ```
2. サーバー再起動
3. 解析テスト実行 → エラーが出ないことを確認（V2が使われている証拠）
4. エラーが出たら、まだ旧コードが使われている → 原因調査

**テスト**: 新しい動画をアップロード→解析→成功確認

#### 1.2 旧SAM Trackerの依存関係を確認
```bash
grep -r "from.*sam_tracker[^_]" backend/app/
```

**置き換え箇所**:
- `analysis.py`: すでにV2使用なので不要
- `videos.py`: 器具選択用 → `sam_tracker_unified`に置き換え

**テスト**: 器具選択機能が動作するか確認

---

### **Phase 2: レガシーコード削除（20分）**

#### 2.1 旧SAM Tracker削除
```bash
# バックアップ（念のため）
cp backend/app/ai_engine/processors/sam_tracker.py backend/sam_tracker.py.bak

# 削除
rm backend/app/ai_engine/processors/sam_tracker.py
```

#### 2.2 `analysis.py`から旧処理関数削除
**削除対象**:
- `process_with_mediapipe()` 関数全体 (Line 500-700)
- 関連するインポート

**テスト**: サーバー起動 → エラーなし → 解析実行 → 成功

#### 2.3 未使用の検出器整理
**判断基準**:
- `skeleton_detector.py`: V2で使用中 → **保持**
- `enhanced_hand_detector.py`: 未使用？ → 調査後判断

```bash
grep -r "enhanced_hand_detector" backend/app/
```

---

### **Phase 3: テストファイル整理（15分）**

#### 3.1 アクティブなテストを特定
```bash
# 最近実行されたテスト（modification timeでソート）
ls -lt backend/test_*.py | head -10
```

#### 3.2 tests/ディレクトリへ移動
```bash
mkdir -p backend/tests/legacy
mv backend/test_*.py backend/tests/legacy/
mv backend/upload_test_video.py backend/tests/legacy/
```

#### 3.3 必要なテストのみtests/に移動
- `tests/test_integration.py` - 既に正しい場所
- `backend/tests/legacy/test_sam_auto_detect.py` → `tests/test_sam_unified.py`（リネーム）

**テスト**: 重要なテストケースが動作するか確認

---

### **Phase 4: コードの最終簡素化（20分）**

#### 4.1 import文の整理
**対象ファイル**:
- `analysis.py`: 未使用のimportを削除
- `videos.py`: SAM関連を`sam_tracker_unified`に統一

#### 4.2 ログメッセージの統一
- `[V2]` プレフィックスを全て `[ANALYSIS]` に統一
- 一貫性のあるログフォーマット

#### 4.3 ドキュメント更新
```markdown
# docs/06_development/code_structure.md
## Analysis Pipeline (Simplified)
1. Upload: POST /api/v1/videos/upload
2. Analyze: POST /api/v1/analysis/{video_id}/analyze
   - Uses: AnalysisServiceV2 ONLY
   - SAM: sam_tracker_unified ONLY
   - Skeleton: skeleton_detector
3. Results: GET /api/v1/analysis/{analysis_id}
```

**テスト**: ドキュメントと実装が一致しているか確認

---

### **Phase 5: 最終検証（30分）**

#### 5.1 全機能の包括的テスト
```bash
# E2Eテスト
cd frontend
npm run test tests/e2e-v2-upload.spec.ts
npm run test tests/e2e-v2-analysis-external.spec.ts
npm run test tests/e2e-v2-analysis-internal.spec.ts
```

#### 5.2 パフォーマンス確認
- 解析速度が遅くなっていないか
- メモリリークがないか
- ログが適切に出力されているか

#### 5.3 エラーハンドリング確認
- 異常な入力でクラッシュしないか
- 適切なエラーメッセージが出るか

---

## 📊 削除・整理予定ファイルリスト

### 🔴 完全削除
- [ ] `backend/app/ai_engine/processors/sam_tracker.py`
- [ ] `backend/app/api/routes/analysis.py` の `process_with_mediapipe()` 関数

### 🟡 移動・リネーム
- [ ] `backend/test_*.py` (18ファイル) → `backend/tests/legacy/`
- [ ] `backend/upload_test_video.py` → `backend/tests/legacy/`

### 🟢 保持・更新
- [x] `backend/app/ai_engine/processors/sam_tracker_unified.py` - メイン実装
- [x] `backend/app/services/analysis_service_v2.py` - メインサービス
- [x] `backend/app/ai_engine/processors/skeleton_detector.py` - 骨格検出

### ❓ 調査が必要
- [ ] `backend/app/ai_engine/processors/enhanced_hand_detector.py` - 使用状況確認

---

## 🎯 成功基準

### 即座（各Phase完了時）:
- [ ] サーバーが起動する（エラーなし）
- [ ] 新しい動画のアップロードが成功
- [ ] 解析が完了し、結果が表示される
- [ ] 器具選択と追跡が動作する

### 最終（Phase 5完了時）:
- [ ] E2Eテスト全てパス
- [ ] コードベースから旧実装が完全削除
- [ ] ログが明確で追跡可能
- [ ] ドキュメントが最新の実装を反映

---

## ⚠️ リスクと対策

| リスク | 対策 |
|--------|------|
| V2が全機能をカバーしていない | Phase 0で徹底確認、問題あれば移行を中止 |
| 削除後に未知の依存関係が発覚 | 各Phaseでテスト、問題あればバックアップから復元 |
| パフォーマンス低下 | Phase 5でベンチマーク、問題あれば最適化 |
| 既存ユーザーへの影響 | データベース互換性確保、段階的ロールアウト |

---

## 📝 実行ログ

### Phase 0: 安全確認
- **開始**: 2025-10-05 02:30 JST
- **結果**: ✅ 完了
  - Lock fileメカニズム実装 (PID: 34584)
  - 骨格検出修正: `skeleton_detector.py`に`detected`キー追加
  - 解析成功: 292フレーム検出 (Analysis ID: 3493e268-6b94-471b-b21b-fe95f2a6cc59)
  - 複数バックエンド問題解決

### Phase 1: V2移行確認
- **開始**: 2025-10-05 03:00 JST
- **結果**: ✅ 完了
  - `process_with_mediapipe`関数: DEPRECATED化確認 (Line 439)
  - 呼び出し元: なし（V2が使用中）
  - SAM Tracker: `videos.py`で使用中（器具選択用）→ 保持

### Phase 2: レガシー削除
- **開始**: 2025-10-05 03:10 JST
- **結果**: ✅ 完了
  - 削除: Line 438-1122 (685行削除)
  - 削除対象:
    - `process_with_mediapipe_DEPRECATED()` (Line 439-793)
    - `sync_process_with_mock_enhanced_DEPRECATED()` (Line 794-940)
    - `sync_process_with_mock_DEPRECATED()` (Line 941-948)
    - `process_with_mock_DEPRECATED()` (Line 951-1122)
  - コード削減: 1,291行 → 606行 (53%削減)
  - サーバー正常稼働確認

### Phase 3: テスト整理
- **開始**: 2025-10-05 03:15 JST
- **結果**: ✅ 完了
  - `tests/legacy/` ディレクトリ作成
  - 移動: 16ファイル → `tests/legacy/`
  - リネーム:
    - `test_sam_auto_detect.py` → `tests/test_sam_unified.py`
    - `test_mediapipe_direct.py` → `tests/test_mediapipe.py`
  - ルートディレクトリ: test_*.py完全削除

### Phase 4: 最終簡素化
- **開始**: 2025-10-05 03:20 JST
- **結果**: ✅ 完了
  - ログメッセージ統一: `[V2]` → `[ANALYSIS]` (88箇所)
    - `analysis_service_v2.py`: 79箇所
    - `analysis.py`: 9箇所
  - インポート整理: 未使用なし
  - SAM Tracker: `videos.py`で使用中（削除不可）

### Phase 5: 最終検証
- **開始**: [次のフェーズ]
- **結果**: [実行待ち]
