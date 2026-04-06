# CLAUDE.md

## Language / 言語
**日本語で応答してください** - Always respond in Japanese unless explicitly requested otherwise.

## Project Overview
**MindMotionAI** - 手術手技動画を解析し、手・器具の動きを追跡してモーションメトリクスを計算、パフォーマンスフィードバックを提供するWebプラットフォーム。

## Architecture
```
Frontend (Next.js 15, Port 3000)  →  Backend (FastAPI, Port 8001)  →  SQLite (aimotion.db)
                                          ↓
                                    AI Pipeline: MediaPipe(骨格) + YOLOv8(器具検出) + SAM2(追跡) + DeepGaze III(視線)
```

## Directory Structure
```
├── backend_experimental/          # Backend (Python 3.11, FastAPI)
│   ├── app/api/routes/           # API endpoints
│   ├── app/services/             # Business logic (analysis_service_v2.py が中核)
│   ├── app/ai_engine/processors/ # AI処理 (skeleton, SAM, gaze)
│   ├── app/core/                 # WebSocket, config
│   ├── venv311/                  # Python 3.11 venv (REQUIRED)
│   └── tests/                    # unit/ + integration/
├── frontend/                     # Next.js App Router + TypeScript
│   ├── app/                      # Pages (upload, dashboard, scoring, library)
│   ├── components/               # React components
│   ├── tests/                    # Playwright E2E (90+ tests, 日本語UI期待)
│   └── .env.local                # API URL設定
└── docs/                         # 設計ドキュメント (日本語)
```

## Quick Start
```bash
run.bat                               # ローカル開発 (Frontend 3000 + Backend 8001)
run.bat ngrok                         # 公開デモ (ngrokデュアルドメイン)
kill.bat                              # 全サーバー停止
```

## Critical Rules

### Python 3.11 MANDATORY
Python 3.12+ は MediaPipe/OpenCV 非対応。常に `./venv311/Scripts/python.exe` を使用。
インストールパス: `C:\Users\ajksk\AppData\Local\Programs\Python\Python311`

### CORS Configuration
ローカル: `.env.local` で `NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1`
ngrok: `backend_experimental/app/main.py` の `allow_origins` と `.env.local` を合わせる

### Fail Fast Validation
```python
# ❌ Bad: data.get('key', default)  — 問題を隠蔽
# ✅ Good: if 'key' not in data: raise ValueError("key required")
```

### Git Commit
大容量ファイル除外: `git add --all -- . ":!*.pt" ":!*.mp4" ":!*.jpg" ":!*.png"`

## Testing
```bash
cd frontend && npm run test          # Playwright E2E (headless)
cd frontend && npm run build         # TypeScript + build check
cd backend_experimental && ./venv311/Scripts/python.exe -m pytest tests/ -v
```

## Key API Endpoints
- `POST /api/v1/videos/upload` — 動画アップロード (1GB max, .mp4)
- `POST /api/v1/analysis/{video_id}/analyze` — 解析開始
- `GET /api/v1/analysis/{analysis_id}/status` — 進捗確認
- `WS /ws/analysis/{analysis_id}` — リアルタイム進捗

## Protected File: GazeDashboardClient.tsx
独自のビデオ同期Canvas + Chart.jsグラフ実装（879行）。`git restore` 禁止。
詳細: [POST_MORTEM_GAZE_DASHBOARD_CUSTOM_DESIGN.md](docs/POST_MORTEM_GAZE_DASHBOARD_CUSTOM_DESIGN.md)

## Debugging Protocol
全トラブルシューティングで3つの質問に回答すること:
1. 修正してもほかの部分に影響ないか？
2. なぜこういう作りになっているのか？
3. 同じ問題を起こしそうな場所はないか？
詳細: [DEBUGGING_PROTOCOL.md](docs/DEBUGGING_PROTOCOL.md)

## Documentation
- [プロジェクト概要](docs/00_overview/00_project_overview.md)
- [アーキテクチャ設計](docs/01_architecture/01_architecture_design.md)
- [データベース設計](docs/02_database/02_database_design.md)
- [API設計](docs/03_api/03_api_design.md)
- [フロントエンド設計](docs/04_frontend/04_frontend_design.md)
- [開発環境セットアップ](docs/06_development/06_development_setup.md)
- [データパイプラインガイドライン](docs/06_development/data_pipeline_guidelines.md)
- [POST MORTEM一覧](docs/) — POST_MORTEM_*.md

## Common Errors
| Error | Solution |
|-------|----------|
| CORS error | `allow_origins` in main.py + `.env.local` を確認 |
| MediaPipe errors | Python 3.11 を使用 (3.12+ 不可) |
| Upload failures | 1GB max, .mp4 only |
| `.next` cache | `cd frontend && rmdir /s /q .next` |
| Port in use | `kill_all_servers.bat` |
