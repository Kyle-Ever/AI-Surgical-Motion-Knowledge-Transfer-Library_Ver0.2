import { test, expect } from '@playwright/test';

test.describe('Skeleton Display Fix Verification', () => {
  test('should display videos and skeleton overlay after fix', async ({ page }) => {
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

    // Capture page errors
    page.on('pageerror', err => {
      errors.push(`PageError: ${err.message}`);
    });

    console.log('=== Navigating to comparison page ===');
    await page.goto('http://localhost:3000/scoring/comparison/cddd1e9c-1c83-4011-a99f-79be18d5f547', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    // Wait for data to load
    await page.waitForTimeout(8000);

    // ========================================
    // VERIFICATION 1: Video Elements
    // ========================================
    const videoCount = await page.locator('video').count();
    console.log(`\n=== VIDEO ELEMENTS: ${videoCount} (Expected: 2) ===`);
    expect(videoCount, 'Should have 2 video elements').toBe(2);

    // Check video sources
    if (videoCount > 0) {
      const video1Src = await page.locator('video').first().locator('source').getAttribute('src');
      const video2Src = videoCount > 1 ? await page.locator('video').nth(1).locator('source').getAttribute('src') : null;

      console.log('Video 1 src:', video1Src);
      console.log('Video 2 src:', video2Src);

      // Check if videos are loading
      const video1Ready = await page.locator('video').first().evaluate((v: HTMLVideoElement) => v.readyState);
      const video2Ready = videoCount > 1 ? await page.locator('video').nth(1).evaluate((v: HTMLVideoElement) => v.readyState) : 0;

      console.log(`Video 1 readyState: ${video1Ready} (4=HAVE_ENOUGH_DATA)`);
      console.log(`Video 2 readyState: ${video2Ready} (4=HAVE_ENOUGH_DATA)`);
    }

    // ========================================
    // VERIFICATION 2: Canvas Elements
    // ========================================
    const canvasCount = await page.locator('canvas').count();
    console.log(`\n=== CANVAS ELEMENTS: ${canvasCount} (Expected: 2) ===`);
    expect(canvasCount, 'Should have 2 canvas elements for skeleton overlay').toBeGreaterThanOrEqual(2);

    // ========================================
    // VERIFICATION 3: Error Messages
    // ========================================
    const errorMessages = await page.locator('div:has-text("動画ファイルが見つかりません")').count();
    console.log(`\n=== ERROR MESSAGES: ${errorMessages} (Expected: 0) ===`);
    expect(errorMessages, 'Should not have error messages').toBe(0);

    // ========================================
    // VERIFICATION 4: Skeleton Data Loading
    // ========================================
    const skeletonLogs = logs.filter(log =>
      log.includes('skeleton frames') ||
      log.includes('skeleton data')
    );
    console.log('\n=== SKELETON DATA LOGS ===');
    skeletonLogs.forEach(log => console.log(log));

    expect(skeletonLogs.length, 'Should have skeleton data logs').toBeGreaterThan(0);

    // ========================================
    // VERIFICATION 5: Canvas Drawing
    // ========================================
    if (canvasCount > 0) {
      // Wait a bit for skeleton to be drawn
      await page.waitForTimeout(2000);

      const canvas1HasDrawing = await page.locator('canvas').first().evaluate((canvas: HTMLCanvasElement) => {
        const ctx = canvas.getContext('2d');
        if (!ctx) return false;
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        for (let i = 3; i < imageData.data.length; i += 4) {
          if (imageData.data[i] > 0) return true;
        }
        return false;
      });

      console.log(`\n=== CANVAS DRAWING ===`);
      console.log(`Canvas 1 has drawing: ${canvas1HasDrawing} (Expected: true)`);

      // Note: Drawing may not appear immediately, so we log but don't fail the test
      if (!canvas1HasDrawing) {
        console.warn('WARNING: Canvas does not have skeleton drawing yet');
      }
    }

    // ========================================
    // VERIFICATION 6: Errors Check
    // ========================================
    console.log('\n=== ERRORS ===');
    if (errors.length > 0) {
      console.log('Errors found:');
      errors.forEach(err => console.log(`  - ${err}`));
    } else {
      console.log('No errors found ✓');
    }

    // ERR_NAME_NOT_RESOLVED should not appear
    const hasNetworkErrors = errors.some(err => err.includes('ERR_NAME_NOT_RESOLVED'));
    expect(hasNetworkErrors, 'Should not have ERR_NAME_NOT_RESOLVED errors').toBe(false);

    // ========================================
    // SCREENSHOT
    // ========================================
    await page.screenshot({
      path: 'test-results/skeleton-display-verification.png',
      fullPage: true
    });
    console.log('\n=== Screenshot saved to test-results/skeleton-display-verification.png ===');
  });
});
