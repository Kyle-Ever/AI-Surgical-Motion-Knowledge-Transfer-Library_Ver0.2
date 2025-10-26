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
- Virtual environment: `backend_experimental\venv311\`
- Always use: `./venv311/Scripts/python.exe` for backend operations
- Check version: `./venv311/Scripts/python.exe --version` should show 3.11.x
- If venv311 doesn't exist: Run `start_backend_experimental.bat` to auto-create with Python 3.11
- Required Python 3.11 installation path: `C:\Users\ajksk\AppData\Local\Programs\Python\Python311`

### CORS Configuration
**🚨 CRITICAL: Upload feature requires these settings to work**

**ngrokデュアルドメイン構成（本番・展示会用）**:
- **Backend CORS** (`backend_experimental/app/main.py`):
  ```python
  allow_origins=[
      "https://mindmotionai.ngrok-free.dev",  # フロントエンド
      "https://dev.mindmotionai.ngrok-free.dev",  # バックエンド
      "http://localhost:3000",  # ローカル開発用
      "http://localhost:8001",  # ローカルバックエンド
  ]
  ```
- **Frontend** (`.env.local`):
  ```bash
  NEXT_PUBLIC_API_URL=https://dev.mindmotionai.ngrok-free.dev/api/v1
  NEXT_PUBLIC_WS_URL=wss://dev.mindmotionai.ngrok-free.dev/ws
  ```
- **起動方法**: `start_dual_ngrok.bat` を実行
- **Common Issue**: If uploads fail with CORS errors, verify these settings first

### Environment Variables
**Backend Experimental (.env)**
```
DATABASE_URL=sqlite:///./aimotion.db
UPLOAD_DIR=data/uploads
MAX_UPLOAD_SIZE=1073741824  # 1GB in bytes
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost:8001"]
PORT=8001  # Experimental backend port
FRAME_EXTRACTION_FPS=15  # Target FPS for frame extraction
USE_SAM2_VIDEO_API=true  # Enable SAM2 Video API
```

**Frontend (.env.local)**
```bash
# ngrokデュアルドメイン構成
NEXT_PUBLIC_API_URL=https://dev.mindmotionai.ngrok-free.dev/api/v1
NEXT_PUBLIC_WS_URL=wss://dev.mindmotionai.ngrok-free.dev/ws

# ローカル開発時は以下に変更:
# NEXT_PUBLIC_API_URL=/api/v1  # Next.js APIプロキシ経由
# NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

## Commands

### Quick Start
**📖 詳細は [START_HERE.md](START_HERE.md) を参照**

```bash
# 🌐 推奨: ngrokデュアルドメイン構成（展示会・本番用）
start_dual_ngrok.bat
# → フロントエンド: https://mindmotionai.ngrok-free.dev
# → バックエンド: https://dev.mindmotionai.ngrok-free.dev

# 🟢 ローカル開発: フロントエンド + Experimentalバックエンド (Port 3000 + 8001)
start_both_experimental.bat

# 🔵 Experimentalバックエンドのみ (Port 8001)
start_backend_experimental.bat

# 🔴 全サーバー停止（通常のトラブル時）
kill_all_servers.bat

# ⚠️ 完全終了（慎重に使用、確認プロンプト付き）
kill_all_processes.bat

# Frontend only (手動起動が必要な場合)
cd frontend
npm install         # First time only
npm run dev         # Start development server (Port 3000)
```

**重要:**
- **ngrok $20プラン**: デュアルドメイン構成でフロントエンド・バックエンド両方を公開
- **ローカル開発**: `start_both_experimental.bat` でAPIプロキシ経由
- Experimentalバックエンド (Port 8001) を使用
- Python 3.11必須（`backend_experimental/venv311/`）

**バッチファイルの使い分け:**
- `kill_all_servers.bat`: 通常のトラブル時に使用（確認なしで即座に実行）
- `kill_all_processes.bat`: より確実な終了が必要な場合（実行前に確認プロンプト表示）

### Testing
```bash
# Frontend E2E (Playwright) - ALWAYS cd to frontend first
cd frontend
npm run test              # Headless mode - all tests
npm run test:headed       # With browser window
npm run test:ui           # Interactive UI mode
npm run test:debug        # Debug mode with Playwright Inspector
npm run test:report       # Show last test results HTML report

# Single test file execution
npx playwright test tests/e2e-v2-upload.spec.ts
npx playwright test tests/experimental-e2e.spec.ts
npx playwright test tests/gaze-dashboard-test.spec.ts

# Pattern matching
npx playwright test --grep "upload"
npx playwright test --grep "dashboard"

# Frontend lint & type check
npm run lint              # ESLint check
npm run build            # Full build with type check
npx tsc --noEmit         # TypeScript check only

# Backend API tests (Experimental) - ALWAYS cd to backend_experimental first
cd backend_experimental
./venv311/Scripts/python.exe test_api.py           # Basic API functionality
./venv311/Scripts/python.exe tests/unit/test_frame_extraction_service.py  # Frame extraction
./venv311/Scripts/python.exe tests/integration/test_analysis_pipeline_25fps.py  # 25fps pipeline

# Database operations - Execute from backend_experimental directory
./venv311/Scripts/python.exe check_db.py           # View database contents
./venv311/Scripts/python.exe check_analysis_data.py # Check analysis results
./venv311/Scripts/python.exe verify_fix.py         # Verify latest analysis data structure

# Direct SQLite access
sqlite3 aimotion.db ".tables"
sqlite3 aimotion.db "SELECT id, status, created_at FROM analyses ORDER BY created_at DESC LIMIT 5;"
sqlite3 aimotion.db "SELECT COUNT(*) FROM videos;"
```

## High-Level Architecture

### Processing Pipeline
1. **Upload**: Video → `backend_experimental/data/uploads/` (1GB max, .mp4 only)
2. **Frame Extraction**: Target 15 FPS with precise timestamp calculation
3. **AI Detection**:
   - **Skeleton**: MediaPipe hand/body tracking
   - **Instruments**: YOLOv8 detection + SAM2 Video API tracking
   - **Gaze**: DeepGaze III eye gaze analysis (experimental)
4. **Score Calculation**: Motion efficiency metrics
5. **Real-time Updates**: WebSocket progress at `/ws/analysis/{analysis_id}`

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
- **AnalysisService** (`backend_experimental/app/services/analysis_service_v2.py`): Orchestrates processing pipeline
- **ScoringService** (`backend_experimental/app/services/scoring_service.py`): Calculates motion metrics
- **InstrumentTrackingService** (`backend_experimental/app/services/instrument_tracking_service.py`): Instrument detection/tracking
- **FrameExtractionService** (`backend_experimental/app/services/frame_extraction_service.py`): Video frame extraction with precise FPS handling
- **MetricsCalculator** (`backend_experimental/app/services/metrics_calculator.py`): Computes motion metrics
- **WebSocket Manager** (`backend_experimental/app/core/websocket.py`): Real-time client connections
- **AI Processors** (`backend_experimental/app/ai_engine/processors/`):
  - `skeleton_detector.py`: MediaPipe hand/body tracking
  - `sam_tracker.py`: Segment Anything Model for instruments
  - `sam2_tracker_video.py`: SAM2 Video API for instrument tracking
  - `gaze_analyzer.py`: DeepGaze III for eye gaze analysis
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
  - Required path: `C:\Users\ajksk\AppData\Local\Programs\Python\Python311`
  - Virtual env: `backend_experimental\venv311\`
- **Framework**: FastAPI with async/await, SQLAlchemy ORM
- **AI Libraries**:
  - MediaPipe >=0.10.0 (hand tracking)
  - YOLOv8 (ultralytics==8.0.200, instrument detection)
  - SAM & SAM2 (segmentation & video tracking)
  - DeepGaze III (eye gaze analysis)
  - PyTorch with CUDA 11.8 (RTX 3060 GPU support)
- **Critical Dependencies**: `numpy<2`, `ultralytics==8.0.200`, `mediapipe>=0.10.0`
- **Database**: SQLite with migrations via Alembic
- **Important**: Always use `./venv311/Scripts/python.exe` for backend operations

### Frontend
- **Framework**: Next.js 15.5.2 with App Router
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS v4
- **State Management**: Zustand v5.0.8
- **Charts**: Chart.js v4.5.0, recharts v3.2.1
- **3D Rendering**: Three.js with @react-three/fiber
- **HTTP Client**: Axios v1.11.0
- **Testing**: Playwright v1.55.0 (expects Japanese UI text)

### Infrastructure
- **Ports**: Backend 8001 (Experimental), Frontend 3000
- **File Limits**: 1GB max upload, .mp4 format only
- **WebSocket**: Real-time progress updates during analysis
- **OS**: Windows 10/11 (batch files use Windows commands)
- **Note**: Legacy backend (Port 8000) is deprecated

### Common Development Paths
```bash
# Working directories
cd frontend                    # Frontend development
cd backend_experimental        # Backend development

# Python executable
./venv311/Scripts/python.exe   # Backend Python (from backend_experimental/)

# Database
backend_experimental/aimotion.db  # SQLite database file

# Video uploads
backend_experimental/data/uploads/  # Video storage directory
```

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
netstat -ano | findstr :8001    # Experimental Backend

# Kill specific process
taskkill /PID <process_id> /F

# Kill all servers (recommended for normal issues)
kill_all_servers.bat

# Complete shutdown (use if kill_all_servers.bat doesn't work)
kill_all_processes.bat

# Manual process kill (use with extreme caution - affects ALL Node.js/Python processes)
taskkill /F /IM node.exe
taskkill /F /IM python.exe

# Clear frontend cache after code changes
cd frontend && rmdir /s /q .next
npm run dev

# Windows-specific directory operations
# ❌ Wrong (Linux): rm -rf .next
# ✅ Correct (Windows): rmdir /s /q .next
```

### Common Errors
| エラー | 解決方法 |
|--------|----------|
| CORS error | Backend: `allow_origins=["*"]` in `backend_experimental/app/main.py` |
| Import errors | Use `./venv311/Scripts/python.exe` in `backend_experimental/` |
| WebSocket disconnects | Run `start_both_experimental.bat` to restart both servers |
| WebSocket connection refused | Backend not running or port 8001 blocked |
| Upload failures | 1GB max, .mp4 only |
| MediaPipe errors | Switch to Python 3.11 (NOT 3.12 or 3.13) |
| Button not clickable | Must be `<button>`, not `<span>` |
| `.next` cache issues | Delete `.next` folder: `rmdir /s /q .next` |

### Critical UI Elements - DO NOT MODIFY
- Upload button: Must be `<button>`, not `<span>` or `<div>`
- Form inputs: Must be `<input>`, not styled divs
- Video player: Must be `<video>` element
- Test after changes: `npx playwright test button-regression.spec.ts`

## 🎨 視線解析ダッシュボード - 独自デザイン保護

### 重要ファイル
- **GazeDashboardClient.tsx**: ビデオ同期Canvas + Chart.js グラフ（879行）
- **バックアップ**: GazeDashboardClient.custom.tsx
- **ドキュメント**: [POST_MORTEM_GAZE_DASHBOARD_CUSTOM_DESIGN.md](docs/POST_MORTEM_GAZE_DASHBOARD_CUSTOM_DESIGN.md)

### 独自デザインの主要機能
1. **ビデオ同期Canvas表示**（2分割）
   - 左Canvas: ゲーズプロットオーバーレイ（緑丸 + 白線）
   - 右Canvas: リアルタイムヒートマップ（半透明カラーマップ）
2. **Chart.js 時系列グラフ**（X/Y座標の動的表示）
3. **リアルタイムヒートマップ**（Gaussian blur、±1秒時間窓）
4. **用語統一**（「固視点」→「ゲーズプロット」）

### 変更時の必須手順
```bash
# 1. バックアップ作成
cp frontend/components/GazeDashboardClient.tsx \
   frontend/components/GazeDashboardClient.backup_$(date +%Y%m%d_%H%M).tsx

# 2. 変更実施

# 3. 動作確認
npm run dev
# http://localhost:3000/dashboard/fcc9c5db-e82d-4cf8-83e0-55af633e397f

# 4. Gitコミット
git add frontend/components/GazeDashboardClient.tsx
git commit -m "feat: 視線解析ダッシュボード改善 - [変更内容]"
```

### 🚨 禁止事項（独自デザインが消える）
- ❌ `git restore frontend/components/GazeDashboardClient.tsx`
- ❌ `saliency_map` ベースの実装に戻す
- ❌ 「固視点」という用語を使用
- ❌ Canvas解像度を1920x1080に戻す

### 緊急復旧手順
```bash
# 独自デザインが消えた場合
cp frontend/components/GazeDashboardClient.custom.tsx \
   frontend/components/GazeDashboardClient.tsx

# または
cp docs/code_snapshots/GazeDashboardClient_custom_design_YYYYMMDD.tsx \
   frontend/components/GazeDashboardClient.tsx

# キャッシュクリアして再起動
cd frontend && rm -rf .next && npm run dev
```

### 🔬 Debugging Protocol (MANDATORY)
**全てのトラブルシューティングで以下3つの質問に回答すること**

詳細: [docs/DEBUGGING_PROTOCOL.md](docs/DEBUGGING_PROTOCOL.md)

#### 必須回答項目
1. **今のところ修正してもほかの部分には影響ないか？**
   - 修正範囲の明確化
   - 依存関係の確認
   - 副作用の評価

2. **なんでこういう作りになっているのか？**
   - 設計意図の調査
   - Git履歴の確認
   - コメントやドキュメントの参照

3. **この部分にも問題を起こしていそうな場所はないか？徹底的に検証して**
   - 類似パターンの検索
   - 同じロジックの他の箇所
   - 同じ開発者の他のコード

#### 調査テンプレート
```markdown
## 問題概要
[問題の簡潔な説明]

## 影響分析（質問1）
### 修正範囲
- 変更ファイル: [file:line]
- 変更内容: [具体的な変更]

### 依存関係
- 呼び出し元: [関数/クラス]
- 呼び出し先: [関数/クラス]
- データフロー: [入力 → 処理 → 出力]

### 副作用評価
- [ ] 他の機能への影響なし
- [ ] テストカバレッジ確認
- [ ] E2Eテストで検証

## 背景調査（質問2）
### 設計意図
- コメント: [該当箇所のコメント]
- Git履歴: [commit hash, author, date]
- 関連Issue/PR: [リンク]

### なぜこの実装？
[推測される理由]

## 類似問題検証（質問3）
### 検索パターン
```bash
# 同じパターンを検索
grep -r "similar_pattern" backend/
```

### 発見した類似箇所
- [file:line] - [説明]
- [file:line] - [説明]

### 修正必要箇所
- [ ] [file:line] - [理由]
- [ ] [file:line] - [理由]
```

## Debug Commands
```bash
# Process check
netstat -ano | findstr :3000
netstat -ano | findstr :8001
tasklist | findstr node
tasklist | findstr python

# Database check (from backend_experimental directory)
cd backend_experimental
sqlite3 aimotion.db "SELECT * FROM videos;"
sqlite3 aimotion.db "SELECT * FROM analyses WHERE status='failed';"
sqlite3 aimotion.db "SELECT id, status, created_at FROM analyses ORDER BY created_at DESC LIMIT 5;"

# Python scripts for debugging (from backend_experimental directory)
./venv311/Scripts/python.exe check_db.py
./venv311/Scripts/python.exe check_analysis_data.py
./venv311/Scripts/python.exe verify_fix.py

# API health check
curl http://localhost:8001/api/v1/health
curl http://localhost:8001/docs  # Interactive API documentation

# Frontend debugging
cd frontend
npm run build  # Check for TypeScript/build errors
npx tsc --noEmit  # TypeScript check only
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

### AI Processing Pipeline Architecture
**Key Services Interaction**:
1. `AnalysisService._run_skeleton_detection()` → calls `SkeletonDetector.detect_batch()`
2. `SkeletonDetector.detect_batch()` → returns list of detection results with `frame_index`
3. `AnalysisService._format_skeleton_data()` → transforms raw results to frontend format
4. **Critical**: Each result MUST contain `frame_index` field (Fail Fast validation enforced)

**Data Flow**:
```
Video Upload → Frame Extraction → Batch Detection → Format Conversion → Database Storage → WebSocket Broadcast → Frontend Display
```

### Required Model Files (Auto-downloaded if missing)
- `backend_experimental/yolov8n.pt`: Instrument detection (~6MB)
- `backend_experimental/yolov8n-pose.pt`: Pose model (~6MB)
- `backend_experimental/sam_b.pt`: Segment Anything Model (~375MB)
- **SAM2**: Downloaded automatically on first use
- **DeepGaze III**: Installed via Git repository (視線解析用)

### File Structure
```
AI Surgical Motion Knowledge Transfer Library_Ver0.2/
├── CLAUDE.md                                # This file - project guide
├── START_HERE.md                            # Quick start guide
├── start_both_experimental.bat              # 🟢 Main startup script
├── start_both_experimental_with_ngrok.bat   # 🌐 Public demo startup
├── start_backend_experimental.bat           # Backend only
├── kill_all_servers.bat                     # 🔴 Quick shutdown
├── kill_all_processes.bat                   # ⚠️ Complete shutdown
│
├── backend_experimental/                    # CURRENT: Experimental backend (Port 8001)
│   ├── app/
│   │   ├── api/routes/                     # API endpoint handlers
│   │   │   ├── analysis.py                 # Analysis endpoints
│   │   │   ├── videos.py                   # Video upload/management
│   │   │   └── scoring.py                  # Scoring endpoints
│   │   ├── ai_engine/processors/           # AI processing modules
│   │   │   ├── skeleton_detector.py        # MediaPipe hand/body tracking
│   │   │   ├── sam_tracker.py              # SAM segmentation
│   │   │   ├── sam2_tracker_video.py       # SAM2 video API tracking
│   │   │   ├── gaze_analyzer.py            # DeepGaze III eye gaze
│   │   │   └── enhanced_hand_detector.py   # Improved detection
│   │   ├── services/                       # Business logic layer
│   │   │   ├── analysis_service_v2.py      # Main orchestration
│   │   │   ├── frame_extraction_service.py # Video frame extraction
│   │   │   ├── scoring_service.py          # Motion metrics
│   │   │   └── instrument_tracking_service.py
│   │   ├── models/                         # SQLAlchemy ORM models
│   │   ├── schemas/                        # Pydantic validation schemas
│   │   └── core/                           # Core infrastructure
│   │       ├── config.py                   # Configuration
│   │       └── websocket.py                # WebSocket manager
│   ├── venv311/                            # Python 3.11 venv (REQUIRED)
│   ├── data/uploads/                       # Video storage (created at runtime)
│   ├── aimotion.db                         # SQLite database
│   ├── requirements.txt                    # Python dependencies
│   ├── check_db.py                         # Database inspection tool
│   └── verify_fix.py                       # Data validation tool
│
├── frontend/                               # Next.js App Router (Port 3000)
│   ├── app/                                # Next.js pages
│   │   ├── page.tsx                        # Home page
│   │   ├── upload/page.tsx                 # Upload page
│   │   ├── analysis/[id]/                  # Analysis detail
│   │   ├── dashboard/[id]/                 # Dashboard view
│   │   └── library/page.tsx                # Video library
│   ├── components/                         # React components
│   │   ├── GazeDashboardClient.tsx         # 🎨 Custom gaze dashboard
│   │   ├── GazeDashboardClient.custom.tsx  # Backup of custom design
│   │   └── ...
│   ├── lib/                                # Utilities
│   │   └── api.ts                          # API client
│   ├── hooks/                              # Custom React hooks
│   │   ├── useApi.ts                       # API hook
│   │   ├── useAnalysisAPI.ts               # Analysis operations
│   │   └── useScoring.ts                   # Scoring operations
│   ├── store/                              # Zustand state management
│   ├── tests/                              # Playwright E2E tests
│   │   ├── e2e-v2-upload.spec.ts
│   │   ├── experimental-e2e.spec.ts
│   │   └── gaze-dashboard-test.spec.ts
│   ├── package.json                        # Node.js dependencies
│   ├── playwright.config.ts                # Playwright configuration
│   └── .env.local                          # Frontend environment variables
│
├── docs/                                   # Design documentation (Japanese)
│   ├── 00_overview/
│   │   └── 00_project_overview.md          # 📚 START HERE for architecture
│   ├── 01_architecture/
│   │   └── 01_architecture_design.md       # System architecture
│   ├── 02_database/
│   │   └── 02_database_design.md           # Database schema
│   ├── 03_api/
│   │   └── 03_api_design.md                # API specifications
│   ├── 04_frontend/
│   │   └── 04_frontend_design.md           # Frontend design patterns
│   ├── 06_development/
│   │   └── 06_development_setup.md         # Development setup guide
│   ├── POST_MORTEM_FILE_UPLOAD_BUTTON.md   # Bug postmortem
│   ├── POST_MORTEM_SKELETON_FRAME_INDEX.md # Data pipeline bug
│   └── DEBUGGING_PROTOCOL.md               # Mandatory debugging steps
│
└── claudedocs/                             # Claude-generated reports
    ├── SAM2_INSTRUMENT_DETECTION_FIX.md
    └── ... (technical reports and analyses)
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
# バックエンドを停止（Ctrl+C）して再起動
start_backend_experimental.bat
```

3. **再起動後の検証**:
```bash
# verify_fix.py で最新データをチェック
backend_experimental/venv311/Scripts/python.exe verify_fix.py

# または手動でAPIヘルスチェック
curl http://localhost:8001/api/v1/health
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
| 変更が反映されない | WatchFilesが検知していない | バックエンド停止（Ctrl+C）→ `start_backend_experimental.bat` |
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