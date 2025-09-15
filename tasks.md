# tasks.md (PRD-001 トレース)

## 完了済みタスク (2025-01-16更新)

### ✅ 環境設定・修正
- [x] Python 3.11環境の確立 (MediaPipe/OpenCV互換性問題解決)
- [x] バックエンドサーバー起動問題の修正 (文字エンコーディング/Python版問題)
- [x] start_backend_py311.bat作成 (Python 3.11専用起動スクリプト)
- [x] SETUP_AND_RUN.md作成 (セットアップと実行ガイド)
- [x] CLAUDE.md更新 (Python 3.11必須の明記)

### ✅ コア機能実装
- [x] 実際のMediaPipe骨格検出の実装 (analysis_service.py)
- [x] リアルモーション解析の実装:
  - _analyze_velocity: 実際の手の動きから速度計算
  - _analyze_trajectory: 軌跡の滑らかさ計算
  - _analyze_stability: 安定性メトリクス (震え検出含む)
  - _analyze_efficiency: 効率性メトリクス
- [x] スコア計算の実装 (実際の解析結果使用)

### ✅ MediaPipe処理修正 (2025-01-15)
- [x] MediaPipeが実際に使用されない問題の診断と修正:
  - 問題: `process_with_mediapipe`が非同期関数でブロッキングI/O使用
  - 解決: 同期関数に変更し`run_in_executor`で実行
  - 座標変換修正 (ピクセル座標→正規化座標0-1)
- [x] 外部カメラ選択時の器具検出無効化:
  - フロントエンド: チェックボックスのグレーアウト実装
  - バックエンド: `video_type == 'internal'`チェック追加
- [x] MediaPipeテストエンドポイント追加 (`/api/v1/analysis/test/mediapipe`)
- [x] デバッグログ強化とエラーハンドリング改善

### ✅ ライブラリ機能修正 (2025-01-16)
- [x] ライブラリページの解析結果表示問題修正:
  - APIエンドポイント修正: `/library/completed` → `/analysis/completed`
  - フロントエンド api.ts のエンドポイント修正
- [x] エクスポート機能の修正:
  - CSVエクスポートエンドポイント実装
  - フロントエンドにエクスポートボタン追加（緑色のダウンロードアイコン）
- [x] 動画表示問題の修正:
  - VideoPlayerコンポーネント: `videoUrl`を直接使用するよう修正
  - サンプル動画へのフォールバック削除
  - エラーハンドリング追加
- [x] バックエンドAPIエラー修正:
  - `get_analysis_result`エンドポイントの500エラー修正
  - `from_orm`の問題を回避して手動でレスポンス作成

### ✅ Playwrightテスト基盤
- [x] テストヘルパーユーティリティ作成:
  - test-data.ts: テストデータ生成
  - api-mock.ts: APIモックユーティリティ
  - page-objects.ts: ページオブジェクトパターン
- [x] 既存テストの修正 (home.spec.ts, upload.spec.ts)
- [x] 包括的なナビゲーションテストスイート (navigation.spec.ts)
- [x] アップロードフローE2Eテスト (upload-flow-e2e.spec.ts)
- [x] 解析進捗とWebSocketテスト (analysis-progress.spec.ts)

## 進行中タスク

### 🔄 T-100: Playwrightテスト完成とバグ修正
- [ ] エラーハンドリングテストスイート作成
- [ ] フロントエンドAPIエンドポイント修正
- [ ] テスト実行とレポート生成
- [ ] テスト実行スクリプトとドキュメント作成
- **Status**: error-handling.spec.ts作成中
- **Next**: APIエンドポイントの修正、全テスト実行

## フェーズA: 設計・下準備
- [x] T-001: PRD-001 合意レビューと不足埋め
  - **完了**: PRD-001_aimotion.md更新済み
  - **成果物**: docs/PRD/PRD-001_aimotion.md

- [x] T-002: API一覧の確定とOpenAPI整備
  - **完了**: FastAPI自動生成OpenAPI (/docs)
  - **成果物**: backend/app/main.py, 各routesファイル

## フェーズB: 機能実装
- [x] T-010: 動画アップロードAPIの確認/補強
  - **完了**: POST /videos/upload実装済み (2GB制限、mp4のみ)
  - **成果物**: backend/app/api/routes/videos.py

- [x] T-011: 解析開始APIとDB登録の安定化
  - **完了**: 解析ステータス管理実装
  - **成果物**: backend/app/api/routes/analysis.py

- [x] T-012: 進捗取得API/WSの整合性
  - **完了**: WebSocket実装、統一されたステップマッピング
  - **成果物**: backend/app/core/websocket.py, analysis.py (L143-185)

- [x] T-013: 骨格/器具検出の結果格納とスコア算出
  - **完了**: MediaPipe統合、実スコア計算
  - **成果物**: backend/app/services/analysis_service.py

- [x] T-014: 完了解析一覧APIの整備
  - **完了**: GET /analysis/completed実装
  - **成果物**: backend/app/api/routes/analysis.py

## フェーズC: テスト (進行中)
- [ ] T-020: フロントエンドE2Eテスト完成
  - Owner: AI
  - Depends: Playwright基盤
  - Estimate: 120m
  - Traces: 全UC/AC
  - Deliverables: frontend/tests/*.spec.ts
  - Acceptance: 全主要フローがテストされ、レポート生成可能
  - Verify: npm test実行、HTMLレポート確認
  - **Progress**: 70% (5/7テストファイル作成済み)

- [ ] T-021: バックエンド統合テスト
  - Owner: AI
  - Depends: T-014
  - Estimate: 60m
  - Traces: AC-02..06
  - Deliverables: backend/tests/test_integration.py
  - Acceptance: 主要APIフローの統合テスト
  - Verify: pytest実行

## フェーズD: ドキュメント/運用
- [x] T-030: README/起動手順の最新化
  - **完了**: SETUP_AND_RUN.md作成
  - **成果物**: SETUP_AND_RUN.md, CLAUDE.md更新

- [ ] T-031: テスト実行ガイド作成
  - Owner: AI
  - Depends: T-020
  - Estimate: 30m
  - Deliverables: frontend/tests/README.md
  - Acceptance: テスト実行手順、レポート確認方法記載
  - Verify: 手順に従ってテスト実行可能

## 次の優先タスク (2025-01-16)

1. **T-100継続**: Playwrightテスト完成
   - error-handling.spec.ts作成
   - 全テスト実行とレポート生成
   - テスト実行ガイド作成

2. **T-021**: バックエンド統合テスト作成
   - 動画アップロード→解析開始→完了の一連フロー
   - WebSocket通信テスト
   - MediaPipe処理の統合テスト

3. **パフォーマンス最適化**:
   - 大容量動画の解析最適化
   - キャッシュ戦略の実装
   - DB クエリ最適化

## 技術的な注意事項

### 必須要件
- **Python 3.11使用** (3.13不可、MediaPipe/OpenCV互換性)
- バックエンド起動: `start_backend_py311.bat`使用
- フロントエンド起動: `start_frontend.bat`使用

### MediaPipe設定（2025-01-15更新）
- 手検出信頼度: 0.3（手袋対応のため低めに設定）
- 追跡信頼度: 0.3
- 最大検出手数: 2
- 座標系: 正規化座標（0-1範囲）使用

### 現在稼働中のサービス
- Backend: http://localhost:8000 (Python 3.11, FastAPI)
- Frontend: http://localhost:3000 (Next.js 15, React 19)
- API Docs: http://localhost:8000/docs

### テスト実行コマンド
```bash
# フロントエンドテスト
cd frontend
npm test              # ヘッドレス実行
npm run test:ui       # UI付き実行
npm run test:headed   # ブラウザ表示
npm run test:report   # レポート表示
```

## プロジェクト成果物

### バックエンド
- ✅ FastAPI RESTful API
- ✅ SQLAlchemy + SQLite DB
- ✅ WebSocket リアルタイム通信
- ✅ MediaPipe骨格検出統合
- ✅ 実モーション解析アルゴリズム

### フロントエンド
- ✅ Next.js 15 + React 19 UI
- ✅ 4ページ実装 (Home, Upload, Library, Analysis)
- 🔄 Playwrightテストスイート (70%完成)

### ドキュメント
- ✅ PRD-001_aimotion.md (要件定義)
- ✅ SETUP_AND_RUN.md (セットアップガイド)
- ✅ CLAUDE.md (AI開発ガイド)
- ✅ AGENTS.md (運用ルール)

## 備考
- プロジェクトはMVP実装段階
- コア機能は動作確認済み
- フロントエンドのバグ修正とテスト完成が最優先
- Python 3.11環境の維持が重要