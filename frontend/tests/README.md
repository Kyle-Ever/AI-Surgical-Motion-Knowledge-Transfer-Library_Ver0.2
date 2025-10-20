# Playwrightテスト実行ガイド

## 概要

このドキュメントは、AI手技モーションライブラリのフロントエンドE2Eテストの実行方法を説明します。

## セットアップ

### 1. 依存関係のインストール

```bash
cd frontend
npm install
npx playwright install --with-deps
```

### 2. 環境準備

テスト実行前に、以下のサービスが起動していることを確認してください：

- **バックエンドAPI**: http://localhost:8000
- **フロントエンド**: http://localhost:3000

```bash
# ルートディレクトリから
start_both.bat  # Windows環境
```

## テスト実行コマンド

### 全テストを実行

```bash
npm test
```

### 特定のテストファイルを実行

```bash
npx playwright test home.spec.ts
npx playwright test upload.spec.ts
npx playwright test library.spec.ts
npx playwright test analysis-progress.spec.ts
npx playwright test error-handling.spec.ts
```

### ブラウザを指定して実行

```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

### UIモードで実行（インタラクティブ）

```bash
npm run test:ui
```

### ブラウザを表示して実行（ヘッドフルモード）

```bash
npm run test:headed
```

### デバッグモードで実行

```bash
npm run test:debug
```

## テストレポート

### HTMLレポートの生成

テスト実行後、自動的にHTMLレポートが生成されます。

```bash
# レポートを表示
npm run test:report
```

### レポートの場所

- `frontend/playwright-report/index.html`

## テストファイル構成

```
frontend/tests/
├── helpers/              # テストヘルパー
│   ├── test-data.ts     # テストデータ生成
│   ├── api-mock.ts      # APIモックユーティリティ
│   └── page-objects.ts  # ページオブジェクト
├── home.spec.ts         # ホームページテスト
├── upload.spec.ts       # アップロードページテスト
├── library.spec.ts      # ライブラリページテスト
├── api.spec.ts          # API統合テスト
├── navigation.spec.ts   # ナビゲーションテスト
├── upload-flow-e2e.spec.ts    # アップロードフローE2E
├── analysis-progress.spec.ts  # 解析進捗テスト
└── error-handling.spec.ts     # エラーハンドリングテスト
```

## トラブルシューティング

### 問題: テストがタイムアウトする

**原因**: バックエンドAPIが起動していない

**解決方法**:
```bash
# 別ターミナルで
start_backend_py311.bat
```

### 問題: params.idエラー

**原因**: Next.js 15で動的パラメータが非同期になった

**解決方法**:
- Server ComponentとClient Componentを分離済み
- `app/analysis/[id]/page.tsx` → Server Component
- `app/analysis/[id]/AnalysisClient.tsx` → Client Component

### 問題: WebSocket接続エラー

**原因**: WebSocketエンドポイントが利用できない

**解決方法**:
- バックエンドが起動していることを確認
- CORS設定を確認（localhost:3000が許可されているか）

### 問題: ファイルアップロードエラー

**原因**: テストファイルのサイズ制限

**解決方法**:
```typescript
// 50MB以下のバッファを使用
const file = {
  name: 'test.mp4',
  mimeType: 'video/mp4',
  buffer: Buffer.from('content')  // 小さいサイズ
}
```

## CI/CD統合

### GitHub Actions設定

`.github/workflows/e2e.yml`にPlaywrightテストが設定されています：

```yaml
- name: Run Playwright tests
  run: |
    cd frontend
    npm ci
    npx playwright install --with-deps
    npm test
```

### 実行タイミング

- プッシュ時: `main`ブランチへのプッシュ
- プルリクエスト時: 自動実行

## テスト書き方のベストプラクティス

### 1. ページオブジェクトパターンを使用

```typescript
// helpers/page-objects.ts
export class HomePage {
  constructor(private page: Page) {}

  async clickNewAnalysis() {
    await this.page.click('a[href="/upload"]')
  }
}
```

### 2. テストデータヘルパーを使用

```typescript
import { createMockFile } from './helpers/test-data'

const mockFile = createMockFile('test.mp4')
```

### 3. APIモックを適切に設定

```typescript
await page.route('**/api/v1/**', route => {
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(mockData)
  })
})
```

### 4. 適切な待機処理

```typescript
// 要素の表示を待つ
await expect(page.locator('.element')).toBeVisible()

// APIレスポンスを待つ
await page.waitForResponse('**/api/v1/videos')
```

## パフォーマンステスト

### 実行時間の測定

```typescript
const startTime = Date.now()
// テスト処理
const endTime = Date.now()
expect(endTime - startTime).toBeLessThan(5000)
```

### レスポンスタイムの確認

```typescript
const response = await page.request.get('/api/v1/health')
expect(response.timing().duration).toBeLessThan(1000)
```

## デバッグ方法

### 1. スクリーンショット

```typescript
await page.screenshot({ path: 'debug.png' })
```

### 2. トレース

```bash
npx playwright test --trace on
```

### 3. ビデオ録画

playwright.config.tsで設定：
```typescript
use: {
  video: 'on-first-retry'
}
```

## メンテナンス

### 定期実行

毎日のスモークテスト実行を推奨：

```bash
# 基本的なテストのみ実行
npx playwright test --grep @smoke
```

### テストデータのクリーンアップ

テスト後にデータをクリーンアップ：
```typescript
test.afterEach(async ({ page }) => {
  // クリーンアップ処理
})
```

## 問い合わせ

テストに関する質問や問題がある場合は、開発チームまでご連絡ください。