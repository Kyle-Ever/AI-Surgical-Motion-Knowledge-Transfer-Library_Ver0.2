# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## SuperClaude Framework Integration
This project uses the SuperClaude framework for enhanced AI capabilities.

**Framework Components** (loaded from ~/.claude/):
- Core: @FLAGS.md, @PRINCIPLES.md, @RULES.md, @RESEARCH_CONFIG.md
- Modes: @MODE_Brainstorming.md, @MODE_Business_Panel.md, @MODE_DeepResearch.md, @MODE_Introspection.md, @MODE_Orchestration.md, @MODE_Task_Management.md, @MODE_Token_Efficiency.md
- MCP Integration: @MCP_Context7.md, @MCP_Magic.md, @MCP_Morphllm.md, @MCP_Playwright.md, @MCP_Sequential.md, @MCP_Serena.md, @MCP_Tavily.md
- Business: @BUSINESS_PANEL_EXAMPLES.md, @BUSINESS_SYMBOLS.md

**Available Commands**: `/sc:task`, `/sc:analyze`, `/sc:troubleshoot`, `/sc:test`, `/sc:implement`, `/sc:research`, `/sc:design`, `/sc:document`, `/sc:improve`, `/sc:git`, `/sc:build`, `/sc:cleanup`, `/sc:help`

## Language Preference
**日本語で応答してください** - Please respond in Japanese unless explicitly requested otherwise.

## Project Type
**AI Surgical Motion Knowledge Transfer Library** - A web-based video analysis platform for surgical training that tracks hand and instrument movements, calculates motion metrics, and provides performance feedback.

## 📚 Project Documentation
**重要な設計ドキュメントを必ず参照してください**

### 必読ドキュメント（設計の基本）
- **[プロジェクト概要](docs/00_overview/00_project_overview.md)** - まずはここから。ドキュメント全体の構成と使い方
- **[アーキテクチャ設計](docs/01_architecture/01_architecture_design.md)** - システム設計とレイヤー責任。「このコードはどこに書くべき？」の答え
- **[データベース設計](docs/02_database/02_database_design.md)** - テーブル構造、命名規則、リレーション
- **[API設計](docs/03_api/03_api_design.md)** - RESTful API仕様、エラー形式、エンドポイント命名
- **[フロントエンド設計](docs/04_frontend/04_frontend_design.md)** - コンポーネント設計、状態管理、型定義
- **[開発環境セットアップ](docs/06_development/06_development_setup.md)** - 環境構築手順、トラブルシューティング

### 追加ドキュメント
- **[要求仕様書](docs/requirements-doc.md)** - システム要件と機能仕様
- **[AI処理フロー](docs/ai-processing-flow-doc.md)** - AI解析パイプラインの詳細
- **[UI/UX設計](docs/ui-ux-design-doc.md)** - ユーザーインターフェース設計
- **[基本設計](docs/basic-design-doc.md)** - システム基本設計書
- **[Playwright MCP テスト](docs/testing-ui-playwright-mcp.md)** - E2Eテスト戦略
- **[POST MORTEM: ファイルアップロードボタン](docs/POST_MORTEM_FILE_UPLOAD_BUTTON.md)** - 過去の重大バグと教訓

### 設計原則の適用例
```
新機能追加時:
1. アーキテクチャ設計 → レイヤー配置を確認
2. データベース設計 → 必要なテーブル変更
3. API設計 → エンドポイント規約に従う
4. フロントエンド設計 → コンポーネント配置

バグ修正時:
1. 該当レイヤーの設計書を確認
2. 設計原則に違反していないか確認
3. 修正後も原則を維持
```

## Critical Environment Requirements

### Python 3.11 MANDATORY
**MUST use Python 3.11** - Python 3.12+ breaks MediaPipe/OpenCV compatibility
- **DO NOT use Python 3.13**: Completely incompatible with MediaPipe/OpenCV
- Virtual environment: `backend\venv311\`
- Always use: `./venv311/Scripts/python.exe` for backend operations
- Check version: `./venv311/Scripts/python.exe --version` should show 3.11.x
- If venv311 doesn't exist: Run `start_backend_py311.bat` to auto-create with Python 3.11
- Required Python 3.11 installation path: `C:\Users\ajksk\AppData\Local\Programs\Python\Python311`

### CORS Configuration (Development)
**🚨 CRITICAL: Upload feature requires these settings to work**
- **Backend**: `allow_origins=["*"]` in `backend/app/main.py` (line 96)
  - This is ALREADY configured correctly in the current codebase
  - DO NOT change this setting unless deploying to production
- **Frontend**: `.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`
- **Backend** `.env`: `BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost:8000"]`
- **Common Issue**: If uploads fail with CORS errors, verify these settings first

### Environment Variables
**Backend (.env)**
```
DATABASE_URL=sqlite:///./aimotion.db
UPLOAD_DIR=data/uploads
MAX_UPLOAD_SIZE=1073741824  # 1GB in bytes
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
# Both servers (recommended) - Windows
start_both.bat      # Kills existing processes, starts both servers

# Backend only - Windows
start_backend_py311.bat  # Auto-creates venv311, installs deps, starts server
# OR manually:
cd backend && ./venv311/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend
npm install         # First time only
npm run dev         # Start development server
```

### Testing
```bash
# Frontend E2E (Playwright)
cd frontend
npm run test              # Headless mode - all tests
npm run test:headed       # With browser window
npm run test:ui           # Interactive UI mode
npm run test:debug        # Debug mode with Playwright Inspector
npm run test:report       # Show last test results HTML report
npx playwright test upload.spec.ts  # Single file
npx playwright test --grep "upload"  # Tests matching pattern
npx playwright test tests/e2e-v2-upload.spec.ts  # Specific test file

# Frontend lint & type check
npm run lint              # ESLint check
npm run build            # Full build with type check
npx tsc --noEmit         # TypeScript check only

# Backend API tests
cd backend
./venv311/Scripts/python.exe test_api.py           # Basic API functionality
./venv311/Scripts/python.exe test_mediapipe_integration.py  # MediaPipe detection
./venv311/Scripts/python.exe tests/test_integration.py      # Full integration
./venv311/Scripts/python.exe test_analysis_direct.py        # Analysis pipeline
./venv311/Scripts/python.exe test_sam_direct.py             # SAM tracker

# Database operations
./venv311/Scripts/python.exe check_db.py           # View database contents
./venv311/Scripts/python.exe check_analysis_data.py # Check analysis results
sqlite3 aimotion.db ".tables"                      # Direct SQLite access
```

## High-Level Architecture

### Processing Pipeline
1. **Upload**: Video → `backend/data/uploads/` (1GB max, .mp4 only)
2. **Analysis**: Frame extraction → AI detection → Score calculation
3. **Detection Types**:
   - `external`: MediaPipe skeleton detection (hand tracking)
   - `internal`: YOLOv8 instrument detection + SAM tracker
4. **Real-time Updates**: WebSocket progress at `/ws/analysis/{analysis_id}`

### Key API Endpoints
- `POST /api/v1/videos/upload` - Upload video (1GB limit)
- `POST /api/v1/analysis/{video_id}/analyze` - Start analysis
- `GET /api/v1/analysis/{analysis_id}/status` - Check progress
- `GET /api/v1/videos` - List all videos
- `GET /api/v1/analysis/{analysis_id}` - Get analysis results
- `POST /api/v1/scoring/compare` - Compare with reference
- `GET /api/v1/library/references` - Get reference videos
- `POST /api/v1/instrument-tracking/{video_id}/track` - Start instrument tracking
- `WS /ws/analysis/{analysis_id}` - Real-time progress

### Core Services Architecture
- **AnalysisService** (`backend/app/services/analysis_service_v2.py`): Orchestrates processing pipeline
- **ScoringService** (`backend/app/services/scoring_service.py`): Calculates motion metrics
- **InstrumentTrackingService** (`backend/app/services/instrument_tracking_service.py`): Instrument detection/tracking
- **MetricsCalculator** (`backend/app/services/metrics_calculator.py`): Computes motion metrics
- **WebSocket Manager** (`backend/app/core/websocket.py`): Real-time client connections
- **AI Processors** (`backend/app/ai_engine/processors/`):
  - `skeleton_detector.py`: MediaPipe hand/body tracking
  - `sam_tracker.py`: Segment Anything Model for instruments
  - `enhanced_hand_detector.py`: Improved detection accuracy
- **Frontend State**: Zustand for global state, custom hooks for WebSocket

### Database Schema
SQLite at `backend/aimotion.db` with SQLAlchemy ORM:
- `videos`: Video metadata and upload info
- `analyses`: Analysis sessions and results
- `reference_videos`: Gold standard references
- `comparisons`: Score comparisons

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
import { create } from 'zustand'

const useVideoStore = create((set) => ({
  videos: [],
  setVideos: (videos) => set({ videos }),
  addVideo: (video) => set((state) => ({
    videos: [...state.videos, video]
  }))
}))
```

## Key Constraints & Technology Stack

### Backend
- **Python**: 3.11 ONLY (3.12+ breaks MediaPipe/OpenCV)
- **Framework**: FastAPI with async/await, SQLAlchemy ORM
- **AI Libraries**: MediaPipe (hand tracking), YOLOv8 (instrument detection), SAM (segmentation)
- **Critical Dependencies**: `numpy<2`, `ultralytics==8.0.200`, `mediapipe>=0.10.0`
- **Database**: SQLite with migrations via Alembic

### Frontend
- **Framework**: Next.js 15.5.2 with App Router
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS v4
- **State Management**: Zustand v5.0.8
- **Charts**: Chart.js v4.5.0, recharts v3.2.1
- **3D Rendering**: Three.js with @react-three/fiber
- **HTTP Client**: Axios v1.11.0

### Infrastructure
- **Ports**: Backend 8000, Frontend 3000
- **File Limits**: 1GB max upload, .mp4 format only
- **WebSocket**: Real-time progress updates during analysis
- **Testing**: Playwright v1.55.0 (expects Japanese UI text)

## Git Commit Guidelines
**Large File Exclusion**
- Exclude: `*.pt` (models 100MB+), `*.mp4`, `*.jpg`, `*.png`
- Already in `.gitignore`
- Commit with: `git add --all -- . ":!*.pt" ":!*.mp4" ":!*.jpg" ":!*.png"`
- GitHub limit: 100MB per file

## 🚨 Critical Troubleshooting

### Process Management (Windows)
```bash
# Find processes on ports
netstat -ano | findstr :3000    # Frontend
netstat -ano | findstr :8000    # Backend

# Kill specific process
taskkill /PID <process_id> /F

# Kill all Node.js/Python
taskkill /F /IM node.exe
taskkill /F /IM python.exe

# Clear frontend cache after code changes
cd frontend && rmdir /s /q .next
npm run dev
```

### Common Errors
| エラー | 解決方法 |
|--------|----------|
| CORS error | Backend: `allow_origins=["*"]` in `app/main.py` line 96 |
| Import errors | Use `./venv311/Scripts/python.exe` |
| WebSocket disconnects | Run `start_both.bat` to restart both servers |
| WebSocket connection refused | Backend not running or port 8000 blocked |
| Upload failures | 1GB max, .mp4 only |
| MediaPipe errors | Switch to Python 3.11 (NOT 3.12 or 3.13) |
| Button not clickable | Must be `<button>`, not `<span>` |
| `.next` cache issues | Delete `.next` folder: `rmdir /s /q .next` |

### Critical UI Elements - DO NOT MODIFY
- Upload button: Must be `<button>`, not `<span>` or `<div>`
- Form inputs: Must be `<input>`, not styled divs
- Video player: Must be `<video>` element
- Test after changes: `npx playwright test button-regression.spec.ts`

## Debug Commands
```bash
# Process check
netstat -ano | findstr :3000
tasklist | findstr node

# Database check
cd backend
sqlite3 aimotion.db "SELECT * FROM videos;"
sqlite3 aimotion.db "SELECT * FROM analyses WHERE status='failed';"

# API health
curl http://localhost:8000/api/v1/health
```

## Project-Specific Notes

### AI Surgical Motion Knowledge Transfer Library
Analyzes surgical procedure videos to:
1. Track hand and instrument movements
2. Calculate motion efficiency metrics
3. Compare performance against references
4. Provide feedback for skill improvement

### Video Processing Modes
- **external/external_no_instruments**: Hand tracking (MediaPipe)
- **external_with_instruments/internal**: Instrument tracking (YOLOv8 + SAM)
- White surgical gloves require enhanced detection

### Required Model Files (Auto-downloaded if missing)
- `backend/yolov8n.pt`: Instrument detection (~6MB)
- `backend/yolov8n-pose.pt`: Pose model (~6MB)
- `backend/sam_b.pt`: Segment Anything Model (~375MB)

### File Structure
```
backend/
  app/
    api/routes/         # API endpoint handlers
    ai_engine/          # AI processing (MediaPipe, YOLOv8, SAM)
      processors/       # skeleton_detector.py, sam_tracker.py
    services/           # Business logic (analysis, scoring, instrument tracking)
    models/             # SQLAlchemy ORM models
    schemas/            # Pydantic schemas for validation
    core/               # Config, WebSocket, error handlers
  venv311/              # Python 3.11 virtual environment (REQUIRED)
  data/uploads/         # Video upload directory
  aimotion.db           # SQLite database

frontend/
  app/                  # Next.js App Router pages
  components/           # React components
  lib/                  # Utilities and API client
  hooks/                # Custom React hooks (useScoring, useAnalysisAPI, etc.)
  store/                # Zustand state management
  tests/                # Playwright E2E tests

docs/                   # Design documentation (Japanese)
  00_overview/          # Project overview
  01_architecture/      # Architecture design
  02_database/          # Database schema
  03_api/               # API specifications
  04_frontend/          # Frontend design
  06_development/       # Development setup
```

## 🛡️ データパイプライン品質保証

### Fail Fast原則（必須）
**データの存在を仮定せず、早期に大きく失敗する**

❌ **悪い例（サイレント失敗）**:
```python
frame_idx = result.get('frame_index', 0)  # デフォルト値で問題を隠蔽
```

✅ **良い例（Fail Fast）**:
```python
if 'frame_index' not in result:
    logger.error(f"Missing required field: {result}")
    raise ValueError("frame_index is required")
frame_idx = result['frame_index']
```

### 必須バリデーションパターン

#### パターン1: 上流依存の検証
新しいコードが既存関数のデータに依存する場合:
```python
# 1. まず上流の出力を確認
upstream_output = existing_function()
logger.debug(f"Upstream output keys: {upstream_output.keys()}")

# 2. 必須フィールドを検証
required_fields = ['field1', 'field2']
missing = [f for f in required_fields if f not in upstream_output]
if missing:
    raise ValueError(f"Missing required fields: {missing}")
```

#### パターン2: データ構造の妥当性検証
```python
# フレームデータの例
if len(frames_dict) < expected_minimum:
    raise ValueError(f"Insufficient frames: {len(frames_dict)} < {expected_minimum}")

for frame_num, hands in frames_dict.items():
    if len(hands) > 10:  # 異常な手の数
        logger.warning(f"Frame {frame_num} has {len(hands)} hands (expected 1-4)")
```

### 3層テスト戦略（必須）

#### レベル1: ユニットテスト
- **いつ**: 関数を新規作成・修正したとき
- **何を**: エッジケース、異常系、欠損データ
- **場所**: `tests/unit/test_<module_name>.py`

```python
# 例: frame_index欠損時のエラーハンドリング検証
def test_format_without_frame_index_fails():
    raw_results = [{'detected': True, 'hands': [...]}]  # frame_index なし
    with pytest.raises(ValueError) as exc_info:
        service._format_skeleton_data(raw_results)
    assert "frame_index" in str(exc_info.value)
```

#### レベル2: 統合テスト
- **いつ**: データパイプラインを変更したとき
- **何を**: **新規データで新コードパスを実行**
- **重要**: 既存データのテストだけでは不十分！

```python
# ❌ 悪い例: 古いデータをテスト
def test_analysis():
    old_analysis_id = "existing-id"
    verify(old_analysis_id)  # 新コードを実行していない

# ✅ 良い例: 新規解析を実行
def test_analysis():
    video_id = upload_test_video()
    analysis_id = start_new_analysis(video_id)  # 新コード実行
    verify(analysis_id)
```

#### レベル3: E2Eテスト
- **いつ**: フロントエンド連携があるとき
- **何を**: データ構造の妥当性も検証

```typescript
// ❌ 不十分: キーの存在のみ
expect(data).toHaveProperty('skeleton_data')

// ✅ 完全: 構造の妥当性も
expect(data.skeleton_data.length).toBeGreaterThan(100)
expect(data.skeleton_data[0].hands.length).toBeLessThan(5)
```

### 新規コードパス検証義務
**データ処理ロジックを変更した場合、必ず新規データで検証すること**

チェックリスト:
- [ ] ユニットテストで異常系・欠損データをカバー
- [ ] 統合テストで新規解析を実行（既存データのみ✗）
- [ ] E2Eテストでデータ構造の妥当性を検証
- [ ] 実際のUIで動作確認

### 過去の重大バグ
- [POST_MORTEM: ファイルアップロードボタン](docs/POST_MORTEM_FILE_UPLOAD_BUTTON.md)
- [POST_MORTEM: 骨格検出フレームインデックス](docs/POST_MORTEM_SKELETON_FRAME_INDEX.md)

---

## 🔄 サーバー再起動検証プロトコル

### バックエンドコード変更時の検証手順

**問題**: Uvicornの `--reload` が時々ファイル変更を検知しない

**解決手順**:

1. **コード変更後の必須確認**:
```bash
# バックエンドサーバーのログを確認
# "Reloading..." または "Application startup complete" が表示されるか確認
```

2. **リロードが検知されない場合**:
```bash
# 専用スクリプトで明示的に再起動
./restart_backend.bat
```

3. **再起動後の検証**:
```bash
# verify_fix.py で最新データをチェック
backend/venv311/Scripts/python.exe verify_fix.py

# または手動でAPIヘルスチェック
curl http://localhost:8000/api/v1/health
```

4. **新規解析を実行して検証**:
```
- フロントエンドから新しい動画をアップロード
- 解析を実行
- データベースで結果を確認
- UIで表示を確認
```

### 検証チェックリスト

コード変更後、必ず以下を確認:

- [ ] バックエンドログに "Reloading..." が表示された
- [ ] 新規解析を実行（既存データのテストは不十分）
- [ ] データベースで新形式データを確認
- [ ] UIで期待通りの表示を確認
- [ ] ブラウザのコンソールにエラーがないことを確認

### トラブルシューティング

| 症状 | 原因 | 解決方法 |
|------|------|----------|
| 変更が反映されない | WatchFilesが検知していない | `restart_backend.bat` 実行 |
| "古いコード"が動作 | フロントエンドキャッシュ | `.next` フォルダを削除 |
| 新データでもバグ再現 | 変更が保存されていない | ファイル保存を確認、エディタをチェック |

---

## 🚨 よくある落とし穴

### 落とし穴1: デフォルト値による隠蔽
```python
# ❌ 問題を隠す
value = data.get('key', default_value)

# ✅ 問題を表面化
if 'key' not in data:
    raise ValueError("Required key missing")
value = data['key']
```

### 落とし穴2: 古いデータでのテスト
```python
# ❌ 新コードをテストしていない
existing_analysis = get_analysis("old-id")
assert existing_analysis['status'] == 'completed'

# ✅ 新コードを実行
new_analysis_id = create_new_analysis()
verify_new_code_path(new_analysis_id)
```

### 落とし穴3: フォーマットのみの検証
```typescript
// ❌ 構造が壊れていても気づかない
expect(data).toHaveProperty('results')

// ✅ データの妥当性も確認
expect(data.results.length).toBeGreaterThan(0)
expect(data.results[0]).toMatchObject({
  id: expect.any(String),
  value: expect.any(Number)
})
```