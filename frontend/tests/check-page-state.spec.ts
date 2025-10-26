import { test } from '@playwright/test';

test('Check page state and errors', async ({ page }) => {
  const logs: string[] = [];
  const errors: string[] = [];

  page.on('console', msg => {
    const text = msg.text();
    logs.push(`[${msg.type()}] ${text}`);
    if (msg.type() === 'error') {
      errors.push(text);
    }
  });

  page.on('pageerror', err => {
    errors.push(`PageError: ${err.message}`);
  });

  await page.goto('http://localhost:3000/scoring/comparison/55653dc2-33eb-4a3c-8b6f-8892a3eb94a5', {
    waitUntil: 'domcontentloaded',
    timeout: 60000
  });

  await page.waitForTimeout(5000);

  // ページのテキストコンテンツを確認
  const bodyText = await page.textContent('body');
  console.log('\n=== Page Body Text ===');
  console.log(bodyText?.slice(0, 500));

  // DualVideoSectionが存在するか
  const hasDualVideo = await page.locator('[class*="grid"]').count();
  console.log('\n=== Grid Elements ===', hasDualVideo);

  // motion要素を確認
  const motionSections = await page.locator('section').count();
  console.log('=== Motion Sections ===', motionSections);

  // エラーメッセージ要素を確認
  const errorDiv = await page.locator('div:has-text("比較データが見つかりません")').count();
  console.log('=== Error Message Count ===', errorDiv);

  console.log('\n=== All Console Logs ===');
  logs.forEach(log => console.log(log));

  console.log('\n=== Errors ===');
  errors.forEach(err => console.log(err));

  // スクリーンショット
  await page.screenshot({ path: 'test-results/page-state.png', fullPage: true });
});
