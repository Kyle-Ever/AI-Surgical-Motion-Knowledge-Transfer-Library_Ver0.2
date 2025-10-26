# SAM2器具検出バグ修正テスト

## 修正内容

### 問題
**ファイル**: `backend_experimental/app/ai_engine/processors/sam2_tracker_video.py`

**バグ箇所**: 367-368行目がif文の中にあった
```python
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 mask keys: ...")
    video_segments[out_frame_idx] = masks  # ← frame 0のみ保存
    frame_count += 1  # ← frame 0のみカウント
```

**影響**:
- 563フレーム処理されるが、frame 0のマスクのみ保存
- frame 1-562は破棄される
- 結果: 0件の器具検出

### 修正後
```python
if out_frame_idx == 0:
    logger.info(f"[DEBUG] Frame 0 mask keys: ...")

# 🐛 FIX: 全フレームでマスクを保存（if文の外）
video_segments[out_frame_idx] = masks
frame_count += 1
```

### 追加修正
**338行目**: `frame_count`を`processed_frames`に変更
```python
# 修正前
if frame_count % 100 == 0 or motion_distance > settings.SAM2_MOTION_THRESHOLD_FAST:

# 修正後
if processed_frames % 100 == 0 or motion_distance > settings.SAM2_MOTION_THRESHOLD_FAST:
```

## 検証手順

### 1. コード修正確認
```bash
cd backend_experimental/app/ai_engine/processors
grep -A 2 "FIX: 全フレームでマスクを保存" sam2_tracker_video.py
```

期待される出力:
```
# 🐛 FIX: 全フレームでマスクを保存（if文の外）
video_segments[out_frame_idx] = masks
frame_count += 1
```

### 2. バックエンド再起動
```bash
cd backend_experimental
rm -f backend.lock
./venv311/Scripts/python.exe -m uvicorn app.main:app --reload --port 8001 --host 0.0.0.0
```

### 3. 修正前の動画で再解析
```bash
# 既存の器具追跡対応動画で解析
curl -X POST "http://localhost:8001/api/v1/analysis/{video_id}/analyze" \
  -H "Content-Type: application/json" \
  -d '{"video_id":"{video_id}"}'
```

### 4. ログで確認
期待されるログ:
```
[PROPAGATION] Processed 100 frames, current frame_idx=...
[PROPAGATION] Processed 200 frames, current frame_idx=...
...
[PROPAGATION] Completed: 563 frames total, 563 frames with masks  # ← 563件のマスク保存
```

修正前（バグ）:
```
[PROPAGATION] Completed: 563 frames total, 0 frames with masks  # ← 0件
```

### 5. 結果確認
```bash
cd backend_experimental
./venv311/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('./aimotion_experimental.db')
c = conn.cursor()
result = c.execute('''
    SELECT id, status,
           json_array_length(instrument_tracking_data) as instrument_frames
    FROM analysis_results
    ORDER BY created_at DESC LIMIT 1
''').fetchone()
print(f'Analysis ID: {result[0]}')
print(f'Status: {result[1]}')
print(f'Instrument frames: {result[2]}')  # 0 → 282+ を期待
"
```

## 成功基準

✅ **修正成功**: `Instrument frames: 282` （または解析フレーム数）
❌ **修正前**: `Instrument frames: 0`

## トラブルシューティング

### バックエンドが起動しない
```bash
# Port 8000/8001を使用しているプロセスを確認
netstat -ano | findstr :8001

# Pythonプロセスを全て終了
taskkill /F /IM python.exe

# ロックファイルを削除
rm backend_experimental/backend.lock
```

### 古いコードが動作している
```bash
# Pythonキャッシュをクリア
find backend_experimental/app -name "__pycache__" -type d -exec rm -rf {} +

# バックエンド再起動
```

### データベースが空
```bash
# backendのDBをコピー
cp backend/aimotion.db backend_experimental/aimotion_experimental.db
```

## 関連ドキュメント
- [docs/DEBUGGING_PROTOCOL.md](docs/DEBUGGING_PROTOCOL.md) - デバッグプロトコル
- [docs/POST_MORTEM_SKELETON_FRAME_INDEX.md](docs/POST_MORTEM_SKELETON_FRAME_INDEX.md) - 過去の類似バグ
