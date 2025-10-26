import { test } from '@playwright/test';

test('Debug result state and rendering logic', async ({ page }) => {
  console.log('=== Navigating to page ===');

  await page.goto('http://localhost:3000/scoring/comparison/cddd1e9c-1c83-4011-a99f-79be18d5f547', {
    waitUntil: 'domcontentloaded',
    timeout: 60000
  });

  // Wait for various intervals and check state
  const intervals = [1000, 3000, 5000, 8000];

  for (const interval of intervals) {
    await page.waitForTimeout(interval);

    console.log(`\n=== After ${interval}ms ===`);

    // Check rendering
    const videoCount = await page.locator('video').count();
    const canvasCount = await page.locator('canvas').count();
    const errorCount = await page.locator('div:has-text("動画ファイルが見つかりません")').count();
    const loadingCount = await page.locator('div:has-text("比較データを読み込み中")').count();

    console.log(`Videos: ${videoCount}, Canvas: ${canvasCount}, Errors: ${errorCount}, Loading: ${loadingCount}`);

    // Try to expose internal state
    const stateInfo = await page.evaluate(() => {
      // Check if DualVideoSection is rendered
      const dualSection = document.querySelector('[class*="grid"]');
      return {
        hasDualSection: !!dualSection,
        bodyHTML: document.body.innerHTML.substring(0, 500)
      };
    });

    console.log('Has DualVideoSection:', stateInfo.hasDualSection);
    console.log('Body HTML (first 500 chars):', stateInfo.bodyHTML);
  }

  await page.screenshot({ path: 'test-results/debug-result-state.png', fullPage: true });
  console.log('\n=== Screenshot saved ===');
});
