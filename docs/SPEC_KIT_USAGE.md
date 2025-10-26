# Spec-Kit 使用ガイド

## 概要

**Spec-Kit**は、仕様駆動開発（Spec-Driven Development: SDD）のためのオープンソースツールキットです。
従来のコード中心の開発を反転させ、**仕様を実行可能な成果物**として扱い、そこからコードを生成します。

**公式リポジトリ**: https://github.com/github/spec-kit

## インストール状況

✅ **インストール完了**:
- リポジトリクローン: `~/.claude/spec-kit/`
- CLI ツール: `specify` コマンド（uv tool経由）

```bash
# インストール確認
specify --help  # ⚠️ Windows日本語環境でUnicodeエラー発生の可能性あり
```

## Spec-Driven Development（SDD）とは？

### 従来の開発との違い

| 従来の開発 | Spec-Driven Development |
|-----------|------------------------|
| コードが「真実の源泉」 | 仕様が「真実の源泉」 |
| 仕様 → コード（手動実装） | 仕様 → コード（自動生成） |
| 仕様は「ガイド」 | 仕様は「実行可能」 |
| コード変更 → 仕様が陳腐化 | 仕様変更 → コード再生成 |

### 核心理念

1. **仕様が共通言語（Lingua Franca）**
   - 仕様が主要な成果物
   - コードは特定の言語/フレームワークでの「表現」

2. **実行可能な仕様**
   - 曖昧さのない、完全な仕様
   - AIが動作するシステムを生成可能

3. **継続的改善**
   - AIによる仕様の曖昧性・矛盾・ギャップの継続分析

4. **リサーチ駆動コンテキスト**
   - 技術オプション、パフォーマンス、組織制約の調査

5. **双方向フィードバック**
   - 本番環境のメトリクス・インシデントが仕様の改善に反映

## 開発フロー

### ステップ1: プロジェクト初期化

```bash
# プロジェクト作成
specify init <PROJECT_NAME>

# または、一時実行
uvx --from git+https://github.com/github/spec-kit.git specify init <PROJECT_NAME>
```

### ステップ2: プロジェクト憲法の確立

AI assistantで `/speckit.constitution` コマンドを使用:

```markdown
/speckit.constitution Create principles focused on code quality,
testing standards, user experience consistency, and performance requirements
```

**生成される内容**:
- コード品質基準
- テスト標準
- UX一貫性ガイドライン
- パフォーマンス要件

### ステップ3: 仕様の作成

`/speckit.specify` コマンドで「何を」「なぜ」を記述（技術スタックではない）:

```markdown
/speckit.specify Build an application that analyzes surgical videos
to track hand movements and instrument positions. The system should
calculate motion efficiency metrics and compare with reference videos.

Key requirements:
- Support 1GB video files (.mp4)
- Real-time progress updates via WebSocket
- Motion metrics: path length, smoothness, duration
- Comparison with gold-standard references
```

**生成される仕様ファイル**:
- 機能要件
- 非機能要件
- ユーザーストーリー
- 受け入れ基準

### ステップ4: 実装計画の作成

`/speckit.plan` コマンドで技術的な実装計画を生成:

```markdown
/speckit.plan Create implementation plan for the surgical video analysis application
```

**生成される計画**:
- アーキテクチャ設計
- 技術スタック選択（根拠付き）
- データモデル定義
- API エンドポイント設計
- セキュリティ考慮事項

### ステップ5: タスク分解

`/speckit.tasks` コマンドで実装計画を具体的なタスクに分解:

```markdown
/speckit.tasks Break down the implementation plan into concrete development tasks
```

**生成されるタスク**:
- データベーススキーマ作成
- API エンドポイント実装
- フロントエンドコンポーネント開発
- AI処理パイプライン構築
- テスト作成

### ステップ6: 実装

`/speckit.implement` コマンドでタスクを実装:

```markdown
/speckit.implement Task 1: Create database schema for video metadata
```

## プロジェクト固有の使用例

### 例1: 新機能の追加（視線解析）

```markdown
# ステップ1: 仕様更新
/speckit.specify Add eye gaze analysis feature to the surgical video analysis system.

Requirements:
- Track surgeon's gaze points during procedure
- Generate heatmap of attention areas
- Compare gaze patterns with expert references
- Real-time gaze visualization

# ステップ2: 実装計画
/speckit.plan Create implementation plan for eye gaze analysis feature

# ステップ3: タスク分解
/speckit.tasks Break down gaze analysis implementation

# ステップ4: 実装
/speckit.implement Task 1: Integrate DeepGaze III model
/speckit.implement Task 2: Create gaze heatmap generation service
/speckit.implement Task 3: Build real-time visualization component
```

### 例2: アーキテクチャ変更（マイクロサービス化）

```markdown
# 現状の仕様を確認
specify check

# 新しいアーキテクチャ仕様を作成
/speckit.specify Refactor the monolithic backend into microservices:
- Video Processing Service (frame extraction, storage)
- AI Analysis Service (skeleton, instrument, gaze detection)
- Scoring Service (metrics calculation, comparison)
- API Gateway (request routing, authentication)

# 実装計画生成
/speckit.plan Create migration plan to microservices architecture

# 段階的な移行タスク
/speckit.tasks Generate phased migration tasks with rollback strategies
```

### 例3: パフォーマンス最適化

```markdown
# パフォーマンス要件を仕様に追加
/speckit.specify Update performance requirements:
- Frame extraction: < 30 seconds for 5-minute video
- Skeleton detection: < 2 minutes for 300 frames
- WebSocket updates: < 500ms latency
- Concurrent analysis: Support 10 simultaneous uploads

# 最適化実装計画
/speckit.plan Create performance optimization plan

# 具体的な最適化タスク
/speckit.tasks Generate optimization tasks:
- Parallel frame processing
- GPU acceleration for AI models
- Database query optimization
- Caching strategies
```

### 例4: セキュリティ強化

```markdown
# セキュリティ要件を仕様に追加
/speckit.specify Enhance security requirements:
- User authentication with JWT
- Role-based access control (Admin, Doctor, Student)
- Video encryption at rest and in transit
- Audit logging for all analysis operations
- GDPR compliance for patient data

# セキュリティ実装計画
/speckit.plan Create security enhancement implementation plan

# セキュリティタスク
/speckit.tasks Break down security implementation
```

## Spec-Kitのディレクトリ構造

```
~/.claude/spec-kit/
├── README.md              # プロジェクト概要
├── spec-driven.md         # SDD理論と哲学
├── AGENTS.md              # AI Agent統合ガイド
├── templates/             # 仕様・計画テンプレート
│   ├── constitution/
│   ├── specify/
│   ├── plan/
│   └── tasks/
├── scripts/               # 自動化スクリプト
├── docs/                  # 詳細ドキュメント
└── src/                   # CLI ソースコード
```

## `/speckit.*` コマンド一覧

| コマンド | 目的 | 入力 | 出力 |
|---------|------|------|------|
| `/speckit.constitution` | プロジェクト原則確立 | 品質・テスト・UX要件 | 憲法ドキュメント |
| `/speckit.specify` | 仕様作成 | 機能要件（自然言語） | 構造化仕様 |
| `/speckit.plan` | 実装計画 | 仕様ドキュメント | 技術設計書 |
| `/speckit.tasks` | タスク分解 | 実装計画 | タスクリスト |
| `/speckit.implement` | 実装 | 特定のタスク | コード |

## ベストプラクティス

### ✅ 推奨

1. **仕様ファースト**: コードを書く前に仕様を完成させる
2. **バージョン管理**: 仕様・計画をGitで管理
3. **ブランチ戦略**: 仕様変更は専用ブランチで作成
4. **レビュープロセス**: 仕様のチームレビューを実施
5. **継続的改善**: 本番環境のフィードバックを仕様に反映

### ❌ 避けるべき

1. **仕様なしでコーディング**: 「とりあえず動かす」コードは避ける
2. **仕様と実装の乖離**: コード変更後に仕様を更新しない
3. **技術の先行決定**: 仕様前に技術スタックを固定
4. **一度きりの仕様**: 書いて終わりではなく、継続的に進化させる

## トラブルシューティング

### Q1: specify コマンドがUnicodeエラーで動作しない

**症状**: Windows日本語環境で `UnicodeEncodeError: 'cp932'` エラー

**解決策**:
```bash
# オプション1: PowerShell のエンコーディング変更
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# オプション2: 環境変数設定
set PYTHONIOENCODING=utf-8

# オプション3: Claude Code内で `/speckit.*` コマンドを直接使用（推奨）
```

### Q2: `/speckit.*` コマンドが認識されない

**症状**: AI assistantがコマンドを理解しない

**解決策**:
1. `specify init <PROJECT>` を実行してプロジェクト初期化
2. プロジェクトディレクトリ内でAI assistantを起動
3. `.speckit/` ディレクトリが存在することを確認

### Q3: 生成されたコードが仕様と一致しない

**症状**: 実装が仕様の意図と異なる

**解決策**:
1. `/speckit.plan` で実装計画を再確認
2. 仕様の曖昧な部分を明確化
3. `/speckit.specify` で仕様を更新
4. `/speckit.plan` で計画を再生成
5. `/speckit.implement` で再実装

## プロジェクトへの統合

### 既存プロジェクトへの適用

```bash
# 1. プロジェクトルートで初期化
cd "C:\Users\ajksk\Desktop\Dev\AI Surgical Motion Knowledge Transfer Library_Ver0.2"
specify init surgical-motion-library

# 2. 既存コードから仕様を抽出
/speckit.specify Extract specification from existing codebase:
- Review backend_experimental/app/services/
- Review frontend/components/
- Document current features and architecture

# 3. 憲法を確立
/speckit.constitution Establish development principles based on:
- Python 3.11 requirement
- FastAPI + Next.js stack
- AI processing pipeline architecture
- Testing standards (Playwright E2E)

# 4. 新機能は仕様駆動で追加
/speckit.specify [新機能の要件]
/speckit.plan [実装計画]
/speckit.tasks [タスク分解]
/speckit.implement [実装]
```

## 参考リンク

- [公式リポジトリ](https://github.com/github/spec-kit)
- [公式ドキュメント](https://github.github.io/spec-kit/)
- [Spec-Driven Development 理論](~/.claude/spec-kit/spec-driven.md)
- [AGENTS.md](~/.claude/spec-kit/AGENTS.md) - AI Agent統合ガイド

## 更新履歴

- **2025-10-25**: 初版作成、Spec-Kitインストールと統合完了
