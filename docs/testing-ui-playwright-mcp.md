# UI E2E テスト: Playwright + MCP 連携（任意）

このドキュメントでは、フロントエンドの UI 動作テストを Playwright で実行する方法と、Model Context Protocol（MCP）経由で補助的に操作・検証する構成（任意）を記載します。

## 前提
- Node.js 20 以上（フロントエンド）
- フロントエンド: `frontend/` ディレクトリ
- Playwright は `devDependencies` 済み（`@playwright/test`）。初回のみブラウザを取得:

```bash
cd frontend
npm ci
npx playwright install --with-deps
```

## ローカルでの実行
1. （必要なら）バックエンドを起動
   - ルートで `start_backend.bat` 実行（Windows）
2. フロントエンドで E2E 実行

```bash
cd frontend
npm run test      # ヘッドレス実行
npm run test:ui   # Playwright UI でインタラクティブ実行
```

Playwright は `playwright.config.ts` により、`npm run dev`（Next.js）をテスト前に起動し、`http://localhost:3000` で待ち受けます（CI では 1 並列で実行）。

## 代表テスト
- `frontend/tests/home.spec.ts` など、トップページの表示と主要リンクの存在確認
- 必要に応じて、`upload.spec.ts` や `library.spec.ts` などを拡充

## MCP 連携（任意）
Playwright を MCP サーバとして公開し、エージェントからブラウザ操作・検証を実行する構成です。

> 注意: MCP サーバ（Playwright MCP）は別途インストールが必要です。LLM/エージェント側の MCP クライアント（例: IDE/ツール）に、Playwright MCP のエンドポイントを登録してください。

### 概要手順（参考）
1. Playwright MCP サーバをセットアップ（例: Node 製の MCP サーバをインストール）
2. MCP クライアント（IDE/ツール）にサーバの定義を追加
3. 以下のような操作を行うツールを有効化
   - `page.goto(url)`、`locator(text)`、`expect` に相当する操作
   - スクリーンショット取得、コンソールログ収集、トレース保存

本リポジトリでは、まず通常の Playwright テスト運用を標準とし、MCP 連携は「補助ツール」として利用します。導入時はセキュリティ要件（ポート・認証・ログ）を確認してください。

## GitHub Actions（手動トリガ）
`/.github/workflows/e2e.yml` を用意しています（手動トリガ）。

```yaml
on: { workflow_dispatch: {} }
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - name: Install deps
        run: |
          cd frontend
          npm ci
          npx playwright install --with-deps
      - name: Run Playwright
        env:
          CI: 'true'
        run: |
          cd frontend
          npx playwright test
```

バックエンド連携が必要なテストを有効化する場合は、Action 内でバックエンドを別ジョブ/同ジョブのバックグラウンドで起動してください（ポート 8000）。

