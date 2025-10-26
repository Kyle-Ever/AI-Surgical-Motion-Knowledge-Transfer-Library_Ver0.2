# 🚀 AI手技モーションライブラリ - クイックスタートガイド

## 📋 バッチファイル一覧（5つ）

### 1️⃣ `start_both_experimental.bat` - **ローカル開発はこれを使用**
フロントエンド（Port 3000）とExperimentalバックエンド（Port 8001）を同時起動

```bash
# 使用方法
start_both_experimental.bat
```

**起動後:**
- フロントエンド: http://localhost:3000
- バックエンドAPI: http://localhost:8001/docs

---

### 2️⃣ `start_both_experimental_with_ngrok.bat` - **🌐 公開デモ・外部アクセス用**
フロントエンド + バックエンド + ngrokトンネルを同時起動

```bash
# 使用方法
start_both_experimental_with_ngrok.bat
```

**起動後:**
- ローカル: http://localhost:3000
- 公開URL: ngrokウィンドウに表示されるURL（例: https://abc123.ngrok-free.app）
- ngrok管理画面: http://localhost:4040

**機能:**
- ✅ インターネット経由でアプリにアクセス可能
- ✅ 無料アカウント登録で固定URL使用可能
- ✅ 24時間以上の継続公開（アカウント登録時）
- ✅ リクエスト/レスポンスのリアルタイム監視

**推奨:**
- デモンストレーション時
- 外部からのテスト・レビュー
- モバイル端末での動作確認
- チームメンバーとの共有

**注意:**
- ngrokのインストールが必要（初回のみ）
- 無料アカウント登録推奨（固定URL、無制限時間）
- 匿名使用は2時間制限

---

### 3️⃣ `start_backend_experimental.bat`
Experimentalバックエンドのみを起動（フロントエンドは別途起動）

```bash
# 使用方法
start_backend_experimental.bat
```

**使用シーン:**
- フロントエンド開発中（`npm run dev`を別途実行）
- バックエンドのみ再起動したい場合

---

### 4️⃣ `kill_all_servers.bat` - **通常のトラブル時に使用**
開発サーバーのプロセスを素早く終了（推奨）

```bash
# 使用方法
kill_all_servers.bat
```

**使用シーン:**
- サーバーが応答しなくなった
- ポートが使用中エラーが出た
- 通常の再起動前

**処理内容:**
- Port 3000, 8000, 8001のプロセス終了
- 全てのNode.jsプロセス終了
- 全てのPythonプロセス終了
- ✅ 確認なしで即座に実行
- ✅ 素早い終了

---

### 5️⃣ `kill_all_processes.bat` - **完全終了（慎重に使用）**
全てのPython/Node.jsプロセスを確実に終了

```bash
# 使用方法
kill_all_processes.bat
```

**使用シーン:**
- `kill_all_servers.bat`で解決しない場合
- プロセスが完全にハングした
- 確実にクリーンな状態にしたい

**処理内容:**
- ⚠️ 実行前に確認プロンプト表示
- Port 3000, 8000, 8001のプロセス終了
- 全てのNode.jsプロセス強制終了
- 全てのPythonプロセス強制終了
- 詳細な進捗表示（6段階）
- 終了後の状態確認と結果表示

**⚠️ 注意:**
- 他のPython/Node.jsアプリにも影響します
- 実行前に他のアプリが実行中でないことを確認

**詳細:** [KILL_SCRIPTS_COMPARISON.md](KILL_SCRIPTS_COMPARISON.md) を参照

---

## 🔧 開発環境要件

### Python
- **Python 3.11 必須**（3.12以降は非対応）
- 仮想環境: `backend_experimental/venv311/`

### Node.js
- Node.js 18以降推奨
- フロントエンド依存関係: `frontend/node_modules/`

---

## 📝 典型的な使用フロー

### 🟢 通常の開発開始（ローカル）
```bash
# 1. 両サーバーを起動
start_both_experimental.bat

# 2. ブラウザでアクセス
# → http://localhost:3000

# 3. 動画をアップロードして解析
```

### 🌐 デモ・公開アクセス
```bash
# 1. ngrok付きで起動
start_both_experimental_with_ngrok.bat

# 2. ngrokウィンドウで公開URLを確認
# 例: https://abc123.ngrok-free.app

# 3. そのURLを共有
# - モバイル端末でアクセス
# - チームメンバーと共有
# - デモンストレーション

# 4. トラフィック監視（オプション）
# → http://localhost:4040
```

### 🔴 トラブルシューティング
```bash
# 1. 全サーバー停止
kill_all_servers.bat

# 2. 2秒待機

# 3. 再起動
start_both_experimental.bat
```

### 🔵 バックエンドのみ再起動
```bash
# フロントエンドはそのままで、バックエンドだけ再起動
# 1. バックエンドプロセスを終了（Ctrl+C）
# 2. 再起動
start_backend_experimental.bat
```

---

## 🆘 よくあるエラーと解決方法

### ❌ Port already in use (ポート使用中)
```bash
kill_all_servers.bat
# 2秒待機
start_both_experimental.bat
```

### ❌ Python version error (Pythonバージョンエラー)
```bash
# Python 3.11がインストールされているか確認
C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe --version

# 仮想環境を再作成
cd backend_experimental
rmdir /s /q venv311
C:\Users\ajksk\AppData\Local\Programs\Python\Python311\python.exe -m venv venv311
.\venv311\Scripts\activate
pip install -r requirements.txt
```

### ❌ Module not found (モジュールが見つからない)
```bash
cd backend_experimental
.\venv311\Scripts\activate
pip install -r requirements.txt
```

### ❌ Frontend errors (フロントエンドエラー)
```bash
cd frontend
rmdir /s /q node_modules .next
npm install
npm run dev
```

---

## 📂 ディレクトリ構造

```
AI Surgical Motion Knowledge Transfer Library_Ver0.2/
│
├── START_HERE.md                             # このファイル
├── start_both_experimental.bat               # ローカル開発用
├── start_both_experimental_with_ngrok.bat    # 公開デモ用（NEW）
├── start_backend_experimental.bat            # バックエンド単体起動
├── kill_all_servers.bat                     # 全サーバー停止
│
├── backend_experimental/                     # Experimentalバックエンド (Port 8001)
│   ├── venv311/                             # Python 3.11仮想環境
│   ├── app/                                # アプリケーションコード
│   ├── data/uploads/                       # 動画ファイル
│   └── aimotion.db                         # SQLiteデータベース
│
├── frontend/                                # Next.jsフロントエンド (Port 3000)
│   ├── app/                                # Next.js App Router
│   ├── components/                         # Reactコンポーネント
│   └── tests/                              # Playwrightテスト
│
├── docs/                                    # 設計ドキュメント
│   ├── 00_overview/                        # プロジェクト概要
│   ├── 01_architecture/                    # アーキテクチャ設計
│   └── demo_instructions_for_customer.md   # デモ手順書
│
└── claudedocs/                              # 技術レポート（Claude生成）
    ├── BATCH_FILES_CLEANUP.md
    ├── SAM2_INSTRUMENT_DETECTION_FIX.md
    └── ... (バグ修正・テストレポート)
```

---

## 🧪 テスト実行

### E2Eテスト（Playwright）
```bash
cd frontend
npm run test              # 全テスト実行
npm run test:headed       # ブラウザ表示
npm run test:ui           # インタラクティブUI
```

### バックエンドテスト
```bash
cd backend_experimental
.\venv311\Scripts\python.exe test_api.py
```

---

## 📖 詳細ドキュメント

- **プロジェクト概要**: [docs/00_overview/00_project_overview.md](docs/00_overview/00_project_overview.md)
- **アーキテクチャ**: [docs/01_architecture/01_architecture_design.md](docs/01_architecture/01_architecture_design.md)
- **開発セットアップ**: [docs/06_development/06_development_setup.md](docs/06_development/06_development_setup.md)
- **CLAUDE.md**: プロジェクト全体のガイド

---

## 🔄 バージョン情報

**Current Version**: v0.2.0-experimental

**主な機能:**
- ✅ FrameExtractionService（リファクタリング完了）
- ✅ 25fps動画の正確な処理（round()修正）
- ✅ フレーム抽出の完全性（282/282フレーム）
- ✅ 正確なタイムスタンプ（0.08秒間隔）
- ✅ WebSocket進捗更新
- ✅ 骨格検出（MediaPipe）
- ✅ 器具検出（YOLOv8 + SAM2）

---

**🎯 開発を始めるには `start_both_experimental.bat` を実行するだけです！**
