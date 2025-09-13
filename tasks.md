# tasks.md (PRD-001 トレース)

## フェーズA: 設計・下準備
- [ ] T-001: PRD-001 合意レビューと不足埋め（未確定の確定）
  - Owner: Pair(AI+User)
  - Depends: なし
  - Estimate: 45m
  - Traces: PRD-001, UC-01..05, FR/NFR 全般
  - Deliverables: `docs/PRD/PRD-001_aimotion.md` 更新
  - Acceptance: 未確定箇所が最小化され、承認コメントが付く
  - Verify: 文面レビュー、差分確認

- [ ] T-002: API一覧の確定とOpenAPI整備
  - Owner: AI
  - Depends: T-001
  - Estimate: 45m
  - Traces: API-01..07, FR-01..06, AC-01..06
  - Deliverables: `backend/app/main.py` ルーティング、OpenAPI説明
  - Acceptance: /docsで全エンドポイントが説明付きで参照可能
  - Verify: `uvicorn`起動後に `/docs` を手動確認

## フェーズB: 機能実装
- [ ] T-010: 動画アップロードAPIの確認/補強（mp4/2GB, 保存）
  - Owner: AI
  - Depends: T-002
  - Estimate: 60m
  - Traces: UC-01, FR-01, AC-01
  - Deliverables: `backend/app/api/routes/videos.py`, 保存ディレクトリ設定
  - Acceptance: mp4のみを受け付けID返却。拡張子違いは400
  - Verify: 手動curl/`test_integration.py` 追加（任意）

- [ ] T-011: 解析開始APIとDB登録の安定化
  - Owner: AI
  - Depends: T-010
  - Estimate: 60m
  - Traces: UC-02, FR-02, AC-02
  - Deliverables: `backend/app/api/routes/analysis.py`
  - Acceptance: PENDING→PROCESSINGの遷移がDBに反映
  - Verify: sqliteレコード確認

- [ ] T-012: 進捗取得API/WSの整合性（ステップ/％）
  - Owner: AI
  - Depends: T-011
  - Estimate: 60m
  - Traces: UC-02/03, FR-03, AC-03
  - Deliverables: `backend/app/core/websocket.py`, `analysis.py`
  - Acceptance: ステップと%がAPI/WSで同期
  - Verify: 手動確認（WSクライアント）

- [ ] T-013: 骨格/器具検出の結果格納とスコア算出
  - Owner: AI
  - Depends: T-012
  - Estimate: 120m
  - Traces: UC-04, FR-04, AC-04
  - Deliverables: `backend/app/services/analysis_service.py`
  - Acceptance: `scores.total_frames`等が設定
  - Verify: 疑似/短編動画で実行

- [ ] T-014: 完了解析一覧APIの整備
  - Owner: AI
  - Depends: T-013
  - Estimate: 30m
  - Traces: UC-05, FR-06, AC-06
  - Deliverables: `backend/app/api/routes/analysis.py`
  - Acceptance: ページングで一覧取得
  - Verify: 手動確認

## フェーズC: テスト
- [ ] T-020: ヘルス/基本APIの統合テスト雛形
  - Owner: AI
  - Depends: T-014
  - Estimate: 45m
  - Traces: AC-02..06
  - Deliverables: `tests/test_basic_api.py`
  - Acceptance: 主要APIが200/期待応答
  - Verify: `pytest -q`

## フェーズD: ドキュメント/運用
- [ ] T-030: README/起動手順の最新化
  - Owner: AI
  - Depends: T-020
  - Estimate: 20m
  - Traces: NFR-運用
  - Deliverables: `README.md`
  - Acceptance: 新規環境で15分以内に起動
  - Verify: 手順レビュー

## Top-3 先行タスク提案
1) T-001 PRD合意レビュー
2) T-002 API一覧の確定
3) T-010 動画アップロードAPIの補強

