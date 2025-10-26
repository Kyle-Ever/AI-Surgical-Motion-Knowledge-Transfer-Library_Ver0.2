# SAM2器具検出バグ修正完了レポート

## 🐛 問題の概要

**症状**: 器具検出が0件になり、追跡が動作しない
**影響範囲**: `external_with_instruments` / `internal` タイプの全動画
**発見日**: 2025-10-18
**修正日**: 2025-10-18

## 📊 根本原因分析

### バグ箇所
**ファイル**: `backend_experimental/app/ai_engine/processors/sam2_tracker_video.py`
**行番号**: 367-368（修正前）

### コード詳細

#### ❌ 修正前（バグコード）
```python
# 360-368行目
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 mask keys: {list(masks.keys())}")
    for obj_id in masks:
        logger.info(f"[DEBUG] Frame 0 obj_id={obj_id}: mask shape={masks[obj_id].shape}")

    video_segments[out_frame_idx] = masks  # ← 🐛 if文の中
    frame_count += 1  # ← 🐛 if文の中
```

**問題点**:
1. `video_segments[out_frame_idx] = masks` が **frame 0の条件分岐の中**
2. `frame_count += 1` も **frame 0の条件分岐の中**
3. そのため、**frame 0（最初のフレーム）のマスクしか保存されない**
4. SAM2は563フレーム全てを処理（8分26秒かかる）
5. しかし、**frame 1-562の結果は全て破棄される**

#### ✅ 修正後（正しいコード）
```python
# 360-372行目
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 mask keys: {list(masks.keys())}")
    for obj_id in masks:
        logger.info(f"[DEBUG] Frame 0 obj_id={obj_id}: mask shape={masks[obj_id].shape}")

# 🐛 FIX: 全フレームでマスクを保存（if文の外）
video_segments[out_frame_idx] = masks
frame_count += 1

# 🆕 進捗ログ強化（100フレームごと + 詳細情報）
if processed_frames % 100 == 0:
    logger.warning(f"[PROPAGATION] Processed {processed_frames} frames, current frame_idx={out_frame_idx}")
```

### 追加修正

#### 修正2: 進捗ログの変数修正
**ファイル**: 同上
**行番号**: 338

```python
# ❌ 修正前
if frame_count % 100 == 0 or motion_distance > settings.SAM2_MOTION_THRESHOLD_FAST:

# ✅ 修正後
if processed_frames % 100 == 0 or motion_distance > settings.SAM2_MOTION_THRESHOLD_FAST:
```

**理由**: `frame_count`はif文の中でしかインクリメントされないため、常に0か1のまま

## 🔍 影響分析（質問1: 修正してもほかの部分には影響ないか？）

### 修正範囲
- **変更ファイル**: `sam2_tracker_video.py:367-369, 338`
- **変更内容**: インデントを4スペース削除（if文の外に移動）、変数名を修正

### 依存関係
```
SAM2Tracker.propagate_in_video_batch()
├─ predictor.propagate_in_video() [SAM2ライブラリ]
│   └─ out_frame_idx, out_obj_ids, out_mask_logits を返す
├─ video_segments[out_frame_idx] = masks  ← 🔧 修正箇所
└─ frame_count += 1  ← 🔧 修正箇所
```

**呼び出し元**:
- `InstrumentTrackingService.track_instruments()`
- `AnalysisServiceV2._run_instrument_tracking()`

**データフロー**:
```
動画フレーム → SAM2処理 → video_segments辞書 → データベース → フロントエンド表示
                           ↑ 🔧 ここを修正
```

### 副作用評価
- ✅ **他の機能への影響なし**: データ保存ロジックの修正のみ
- ✅ **既存の動作を壊さない**: if文の外に移動しただけ
- ✅ **パフォーマンス影響なし**: 処理ロジックは同じ
- ⚠️ **検証必要**: 新規解析でマスク保存が正常に動作するか確認

## 📚 背景調査（質問2: なんでこういう作りになっているのか？）

### 設計意図の推測

#### デバッグコードの名残り
```python
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 mask keys: ...")
```

このブロックは **frame 0のデバッグ情報を出力するため** に追加された。
開発中に、最初のフレームだけ詳細情報を確認したかったと推測される。

#### インデントミスの発生経緯
1. **初期実装**: データ保存コードはif文の外にあった（推測）
2. **デバッグ追加**: frame 0のログ出力を追加
3. **インデントミス**: データ保存コードを誤ってif文の中に移動
4. **テスト不足**: 新規解析でのテストがなく、バグが発見されなかった

### Git履歴（推測）
- コミット履歴を確認すべきだが、現時点では不明
- おそらく「デバッグログ追加」のコミットでミス混入

## 🔎 類似問題検証（質問3: 他にも問題を起こしていそうな場所はないか？）

### 検索パターン
```bash
# frame 0の条件分岐を検索
grep -n "if out_frame_idx == 0" backend_experimental/app/ai_engine/processors/sam2_tracker_video.py

# 結果
301:                if out_frame_idx == 0:
361:                if out_frame_idx == 0:
```

### 発見した類似箇所

#### 箇所1: 301行目（問題なし）
```python
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 out_mask_logits: shape={out_mask_logits.shape}, ...")
```
✅ **問題なし**: ログ出力のみ、データ保存は含まれていない

#### 箇所2: 361行目（今回修正）
```python
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 mask keys: ...")
    video_segments[out_frame_idx] = masks  # ← 🐛 修正済み
```
✅ **修正済み**: if文の外に移動

### 他のループでの類似パターン検索
```bash
# frame_count のインクリメント箇所
grep -n "frame_count +=" backend_experimental/app/ai_engine/processors/sam2_tracker_video.py

# 結果
369:                frame_count += 1
```

✅ **他に類似箇所なし**: frame_countのインクリメントは1箇所のみ

### processed_frames の使用箇所検証
```bash
grep -n "processed_frames" backend_experimental/app/ai_engine/processors/sam2_tracker_video.py

# 結果
298:                    processed_frames += 1
338:                            if processed_frames % 100 == 0 or ...  # ← 🔧 修正済み
372:                    if processed_frames % 100 == 0:
374:                logger.info(f"[PROPAGATION] Completed: {processed_frames} frames total, ...")
```

✅ **全て正常**: processed_framesの使用は適切

## ✅ 修正必要箇所

- [x] `sam2_tracker_video.py:367-368` - データ保存をif文の外に移動 ✅ **完了**
- [x] `sam2_tracker_video.py:338` - `frame_count`を`processed_frames`に修正 ✅ **完了**
- [x] `CLAUDE.md` - デバッグプロトコル追加 ✅ **完了**

## 🧪 検証手順

### 1. コード修正確認
```bash
cd backend_experimental/app/ai_engine/processors
grep -A 2 "FIX: 全フレームでマスクを保存" sam2_tracker_video.py
```

**期待される出力**:
```
# 🐛 FIX: 全フレームでマスクを保存（if文の外）
video_segments[out_frame_idx] = masks
frame_count += 1
```

### 2. バックエンド再起動
```bash
cd backend_experimental
rm -f backend.lock
./venv311/Scripts/python.exe -m uvicorn app.main:app --reload --port 8001
```

### 3. 新規解析実行
```bash
# 器具追跡対応の動画で解析
curl -X POST "http://localhost:8001/api/v1/analysis/{video_id}/analyze" \
  -H "Content-Type: application/json" \
  -d '{"video_id":"{video_id}"}'
```

### 4. ログ確認
**期待されるログ（修正後）**:
```
[PROPAGATION] Processed 100 frames, current frame_idx=99
[PROPAGATION] Processed 200 frames, current frame_idx=199
...
[PROPAGATION] Completed: 563 frames total, 563 frames with masks  # ← 563件
```

**修正前（バグ）**:
```
[PROPAGATION] Completed: 563 frames total, 0 frames with masks  # ← 0件
```

### 5. データベース確認
```python
import sqlite3
conn = sqlite3.connect('./aimotion_experimental.db')
c = conn.cursor()

# 最新の解析結果を確認
result = c.execute('''
    SELECT
        id,
        status,
        json_array_length(instrument_tracking_data) as instrument_frames
    FROM analysis_results
    ORDER BY created_at DESC LIMIT 1
''').fetchone()

print(f'Analysis ID: {result[0]}')
print(f'Status: {result[1]}')
print(f'Instrument frames: {result[2]}')  # 0 → 282+ を期待
```

## 📈 成功基準

| 指標 | 修正前 | 修正後（期待値） |
|------|--------|------------------|
| 処理フレーム数 | 563 | 563 |
| 保存マスク数 | **0** | **563** |
| instrument_tracking_data長 | **0** | **282+** |
| ログ出力 | "0 frames with masks" | "563 frames with masks" |

## 🎓 教訓

### Fail Fast原則の重要性
- **データの存在を仮定しない**
- **早期に大きく失敗する**（Silent Failureを避ける）
- **新規データで必ずテスト**（既存データのみは不十分）

### インデントバグの危険性
- **デバッグコード追加時は特に注意**
- **if文の中に重要なロジックを入れない**
- **コードレビューで必ず確認**

### テスト戦略
1. **ユニットテスト**: エッジケース、異常系、欠損データ
2. **統合テスト**: **新規データで新コードパスを実行**（重要！）
3. **E2Eテスト**: データ構造の妥当性も検証

## 📎 関連ドキュメント

- [docs/DEBUGGING_PROTOCOL.md](docs/DEBUGGING_PROTOCOL.md) - 今回制定したデバッグプロトコル
- [docs/POST_MORTEM_SKELETON_FRAME_INDEX.md](docs/POST_MORTEM_SKELETON_FRAME_INDEX.md) - 類似の過去バグ
- [CLAUDE.md](CLAUDE.md) - デバッグプロトコル参照を追加

## ⚠️ 残タスク

- [ ] 新規解析を実行して動作確認
- [ ] ログで563件のマスク保存を確認
- [ ] データベースでinstrument_tracking_data > 0を確認
- [ ] E2Eテストを作成
- [ ] POST_MORTEMドキュメント作成（必要に応じて）

---

**修正者**: Claude Code (Sonnet 4.5)
**修正日時**: 2025-10-18
**検証状態**: コード修正完了、動作検証保留
