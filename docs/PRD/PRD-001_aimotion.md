---
title: PRD-001 AI手技モーション伝承ライブラリ（バックエンド）
version: 0.2
owner: Product/Tech Lead
last_updated: 2025-09-13
---

## 1. 概要
- 目標: 手術動画から骨格・器具の動きを抽出・解析し、学習/評価に活用できる API を提供する。
- 背景: 手技の暗黙知を客観的指標に変換し、教育と品質向上を図るニーズがある。
- 主用途: 教育支援、研究用途。
- 想定導入現場: 大学/研究室。
- 成果物種別: `code`
- 関連Jira/Issue: `PRD-001`

## 2. ユースケース
| UC-ID | タイトル | 主要ステップ | 成功条件 |
|------|----------|--------------|----------|
| UC-01 | 動画アップロード | mp4選択→アップロード→保存 | 2GB以下mp4が保存されIDが返る |
| UC-02 | 解析開始 | 動画ID指定→解析キュー投入→進捗取得 | 解析IDが発行され進捗が取得できる |
| UC-03 | 進捗監視(WS) | WS接続→進捗イベント受信 | ステップ名と%の更新が受信できる |
| UC-04 | 解析結果取得 | 解析ID指定→結果取得 | 統計/座標/スコアが取得できる |
| UC-05 | 自己評価（暫定） | 解析結果を確認→自己の手技評価 | スコアと主要指標を理解できる |
| UC-06 | 教員レビュー（仮説） | 学生の結果を参照→コメント | コメントを外部で共有（システム外） |

## 3. 機能要件（FR）
| FR-ID | 説明 | 関連UC | 優先度 | 受け入れ基準(AC) |
|------|------|--------|--------|-------------------|
| FR-01 | mp4を2GBまで受け入れて保存する | UC-01 | High | AC-01 |
| FR-02 | 解析ジョブを起動しIDを返す | UC-02 | High | AC-02 |
| FR-03 | 解析進捗(ステップ/%)をAPI/WSで提供 | UC-02/03 | High | AC-03 |
| FR-04 | 骨格/器具の検出と簡易スコア算出 | UC-04 | High | AC-04 |
| FR-05 | 解析結果（統計/座標/スコア）取得 | UC-04 | High | AC-05 |
| FR-06 | 完了解析の一覧と動画メタを返す | UC-06 | Med | AC-06 |

## 4. 非機能要件（NFR）
- 性能（暫定）:
  - メタ系API（GET /, /health, /videos 等）P95 200ms以下
  - 同時アップロード5件想定、解析は非同期（時間は動画長に依存）
- 可用性（暫定）: 学内/研究室で 99.5% 稼働（シングルノード）
- セキュリティ（MVP）: mp4のみ許可、保存パス固定、.envで設定管理、PIIは扱わない前提
- 運用/監視（MVP）: ログ/例外記録、`/api/v1/health` のみ（監視連携は後続）

## 5. API/インタフェース（初期案）
| API-ID | メソッド | パス | 入力 | 出力 | エラー |
|--------|----------|------|------|------|-------|
| API-01 | GET | `/` | - | サービス情報 | 5xx |
| API-02 | GET | `/api/v1/health` | - | `{ "status": "healthy" }` | 5xx |
| API-03 | POST | `/api/v1/videos/upload` | multipart mp4 + form(video_type等) | `video_id` | 400/413/5xx |
| API-04 | POST | `/api/v1/analysis/{video_id}/analyze` | instruments, sampling_rate | `analysis_id` | 400/404/5xx |
| API-05 | GET | `/api/v1/analysis/{analysis_id}/status` | - | 進捗/ステップ | 404/5xx |
| API-06 | GET | `/api/v1/analysis/{analysis_id}` | - | 結果オブジェクト | 404/5xx |
| API-07 | GET | `/api/v1/analysis/completed` | skip,limit | 完了一覧 | 5xx |
| WS-01  | WS | `/ws/analysis/{analysis_id}` | - | 進捗イベント | - |

## 6. データモデル（初期案）
- Video: `id:string`, `filename`, `original_filename`, `video_type[internals|external]`, `surgery_*`, `file_path`, `duration`, `created_at`
- AnalysisResult: `id`, `video_id`, `status[pending|processing|completed|failed]`, `progress:int`, `current_step`, `skeleton_data(JSON)`, `instrument_data(JSON)`, `motion_analysis(JSON)`, `scores(JSON)`, `avg_velocity:float`, `max_velocity:float`, `total_distance:float`, `total_frames:int`, `created_at`, `completed_at`

## 7. スコープ/非スコープ
- スコープ: mp4アップロード、非同期解析、骨格/器具検出、進捗/結果API、WS進捗、SQLite保持
- 非スコープ（MVPで除外）: 認証/認可、高度なUX、長期保管/バックアップ、分散処理、外部共有

## 8. 依存関係/制約
- 言語/環境: Python 3.11（固定）、Node 20系/Next.js 15（フロント）
- ライブラリ: FastAPI, SQLAlchemy, Pydantic v2, Uvicorn, OpenCV, MediaPipe, Ultralytics
- 数値計算: `numpy<2`（OpenCV/MediaPipe互換）
- DB: SQLite ローカル、`UPLOAD_DIR=data/uploads`、`MAX_UPLOAD_SIZE=2GB`、`.mp4` のみ
- ハードウェア（暫定）: CPUで動作（GPU任意）

## 9. 受け入れ基準（AC）
- AC-01: 2GB以下mp4を受け付け `video_id` を返す（拡張子不正=400、サイズ超過=413）
- AC-02: `video_id` を与えると `analysis_id` が発行され、DBに PENDING→PROCESSING と進む
- AC-03: `/status` と WS で `current_step` と `%` を整合して返す（ステップ名: preprocessing, frame_extraction, ...）
- AC-04: 完了時 `scores` と `total_frames` が設定される（MVPは疑似スコア可）
- AC-05: `/analysis/{id}` は200で結果、未存在は404、エラーメッセージ含む
- AC-06: `/analysis/completed` は skip/limit でページング可能

## 10. リスク・未決（暫定）
- R-01: モデル精度/負荷 未確定 → 小規模データで暫定閾値決定（Owner: AI+User, Due: TBA）
- R-02: 大容量I/O ボトルネック → 分割アップロード/外部ストレージは将来検討
- R-03: 環境依存（Windows予約名等） → .gitignore対応、CI導入時にチェック
- R-04: セキュリティ（MVP） → 学内/閉域前提、公開時は認証・TLSが必要

## 11. 用語集
- 骨格検出: MediaPipeなどで人体ランドマークを抽出
- 器具検出: YOLOなどで器具のバウンディングを検出

（注）未確定箇所は今後の検証で確定させる。

