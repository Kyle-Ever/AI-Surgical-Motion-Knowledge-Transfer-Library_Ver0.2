---
title: PRD-001 AI手技モーション伝承ライブラリ�E�バチE��エンド！Eversion: 0.2
owner: Product/Tech Lead
last_updated: 2025-09-13
---

## 1. 概要E- 目樁E 手術動画から骨格・器具の動きを抽出・解析し、学翁E評価に活用できる API を提供する、E- 背景: 手技の暗黙知を客観皁E��標に変換し、教育と品質向上を図るニーズがある、E- 主用送E 教育支援、研究用途、E- 想定導�E現場: 大学/研究室、E- 成果物種別: `code`
- 関連Jira/Issue: `PRD-001`

## 2. ユースケース
| UC-ID | タイトル | 主要スチE��チE| 成功条件 |
|------|----------|--------------|----------|
| UC-01 | 動画アチE�EローチE| mp4選択�EアチE�Eロード�E保孁E| 2GB以下mp4が保存されIDが返る |
| UC-02 | 解析開姁E| 動画ID持E���E解析キュー投�E→進捗取征E| 解析IDが発行され進捗が取得できる |
| UC-03 | 進捗監要EWS) | WS接続�E進捗イベント受信 | スチE��プ名と%の更新が受信できる |
| UC-04 | 解析結果取征E| 解析ID持E���E結果取征E| 統訁E座樁Eスコアが取得できる |
| UC-05 | 自己評価�E�暫定！E| 解析結果を確認�E自己の手技評価 | スコアと主要指標を琁E��できる |
| UC-06 | 教員レビュー�E�仮説�E�E| 学生�E結果を参照→コメンチE| コメントを外部で共有（シスチE��外！E|

## 3. 機�E要件�E�ER�E�E| FR-ID | 説昁E| 関連UC | 優先度 | 受け入れ基溁EAC) |
|------|------|--------|--------|-------------------|
| FR-01 | mp4めEGBまで受け入れて保存すめE| UC-01 | High | AC-01 |
| FR-02 | 解析ジョブを起動しIDを返す | UC-02 | High | AC-02 |
| FR-03 | 解析進捁EスチE��チE%)をAPI/WSで提侁E| UC-02/03 | High | AC-03 |
| FR-04 | 骨格/器具の検�Eと簡易スコア算�E | UC-04 | High | AC-04 |
| FR-05 | 解析結果�E�統訁E座樁Eスコア�E�取征E| UC-04 | High | AC-05 |
| FR-06 | 完亁E��析�E一覧と動画メタを返す | UC-06 | Med | AC-06 |

## 4. 非機�E要件�E�EFR�E�E- 性能�E�暫定！E
  - メタ系API�E�EET /, /health, /videos 等）P95 200ms以丁E  - 同時アチE�EローチE件想定、解析�E非同期（時間�E動画長に依存！E- 可用性�E�暫定！E 学冁E研究室で 99.5% 稼働（シングルノ�Eド！E- セキュリチE���E�EVP�E�E mp4のみ許可、保存パス固定、Eenvで設定管琁E��PIIは扱わなぁE��揁E- 運用/監視！EVP�E�E ログ/例外記録、`/api/v1/health` のみ�E�監視連携は後続！E
## 5. API/インタフェース�E��E期案！E| API-ID | メソチE�� | パス | 入劁E| 出劁E| エラー |
|--------|----------|------|------|------|-------|
| API-01 | GET | `/` | - | サービス惁E�� | 5xx |
| API-02 | GET | `/api/v1/health` | - | `{ "status": "healthy" }` | 5xx |
| API-03 | POST | `/api/v1/videos/upload` | multipart mp4 + form(video_type筁E | `video_id` | 400/413/5xx |
| API-04 | POST | `/api/v1/analysis/{video_id}/analyze` | instruments, sampling_rate | `analysis_id` | 400/404/5xx |
| API-05 | GET | `/api/v1/analysis/{analysis_id}/status` | - | 進捁EスチE��チE| 404/5xx |
| API-06 | GET | `/api/v1/analysis/{analysis_id}` | - | 結果オブジェクチE| 404/5xx |
| API-07 | GET | `/api/v1/analysis/completed` | skip,limit | 完亁E��覧 | 5xx |
| WS-01  | WS | `/ws/analysis/{analysis_id}` | - | 進捗イベンチE| - |

## 6. チE�EタモチE���E��E期案！E- Video: `id:string`, `filename`, `original_filename`, `video_type[internals|external]`, `surgery_*`, `file_path`, `duration`, `created_at`
- AnalysisResult: `id`, `video_id`, `status[pending|processing|completed|failed]`, `progress:int`, `current_step`, `skeleton_data(JSON)`, `instrument_data(JSON)`, `motion_analysis(JSON)`, `scores(JSON)`, `avg_velocity:float`, `max_velocity:float`, `total_distance:float`, `total_frames:int`, `created_at`, `completed_at`

## 7. スコーチE非スコーチE- スコーチE mp4アチE�Eロード、E��同期解析、E��格/器具検�E、E��捁E結果API、WS進捗、SQLite保持
- 非スコープ！EVPで除外！E 認証/認可、E��度なUX、E��期保管/バックアチE�E、�E散処琁E��外部共朁E
## 8. 依存関俁E制紁E- 言誁E環墁E Python 3.11�E�固定）、Node 20系/Next.js 15�E�フロント！E- ライブラリ: FastAPI, SQLAlchemy, Pydantic v2, Uvicorn, OpenCV, MediaPipe, Ultralytics
- 数値計箁E `numpy<2`�E�EpenCV/MediaPipe互換�E�E- DB: SQLite ローカル、`UPLOAD_DIR=data/uploads`、`MAX_UPLOAD_SIZE=2GB`、`.mp4` のみ
- ハ�Eドウェア�E�暫定！E CPUで動作！EPU任意！E
## 9. 受け入れ基準！EC�E�E- AC-01: 2GB以下mp4を受け付け `video_id` を返す�E�拡張子不正=400、サイズ趁E��=413�E�E- AC-02: `video_id` を与えると `analysis_id` が発行され、DBに PENDING→PROCESSING と進む
- AC-03: `/status` と WS で `current_step` と `%` を整合して返す�E�スチE��プ名: preprocessing, frame_extraction, ...�E�E- AC-04: 完亁E�� `scores` と `total_frames` が設定される�E�EVPは疑似スコア可�E�E- AC-05: `/analysis/{id}` は200で結果、未存在は404、エラーメチE��ージ含む
- AC-06: `/analysis/completed` は skip/limit でペ�Eジング可能

## 10. リスク・未決�E�暫定！E- R-01: モチE��精度/負荷 未確宁EↁE小規模チE�Eタで暫定閾値決定！Ewner: AI+User, Due: TBA�E�E- R-02: 大容量I/O ボトルネック ↁE刁E��アチE�EローチE外部ストレージは封E��検訁E- R-03: 環墁E��存！Eindows予紁E��等！EↁE.gitignore対応、CI導�E時にチェチE��
- R-04: セキュリチE���E�EVP�E�EↁE学冁E閉域前提、�E開時は認証・TLSが忁E��E
## 11. 用語集
- 骨格検�E: MediaPipeなどで人体ランド�Eークを抽出
- 器具検�E: YOLOなどで器具のバウンチE��ングを検�E

�E�注�E�未確定箁E��は今後�E検証で確定させる、E

## 12. UI�f�U�C�����P�v��
- ��Ã_�b�V���{�[�h�z�F�i��CSS�j��frontend/previews�Ńv���r���[�����A���X�^�C���Ƃ̍������m�F����B
- �V�X�^�C���̓K�p�͈͂�Home/���ʃ��C�A�E�g����i�K�I�Ɍ��؂��A����p�̗L����c������B
- �f�U�C�����؊������Tailwind�ݒ�Ƌ��ʃR���|�[�l���g�֔��f����菇���܂Ƃ߂�B
