/**
 * エラーページデバッグテスト
 */

import { test } from '@playwright/test';

test('存在しないComparison IDページの内容を確認', async ({ page }) => {
  const nonExistentId = '29eadcf7-b399-4ce3-907d-20874a558f7c';

  // コンソールログを記録
  page.on('console', (msg) => {
    console.log(`[Browser Console ${msg.type()}]:`, msg.text());
  });

  await page.goto(`http://localhost:3000/scoring/comparison/${nonExistentId}`);

  // ページ読み込み完了を待つ
  await page.waitForTimeout(3000);

  // スクリーンショット
  await page.screenshot({ path: 'test-results/error-page-screenshot.png', fullPage: true });

  // ページのHTML全体を取得
  const html = await page.content();
  console.log('===== Page HTML =====');
  console.log(html.substring(0, 2000));  // 最初の2000文字

  // 表示されているテキストを確認
  const bodyText = await page.locator('body').textContent();
  console.log('\n===== Body Text Content =====');
  console.log(bodyText);
});
