---
title: タスク生成規則（Vibe Coding 3-File System / 02）
version: 1.0
owner: Tech Lead/PM
last_updated: 2025-09-08
---

# 目的
合意済みPRDから、実装可能な**チェックリスト型タスク**へ自動分解し、進捗可視化と品質一貫性を担保する。

# 入力
- `01_prd_generation_rules.md`で作成・合意済みのPRD
- プロジェクトのリポジトリ構成/ブランチ戦略/CIルール

# 出力（tasks.md）
- Markdownのチェックボックスとメタ情報（ID、依存、AC、見積、責任、トレース）

# 分解原則
1. 粒度は**15〜90分/タスク**を目安（超える場合は分割）。
2. **1タスク=1成果物**（テスト/ドキュメント含む）。
3. すべてのタスクが**PRDのID（FR/NFR/AC）**へトレース可能。
4. 各タスクには**完了条件（AC）**と**検証手順**を必ず付与。
5. 依存関係を明示し、並行実行可能部分を抽出。

# 生成アルゴリズム（AI手順）
1. PRDを解析し、**ユースケース→機能→API/データ→テスト→運用**の順に候補列挙。
2. 各候補を15〜90分に調整し、**依存**と**前後関係**を付与。
3. 各タスクに**受け入れ基準**と**検証コマンド**を記述。
4. 並行可能なタスクを**フェーズ/スイムレーン**に整理。
5. チェックリスト（Markdown）を出力し、最初の実行候補（Top-3）を提案。

# tasks.md テンプレート（出力フォーマット）
## フェーズA: 設計・下準備
- [ ] **T-001**: 開発ブランチ/CIの初期設定  
  - Owner: AI  
  - Depends: なし  
  - Estimate: 30m  
  - Traces: NFR-運用, AC-ログ収集  
  - Deliverables: `.github/workflows/ci.yml`  
  - Acceptance: `PRが作成され、CIが成功すること`
  - Verify: `git push`後にCIが成功

## フェーズB: 機能実装
- [ ] **T-010**: API-01 ハンドラの追加  
  - Owner: AI  
  - Depends: T-001  
  - Estimate: 60m  
  - Traces: FR-01, API-01, AC-01  
  - Deliverables: `src/api/v1/handler.ts`  
  - Acceptance: `UC-01の成功条件を満たす200応答`  
  - Verify: `npm test api/api01.spec.ts`

## フェーズC: テスト
- [ ] **T-020**: UC-01 E2Eテスト  
  - Owner: AI  
  - Depends: T-010  
  - Estimate: 45m  
  - Traces: UC-01, AC-01  
  - Deliverables: `e2e/uc01.spec.ts`  
  - Acceptance: `P95 200ms以下で成功`  
  - Verify: `npm run e2e`

## フェーズD: ドキュメント/運用
- [ ] **T-030**: README更新（セットアップ/実行/テスト）  
  - Owner: AI  
  - Depends: T-010, T-020  
  - Estimate: 20m  
  - Traces: NFR-運用  
  - Deliverables: `README.md`  
  - Acceptance: `新規開発者が15分で環境構築できる`  
  - Verify: 手順検証

# メタデータ記法
- **Owner**: `AI | User | Pair(AI+User)`
- **Estimate**: `Xm`（分）
- **Traces**: `FR/NFR/UC/API/AC`のID列挙
- **Depends**: 先行タスクID列挙

# 品質チェック（AI自己点検）
- [ ] すべてのタスクに**Deliverables/Acceptance/Verify**がある
- [ ] すべてのタスクが**PRDのID**にトレースされる
- [ ] 90分超タスクは分割済み
- [ ] 並列可能な束を明示
- [ ] 最初に着手すべきTop-3が提案されている

# 出力規約
- 形式は**Markdownチェックリスト**のみ。
- 追加の背景説明は**別ファイル**（PRD）を参照。
