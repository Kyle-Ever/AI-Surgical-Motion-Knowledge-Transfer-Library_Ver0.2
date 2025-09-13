# 開発エージェント運用ルール（本リポジトリ専用）

この AGENTS.md は本リポジトリ配下すべてに適用されます。開発・コーディング時は、必ず `docs/Rules` のルール群を参照し、それに従って作業してください。

参照ルール（常時遵守）
- PRD作成: `docs/Rules/01_prd_generation_rules.md`
- タスク化: `docs/Rules/02_task_generation_rules.md`
- 実行手順: `docs/Rules/03_task_execution_rules.md`

上記は「PRD → タスク化 → 実行」という三段階の運用を規定します。小さな修正（明確なバグ修正、コメント微調整、CI設定の微修正など）を除き、原則この順序で進めます。

## ワークフロー（厳守）

1) PRD（合意形成）
- 新規機能や仕様変更は、まず PRD テンプレートに沿って作成・合意します。
- 質問事項（背景/スコープ/非スコープ/受け入れ基準など）が未確定の場合は「未確定」と明記し、仮説を提示します。

2) タスク分解（tasks.md）
- PRD の ID（UC/FR/NFR/API/AC 等）へ必ずトレース可能にします。
- 粒度は15〜90分を目安。「1タスク=1成果物」を原則とします。
- 各タスクに Deliverables / Acceptance(AC) / Verify（検証手順）を必須で記載します。

3) 実行（One-Task-At-A-Time）
- 着手前に「Plan / Files / Test / Risk」を簡潔に提示し、ユーザー承認を得てから実行します。
- 変更は最小差分（diff）で提示。副作用のある変更は分割します。
- 実行後は検証結果を提示し、AC 充足を明記。無断で次タスクへ進みません。

## 本リポジトリの技術・運用方針

- 言語/環境
  - Backend: Python 3.11（`backend/venv`）。FastAPI + SQLAlchemy + Pydantic v2。
  - 依存: OpenCV / MediaPipe 利用のため `numpy<2` を維持。
  - DB: SQLite（`backend/aimotion.db`）。バイナリはコミットしません。

- 実行・検証
  - バックエンド起動: `start_backend.bat`（初回に venv 作成と依存導入）。
  - 版数確認: `backend/_check_versions.py`。
  - アプリ import 確認: `backend/_import_app.py`（FastAPI アプリが読み込めること）。
  - ヘルスチェック（任意）: `backend/_healthcheck.py`（必要なら `httpx` を追加）。

- コーディング規約
  - 既存の構成・命名を尊重し、変更は最小限に留めます。
  - 無関係な修正・リファクタは行いません（必要なら別タスク化）。
  - 文字コードは UTF-8 を推奨。ログ/UI文言は既存の表記・言語に合わせます。

- Git/ファイル運用
  - `venv/`, `.env`, `aimotion.db`, `data/uploads`, `data/temp` はコミット禁止。
  - Windows 予約名によるファイル（例: `backend/nul`）は Git 対象外とし、追加しないでください。
  - 小さな論理単位でコミットし、明確なメッセージを付与します。

## このファイルの優先度

この AGENTS.md は本リポジトリ全体に適用され、同階層以下の作業で必ず参照されます。上位の直接指示（ユーザー/開発者メッセージ）がある場合はそれを優先します。`docs/Rules` の内容更新があれば、それに追随します。

