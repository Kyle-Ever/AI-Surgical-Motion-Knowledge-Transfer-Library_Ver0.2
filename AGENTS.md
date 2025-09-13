# 開発エージェント運用ルール（本リポジトリ専用）

この AGENTS.md は本リポジトリ配下すべてに適用されます。開発・コーディング時は必ず最新のルール/構成/手順をここで確認してください。

参照ルール（常時遵守）
- PRD作成: `docs/Rules/01_prd_generation_rules.md`
- タスク化: `docs/Rules/02_task_generation_rules.md`
- 実行手順: `docs/Rules/03_task_execution_rules.md`

小さな修正（明確なバグ修正、コメント微調整、CI微修正など）を除き、「PRD → タスク化 → 実行」の順に進めます。

## プロジェクト概要
- 目的: 手術動画から骨格/器具の動作を抽出・解析し、教育/評価に活用できる API/UI を提供。
- サブプロジェクト: Backend(FastAPI) / Frontend(Next.js) / Docs(PRD/設計/Rules)。
- 現行PRD: `docs/PRD/PRD-001_aimotion.md`（随時更新）。タスク一覧: `tasks.md`。

## リポジトリ構成（主要）
- `backend/` バックエンド（Python 3.11 / FastAPI）
  - `app/main.py` エントリ、ルータ登録、CORS、WS。
  - `app/api/routes/` `videos.py`, `analysis.py` 等のAPI群。
  - `app/core/` `config.py`（設定）, `websocket.py`（接続管理）。
  - `app/models/` `video.py`, `analysis.py`, `database.py`（SQLAlchemy）。
  - `app/schemas/` Pydantic v2 スキーマ。
  - `ai_engine/processors/` 骨格/器具/動画解析のユーティリティ。
  - `_check_versions.py`, `_import_app.py`, `_healthcheck.py` 検証補助。
  - `requirements.txt` 依存（OpenCV/MediaPipe/Ultralytics 等）。
- `frontend/` フロントエンド（Next.js 15 / React 19 / TypeScript）
  - `package.json`（scripts: `dev/build/start/lint`）。
  - `app/`, `components/`, `hooks/`, `lib/`, `public/`, `types/`。
- `docs/` 仕様/設計/ルール
  - `Rules/01..03_*.md` 運用ルール。
  - `PRD/PRD-001_aimotion.md` 現行PRD。
- ルートスクリプト: `start_backend.bat`, `start_frontend.bat`, `start_both.bat`。

## バックエンド（詳細）
- 実行環境: Python 3.11 固定（`start_backend.bat` が 3.11 venv を作成）。
- 依存: `numpy<2` を維持（OpenCV/MediaPipe互換）、`uvicorn`, `fastapi`, `sqlalchemy`, `pydantic v2` 等。
- 設定: `app/core/config.py`
  - `UPLOAD_DIR=./data/uploads`, `TEMP_DIR=./data/temp`
  - `MAX_UPLOAD_SIZE=2GB`, `ALLOWED_EXTENSIONS={.mp4}`
  - `DATABASE_URL=sqlite:///./aimotion.db`
- API概略
  - `GET /` 情報、`GET /api/v1/health` ヘルス。
  - `POST /api/v1/videos/upload` mp4アップロード（2GBまで）。
  - `GET /api/v1/videos/{video_id}` 取得、`GET /api/v1/videos/` 一覧。
  - `POST /api/v1/analysis/{video_id}/analyze` 解析開始。
  - `GET /api/v1/analysis/{analysis_id}/status` 進捗、`GET /api/v1/analysis/{analysis_id}` 結果。
  - `GET /api/v1/analysis/completed` 完了一覧。
  - `WS /ws/analysis/{analysis_id}` 進捗イベント。
- モデル・スキーマ
  - Video: `id, filename, original_filename, video_type(internal|external), ...`
  - AnalysisResult: `status(pending|processing|completed|failed), progress, scores/json など`
  - Pydanticスキーマは `app/schemas/` を参照。
- サービス
  - `VideoService` メタ情報抽出/フレーム抽出。
  - `AnalysisService` フレーム抽出→骨格/器具検出→モーション解析→スコア→保存（WS進捗送信）。

## フロントエンド（詳細）
- スタック: Next.js 15, React 19, TypeScript, Tailwind4, ESLint9。
- 実行: `cd frontend && npm install && npm run dev`（ポート: 3000）。
- API 先: `http://localhost:8000`（CORS許可済み）。

## 起動手順（開発）
- Backend: ルートで `start_backend.bat` 実行（初回は venv/依存導入）。
- Frontend: ルートで `start_frontend.bat` 実行（npm install→dev）。
- 両方: `start_both.bat`。

## テスト/検証
- 統合試験: ルートの `test_integration.py` を手動実行（別途 `requests` が必要）。
- 簡易確認: `backend/_import_app.py`（アプリ読込）、`_healthcheck.py`（httpx必要）、`_check_versions.py`（依存版数）。

## セキュリティ/データ取扱い
- アップロードは `.mp4` のみ。保存先は `data/uploads/`。
- `.env` は機微を含むためコミット禁止。環境変数で上書き可能。
- SQLite `aimotion.db` はローカル動作専用。配布/共有は避ける。

## コーディング/運用規約
- 既存の構成・命名を尊重。無関係な修正は別タスク化。
- 文字コードは UTF-8 推奨。ログ/UI文言は既存の表記に合わせる。
- Git 対象外: `venv/`, `.env`, `aimotion.db`, `data/uploads`, `data/temp`, `backend/nul`（Windows予約名）。

## 既知の注意点
- Windows 予約名 `nul` に由来する `backend/nul` は Git のインデックスで問題となるため、追跡しない。
- `app/models/__init__.py` と `app/models/database.py` に類似の定義がある。参照先は統一し、循環参照を避ける。
- Python 3.13 では MediaPipe/OpenCV に未対応の版があるため使用しない。

## 作業フロー（厳守）
1) PRD作成/更新: `docs/PRD/PRD-001_aimotion.md` を更新し、未確定は明示/仮説提示。
2) タスク分解: `tasks.md` にトレース（UC/FR/NFR/API/AC）付きで追記。
3) 実行: One-Task-At-A-Time。Plan/Files/Test/Risk を提示→承認後、最小差分で実装→検証→AC確認。

この AGENTS.md は常に最新情報を反映します。更新があれば本ファイルを先に修正してから作業を続行してください。
