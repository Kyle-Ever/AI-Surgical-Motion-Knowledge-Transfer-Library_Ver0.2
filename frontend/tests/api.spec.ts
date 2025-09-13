import { test, expect } from '@playwright/test';

test.describe('API Integration', () => {
  const API_BASE_URL = 'http://localhost:8000/api/v1';

  test('should handle API errors gracefully', async ({ page }) => {
    // APIエラーをシミュレート
    await page.route('**/api/v1/videos', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      });
    });

    await page.goto('/library');

    // エラーメッセージが表示されることを確認
    await expect(page.locator('text=/エラー|失敗|問題/i')).toBeVisible();
  });

  test('should handle network timeout', async ({ page }) => {
    // ネットワークタイムアウトをシミュレート
    await page.route('**/api/v1/videos', async route => {
      await new Promise(resolve => setTimeout(resolve, 35000)); // 35秒待機
      await route.abort();
    });

    await page.goto('/library', { timeout: 5000 });

    // タイムアウトエラーが表示されることを確認
    await expect(page.locator('text=/タイムアウト|接続/i')).toBeVisible({ timeout: 40000 });
  });

  test('should retry failed requests', async ({ page }) => {
    let requestCount = 0;

    // 最初のリクエストは失敗、リトライで成功
    await page.route('**/api/v1/videos', async route => {
      requestCount++;
      if (requestCount === 1) {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Service Unavailable' })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([])
        });
      }
    });

    await page.goto('/library');

    // リトライ後に成功することを確認
    await expect(page.locator('[data-testid="video-list-container"]')).toBeVisible({ timeout: 10000 });
  });

  test('should handle CORS errors', async ({ page }) => {
    // CORSエラーをシミュレート
    await page.route('**/api/v1/videos', async route => {
      await route.fulfill({
        status: 0,
        body: ''
      });
    });

    await page.goto('/library');

    // CORSエラーメッセージが表示されることを確認
    await expect(page.locator('text=/CORS|接続|ネットワーク/i')).toBeVisible();
  });
});

test.describe('WebSocket Connection', () => {
  test('should connect to WebSocket for real-time updates', async ({ page }) => {
    // WebSocket接続をモック
    await page.addInitScript(() => {
      window.WebSocket = class MockWebSocket extends WebSocket {
        constructor(url: string) {
          super(url);
          setTimeout(() => {
            this.dispatchEvent(new Event('open'));
            setTimeout(() => {
              this.dispatchEvent(new MessageEvent('message', {
                data: JSON.stringify({
                  type: 'progress',
                  progress: 50,
                  status: 'processing'
                })
              }));
            }, 1000);
          }, 100);
        }
      };
    });

    // 解析ページに移動
    await page.goto('/analysis/test-id');

    // WebSocket接続インジケーターが表示されることを確認
    await expect(page.locator('[data-testid="ws-connected"]')).toBeVisible({ timeout: 5000 });

    // 進捗更新が反映されることを確認
    await expect(page.locator('text=50%')).toBeVisible({ timeout: 5000 });
  });
});