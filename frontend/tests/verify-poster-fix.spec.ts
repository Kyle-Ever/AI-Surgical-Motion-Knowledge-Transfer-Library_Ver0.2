import { test, expect } from '@playwright/test';

test('Verify poster fix - videos should render without external poster', async ({ page }) => {
  const logs: string[] = [];
  const errors: string[] = [];

  // Capture console logs
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

  console.log('=== Navigating to comparison page ===');
  await page.goto('http://localhost:3000/scoring/comparison/eb9c6a82-d074-4c8c-8f54-44dc0bfcb4b0', {
    waitUntil: 'domcontentloaded',
    timeout: 60000
  });

  // Wait for page to settle
  await page.waitForTimeout(5000);

  // Check for via.placeholder.com errors (should be ZERO after fix)
  const placeholderErrors = errors.filter(err => err.includes('via.placeholder.com'));
  console.log(`\n=== via.placeholder.com Errors: ${placeholderErrors.length} ===`);
  if (placeholderErrors.length > 0) {
    console.log('ERROR: Still getting placeholder errors:');
    placeholderErrors.forEach(err => console.log(`  ${err}`));
  }

  // Check video elements
  const videoCount = await page.locator('video').count();
  console.log(`\n=== Video Elements: ${videoCount} (Expected: 2) ===`);

  // Check canvas elements
  const canvasCount = await page.locator('canvas').count();
  console.log(`=== Canvas Elements: ${canvasCount} (Expected: 2-3) ===`);

  // Check for error messages on page
  const errorMessages = await page.locator('div:has-text("動画ファイルが見つかりません")').count();
  console.log(`=== Error Message Divs: ${errorMessages} (Expected: 0) ===`);

  // Verify videos are loading
  if (videoCount > 0) {
    const video1Ready = await page.locator('video').first().evaluate((v: HTMLVideoElement) => v.readyState);
    const video2Ready = videoCount > 1 ? await page.locator('video').nth(1).evaluate((v: HTMLVideoElement) => v.readyState) : 0;
    console.log(`\n=== Video 1 ReadyState: ${video1Ready} (0=HAVE_NOTHING, 4=HAVE_ENOUGH_DATA) ===`);
    console.log(`=== Video 2 ReadyState: ${video2Ready} ===`);

    // Check video poster attribute (should be undefined/empty after fix)
    const video1Poster = await page.locator('video').first().getAttribute('poster');
    const video2Poster = videoCount > 1 ? await page.locator('video').nth(1).getAttribute('poster') : null;
    console.log(`\n=== Video 1 Poster: ${video1Poster || 'None (CORRECT)'} ===`);
    console.log(`=== Video 2 Poster: ${video2Poster || 'None (CORRECT)'} ===`);
  }

  // Check skeleton data in logs
  const skeletonLogs = logs.filter(log =>
    log.includes('skeleton') ||
    log.includes('Comparison result')
  );
  console.log(`\n=== Skeleton-related logs: ${skeletonLogs.length} ===`);
  skeletonLogs.slice(0, 5).forEach(log => console.log(log));

  // Take screenshot
  await page.screenshot({ path: 'test-results/verify-poster-fix.png', fullPage: true });

  console.log('\n=== Screenshot saved to test-results/verify-poster-fix.png ===');

  // Assert critical conditions
  expect(placeholderErrors.length, 'Should have NO via.placeholder.com errors').toBe(0);
  expect(videoCount, 'Should have 2 video elements').toBe(2);
  expect(errorMessages, 'Should have NO error message divs').toBe(0);
});
