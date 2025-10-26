import { test, expect } from '@playwright/test';

test('verify heatmap overlay on video', async ({ page }) => {
  const analysisId = '9f6d853e-b70f-430a-9d44-423f7e26d148';
  const dashboardUrl = `http://localhost:3000/dashboard/${analysisId}`;

  // Navigate to dashboard
  await page.goto(dashboardUrl, { waitUntil: 'networkidle' });

  // Wait for video element to be ready
  await page.waitForSelector('video', { state: 'attached', timeout: 10000 });

  // Wait for video to load metadata (readyState >= 1)
  await page.waitForFunction(() => {
    const video = document.querySelector('video') as HTMLVideoElement;
    return video && video.readyState >= 1;
  }, { timeout: 15000 });

  console.log('Video metadata loaded');

  // Wait for canvases to render
  await page.waitForTimeout(3000);

  // Play video for a moment to ensure frames are rendered
  await page.evaluate(() => {
    const video = document.querySelector('video') as HTMLVideoElement;
    if (video) video.play();
  });

  await page.waitForTimeout(2000);

  // Take screenshot of right canvas with heatmap overlay
  const gridContainer = page.locator('div.grid.grid-cols-2').first();
  await gridContainer.screenshot({ path: 'heatmap-overlay-verification.png' });

  console.log('✅ Screenshot saved: heatmap-overlay-verification.png');
  console.log('Right canvas should show video with semi-transparent heatmap overlay');
});
