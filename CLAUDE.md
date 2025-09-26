# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language Preference
**日本語で応答してください** - Please respond in Japanese unless explicitly requested otherwise.

## Critical Environment Requirements

### Python 3.11 MANDATORY
**MUST use Python 3.11** - Python 3.13 breaks MediaPipe/OpenCV compatibility
- Virtual environment: `backend\venv311\`
- Always use: `./venv311/Scripts/python.exe` for backend operations
- Check version: `./venv311/Scripts/python.exe --version` should show 3.11.x

### CORS Configuration (Development)
**Upload feature requires these settings:**
- Backend: `allow_origins=["*"]` in `backend/app/main.py`
- Frontend: `.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`
- Backend `.env`: `BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost:8000"]`

### Environment Variables
**Backend (.env)**
```
DATABASE_URL=sqlite:///./aimotion.db
UPLOAD_DIR=data/uploads
MAX_UPLOAD_SIZE=2147483648  # 2GB in bytes
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost:8000"]
```

**Frontend (.env.local)**
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## Commands

### Quick Start
```bash
# Both servers (recommended)
start_both.bat

# Backend only
cd backend && ./venv311/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend && npm install && npm run dev
```

### Dependencies Installation
```bash
# Backend dependencies
cd backend
./venv311/Scripts/python.exe -m pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
```

### Testing
```bash
# Frontend E2E (Playwright)
cd frontend
npm run test              # Headless
npm run test:ui           # Interactive UI
npm run test:headed       # Browser visible
npm run test:report       # View test report
npx playwright test upload.spec.ts  # Single file
npx playwright test --grep "upload"  # Pattern matching

# Frontend type check & lint
cd frontend
npm run lint              # ESLint check
npx tsc --noEmit         # TypeScript check

# Backend API tests
cd backend
./venv311/Scripts/python.exe test_api.py
./venv311/Scripts/python.exe test_mediapipe_integration.py
./venv311/Scripts/python.exe test_analysis_processing.py
./venv311/Scripts/python.exe tests/test_integration.py

# Backend database check
./venv311/Scripts/python.exe check_db.py
```

### Development Commands
```bash
# Frontend
npm run build             # Production build
npm run lint              # ESLint v9
npm run test:debug        # Debug Playwright tests

# Backend database
cd backend
sqlite3 aimotion.db ".tables"  # Direct SQL access
sqlite3 aimotion.db ".schema videos"  # Table schema
```

## High-Level Architecture

### Processing Pipeline
1. **Upload**: Video → `backend/data/uploads/` (2GB max, .mp4 only)
2. **Analysis**: Frame extraction → AI detection → Score calculation
3. **Detection Types**:
   - `external` videos: MediaPipe skeleton detection (hand tracking)
   - `internal` videos: YOLOv8 instrument detection + SAM tracker
4. **Real-time Updates**: WebSocket progress at `/ws/analysis/{analysis_id}`

### Key API Endpoints
- `POST /api/v1/videos/upload` - Upload video (2GB limit)
- `POST /api/v1/analysis/{video_id}/analyze` - Start analysis
- `GET /api/v1/analysis/{analysis_id}/status` - Check progress
- `GET /api/v1/videos` - List all videos with pagination
- `GET /api/v1/analysis/{analysis_id}` - Get analysis results
- `POST /api/v1/scoring/compare` - Compare analysis with reference
- `GET /api/v1/library/references` - Get reference videos
- `POST /api/v1/instrument-tracking/{video_id}/track` - Start instrument tracking
- `WS /ws/analysis/{analysis_id}` - Real-time progress

### Core Services Architecture
- **AnalysisService** (`backend/app/services/analysis_service.py`): Orchestrates entire processing pipeline with step-based progress tracking
- **ScoringService** (`backend/app/services/scoring_service.py`): Calculates motion metrics and comparison scores
- **InstrumentTrackingService** (`backend/app/services/instrument_tracking_service.py`): Handles surgical instrument detection and tracking
- **MetricsCalculator** (`backend/app/services/metrics_calculator.py`): Computes motion metrics from tracking data
- **WebSocket Manager** (`backend/app/core/websocket.py`): Manages real-time client connections
- **AI Processors** (`backend/app/ai_engine/processors/`): Modular detection components
  - `skeleton_detector.py`: MediaPipe hand/body tracking
  - `sam_tracker.py`: Segment Anything Model for instruments
  - `hybrid_hand_detector.py`: Combined detection approach
  - `glove_hand_detector.py`: White surgical glove detection
  - `enhanced_hand_detector.py`: Improved detection accuracy
- **Frontend State**: Zustand for global state, custom hooks for WebSocket connections

### Database Schema
SQLite at `backend/aimotion.db` with SQLAlchemy ORM:
- `videos`: Video metadata and upload info
- `analyses`: Analysis sessions and results
- `reference_videos`: Gold standard references
- `comparisons`: Score comparisons between videos

## Implementation Patterns

### Async Processing (Backend)
```python
# MediaPipe blocks, use executor:
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, process_with_mediapipe, frames)
```

### WebSocket Updates
```python
from app.core.websocket import manager
await manager.send_update(analysis_id, {
    "type": "progress",
    "step": "skeleton_detection",
    "progress": 50
})
```

### Frontend State Management (Zustand)
```typescript
// stores/useVideoStore.ts
import { create } from 'zustand'

const useVideoStore = create((set) => ({
  videos: [],
  setVideos: (videos) => set({ videos }),
  addVideo: (video) => set((state) => ({
    videos: [...state.videos, video]
  }))
}))
```

### Custom Hooks Pattern
```typescript
// hooks/useWebSocket.ts
export function useWebSocket(analysisId: string) {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/analysis/${analysisId}`)
    ws.onmessage = (e) => setProgress(JSON.parse(e.data).progress)
    return () => ws.close()
  }, [analysisId])

  return { progress }
}
```

## Key Constraints
- **Python Version**: Python 3.11.9 ONLY (3.13 breaks MediaPipe/OpenCV)
- **Dependencies**: `numpy<2`, `ultralytics==8.0.200`, `mediapipe>=0.10.0` (fixed versions)
- **File Limits**: 2GB uploads, .mp4 only
- **Ports**: Backend 8000, Frontend 3000
- **Frontend**: Next.js 15.5.2 with Turbopack, TypeScript, Tailwind CSS v4
- **State Management**: Zustand v5.0.8 for global state
- **Charts**: Chart.js v4.5.0, react-chartjs-2 v5.3.0, recharts v3.2.1
- **3D Rendering**: Three.js with @react-three/fiber for 3D visualizations
- **Testing**: Playwright v1.55.0 expects Japanese UI text
- **Batch Files**: Use Windows batch files (`start_both.bat`, etc.) for consistent environment

## Development Process
For non-trivial changes, follow `docs/Rules/`:
1. **PRD Creation** (`01_prd_generation_rules.md`)
2. **Task Decomposition** (`02_task_generation_rules.md`) - 15-90 min tasks
3. **Execution** (`03_task_execution_rules.md`) - One task at a time

## 🚨 Troubleshooting Guide

### ⚠️ **コード変更が反映されない場合**
**原因**: 古いプロセスがキャッシュされたコードを実行している

**診断手順**:
1. ブラウザで変更が反映されているか確認
2. 開発者ツールのConsoleでエラー確認
3. 別のポートで起動して比較
   ```bash
   # ポート3000で問題がある場合、3002で試す
   npm run dev -- --port 3002
   ```

**解決方法**:
```bash
# 1. 現在のポート使用状況を確認
netstat -ano | findstr :3000

# 2. 古いプロセスを強制終了
taskkill /PID <process_id> /F
# または全Node.jsプロセスを終了
taskkill /F /IM node.exe

# 3. .nextキャッシュをクリア（必要な場合）
cd frontend
rmdir /s /q .next
npm run dev

# 4. ブラウザキャッシュもクリア
# Ctrl+Shift+R でハードリロード
```

**予防策**:
- 大きな変更（HTML要素の変更等）後は必ずサーバー再起動
- 長時間実行している開発サーバーは定期的に再起動
- `git diff`で変更内容を確認してから実行

### 🔴 **Runtime TypeErrors (null/undefined参照)**
**症状**: `Cannot read properties of null (reading 'xxx')`

**主な発生箇所**:
- ScoreComparison: `result?.efficiency_score`
- FeedbackPanel: `result?.feedback`
- MotionAnalysisPanel: `analysisData?.skeleton_data`

**解決方法**:
```typescript
// ❌ Bad - null参照エラーの可能性
{result.efficiency_score}

// ✅ Good - Optional chaining + fallback
{result?.efficiency_score ?? '--'}

// ✅ Good - モックデータフォールバック
const data = result?.metrics || mockMetrics
```

### 🟡 **Enum Validation Errors**
**症状**: `422 Unprocessable Entity` - Pydantic validation error

**原因**: Backend model と schema の enum 定義不一致

**解決方法**:
```python
# backend/app/schemas/video.py
class VideoType(str, Enum):
    internal = "internal"
    external = "external"  # 後方互換性
    external_no_instruments = "external_no_instruments"
    external_with_instruments = "external_with_instruments"
```

### 🔵 **Module Not Found Errors**
**症状**: `Module not found: Can't resolve 'tailwind-merge'`

**解決方法**:
```bash
# 依存関係を再インストール
cd frontend
npm install tailwind-merge
# または全体的に再インストール
rm -rf node_modules package-lock.json
npm install
```

### 🟢 **WebSocket Connection Issues**
**症状**: 解析進捗が更新されない

**チェックリスト**:
1. Backend起動確認: `http://localhost:8000/docs`
2. WebSocket URL確認: `ws://localhost:8000/ws/analysis/{id}`
3. CORS設定確認: Backend `allow_origins=["*"]`
4. ブラウザコンソールでWebSocket接続確認

### 🟠 **File Upload Issues**
**症状**: ファイル選択ボタンが反応しない

**根本原因**: Button要素がspan/divに変更されている

**確認方法**:
```bash
# 要素の確認
cd frontend
grep -n "ファイルを選択" app/upload/page.tsx
```

**修正**:
```tsx
// ❌ Bad - クリックイベントが動作しない
<span className="...">ファイルを選択</span>

// ✅ Good - 正しいbutton要素
<button
  type="button"
  onClick={() => open()}
  className="..."
>
  ファイルを選択
</button>
```

### 🔴 **Python Version Issues**
**症状**: `ModuleNotFoundError: No module named 'mediapipe'`

**原因**: Python 3.13でMediaPipeが動作しない

**解決方法**:
```bash
# 必ずPython 3.11を使用
cd backend
./venv311/Scripts/python.exe --version  # 3.11.x確認
./venv311/Scripts/python.exe -m pip install mediapipe
```

### Common Error Patterns & Quick Fixes

| エラー | 原因 | 解決方法 |
|--------|------|----------|
| CORS error | Backend設定不備 | `allow_origins=["*"]` 設定 |
| Import errors | Python version | `./venv311/Scripts/python.exe` 使用 |
| WebSocket disconnects | サーバー未起動 | `start_both.bat` 実行 |
| Upload failures | サイズ制限 | 2GB以下の.mp4のみ |
| MediaPipe errors | Python 3.13使用 | Python 3.11に変更 |
| Detection failures | video_type誤り | external/internal確認 |
| Frontend 404 | ENV設定漏れ | `.env.local` 確認 |
| Async blocks | 同期処理 | `run_in_executor` 使用 |

## ⚠️ Critical UI Elements - DO NOT MODIFY
**These elements must remain as specific HTML tags for functionality:**
- Upload button: Must be `<button>`, not `<span>` or `<div>`
- Form inputs: Must be `<input>`, not styled divs
- Dropzone: Requires proper `useDropzone` hook configuration
- File input: Must have `type="file"` attribute
- Video player: Must be `<video>` element
- Canvas overlays: Must maintain proper z-index

**Testing critical UI elements:**
```bash
# Run regression tests after any UI changes
cd frontend
npx playwright test button-regression.spec.ts
npx playwright test upload.spec.ts
```

## 🔧 Debug Commands

```bash
# プロセス確認
netstat -ano | findstr :3000
netstat -ano | findstr :8000
tasklist | findstr node
tasklist | findstr python

# キャッシュクリア
cd frontend && rmdir /s /q .next
cd backend && del /s /q __pycache__

# ログ確認
cd backend && type uvicorn.log
cd frontend && npm run dev 2>&1 | tee dev.log

# データベース確認
cd backend
sqlite3 aimotion.db "SELECT * FROM videos;"
sqlite3 aimotion.db "SELECT * FROM analyses WHERE status='failed';"
sqlite3 aimotion.db "SELECT * FROM reference_videos;"
sqlite3 aimotion.db "SELECT * FROM comparisons;"

# API健全性チェック
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/docs
```

## Project-Specific Notes

### AI Surgical Motion Knowledge Transfer Library
This system analyzes surgical procedure videos to:
1. Track hand and instrument movements
2. Calculate motion efficiency metrics
3. Compare performance against reference videos
4. Provide feedback for skill improvement

### Video Processing Modes
- **external/external_no_instruments**: Hand-only tracking using MediaPipe
- **external_with_instruments/internal**: Instrument tracking using YOLOv8 + SAM
- Detection accuracy varies with surgical glove color (white gloves require enhanced detection)

### Model Files Required
- `backend/yolov8n.pt`: YOLOv8 nano model for instrument detection
- `backend/yolov8n-pose.pt`: YOLOv8 pose model
- `backend/sam_b.pt`: Segment Anything Model (base)