import { test } from '@playwright/test';

test('Debug comparison eb9c6a82 - skeleton display issue', async ({ page }) => {
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
    errors.push(`PageError: ${err.message}\n${err.stack}`);
  });

  console.log('=== Navigating to comparison page ===');
  await page.goto('http://localhost:3000/scoring/comparison/eb9c6a82-d074-4c8c-8f54-44dc0bfcb4b0', {
    waitUntil: 'networkidle',
    timeout: 60000
  });

  await page.waitForTimeout(8000);

  // Check video elements
  const videoCount = await page.locator('video').count();
  console.log(`\n=== Video Elements: ${videoCount} ===`);

  if (videoCount > 0) {
    const video1Src = await page.locator('video').first().locator('source').getAttribute('src');
    const video2Src = videoCount > 1 ? await page.locator('video').nth(1).locator('source').getAttribute('src') : null;

    console.log('Video 1 src:', video1Src);
    console.log('Video 2 src:', video2Src);

    const video1Ready = await page.locator('video').first().evaluate((v: HTMLVideoElement) => v.readyState);
    const video2Ready = videoCount > 1 ? await page.locator('video').nth(1).evaluate((v: HTMLVideoElement) => v.readyState) : 0;

    console.log(`Video 1 readyState: ${video1Ready} (4=HAVE_ENOUGH_DATA)`);
    console.log(`Video 2 readyState: ${video2Ready}`);
  }

  // Check canvas elements
  const canvasCount = await page.locator('canvas').count();
  console.log(`\n=== Canvas Elements: ${canvasCount} ===`);

  // Check for error messages
  const errorMessages = await page.locator('div:has-text("動画ファイルが見つかりません")').count();
  console.log(`\n=== Error Messages: ${errorMessages} ===`);

  // Check skeleton data logs
  console.log('\n=== Skeleton Data Logs ===');
  const skeletonLogs = logs.filter(log =>
    log.includes('skeleton') ||
    log.includes('BEFORE comparisonData') ||
    log.includes('AFTER comparisonData') ||
    log.includes('videoUrl')
  );
  skeletonLogs.forEach(log => console.log(log));

  // Check all errors
  console.log('\n=== All Errors ===');
  if (errors.length > 0) {
    errors.forEach(err => console.log(err));
  } else {
    console.log('No errors found');
  }

  // Take screenshot
  await page.screenshot({ path: 'test-results/debug-eb9c6a82.png', fullPage: true });
  console.log('\n=== Screenshot saved to test-results/debug-eb9c6a82.png ===');
});
