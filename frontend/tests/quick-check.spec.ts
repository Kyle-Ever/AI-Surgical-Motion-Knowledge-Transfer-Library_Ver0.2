import { test } from '@playwright/test';

test('Quick check - can page load?', async ({ page }) => {
  // ページを開く
  await page.goto('http://localhost:3000/scoring/comparison/55653dc2-33eb-4a3c-8b6f-8892a3eb94a5', {
    waitUntil: 'domcontentloaded',
    timeout: 60000
  });

  // コンソールエラーをキャッチ
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('❌ Console Error:', msg.text());
    }
  });

  page.on('pageerror', err => {
    console.log('❌ Page Error:', err.message);
  });

  // スクリーンショットを撮る
  await page.screenshot({ path: 'test-results/quick-check.png', fullPage: true });

  // ページのHTMLを出力
  const html = await page.content();
  console.log('Page HTML length:', html.length);
  console.log('Has video element:', html.includes('<video'));
  console.log('Has canvas element:', html.includes('<canvas'));

  // 5秒待機
  await page.waitForTimeout(5000);
});
