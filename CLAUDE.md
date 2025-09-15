# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ 重要なルール: docs/ドキュメントを必ず参照
**このプロジェクトでは`docs/`内のドキュメントに従って作業してください**
- **開発プロセス**: `docs/Rules/`の3つのルールに従う
  1. `01_prd_generation_rules.md` - PRD作成ルール
  2. `02_task_generation_rules.md` - タスク分解ルール
  3. `03_task_execution_rules.md` - 実行ルール（1タスクずつ確実に）
- **現行PRD**: `docs/PRD/PRD-001_aimotion.md`を基準に開発
- **設計書**: `docs/`内の各種設計ドキュメント参照
- **運用ルール**: `AGENTS.md`の手順（PRD→タスク化→実行）を遵守

## ⚠️ 重要: Python 3.11 必須
**絶対にPython 3.11を使用してください** - Python 3.13では動作しません（MediaPipe/OpenCV互換性問題）
- 正しいパス: `C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe`
- バッチファイル使用推奨: `start_backend_py311.bat`
- 詳細は`SETUP_AND_RUN.md`参照

## プロジェクト概要

**AI手技モーション伝承ライブラリ** - 手術動画から骨格・器具の動きを抽出・解析し、教育/評価に活用できるWebアプリケーション

## 開発プロセス（必須）

**重要**: 新機能開発や大きな変更を行う際は、以下のプロセスを必ず守ってください：

1. **PRD作成フェーズ** (`docs/Rules/01_prd_generation_rules.md`)
   - 要件ヒアリング（Q2.1〜Q2.9の質問）
   - PRDドキュメント作成・合意
   - `docs/PRD/`に保存

2. **タスク分解フェーズ** (`docs/Rules/02_task_generation_rules.md`)
   - PRDから15〜90分単位のタスクへ分解
   - `tasks.md`にチェックリスト形式で記載
   - 依存関係・受け入れ基準を明記

3. **実行フェーズ** (`docs/Rules/03_task_execution_rules.md`)
   - 1タスクずつ実行（One-Task-At-A-Time）
   - 実行前に計画提示→承認→実装→検証→完了報告
   - 最小差分で実装、副作用を避ける

## 開発コマンド

### バックエンド (Python 3.11必須)
```bash
# 推奨: Python 3.11専用バッチファイル
start_backend_py311.bat  # Python 3.11確認、venv311作成、FastAPI起動

# 手動起動（必ずPython 3.11使用）
cd backend
"C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe" -m venv venv311
venv311\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### フロントエンド
```bash
# 起動（ルートから実行）
start_frontend.bat  # npm install → dev起動

# 手動起動
cd frontend
npm install
npm run dev  # Turbopack使用、ポート3000
npm run build  # プロダクションビルド（Turbopack使用）
npm run lint  # ESLint v9実行（Next.js core-web-vitals）
npm run start  # プロダクションサーバー起動
```

### 両方起動
```bash
start_both.bat  # バックエンドとフロントエンドを並列起動
```

### テスト
```bash
# Playwright E2E（フロントエンド）
cd frontend
npm run test  # ヘッドレスモード（全ブラウザ）
npm run test:headed  # ブラウザ表示モード
npm run test:ui  # UI付きインタラクティブモード
npm run test:debug  # デバッグモード
npm run test:report  # HTMLレポート表示
npx playwright test [filename]  # 特定ファイルのみ実行

# バックエンド検証（venv311使用）
cd backend
venv311\Scripts\python.exe test_mediapipe_integration.py  # MediaPipe統合テスト
venv311\Scripts\python.exe test_frame_extraction.py  # フレーム抽出テスト
venv311\Scripts\python.exe test_server.py  # サーバー動作確認
```

## アーキテクチャ

### バックエンド構成
- **Python 3.11固定**（3.13不可！MediaPipe/OpenCV互換性問題）
- **FastAPI** + Uvicorn（ポート8000）
- **SQLAlchemy** + SQLite（`aimotion.db`）
- **Pydantic v2** スキーマ
- **WebSocket** リアルタイム進捗通知
- **設定**: `backend/app/core/config.py`
  - `UPLOAD_DIR=./data/uploads`（2GB制限）
  - `ALLOWED_EXTENSIONS={.mp4}`のみ
  - `DATABASE_URL=sqlite:///./aimotion.db`

### APIエンドポイント（実装済み）
```
GET  /                                    # サービス情報
GET  /api/v1/health                      # ヘルスチェック
POST /api/v1/videos/upload                # 動画アップロード（2GB制限）
GET  /api/v1/videos/{video_id}            # 動画詳細取得
GET  /api/v1/videos/                      # 動画一覧
POST /api/v1/analysis/{video_id}/analyze  # 解析開始
GET  /api/v1/analysis/{analysis_id}/status # 進捗確認
GET  /api/v1/analysis/{analysis_id}       # 結果取得
GET  /api/v1/analysis/completed           # 完了一覧
WS   /ws/analysis/{analysis_id}           # 進捗WebSocket
```

### フロントエンド構成
- **Next.js 15** + **React 19.1** + TypeScript
- **Tailwind CSS 4** + Lucide icons
- **Zustand** 状態管理、**Chart.js** グラフ
- **主要ページ**:
  - `/` ホーム（4カードメニュー）
  - `/upload` 動画アップロード
  - `/analysis/[id]` 解析結果表示
  - `/library` 解析結果ライブラリ
  - `/annotation` アノテーション
  - `/dashboard` ダッシュボード

## 処理フロー

1. 動画アップロード（`POST /videos/upload`）→ `data/uploads/`保存
2. 解析開始（`POST /analysis/{video_id}/analyze`）→ 非同期実行
3. フレーム抽出（OpenCV）→ 骨格検出（MediaPipe）→ 器具検出（YOLOv8）
4. モーション解析 → スコア算出 → DB保存
5. WebSocketで進捗通知（`current_step`, `progress%`）

## データモデル

- **Video**: `id`, `filename`, `original_filename`, `video_type`, `duration`, `file_path`...
- **AnalysisResult**: `id`, `video_id`, `status`, `progress`, `skeleton_data`, `instrument_data`, `scores`...
- 詳細は`backend/app/models/`および`backend/app/schemas/`参照

## 重要なファイルパス

- **アップロード動画**: `backend/data/uploads/`（2GB制限、.mp4のみ）
- **データベース**: `backend/aimotion.db`（SQLite）
- **仮想環境**: `backend/venv311/`（Python 3.11専用）
- **設定ファイル**: `backend/app/core/config.py`
- **Playwrightテスト**: `frontend/tests/*.spec.ts`

## 重要な制約・注意点

- **Python 3.13非対応**（MediaPipe/OpenCV互換性問題）- 必ずPython 3.11使用
- **Windows予約名**（`nul`）による`backend/nul`はGit追跡しない
- **循環参照回避**: `app/models/__init__.py`と`database.py`の参照を統一
- **CORS設定済み**: localhost:3000からのアクセス許可
- **依存バージョン固定**: `numpy<2`（互換性維持）、`ultralytics==8.0.200`（YOLO固定）
- **WebSocket**: 解析進捗通知は`/ws/analysis/{analysis_id}`で接続

## プロジェクト構成ファイル

### 必読ドキュメント
- **`docs/Rules/`**: 開発プロセスルール（必ず従う）
  - `01_prd_generation_rules.md` - PRD作成時の手順
  - `02_task_generation_rules.md` - タスク分解の基準
  - `03_task_execution_rules.md` - 実装時の手順
- **`docs/PRD/PRD-001_aimotion.md`**: 現行PRD（仕様の基準）
- **`AGENTS.md`**: 運用ルール概要
- **`tasks.md`**: 現在のタスク一覧

### 設計ドキュメント
- **`docs/requirements-doc.md`**: 要件定義書
- **`docs/basic-design-doc.md`**: 基本設計書
- **`docs/ui-ux-design-doc.md`**: UI/UX設計書
- **`docs/ai-processing-flow-doc.md`**: AI処理フロー設計
- **`docs/development-wbs-doc.md`**: 開発WBS

### セットアップ・運用
- **`SETUP_AND_RUN.md`**: セットアップ手順とトラブルシューティング
- **CI/CD**: `.github/workflows/e2e.yml`（Playwright E2E、push/PRトリガ）

## コーディング規約

- **インデント**: Python 4スペース、TypeScript/React 2スペース
- **命名規則**: Python snake_case、TypeScript/React camelCase（コンポーネントはPascalCase）
- **型アノテーション**: Python型ヒント必須、TypeScript厳密型使用
- **スタイリング**: Tailwind CSS優先、インラインスタイル最小限
- **コミット**: タイプ付き（feat:, fix:, chore:, docs:）、簡潔な現在形