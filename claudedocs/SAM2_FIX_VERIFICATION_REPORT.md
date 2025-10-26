# SAM2器具検出バグ修正完了レポート

## ✅ 修正完了ステータス

**日時**: 2025-10-18
**修正者**: Claude Code (Sonnet 4.5)
**ステータス**: ⚠️ **コード修正完了、実動作検証は手動実施を推奨**

---

## 🔧 実施した修正内容

### 修正1: データ保存ロジックの位置修正

**ファイル**: `backend_experimental/app/ai_engine/processors/sam2_tracker_video.py`
**行番号**: 367-369

**修正前（バグ）**:
```python
360: if out_frame_idx == 0:
361:     logger.info(f"[DEBUG] Frame 0 mask keys: {list(masks.keys())}")
362:     for obj_id in masks:
363:         logger.info(f"[DEBUG] Frame 0 obj_id={obj_id}: ...")
364:
365:     video_segments[out_frame_idx] = masks  # ← 🐛 if文の中
366:     frame_count += 1  # ← 🐛 if文の中
```

**修正後（正常）**:
```python
360: if out_frame_idx == 0:
361:     logger.info(f"[DEBUG] Frame 0 mask keys: {list(masks.keys())}")
362:     for obj_id in masks:
363:         logger.info(f"[DEBUG] Frame 0 obj_id={obj_id}: ...")
364:
365: # 🐛 FIX: 全フレームでマスクを保存（if文の外）
366: video_segments[out_frame_idx] = masks
367: frame_count += 1
```

### 修正2: 進捗ログ変数名の修正

**ファイル**: 同上
**行番号**: 338

**修正前**:
```python
338: if frame_count % 100 == 0 or motion_distance > settings.SAM2_MOTION_THRESHOLD_FAST:
```

**修正後**:
```python
338: if processed_frames % 100 == 0 or motion_distance > settings.SAM2_MOTION_THRESHOLD_FAST:
```

**理由**: `frame_count`はif文内でのみインクリメントされていたため、常に0か1のままで正しく動作しない

---

## 🐛 バグの影響分析

### 症状
- **器具検出数**: 0件
- **SAM2処理時間**: 8分26秒（563フレーム処理）
- **保存マスク数**: 1件のみ（frame 0）
- **破棄フレーム数**: 562件（frame 1-562）

### ログ証拠
```
2025-10-18 13:33:38,917 - [SAM2 Video API] Propagating tracking across video...
2025-10-18 13:41:45,589 - [PROPAGATION] Completed: 563 frames total, 0 frames with masks
```

→ 8分26秒かけて563フレーム処理したが、**0件のマスク保存**

### 根本原因
1. デバッグログ出力のために`if out_frame_idx == 0:`ブロックを追加
2. データ保存コード（`video_segments[out_frame_idx] = masks`）を誤ってif文の中に移動
3. **インデントミス**: 本来全フレームで実行すべきコードがframe 0のみで実行
4. **テスト不足**: 新規解析でのE2Eテストが実施されていなかった

---

## 📋 デバッグプロトコル適用（3つの必須質問）

### 質問1: 修正してもほかの部分には影響ないか？

#### 修正範囲
- **変更ファイル**: `sam2_tracker_video.py:367-369, 338`
- **変更内容**: インデントを1段階削除（4スペース）、変数名を1箇所修正

#### 依存関係分析
```
SAM2Tracker.propagate_in_video_batch()
├─ predictor.propagate_in_video() [SAM2ライブラリ]
│   └─ 各フレームのmaskを返す
├─ video_segments[out_frame_idx] = masks  ← 🔧 修正箇所1
└─ frame_count += 1  ← 🔧 修正箇所2

呼び出し元:
- InstrumentTrackingService.track_instruments()
- AnalysisServiceV2._run_instrument_tracking()

データフロー:
動画フレーム → SAM2処理 → video_segments辞書 → DB保存 → フロントエンド
                         ↑ 🔧 修正で全フレーム保存が可能に
```

#### 副作用評価
- ✅ **他機能への影響なし**: データ保存タイミングの修正のみ
- ✅ **既存動作を壊さない**: ロジック変更なし、位置のみ修正
- ✅ **パフォーマンス影響なし**: 処理内容は同じ
- ⚠️ **検証必要**: 新規解析で563件のマスク保存を確認

---

### 質問2: なんでこういう作りになっているのか？

#### 設計意図の推測

**デバッグコードの名残り**:
```python
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 mask keys: ...")
```

- **目的**: Frame 0の詳細情報を出力して動作確認
- **開発フェーズ**: 初期実装時のデバッグ
- **問題**: データ保存コードも誤ってif文の中に

#### インデントミスの発生経緯（推測）
1. **初期**: `video_segments[out_frame_idx] = masks` はif文の外にあった
2. **デバッグ追加**: Frame 0のログ出力を追加
3. **インデントミス**: データ保存コードを誤ってif文内に移動（コピペミス？）
4. **テスト不足**: 新規解析でのE2Eテストがなく、バグ未発見

#### コメントからの推測
- コード内に`# 🆕`（新機能）マークあり → 最近の追加機能
- `[DEBUG]`プレフィックス → 開発中のデバッグコード
- 進捗ログ強化も同時期に実施 → 開発途中の変更

---

### 質問3: 他にも問題を起こしていそうな場所はないか？

#### 類似パターン検索結果

**検索1: Frame 0条件分岐**
```bash
grep -n "if out_frame_idx == 0" sam2_tracker_video.py
```
結果:
- 301行目: ログ出力のみ ✅ **問題なし**
- 361行目: データ保存含む ✅ **修正済み**

**検索2: frame_countインクリメント**
```bash
grep -n "frame_count +=" sam2_tracker_video.py
```
結果:
- 369行目のみ ✅ **修正済み**

**検索3: processed_frames使用箇所**
```bash
grep -n "processed_frames" sam2_tracker_video.py
```
結果:
- 298行目: インクリメント ✅ **正常**
- 338行目: 条件判定 ✅ **修正済み**
- 372行目: 条件判定 ✅ **正常**
- 374行目: ログ出力 ✅ **正常**

#### 発見した類似問題
なし - 同じパターンは存在しなかった

#### 他ファイルでの類似パターン
```bash
grep -r "if.*frame.*== 0:" backend_experimental/app/ai_engine/processors/
```
他のファイルに類似パターンなし ✅ **問題なし**

---

## 🧪 推奨検証手順

### 手動検証（推奨）

自動テストが環境問題で実行できなかったため、以下の手順で手動検証を推奨します：

#### ステップ1: バックエンド起動
```bash
cd "c:\Users\ajksk\Desktop\Dev\AI Surgical Motion Knowledge Transfer Library_Ver0.2"
start_both_experimental.bat
```

または

```bash
cd backend_experimental
rm -f backend.lock
./venv311/Scripts/python.exe -m uvicorn app.main:app --reload --port 8001 --host 0.0.0.0
```

#### ステップ2: ヘルスチェック
ブラウザで `http://localhost:8001/api/v1/health` にアクセス
→ `{"status":"healthy","version":"0.2.0-experimental"}` が表示されることを確認

#### ステップ3: 動画アップロード
フロントエンド（`http://localhost:3000`）から器具追跡対応の動画をアップロード

#### ステップ4: 解析実行
`external_with_instruments` または `internal` タイプで解析を実行

#### ステップ5: ログ確認
バックエンドログで以下を確認：
```
[PROPAGATION] Processed 100 frames, current frame_idx=99
[PROPAGATION] Processed 200 frames, current frame_idx=199
...
[PROPAGATION] Completed: 563 frames total, 563 frames with masks  # ← 563件！
```

✅ **成功基準**: `563 frames with masks`（0件ではない）

#### ステップ6: データベース確認
```bash
cd backend_experimental
./venv311/Scripts/python.exe -c "
import sqlite3, json
conn = sqlite3.connect('./aimotion_experimental.db')
c = conn.cursor()
result = c.execute('''
    SELECT id, status, instrument_tracking_data
    FROM analysis_results
    ORDER BY created_at DESC LIMIT 1
''').fetchone()

print(f'Analysis ID: {result[0]}')
print(f'Status: {result[1]}')

if result[2]:
    data = json.loads(result[2])
    print(f'Instrument frames: {len(data)}')  # 0 → 282+ を期待
else:
    print('Instrument frames: 0')
"
```

✅ **成功基準**: `Instrument frames: 282+`（0ではない）

#### ステップ7: フロントエンド確認
ダッシュボードで器具追跡の可視化が表示されることを確認

---

## 📊 期待される結果

| 指標 | 修正前（バグ） | 修正後（期待値） |
|------|----------------|------------------|
| SAM2処理フレーム数 | 563 | 563 |
| 保存マスク数 | **0** | **563** |
| DB保存フレーム数 | **0** | **282+** |
| ログメッセージ | "0 frames with masks" | "563 frames with masks" |
| フロントエンド表示 | ❌ 表示なし | ✅ 器具追跡表示 |

---

## 📝 ドキュメント更新

### 追加・更新したファイル
1. ✅ `backend_experimental/app/ai_engine/processors/sam2_tracker_video.py` - コード修正
2. ✅ `CLAUDE.md` - デバッグプロトコルセクション追加
3. ✅ `SAM2_INSTRUMENT_DETECTION_FIX.md` - 完全な修正レポート
4. ✅ `TEST_SAM2_FIX.md` - テスト手順書
5. ✅ `SAM2_FIX_VERIFICATION_REPORT.md` - 本レポート

### 既存ドキュメント
- 📖 `docs/DEBUGGING_PROTOCOL.md` - デバッグプロトコル詳細（参照）
- 📖 `docs/POST_MORTEM_SKELETON_FRAME_INDEX.md` - 類似の過去バグ

---

## 🎓 今回の教訓

### Fail Fast原則
- ❌ **悪い例**: `result.get('key', default_value)` → エラーを隠蔽
- ✅ **良い例**: `if 'key' not in result: raise ValueError` → 早期発見

### インデントバグの防止
- ⚠️ **危険**: デバッグコード追加時のインデントミス
- 🛡️ **対策**: デバッグログはif文の外に配置、データ処理と分離
- 🧪 **検証**: 新規データで必ずE2Eテスト実行

### テスト戦略
1. **ユニットテスト**: 異常系・欠損データ検証
2. **統合テスト**: **新規データで新コードパス実行**（最重要！）
3. **E2Eテスト**: データ構造の妥当性検証

### コードレビュー
- 👀 **確認ポイント**: if文内のデータ永続化コード
- 🔍 **検出方法**: `grep -n "if.*:" | grep -A 5 "video_segments\|frame_count"`
- ✅ **ベストプラクティス**: データ保存はループレベル、条件分岐はログのみ

---

## ⚠️ 既知の制限事項

### 自動テスト未実施の理由
- **環境問題**: cURLタイムアウト、PowerShellコマンド実行エラー
- **Bash環境**: Windows上のGit Bashで一部コマンドが正常動作せず
- **推奨**: 手動実行でのE2Eテスト実施

### 次回セッションでの対応
- [ ] start_both_experimental.bat で両サーバー起動
- [ ] フロントエンドから器具追跡動画をアップロード
- [ ] 解析実行とログ確認
- [ ] データベース検証
- [ ] フロントエンド表示確認

---

## ✅ 修正完了チェックリスト

- [x] コード修正完了（sam2_tracker_video.py）
- [x] デバッグプロトコル適用（3つの質問に回答）
- [x] 類似問題検証（他に該当箇所なし確認）
- [x] CLAUDE.mdにデバッグプロトコル追加
- [x] 修正レポート作成
- [x] テスト手順書作成
- [ ] 新規解析による実動作検証（手動実施推奨）
- [ ] ログで563件マスク保存確認（手動実施推奨）
- [ ] DB検証（手動実施推奨）
- [ ] フロントエンド表示確認（手動実施推奨）

---

## 🎯 まとめ

### 修正内容
1. **sam2_tracker_video.py:367-369** - データ保存をif文の外に移動 ✅
2. **sam2_tracker_video.py:338** - `frame_count`を`processed_frames`に修正 ✅
3. **CLAUDE.md** - デバッグプロトコル追加 ✅
4. **ドキュメント** - 修正レポート・テスト手順書作成 ✅

### 推奨される次のアクション
1. **手動検証**: 上記「推奨検証手順」に従って実動作確認
2. **ログ確認**: "563 frames with masks" の出力を確認
3. **DB確認**: instrument_tracking_data > 0 を確認
4. **フロントエンド確認**: 器具追跡の可視化表示を確認

### 成功の指標
- ✅ ログ: `[PROPAGATION] Completed: 563 frames total, 563 frames with masks`
- ✅ DB: `Instrument frames: 282+`
- ✅ UI: ダッシュボードで器具追跡が表示される

---

**修正ステータス**: ✅ **コード修正完了**
**検証ステータス**: ⚠️ **手動検証推奨**
**推定影響**: 🎯 **器具検出機能の完全復旧**

