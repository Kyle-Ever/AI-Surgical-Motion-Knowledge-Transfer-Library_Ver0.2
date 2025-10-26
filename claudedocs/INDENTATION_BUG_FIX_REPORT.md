# SAM2 インデントバグ修正レポート

**日時**: 2025-10-18 22:30
**解析ID**: 00d82127-7d65-45d1-bbf5-361da19e5908
**症状**: 282フレーム中1フレームのみbbox表示

---

## 🚨 根本原因: 致命的なインデントエラー

**ファイル**: `backend_experimental/app/ai_engine/processors/sam2_tracker_video.py`

### 問題の構造

**修正前** (バグあり):
```python
296:                 for out_frame_idx, out_obj_ids, out_mask_logits in \
297:                         self.predictor.propagate_in_video(self.inference_state):
298:                     processed_frames += 1  # ← forループ内（正しい）
299:
300:                 # デバッグ...  ← forループ外！（間違い）
301:                 if out_frame_idx == 0:
...
367:                 video_segments[out_frame_idx] = masks  # ← ループ外
368:                 frame_count += 1                       # ← ループ外
```

**修正後** (正しい):
```python
296:                 for out_frame_idx, out_obj_ids, out_mask_logits in \
297:                         self.predictor.propagate_in_video(self.inference_state):
298:                     processed_frames += 1  # ← forループ内
299:
300:                     # デバッグ...  ← forループ内（正しい）
301:                     if out_frame_idx == 0:
...
367:                     video_segments[out_frame_idx] = masks  # ← ループ内
368:                     frame_count += 1                       # ← ループ内
```

### 影響範囲

**バグの影響を受けた行**: 300-373行（74行）

**修正内容**: 各行のインデントを+4スペース（forループ内に移動）

---

## 🔍 バグの発見プロセス

### 1. データベース調査
```sql
SELECT * FROM analysis_results WHERE id = '00d82127-7d65-45d1-bbf5-361da19e5908';
```

**結果**:
- 総フレーム数: 282
- 検出があるフレーム: 1 (Frame 562のみ)
- 作成日時: 2025-10-18 12:56:55 (UTC)
- 完了日時: 2025-10-18 22:05:52

### 2. タイムゾーン分析
- データベース時刻: 12:56:55 (UTC)
- ログ時刻: 21:56:55 (JST = UTC+9)
- **実際の開始**: 21:56:55 JST

### 3. コード修正との時系列
- 前回の修正: 14:54:19 (368行目を`if out_frame_idx == 0:`の外に移動)
- バックエンド再起動: 21:35:41
- **この解析の開始: 21:56:55** ← 修正後、再起動後！

### 4. ログ分析
```
2025-10-18 22:05:50 - [PROPAGATION] Completed: 563 frames total, 1 frames with masks
```

**矛盾点**:
- ループは563回実行された (`processed_frames = 563`)
- しかし保存されたフレームは1つのみ (`frame_count = 1`)

### 5. インデント検証
```python
# 298行目: forループ内 (indent=20)
processed_frames += 1

# 300行目: forループ外 (indent=16) ← 問題！
# デバッグ...
```

**結論**: 300-373行がforループの外にあるため、563回ループしても最後の1回のみ処理される。

---

## ✅ 修正内容

### 変更ファイル
- `backend_experimental/app/ai_engine/processors/sam2_tracker_video.py`

### 変更サマリ
| 行範囲 | 変更内容 | 理由 |
|--------|---------|------|
| 300-373 | インデント+4スペース | forループ内に移動 |

### 修正後の動作
1. **各フレームで実行される処理**:
   - マスク検出とバイナリ化 (306-358行)
   - デバッグログ出力 (361-365行)
   - マスクの保存 (368-369行)
   - 進捗ログ (372-373行、100フレームごと)

2. **期待される結果**:
   - `processed_frames = 563` (ループ回数)
   - `frame_count = 563` (保存されたフレーム数)
   - 最終ログ: `[PROPAGATION] Completed: 563 frames total, 563 frames with masks`

---

## 🧪 検証計画

### 必須検証項目

1. **新規解析の実行**
   - 既存の動画を再解析
   - 解析完了まで待機

2. **ログ確認**
   ```bash
   grep "PROPAGATION.*Completed" backend_experimental/backend_restart.log | tail -1
   ```
   **期待値**: `563 frames total, 563 frames with masks`

3. **データベース確認**
   ```bash
   sqlite3 aimotion_experimental.db "
   SELECT id, created_at,
          json_array_length(instrument_data) as total_frames,
          (SELECT COUNT(*) FROM json_each(instrument_data)
           WHERE json_array_length(json_extract(value, '$.detections')) > 0) as frames_with_detections
   FROM analysis_results
   ORDER BY created_at DESC
   LIMIT 1;
   "
   ```
   **期待値**: `frames_with_detections = 282` (または全抽出フレーム数)

4. **フロントエンド確認**
   - ダッシュボードで全フレームにbboxが表示される
   - スライダーを動かして全範囲でbbox表示を確認

---

## 🔄 なぜこのバグが発生したのか

### 前回の修正（14:54）の意図
**目的**: 368行目 `video_segments[out_frame_idx] = masks` を `if out_frame_idx == 0:` の外に移動

**しかし**:
- 移動先が間違っていた: forループの外に移動してしまった
- 正しい移動先: forループ内、if文の外

### 見落とされた理由
1. **視覚的な類似性**:
   - forループの終端がどこか分かりにくい
   - 298行目だけがループ内で、300行目以降が外だった

2. **テストの不足**:
   - 修正後に新規解析を実行していなかった
   - 既存の解析結果のみを確認していた

3. **ログの誤解釈**:
   - "563 frames total" を見て全フレーム処理されたと誤解
   - "1 frames with masks" の重大性を見逃した

---

## 📝 今後の防止策

### 1. コード変更時の必須チェック
- [ ] インデント構造の明示的な確認
- [ ] forループの開始と終了を明確に把握
- [ ] Pythonの構文チェッカー使用

### 2. テスト戦略の改善
- [ ] コード変更後は**必ず新規解析**を実行
- [ ] 既存データのテストだけでは不十分
- [ ] ログの数値を詳細に確認（`processed_frames` vs `frame_count`）

### 3. ログの改善
- [ ] 進捗ログを100フレームごとではなく、最終結果のみに変更
- [ ] forループ内でのログ出力を最小化
- [ ] 最終結果ログの位置を明確化

### 4. デバッグプロトコルの適用
**3つの必須質問**:
1. ✅ **影響範囲**: forループ内の全処理に影響
2. ✅ **設計意図**: 前回の修正が不完全だった
3. ✅ **類似箇所**: 他のループ構造も確認が必要

---

## 📌 関連ドキュメント

- [POST_MORTEM: 骨格検出フレームインデックス](POST_MORTEM_SKELETON_FRAME_INDEX.md)
- [デバッグプロトコル](docs/DEBUGGING_PROTOCOL.md)
- [SAM2修正検証レポート](SAM2_FIX_VERIFICATION_REPORT.md)

---

**修正実施者**: Claude Code
**レビュー推奨**: Python開発者によるコードレビュー
**優先度**: 🔴 CRITICAL
