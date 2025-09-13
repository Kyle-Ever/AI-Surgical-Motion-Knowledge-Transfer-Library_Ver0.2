---
title: PRD-001 AI手技モーション伝承ライブラリ（バックエンド）
version: 0.1
owner: Product/Tech Lead
last_updated: 2025-09-13
---

## 1. 概要
- 目標: 手術動画から骨格・器具の動きを抽出・解析し、学習/評価に活用できるAPIを提供する。
- 背景: 手技の暗黙知を客観的指標に変換し、教育と品質向上を図るニーズがある。
- 成果物種別: `code`
- 関連Jira/Issue: `PRD-001`

## 2. ユースケース
| UC-ID | タイトル | 主要ステップ | 成功条件 |
|-------|----------|--------------|----------|
| UC-01 | 動画アップロード | mp4選択→アップロード→保存 | 2GB以下mp4が保存されIDが返る |
| UC-02 | 解析開始 | 動画ID指定→解析キュー投入→進捗取得 | 解析IDが発行され進捗が取得できる |
| UC-03 | 進捗監視(WS) | WS接続→進捗イベントを受信 | 適切なステップ/進捗率が受信できる |
| UC-04 | 解析結果取得 | 解析ID指定→結果取得 | 統計/座標/スコア等が取得できる |
| UC-05 | 解析済み一覧 | 完了解析の一覧取得 | ページング可能な一覧が取得できる |

## 3. 機能要件（FR）
| FR-ID | 説明 | 関連UC | 優先度 | 受け入れ基準(AC) |
|-------|------|--------|--------|-------------------|
| FR-01 | mp4ファイルを2GBまで受け入れて保存する | UC-01 | High | AC-01 |
| FR-02 | 解析ジョブを起動しIDを返す | UC-02 | High | AC-02 |
| FR-03 | 解析進捗(ステップ/%)をAPI/WSで提供 | UC-02/03 | High | AC-03 |
| FR-04 | 骨格/器具の検出と簡易スコア算出 | UC-04 | High | AC-04 |
| FR-05 | 解析結果（統計/座標/スコア）を取得可能 | UC-04 | High | AC-05 |
| FR-06 | 完了解析の一覧と動画メタを返す | UC-05 | Med | AC-06 |

## 4. 非機能要件（NFR）
- 性能: P95 レイテンシ 200ms以下（メタ系API）。重処理は非同期バッチ。
- 可用性: 稼働率 99.9%（学内/研究用途想定、未確定）。
- セキュリティ: mp4のみ許可、アップロードディレクトリ分離、.envで機密管理。
- 運用/監視: ログ出力、例外ハンドリング、簡易ヘルスチェック `/api/v1/health`。

## 5. API/インタフェース（初期案）
| API-ID | メソッド | パス | 入力 | 出力 | エラー |
|--------|----------|------|------|------|-------|
| API-01 | GET | `/` | - | サービス情報 | 5xx |
| API-02 | GET | `/api/v1/health` | - | `{"status":"healthy"}` | 5xx |
| API-03 | POST | `/api/v1/videos/upload`(想定) | multipart mp4 | `video_id` | 400/413/5xx |
| API-04 | POST | `/api/v1/analysis/{video_id}/analyze` | instruments, sampling_rate | `analysis_id` | 400/404/5xx |
| API-05 | GET | `/api/v1/analysis/{analysis_id}/status` | - | 進捗/ステップ | 404/5xx |
| API-06 | GET | `/api/v1/analysis/{analysis_id}` | - | 結果オブジェクト | 404/5xx |
| API-07 | GET | `/api/v1/analysis/completed` | skip,limit | 完了一覧 | 5xx |
| WS-01  | WS | `/ws/analysis/{analysis_id}` | - | 進捗イベント | - |

## 6. データモデル（初期案）
- Video: `id:string`, `file_path:string`, `video_type:string(未確定)`, `created_at`
- AnalysisResult: `id`, `video_id`, `status[pending|processing|completed|failed]`, `progress:int`, `current_step`, `skeleton_data(JSON)`, `instrument_data(JSON)`, `motion_analysis(JSON)`, `scores(JSON)`, `avg_velocity:float`, `max_velocity:float`, `total_distance:float`, `total_frames:int`, `coordinate_data(JSON,互換)`, `created_at`, `completed_at`

## 7. スコープ/非スコープ
- スコープ: mp4アップロード、非同期解析、骨格/器具検出、進捗/結果API、WS進捗、SQLite保持
- 非スコープ: ユーザー管理、閲覧UI（フロント別途）、長期保管/バックアップ、分散スケジューラ

## 8. 依存関係/制約
- Python 3.11、FastAPI、SQLAlchemy、Pydantic v2、Uvicorn
- OpenCV, MediaPipe, Ultralytics(YOLO) 利用。`numpy<2` を維持
- SQLite ローカルDB、`UPLOAD_DIR=data/uploads`、`MAX_UPLOAD_SIZE=2GB`、`.mp4` のみ

## 9. 受け入れ基準（AC）
- AC-01: 2GB以下mp4を受け付け、`video_id` を返す。その他拡張子は拒否
- AC-02: `video_id` を与えると `analysis_id` が発行されDBへPENDING→PROCESSING登録
- AC-03: `/status` と WS で段階的な `current_step` と `%` が観測できる
- AC-04: 解析完了で `scores` と `total_frames` が設定される（疑似でも許容）
- AC-05: `/analysis/{id}` で結果オブジェクトが取得できる（404は未登録）
- AC-06: `/analysis/completed` がページングで完了レコードを返す

## 10. リスク・未決
- R-01: モデル精度・推論負荷は未確定 → データセット準備/閾値調整の検証計画を別途作成
- R-02: 大容量ファイルI/Oのボトルネック → ストレージ/分割アップロードは将来課題
- R-03: Windows環境依存（予約名`nul`等） → .gitignore対応済、CIで検出を検討

## 11. 用語集
- 骨格検出: MediaPipeなどで人体ランドマークを抽出
- 器具検出: YOLOなどで器具のバウンディングを検出

（注）未確定箇所は今後の検証で確定させる。

