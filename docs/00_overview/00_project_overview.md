# プロジェクトドキュメント概要 - AI Surgical Motion Knowledge Transfer Library

## 📚 ドキュメント体系について

このドキュメント体系は、Claude Codeとの効率的な協働開発を前提に設計されています。
各ドキュメントは明確な責任範囲を持ち、開発時の迷いや判断ミスを最小限に抑えることを目的としています。

## 🗺️ ドキュメント構成マップ

```
docs/
├── 00_overview/              # プロジェクト概要とクイックスタート
│   └── 00_project_overview.md  ← 【現在地】まずはここから
│
├── 01_architecture/          # システム設計の骨格
│   └── 01_architecture_design.md  # なぜこの設計か、各レイヤーの責任
│
├── 02_database/              # データ構造の定義
│   └── 02_database_design.md      # テーブル設計、リレーション、命名規則
│
├── 03_api/                   # API仕様
│   └── 03_api_design.md           # エンドポイント、レスポンス形式、エラー体系
│
├── 04_frontend/              # フロントエンド設計
│   └── 04_frontend_design.md      # コンポーネント、状態管理、型定義
│
├── 05_ui_design/             # デザインシステム（作成予定）
│   ├── design_principles.md       # カラー、タイポグラフィ、スペーシング
│   └── component_catalog.md       # UIコンポーネントカタログ
│
├── 06_development/           # 開発ガイド
│   └── 06_development_setup.md    # 環境構築、コマンド、トラブルシューティング
│
├── 07_testing/               # テスト戦略（作成予定）
│   └── test_strategy.md           # テスト方針、カバレッジ目標
│
├── 08_security/              # セキュリティ（作成予定）
│   └── security_guidelines.md     # セキュリティ要件、ベストプラクティス
│
├── 09_performance/           # パフォーマンス（作成予定）
│   └── performance_targets.md     # 目標値、最適化戦略
│
└── 10_deployment/            # デプロイメント（作成予定）
    └── deployment_guide.md        # CI/CD、環境別設定
```

## 🎯 各ドキュメントの役割

### コア設計ドキュメント（必読）

| ドキュメント | 用途 | Claude Codeへの指示例 |
|------------|------|---------------------|
| **01_architecture_design.md** | システム全体の設計思想 | 「新しいサービスはどのレイヤーに配置すべき？」 |
| **02_database_design.md** | データモデルとDB設計 | 「新しいテーブルを追加する際の命名規則は？」 |
| **03_api_design.md** | API仕様と規約 | 「エラーレスポンスの形式に従って実装して」 |
| **04_frontend_design.md** | フロントエンド構成 | 「コンポーネントの配置場所と責任範囲は？」 |
| **06_development_setup.md** | 開発環境構築 | 「Python 3.11の仮想環境でセットアップして」 |

### 補足ドキュメント（随時参照）

- **既存ドキュメント**: `docs/`直下の既存ファイル（移行予定）
- **PRD（Product Requirements Document）**: `docs/PRD/`
- **ルール**: `docs/Rules/`

## 🚀 クイックスタート for Claude Code

### 1. 新機能を追加する場合
```
1. 01_architecture_design.md → レイヤー配置を確認
2. 02_database_design.md → 必要なテーブル変更を確認
3. 03_api_design.md → API設計規約に従って実装
4. 04_frontend_design.md → コンポーネント設計に従って実装
```

### 2. バグ修正の場合
```
1. エラーの種類を特定
2. 該当レイヤーの設計書を確認
3. 設計原則に従って修正
```

### 3. リファクタリングの場合
```
1. 01_architecture_design.md → 設計原則を確認
2. 各レイヤーの責任範囲を維持しながら改善
```

## 💡 Claude Codeとの効果的な対話例

### 良い例 ✅
```
「03_api_design.mdのエラーレスポンス形式に従って、
新しいエンドポイント /api/v1/metrics を追加してください。
レスポンスは統一形式で、ページネーション対応でお願いします。」
```

### 悪い例 ❌
```
「APIを追加して」
→ 設計規約が不明確で、一貫性のない実装になる可能性
```

## 📊 プロジェクト現状

### 実装済み機能
- ✅ 動画アップロード（最大2GB、.mp4形式）
- ✅ AI分析（MediaPipe、YOLOv8、SAM）
- ✅ メトリクス計算（速度、滑らかさ、安定性）
- ✅ リファレンス動画との比較
- ✅ リアルタイム進捗表示（WebSocket）

### 開発中機能
- 🔄 スコアリング比較UI
- 🔄 高度なフィードバック生成
- 🔄 3Dビジュアライゼーション

### 今後の計画
- 📅 認証・認可システム
- 📅 マルチユーザー対応
- 📅 クラウドデプロイメント
- 📅 リアルタイムストリーミング分析

## 🔧 重要な技術的制約

### Python バージョン
```
⚠️ 必ずPython 3.11.9を使用
❌ Python 3.13は MediaPipe/OpenCV との互換性問題あり
```

### 開発環境の起動
```bash
# 推奨: 両サーバー同時起動
start_both.bat

# 個別起動も可能
cd backend && ./venv311/Scripts/python.exe -m uvicorn app.main:app --reload
cd frontend && npm run dev
```

## 📝 ドキュメント更新ガイドライン

### ドキュメントを更新すべきタイミング
1. **新機能追加時**: 設計書に機能を追加
2. **破壊的変更時**: 影響範囲を明記
3. **設計方針変更時**: 理由と新方針を記載
4. **重大なバグ修正時**: 原因と対策を記録

### 更新時の注意点
- 日付を記載（最終更新日）
- 変更理由を明確に
- Claude Codeが理解しやすい具体例を含める
- 既存の命名規則と形式を維持

## 🎓 学習リソース

### プロジェクト固有の知識
- [POST_MORTEM_FILE_UPLOAD_BUTTON.md](../POST_MORTEM_FILE_UPLOAD_BUTTON.md) - UIコンポーネントの実装教訓
- [github-setup.md](../github-setup.md) - Git/GitHub運用ルール

### 外部リソース
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [MediaPipe Solutions](https://developers.google.com/mediapipe)
- [Ultralytics YOLOv8](https://docs.ultralytics.com/)

## 🤝 コントリビューション

このドキュメント体系は継続的に改善されています。
以下の観点でフィードバックをお願いします：

1. **明確性**: 説明が分かりにくい箇所
2. **完全性**: 不足している情報
3. **実用性**: 実際の開発で役立たない部分
4. **一貫性**: 矛盾や不整合

---

## 📌 Next Steps

1. **初めての方**: `06_development_setup.md` から開始
2. **機能追加**: `01_architecture_design.md` を確認
3. **API開発**: `03_api_design.md` を参照
4. **UI開発**: `04_frontend_design.md` を参照

> 💡 **Tips**: CLAUDE.mdにこれらのドキュメントへの参照が追加されているため、
> Claude Codeは常にこれらの設計原則に従って開発を行います。

---
*最終更新: 2024年9月27日*
*Version: 1.0.0*