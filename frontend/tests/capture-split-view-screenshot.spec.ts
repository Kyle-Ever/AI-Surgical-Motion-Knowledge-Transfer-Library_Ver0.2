import { test } from '@playwright/test';

test('capture split view dashboard screenshot', async ({ page }) => {
  const dashboardUrl = 'http://localhost:3000/dashboard/9f6d853e-b70f-430a-9d44-423f7e26d148';

  console.log(`Navigating to: ${dashboardUrl}`);
  await page.goto(dashboardUrl, { waitUntil: 'networkidle' });

  // Wait for video and canvases to be ready
  console.log('Waiting for dashboard to fully load...');
  await page.waitForTimeout(3000);

  // Take full page screenshot
  await page.screenshot({ path: 'split-view-dashboard-full.png', fullPage: true });
  console.log('Full page screenshot saved: split-view-dashboard-full.png');

  // Take screenshot of just the video section
  const videoSection = page.locator('div.bg-white.rounded-lg.shadow-lg').filter({
    has: page.locator('h2:has-text("視線解析動画")')
  });
  await videoSection.screenshot({ path: 'split-view-video-section.png' });
  console.log('Video section screenshot saved: split-view-video-section.png');

  // Play video for a few seconds and take another screenshot
  const playButton = page.locator('button').filter({ hasText: '再生' });
  await playButton.click();
  console.log('Playing video...');
  await page.waitForTimeout(5000);

  await page.screenshot({ path: 'split-view-playing.png', fullPage: false });
  console.log('Playing screenshot saved: split-view-playing.png');

  // Change heatmap window and take screenshot
  const select = page.locator('select').filter({ hasText: /±\d+秒/ });
  await select.selectOption('3');
  console.log('Changed heatmap window to ±3 seconds');
  await page.waitForTimeout(2000);

  await videoSection.screenshot({ path: 'split-view-window-3s.png' });
  console.log('Heatmap ±3s screenshot saved: split-view-window-3s.png');

  // Seek to middle of video
  const slider = page.locator('input[type="range"]');
  await slider.fill('10');
  console.log('Seeked to 10 seconds');
  await page.waitForTimeout(2000);

  await videoSection.screenshot({ path: 'split-view-at-10s.png' });
  console.log('At 10 seconds screenshot saved: split-view-at-10s.png');

  console.log('\n===== Screenshot Capture Complete =====');
  console.log('Generated screenshots:');
  console.log('1. split-view-dashboard-full.png - Full page');
  console.log('2. split-view-video-section.png - Video section only');
  console.log('3. split-view-playing.png - During playback');
  console.log('4. split-view-window-3s.png - With ±3s heatmap');
  console.log('5. split-view-at-10s.png - At 10 second mark');
});
