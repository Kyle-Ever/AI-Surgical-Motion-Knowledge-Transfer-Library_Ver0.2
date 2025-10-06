# 開発環境セットアップガイド - AI Surgical Motion Knowledge Transfer Library

## 目次
1. [必要な環境](#必要な環境)
2. [初期セットアップ](#初期セットアップ)
3. [バックエンドセットアップ](#バックエンドセットアップ)
4. [フロントエンドセットアップ](#フロントエンドセットアップ)
5. [開発用コマンド](#開発用コマンド)
6. [トラブルシューティング](#トラブルシューティング)
7. [開発フロー](#開発フロー)

## 必要な環境

### 必須要件
```yaml
Python: "3.11.9" # 重要: 3.13は互換性問題あり
Node.js: ">= 18.0.0"
npm: ">= 9.0.0"
Git: ">= 2.0.0"
```

### 推奨環境
```yaml
OS: "Windows 10/11, macOS 12+, Ubuntu 20.04+"
メモリ: "8GB以上"
ディスク: "10GB以上の空き容量"
GPU: "CUDA対応GPU（オプション、パフォーマンス向上）"
```

## 初期セットアップ

### 1. リポジトリのクローン
```bash
git clone https://github.com/your-org/ai-surgical-motion-library.git
cd ai-surgical-motion-library
```

### 2. 環境変数の設定

#### バックエンド環境変数（`backend/.env`）
```env
# Database
DATABASE_URL=sqlite:///./aimotion.db

# File Upload
UPLOAD_DIR=data/uploads
MAX_UPLOAD_SIZE=2147483648  # 2GB in bytes

# CORS Settings (Development)
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost:8000"]

# AI Model Paths
YOLO_MODEL_PATH=yolov8n.pt
SAM_MODEL_PATH=sam_b.pt
YOLO_POSE_MODEL_PATH=yolov8n-pose.pt

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# WebSocket
WS_HEARTBEAT_INTERVAL=30
WS_MESSAGE_QUEUE_SIZE=100
```

#### フロントエンド環境変数（`frontend/.env.local`）
```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Upload Settings
NEXT_PUBLIC_MAX_FILE_SIZE=2147483648
NEXT_PUBLIC_ACCEPTED_FORMATS=.mp4

# Feature Flags (optional)
NEXT_PUBLIC_ENABLE_3D_VIEWER=true
NEXT_PUBLIC_ENABLE_ADVANCED_METRICS=true
```

## バックエンドセットアップ

### 1. Python仮想環境の作成（重要: Python 3.11使用）
```bash
cd backend

# Windows
python -m venv venv311
.\venv311\Scripts\activate

# macOS/Linux
python3.11 -m venv venv311
source venv311/bin/activate
```

### 2. 依存関係のインストール
```bash
# 仮想環境がアクティブな状態で実行
pip install --upgrade pip
pip install -r requirements.txt

# 開発用依存関係
pip install -r requirements-dev.txt
```

### 3. モデルファイルのダウンロード
```bash
# AIモデルの自動ダウンロードスクリプト
python scripts/download_models.py

# または手動でダウンロード
# - yolov8n.pt: https://github.com/ultralytics/assets/releases/
# - sam_b.pt: https://github.com/facebookresearch/segment-anything
```

### 4. データベースの初期化
```bash
# データベース作成とマイグレーション
python -c "from app.db.database import init_db; init_db()"

# テストデータの投入（オプション）
python scripts/seed_database.py
```

### 5. ディレクトリ構造の確認
```bash
# 必要なディレクトリを作成
mkdir -p data/uploads
mkdir -p logs
mkdir -p temp
```

### 6. バックエンドサーバーの起動
```bash
# 開発サーバー起動
./venv311/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# または
python -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

## フロントエンドセットアップ

### 1. Node.js依存関係のインストール
```bash
cd frontend

# パッケージインストール
npm install

# または yarn を使用
yarn install
```

### 2. TypeScript型定義の生成
```bash
# API型定義の自動生成（オプション）
npm run generate:types
```

### 3. 開発サーバーの起動
```bash
# Next.js開発サーバー
npm run dev

# ポートを指定する場合
npm run dev -- --port 3001
```

### 4. ビルドとプロダクション実行
```bash
# プロダクションビルド
npm run build

# プロダクションサーバー起動
npm run start
```

## 開発用コマンド

### 統合起動スクリプト
```bash
# Windows: 両方のサーバーを同時起動
start_both.bat

# macOS/Linux: 並列起動スクリプト
./scripts/start_dev.sh
```

### バックエンドコマンド
```bash
# テスト実行
cd backend
python -m pytest tests/

# カバレッジ測定
python -m pytest --cov=app tests/

# リンター実行
python -m flake8 app/
python -m black app/
python -m mypy app/

# API ドキュメント確認
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

### フロントエンドコマンド
```bash
# テスト実行
cd frontend
npm run test

# E2Eテスト（Playwright）
npm run test:e2e
npx playwright test --ui  # UI モードで実行

# リンター実行
npm run lint
npm run lint:fix  # 自動修正

# 型チェック
npm run type-check

# Storybook起動（コンポーネント開発）
npm run storybook
```

## トラブルシューティング

### Python関連

#### ❌ エラー: `ModuleNotFoundError: No module named 'mediapipe'`
```bash
# 解決法: Python 3.11を使用していることを確認
python --version  # 3.11.x であることを確認
pip install mediapipe==0.10.0
```

#### ❌ エラー: `numpy version incompatible`
```bash
# 解決法: numpy v1を使用
pip uninstall numpy
pip install "numpy<2"
```

#### ❌ エラー: `CUDA not available`
```bash
# 解決法: CPU版のPyTorchを使用（GPUがない場合）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### フロントエンド関連

#### ❌ エラー: `EADDRINUSE: Port 3000 is already in use`
```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <process_id> /F

# macOS/Linux
lsof -i :3000
kill -9 <process_id>
```

#### ❌ エラー: `CORS error`
```javascript
// backend/app/main.py を確認
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  // 開発環境では全許可
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### ❌ エラー: `WebSocket connection failed`
```bash
# バックエンドサーバーが起動していることを確認
curl http://localhost:8000/api/v1/health

# ファイアウォール設定を確認
# Windows Defender、アンチウイルスソフトの設定
```

### データベース関連

#### ❌ エラー: `sqlite3.OperationalError: database is locked`
```bash
# 解決法: データベース接続をリセット
cd backend
rm aimotion.db
python -c "from app.db.database import init_db; init_db()"
```

### 一般的な問題

#### キャッシュクリア
```bash
# フロントエンド
cd frontend
rm -rf .next node_modules
npm install
npm run dev

# バックエンド
cd backend
find . -type d -name __pycache__ -exec rm -r {} +
rm -rf .pytest_cache
```

## 開発フロー

### 1. 新機能開発の流れ

```mermaid
graph LR
    A[Issue作成] --> B[Branch作成]
    B --> C[開発]
    C --> D[テスト作成]
    D --> E[ローカルテスト]
    E --> F[PR作成]
    F --> G[コードレビュー]
    G --> H[マージ]
```

### 2. ブランチ戦略
```bash
# Feature branch
git checkout -b feature/video-comparison

# Bug fix
git checkout -b fix/upload-error

# Hotfix
git checkout -b hotfix/critical-bug
```

### 3. コミット規約
```bash
# コミットメッセージフォーマット
# <type>: <subject>
#
# <body>

# 例
git commit -m "feat: 動画比較機能を追加

- 2つの動画を同期再生
- リアルタイムメトリクス表示
- フィードバック生成

Closes #123"
```

#### コミットタイプ
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント更新
- `style`: コードスタイル変更
- `refactor`: リファクタリング
- `test`: テスト追加・修正
- `chore`: ビルド・補助ツール変更

### 4. デバッグツール

#### バックエンド
```python
# デバッグログ
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Processing video: {video_id}")

# Python Debugger
import pdb; pdb.set_trace()

# IPython Debugger（より高機能）
import ipdb; ipdb.set_trace()
```

#### フロントエンド
```javascript
// React Developer Tools
// Chrome/Firefox拡張機能をインストール

// Console debugging
console.log('State:', state);
console.table(data);
console.time('Performance');
// ... code ...
console.timeEnd('Performance');

// Breakpoint
debugger;
```

### 5. パフォーマンス監視

#### バックエンド
```python
# プロファイリング
python -m cProfile -o profile.stats app.main:app

# メモリプロファイリング
from memory_profiler import profile

@profile
def process_video(video_path):
    # ...
```

#### フロントエンド
```javascript
// Chrome DevTools Performance タブ
// Lighthouse によるパフォーマンス分析

// React Profiler
import { Profiler } from 'react';

<Profiler id="VideoUploader" onRender={onRenderCallback}>
  <VideoUploader />
</Profiler>
```

## 継続的インテグレーション

### GitHub Actions設定例
```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: |
          cd backend
          pip install -r requirements.txt
          python -m pytest tests/

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
        with:
          node-version: '18'
      - run: |
          cd frontend
          npm ci
          npm run build
          npm run test
```

---
*最終更新: 2024年9月27日*
*このドキュメントはClaude Codeとの協働開発を前提に作成されています*