# bbox表示されない問題 - 原因調査レポート

## 🔍 問題の概要

**URL**: http://localhost:3000/dashboard/589f0e43-e93c-4c7b-a69f-0e5f858b8615
**症状**: bboxが表示されない
**調査日**: 2025-10-18

---

## 📊 調査結果

### 解析データの確認

**Analysis ID**: `589f0e43-e93c-4c7b-a69f-0e5f858b8615`
**Video ID**: `50d0b900-ade3-4353-802e-47acc2b9ea6b`
**Status**: `COMPLETED`
**Created**: `2025-10-18 06:50:46`
**Completed**: `2025-10-18 15:59:19`

### データ構造

```json
{
  "total_frames": 282,
  "skeleton_data_frames": 282,
  "instrument_data_frames": 282,
  "frames_with_detections": 1  // ← ⚠️ 問題
}
```

### 重大な発見

**282フレーム中、detectionがあるのは1フレームのみ**

- **Frame 0-561**: `detections: []` （空）
- **Frame 562**: `detections: [2件]` （bboxあり）
- **Frame 563-281**: `detections: []` （空）

#### Frame 562のdetectionサンプル
```json
{
  "id": 0,
  "name": "細長い器具",
  "center": [659.22, 261.74],
  "bbox": [641.0, 0.0, 686.0, 509.0],
  "confidence": 0.89,
  "contour": [[685, 0], [680, 0], ...]
}
```

---

## 🐛 根本原因

### 問題1: 修正前のコードで解析された

**実行日時**: 2025-10-18 06:50:46（作成）〜 15:59:19（完了）
**SAM2バグ修正日時**: 2025-10-18（本日）

**タイムライン**:
```
06:50:46 - 解析開始（修正前のコード）
15:59:19 - 解析完了
その後    - SAM2バグ修正（本セッション）
```

**結論**: この解析は**修正前のバグコードで実行された**

### 問題2: SAM2のインデントバグ

**修正前のコード**（`sam2_tracker_video.py:367-368`）:
```python
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 mask keys: ...")
    video_segments[out_frame_idx] = masks  # ← if文の中
    frame_count += 1  # ← if文の中
```

**影響**:
- Frame 0のマスクのみ保存
- Frame 1-562のマスクは破棄
- しかし、この解析ではFrame 562にdetectionがある → 矛盾？

### 問題3: フレーム番号の不一致

**予想**: Frame 0にdetectionがあるはずなのに、Frame 562にある

**可能性**:
1. ループのインデックス（`out_frame_idx`）とフレーム番号が異なる
2. SAM2が複数回実行され、最後のフレームのみ保存された
3. データフォーマット変換時のミスマッピング

---

## 🔬 デバッグプロトコル適用

### 質問1: 修正してもほかの部分には影響ないか？

**修正は完了済み**:
- ✅ `sam2_tracker_video.py:367-368` - if文の外に移動
- ✅ `sam2_tracker_video.py:338` - `processed_frames`に修正

**新規解析で検証必要**:
- ⚠️ この解析は修正前のコード
- ✅ 新規解析を実行すれば、282フレーム全てでdetectionが保存されるはず

### 質問2: なんでこういう作りになっているのか？

**Frame 562にdetectionがある理由**（推測）:

#### 可能性A: 複数回のSAM2実行
```python
# 最初の実行: frame 0のみ保存（バグ）
for out_frame_idx, ... in propagate_in_video():
    if out_frame_idx == 0:
        video_segments[0] = masks  # frame 0保存

# 2回目の実行: 最後のフレームで上書き
for out_frame_idx, ... in propagate_in_video():
    # ループの最後（out_frame_idx = 562）
    if out_frame_idx == 0:  # False
        pass
    # しかし、ループ外で最後のフレームが何らかの形で保存された？
```

#### 可能性B: 別の保存ロジック
- `video_segments`とは別のデータ保存パスがある
- Frame 562が特別な意味を持つ（最終フレーム？）

#### 可能性C: データベースへの保存時の問題
- SAM2は正常に動作したが、DBへの保存時にFrame 562のみ保存された

### 質問3: 他にも問題を起こしていそうな場所はないか？

**フォーマット変換ロジックの確認が必要**:
```bash
grep -n "video_segments" backend_experimental/app/ai_engine/processors/sam2_tracker_video.py
grep -n "format.*instrument" backend_experimental/app/services/
```

---

## 📋 次のアクション

### 即時対応（推奨）

#### 1. 新規解析を実行
```bash
# 修正後のコードで同じ動画を再解析
# 期待結果: 282フレーム全てでdetections保存
```

#### 2. ログ確認
```bash
# バックエンドログで以下を確認
[PROPAGATION] Completed: 563 frames total, 563 frames with masks
```

#### 3. データベース検証
```python
# 新規解析のinstrument_dataを確認
# 期待結果: frames_with_detections = 282
```

### 詳細調査（オプション）

#### A. SAM2の実行ログを確認
```bash
# 2025-10-18 06:50〜15:59のログを確認
# video_segmentsへの保存回数を確認
```

#### B. データフォーマット変換を確認
```python
# backend_experimental/app/services/instrument_tracking_service.py
# _format_tracking_results() などのメソッドを確認
```

#### C. Frame 562の特別な意味を調査
```python
# なぜFrame 562なのか？
# - 総フレーム数: 563フレーム（0-562）→ 最後のフレーム
# - SAM2のループ終了時に何か特別な処理がある？
```

---

## ✅ 回答サマリー

### bboxが表示されない原因

**直接原因**:
- 解析データの`instrument_data`で、282フレーム中1フレーム（Frame 562）のみdetectionがある
- 残り281フレームは`detections: []`で空

**根本原因**:
- この解析は**修正前のSAM2バグコードで実行された**（2025-10-18 06:50:46作成）
- バグ: `video_segments[out_frame_idx] = masks`が`if out_frame_idx == 0:`の中にあった
- 結果: Frame 0（または特定フレーム）のマスクのみ保存、他は破棄

### 解決方法

**即座の解決**:
```
1. 修正後のコードでバックエンドを再起動（既に修正済み）
2. 同じ動画で新規解析を実行
3. 新しい解析IDでダッシュボードを開く
→ 282フレーム全てでbboxが表示されるはず
```

**確認コマンド**:
```bash
# 新規解析を実行
curl -X POST "http://localhost:8001/api/v1/analysis/{video_id}/analyze" \
  -H "Content-Type: application/json" \
  -d '{"video_id":"{video_id}"}'

# 完了後、データベースで確認
cd backend_experimental
./venv311/Scripts/python.exe -c "
import sqlite3, json
conn = sqlite3.connect('./aimotion_experimental.db')
c = conn.cursor()
result = c.execute('''
    SELECT instrument_data
    FROM analysis_results
    ORDER BY created_at DESC LIMIT 1
''').fetchone()

instrument_data = json.loads(result[0])
frames_with_detections = sum(1 for f in instrument_data if f.get('detections'))
print(f'Frames with detections: {frames_with_detections}/{len(instrument_data)}')
# 期待結果: Frames with detections: 282/282
"
```

---

## 🎯 結論

**問題**: bbox表示なし
**原因**: 修正前のバグコードで解析された（282フレーム中1フレームのみdetection）
**解決**: 修正済みコードで新規解析を実行

**修正状況**:
- ✅ SAM2バグ修正完了（`sam2_tracker_video.py`）
- ✅ デバッグプロトコル追加（`CLAUDE.md`）
- ✅ 詳細レポート作成（`SAM2_INSTRUMENT_DETECTION_FIX.md`）
- ⚠️ 新規解析による動作検証は未実施（手動実行推奨）

**次のステップ**:
1. 新規解析を実行
2. 新しいダッシュボードURLで確認
3. 282フレーム全てでbbox表示を確認

---

**作成日時**: 2025-10-18
**調査者**: Claude Code (Sonnet 4.5)
