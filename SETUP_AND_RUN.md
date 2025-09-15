# セットアップと起動ガイド

## 重要: Python バージョン要件
**必ずPython 3.11を使用してください**
- Python 3.13では動作しません（MediaPipe/OpenCV互換性問題）
- Python 3.11のパス: `C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe`

## クイックスタート

### 1. バックエンド起動（Python 3.11）
```bash
# 方法1: バッチファイルを使用（推奨）
start_backend_py311.bat

# 方法2: 手動で起動
cd backend
"C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe" -m uvicorn app.main:app --reload --port 8000
```

### 2. フロントエンド起動
```bash
# 方法1: バッチファイルを使用（推奨）
start_frontend.bat

# 方法2: 手動で起動
cd frontend
npm install  # 初回のみ
npm run dev
```

### 3. 両方同時に起動
```bash
start_both.bat
```

## アクセスURL

| サービス | URL | 説明 |
|---------|-----|------|
| フロントエンド | http://localhost:3000 | メインUI |
| バックエンドAPI | http://127.0.0.1:8000 | APIサーバー |
| APIドキュメント | http://127.0.0.1:8000/docs | Swagger UI |
| ヘルスチェック | http://127.0.0.1:8000/api/v1/health | 動作確認 |

## トラブルシューティング

### バックエンドが起動しない場合

1. **Python バージョン確認**
   ```bash
   python --version
   # 3.11.x でない場合は、以下を使用
   "C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe" --version
   ```

2. **文字エンコーディングエラー**
   - `backend/app/api/routes/analysis.py`に文字化けがある場合
   - UTF-8エンコーディングで保存し直す

3. **依存関係のインストール**
   ```bash
   cd backend
   "C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe" -m pip install -r requirements.txt
   ```

### フロントエンドが起動しない場合

1. **Node.jsバージョン確認**
   ```bash
   node --version  # v18以上推奨
   ```

2. **依存関係のインストール**
   ```bash
   cd frontend
   npm install
   ```

3. **キャッシュクリア**
   ```bash
   cd frontend
   npm run clean  # または rm -rf .next
   npm install
   npm run dev
   ```

## 環境変数設定

### バックエンド（backend/.env）
```env
DATABASE_URL=sqlite:///./aimotion.db
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_SIZE=2147483648  # 2GB
ALLOWED_EXTENSIONS=.mp4
```

### フロントエンド（frontend/.env.local）
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## 重要な注意事項

### Python 3.11の使用（必須）
- **絶対にPython 3.13を使用しないでください**
- MediaPipeとOpenCVの互換性のため、Python 3.11が必要です
- `start_backend_py311.bat`を使用することを推奨

### ポート設定
- バックエンド: 8000番ポート
- フロントエンド: 3000番ポート
- 他のアプリケーションがこれらのポートを使用していないことを確認

### ファイルパス
- Windows環境のため、パス区切りは`\`を使用
- 日本語パスは避ける

## 開発時のコマンド

### バックエンド
```bash
# テスト実行
cd backend
python -m pytest

# 型チェック
python -m mypy app

# フォーマット
python -m black app
```

### フロントエンド
```bash
# テスト実行
cd frontend
npm test

# ビルド
npm run build

# Lint実行
npm run lint

# 型チェック
npm run type-check
```

## 動作確認手順

1. バックエンドの確認
   ```bash
   curl http://127.0.0.1:8000/api/v1/health
   # 期待される応答: {"status":"healthy","version":"0.1.0"}
   ```

2. フロントエンドの確認
   - ブラウザで http://localhost:3000 にアクセス
   - ホームページが表示されることを確認

3. API連携の確認
   - フロントエンドの「新規解析」ボタンをクリック
   - アップロード画面が表示されることを確認

## 更新履歴

- 2025-09-14: Python 3.11専用バッチファイル作成
- 2025-09-14: 文字エンコーディング問題修正
- 2025-09-14: 初回ドキュメント作成