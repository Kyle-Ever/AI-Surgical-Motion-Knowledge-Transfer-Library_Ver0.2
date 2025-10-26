import { test } from '@playwright/test';

test('Debug specific comparison cddd1e9c', async ({ page }) => {
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
  await page.goto('http://localhost:3000/scoring/comparison/cddd1e9c-1c83-4011-a99f-79be18d5f547', {
    waitUntil: 'domcontentloaded',
    timeout: 60000
  });

  await page.waitForTimeout(5000);

  // Check video elements
  const videoCount = await page.locator('video').count();
  console.log(`\n=== Video Elements: ${videoCount} ===`);

  // Check canvas elements
  const canvasCount = await page.locator('canvas').count();
  console.log(`=== Canvas Elements: ${canvasCount} ===`);

  // Check for error messages on page
  const errorMessages = await page.locator('div:has-text("動画ファイルが見つかりません")').count();
  console.log(`=== Error Message Divs: ${errorMessages} ===`);

  // Check if videos are actually loaded
  if (videoCount > 0) {
    const video1Ready = await page.locator('video').first().evaluate((v: HTMLVideoElement) => v.readyState);
    const video2Ready = videoCount > 1 ? await page.locator('video').nth(1).evaluate((v: HTMLVideoElement) => v.readyState) : 0;
    console.log(`=== Video1 ReadyState: ${video1Ready} (0=HAVE_NOTHING, 4=HAVE_ENOUGH_DATA) ===`);
    console.log(`=== Video2 ReadyState: ${video2Ready} ===`);
  }

  // Check canvas drawing
  if (canvasCount > 0) {
    const canvas1HasDrawing = await page.locator('canvas').first().evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return false;
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 3; i < imageData.data.length; i += 4) {
        if (imageData.data[i] > 0) return true;
      }
      return false;
    });
    console.log(`=== Canvas1 Has Drawing: ${canvas1HasDrawing} ===`);

    if (canvasCount > 1) {
      const canvas2HasDrawing = await page.locator('canvas').nth(1).evaluate((canvas: HTMLCanvasElement) => {
        const ctx = canvas.getContext('2d');
        if (!ctx) return false;
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        for (let i = 3; i < imageData.data.length; i += 4) {
          if (imageData.data[i] > 0) return true;
        }
        return false;
      });
      console.log(`=== Canvas2 Has Drawing: ${canvas2HasDrawing} ===`);
    }
  }

  // Check console logs for skeleton data
  console.log('\n=== Relevant Console Logs ===');
  const skeletonLogs = logs.filter(log =>
    log.includes('skeleton') ||
    log.includes('Comparison result') ||
    log.includes('video ID') ||
    log.includes('analysis')
  );
  skeletonLogs.forEach(log => console.log(log));

  console.log('\n=== All Errors ===');
  errors.forEach(err => console.log(err));

  // Take screenshot
  await page.screenshot({ path: 'test-results/debug-cddd1e9c.png', fullPage: true });

  console.log('\n=== Screenshot saved to test-results/debug-cddd1e9c.png ===');
});
