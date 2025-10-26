# Claude Skills 使用ガイド

## 概要

このプロジェクトでは、[Anthropic公式Claude Skills](https://github.com/anthropics/skills)を統合しています。
スキルは、特定のタスクに特化した指示、スクリプト、リソースのフォルダーで、Claudeが動的にロードして専門タスクのパフォーマンスを向上させます。

## インストール状況

✅ **インストール完了**: 全てのスキルが `~/.claude/skills/` にクローン済み

```
~/.claude/
├── CLAUDE.md          # SuperClaude エントリーポイント（@SKILLS.md参照を含む）
├── SKILLS.md          # スキルインデックスファイル（新規作成）
└── skills/            # 公式スキルリポジトリ（クローン済み）
    ├── document-skills/
    ├── mcp-builder/
    ├── webapp-testing/
    ├── artifacts-builder/
    └── [その他のスキル...]
```

## 利用可能なスキル一覧

### 📄 Document Skills（ドキュメント処理）

| スキル | 用途 | 参照パス |
|--------|------|----------|
| **PDF** | PDF抽出、作成、結合、分割、フォーム処理 | `@skills/document-skills/pdf/SKILL.md` |
| **DOCX** | Word文書の作成、編集、解析 | `@skills/document-skills/docx/SKILL.md` |
| **XLSX** | Excel処理、データ分析、グラフ作成 | `@skills/document-skills/xlsx/SKILL.md` |
| **PPTX** | PowerPoint作成、編集、自動化 | `@skills/document-skills/pptx/SKILL.md` |

### 🛠️ Development & Technical Skills

| スキル | 用途 | 参照パス |
|--------|------|----------|
| **MCP Builder** | Model Context Protocol サーバー構築 | `@skills/mcp-builder/SKILL.md` |
| **WebApp Testing** | Playwright による Webアプリ自動テスト | `@skills/webapp-testing/SKILL.md` |
| **Artifacts Builder** | Claude.ai HTMLアーティファクト構築 | `@skills/artifacts-builder/SKILL.md` |

### 🎨 Creative & Design Skills

| スキル | 用途 | 参照パス |
|--------|------|----------|
| **Algorithmic Art** | p5.js ジェネレーティブアート | `@skills/algorithmic-art/SKILL.md` |
| **Canvas Design** | ビジュアルアート（PNG/PDF） | `@skills/canvas-design/SKILL.md` |
| **Slack GIF Creator** | Slack用GIFアニメーション | `@skills/slack-gif-creator/SKILL.md` |

### 💼 Enterprise & Communication Skills

| スキル | 用途 | 参照パス |
|--------|------|----------|
| **Brand Guidelines** | ブランドガイドライン適用 | `@skills/brand-guidelines/SKILL.md` |
| **Internal Comms** | 社内コミュニケーション文書 | `@skills/internal-comms/SKILL.md` |
| **Theme Factory** | プロフェッショナルテーマ生成 | `@skills/theme-factory/SKILL.md` |

### 🧰 Meta Skills

| スキル | 用途 | 参照パス |
|--------|------|----------|
| **Skill Creator** | カスタムスキル作成ガイド | `@skills/skill-creator/SKILL.md` |
| **Template Skill** | 新規スキル作成テンプレート | `@skills/template-skill/SKILL.md` |

## 使用方法

### 基本的な使い方

スキルを使用するには、以下の3つの方法があります：

#### 1. 明示的なスキル参照

```markdown
@skills/webapp-testing/SKILL.md を使用して、
フロントエンド（Port 3000）のPlaywrightテストを作成してください。
```

#### 2. スキル名での指定

```markdown
Use the PDF skill to extract text from backend_experimental/docs/api_spec.pdf
```

#### 3. 暗黙的な適用（自動）

特定のタスクを要求すると、関連するスキルが自動的に適用される場合があります。

### プロジェクト固有の使用例

#### 例1: E2Eテストの作成

```markdown
@skills/webapp-testing/SKILL.md を参照して、
以下のシナリオをテストするPlaywrightスクリプトを作成してください：

1. 動画アップロード（Port 3000）
2. 解析開始（Backend Port 8001）
3. WebSocket進捗確認
4. 結果表示の検証
```

**期待される出力**:
- `scripts/with_server.py` を使用した複数サーバー起動
- Playwright自動化スクリプト
- スクリーンショット取得とDOM検証

#### 例2: 技術ドキュメントのPDF化

```markdown
@skills/document-skills/pdf/SKILL.md を使用して、
docs/ ディレクトリの設計ドキュメント（Markdown）を
PDFに変換してください。目次と見出しを含めてください。
```

**期待される出力**:
- `reportlab` を使用したPDF生成スクリプト
- Markdownパース処理
- 目次とページ番号付きPDF

#### 例3: AI解析API用MCPサーバー

```markdown
@skills/mcp-builder/SKILL.md を参照して、
backend_experimental/app/api/routes/analysis.py の
解析APIをMCPサーバーとして公開してください。

要件:
- 解析開始、状態確認、結果取得ツール
- WebSocket進捗監視
- エラーハンドリングとリトライ
```

**期待される出力**:
- Python FastMCP実装
- Pydantic入力検証
- 包括的なツールドキュメント
- 評価ハーネス（10問のテスト）

#### 例4: データベース内容のExcel出力

```markdown
@skills/document-skills/xlsx/SKILL.md を使用して、
backend_experimental/aimotion.db のanalysesテーブルを
Excelファイルに出力してください。

要件:
- 各列の適切なフォーマット
- 日時列の人間可読形式
- ステータス別の色分け
- グラフ（解析成功/失敗の割合）
```

**期待される出力**:
- SQLiteからデータ読み取り
- `openpyxl` または `xlsxwriter` でExcel作成
- 条件付き書式とグラフ

## 高度な使用例

### 複数スキルの組み合わせ

```markdown
以下の手順でレポートを作成してください：

1. @skills/webapp-testing/SKILL.md でE2Eテスト実行
2. 結果をスクリーンショット取得
3. @skills/document-skills/pptx/SKILL.md でプレゼン作成
   - テスト結果サマリー
   - スクリーンショット挿入
   - 問題点と改善提案
```

### カスタムスキルの作成

```markdown
@skills/skill-creator/SKILL.md と @skills/template-skill/SKILL.md を参照して、
「外科手術動画解析レポート作成」スキルを作成してください。

機能:
- 解析結果JSONからメトリクス抽出
- グラフとチャート生成
- PDF形式でレポート出力
```

## トラブルシューティング

### Q1: スキルが認識されない

**症状**: `@skills/...` 参照がエラーになる

**解決策**:
1. `~/.claude/skills/` ディレクトリが存在するか確認
2. `~/.claude/CLAUDE.md` に `@SKILLS.md` 参照があるか確認
3. Claude Codeを再起動

### Q2: スキルのスクリプトが実行できない

**症状**: `scripts/with_server.py` などのスクリプトエラー

**解決策**:
1. スクリプトに実行権限を付与（Linux/Mac: `chmod +x scripts/*.py`）
2. 必要な依存関係をインストール（`pip install playwright pdfplumber reportlab`）
3. `--help` で使用方法を確認してから実行

### Q3: Document Skillsがうまく動作しない

**症状**: PDF/Excel/Word処理でエラー

**解決策**:
```bash
# Python依存関係インストール
pip install pypdf pdfplumber reportlab python-docx openpyxl python-pptx

# Playwrightブラウザインストール（WebApp Testingの場合）
playwright install chromium
```

## ベストプラクティス

### ✅ 推奨

1. **スキル参照は明示的に**: `@skills/...` 形式で明確に指定
2. **--help を活用**: スクリプトは必ず `--help` で使用方法を確認
3. **エラーハンドリング**: スキルのガイドラインに従った堅牢な実装
4. **ドキュメント化**: スキル使用結果を `claudedocs/` に記録

### ❌ 避けるべき

1. **スクリプトのコンテキスト汚染**: スクリプトは「ブラックボックス」として使用（ソースを読まない）
2. **依存関係の仮定**: 必要なライブラリは事前確認とインストール
3. **パス指定の曖昧さ**: 絶対パスまたはプロジェクトルートからの相対パスを使用

## 参考リンク

- [公式スキルリポジトリ](https://github.com/anthropics/skills)
- [スキルとは？（公式ドキュメント）](https://support.claude.com/en/articles/12512176-what-are-skills)
- [スキルの使用方法](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [カスタムスキルの作成](https://support.claude.com/en/articles/12512198-creating-custom-skills)
- [Agent Skills技術記事](https://anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

## 更新履歴

- **2025-10-25**: 初版作成、全スキルのインストールと統合完了
