# Playwright E2Eテストガイド

## セットアップ完了

Playwrightのセットアップが完了しました。以下のコマンドでテストを実行できます：

## テスト実行コマンド

```bash
# すべてのテストを実行
npm test

# ブラウザを表示しながらテスト実行
npm run test:headed

# UIモードでテスト実行（インタラクティブ）
npm run test:ui

# デバッグモードでテスト実行
npm run test:debug

# テストレポートを表示
npm run test:report
```

## テストファイル構成

```
frontend/
├── tests/
│   ├── home.spec.ts       # ホームページのテスト
│   ├── upload.spec.ts     # アップロードページのテスト
│   ├── library.spec.ts    # ライブラリページのテスト
│   └── api.spec.ts        # API統合テスト
└── playwright.config.ts   # Playwright設定ファイル
```

## テストの実行例

### 1. 基本的なテスト実行

```bash
cd frontend
npm test
```

### 2. 特定のテストファイルのみ実行

```bash
npx playwright test tests/home.spec.ts
```

### 3. 特定のブラウザでテスト

```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

### 4. UIモードで実行（推奨）

```bash
npm run test:ui
```

UIモードでは：
- テストをビジュアルに確認できる
- ステップごとに実行を制御できる
- タイムトラベルデバッグが可能

## テストの書き方

### 基本的なテスト構造

```typescript
import { test, expect } from '@playwright/test';

test.describe('機能名', () => {
  test('テストケース名', async ({ page }) => {
    // ページに移動
    await page.goto('/path');

    // 要素を取得して操作
    await page.click('button:has-text("ボタン")');

    // アサーション
    await expect(page.locator('h1')).toContainText('期待するテキスト');
  });
});
```

### data-testid を使用した要素の選択

```typescript
// HTMLに data-testid を追加
<div data-testid="upload-area">...</div>

// テストで選択
await page.locator('[data-testid="upload-area"]').click();
```

## 注意事項

1. **開発サーバーの自動起動**
   - テスト実行時に自動的に開発サーバー（`npm run dev`）が起動します
   - 既に起動している場合は既存のサーバーを使用します

2. **並列実行**
   - デフォルトでテストは並列実行されます
   - 順次実行したい場合は `--workers=1` オプションを使用

3. **レポート**
   - テスト終了後、`npm run test:report` でHTMLレポートを確認できます
   - 失敗時のスクリーンショットも自動保存されます

## トラブルシューティング

### ブラウザがインストールされていない場合

```bash
npx playwright install
```

### 特定のブラウザのみインストール

```bash
npx playwright install chromium
```

### テストがタイムアウトする場合

`playwright.config.ts` でタイムアウト時間を調整：

```typescript
use: {
  // アクションのタイムアウト
  actionTimeout: 10000,
  // ナビゲーションのタイムアウト
  navigationTimeout: 30000,
}
```