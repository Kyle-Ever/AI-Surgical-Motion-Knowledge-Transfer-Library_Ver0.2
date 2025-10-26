import { test } from '@playwright/test';

test('Check video playback and skeleton data', async ({ page }) => {
  console.log('=== Navigating to comparison page ===');
  await page.goto('http://localhost:3000/scoring/comparison/eb9c6a82-d074-4c8c-8f54-44dc0bfcb4b0', {
    waitUntil: 'networkidle',
    timeout: 60000
  });

  // Wait for page to fully load
  await page.waitForTimeout(5000);

  // Check video elements
  const videos = page.locator('video');
  const videoCount = await videos.count();
  console.log(`\n=== Video Elements: ${videoCount} ===`);

  if (videoCount > 0) {
    // Check first video (Reference)
    const video1 = videos.first();
    const video1Src = await video1.locator('source').getAttribute('src');
    const video1ReadyState = await video1.evaluate((v: HTMLVideoElement) => v.readyState);
    const video1CurrentTime = await video1.evaluate((v: HTMLVideoElement) => v.currentTime);
    const video1Duration = await video1.evaluate((v: HTMLVideoElement) => v.duration);
    const video1Paused = await video1.evaluate((v: HTMLVideoElement) => v.paused);
    const video1Error = await video1.evaluate((v: HTMLVideoElement) => v.error?.message || null);

    console.log('\n=== Reference Video ===');
    console.log(`  Source: ${video1Src}`);
    console.log(`  ReadyState: ${video1ReadyState} (0=NOTHING, 1=METADATA, 2=CURRENT, 3=FUTURE, 4=ENOUGH)`);
    console.log(`  CurrentTime: ${video1CurrentTime}s`);
    console.log(`  Duration: ${video1Duration}s`);
    console.log(`  Paused: ${video1Paused}`);
    console.log(`  Error: ${video1Error || 'None'}`);

    // Check second video (Evaluation)
    if (videoCount > 1) {
      const video2 = videos.nth(1);
      const video2Src = await video2.locator('source').getAttribute('src');
      const video2ReadyState = await video2.evaluate((v: HTMLVideoElement) => v.readyState);
      const video2CurrentTime = await video2.evaluate((v: HTMLVideoElement) => v.currentTime);
      const video2Duration = await video2.evaluate((v: HTMLVideoElement) => v.duration);
      const video2Paused = await video2.evaluate((v: HTMLVideoElement) => v.paused);
      const video2Error = await video2.evaluate((v: HTMLVideoElement) => v.error?.message || null);

      console.log('\n=== Evaluation Video ===');
      console.log(`  Source: ${video2Src}`);
      console.log(`  ReadyState: ${video2ReadyState}`);
      console.log(`  CurrentTime: ${video2CurrentTime}s`);
      console.log(`  Duration: ${video2Duration}s`);
      console.log(`  Paused: ${video2Paused}`);
      console.log(`  Error: ${video2Error || 'None'}`);
    }
  }

  // Check canvas elements (skeleton overlay)
  const canvases = page.locator('canvas');
  const canvasCount = await canvases.count();
  console.log(`\n=== Canvas Elements: ${canvasCount} ===`);

  if (canvasCount > 0) {
    // Check first canvas
    const canvas1 = canvases.first();
    const canvas1Width = await canvas1.evaluate((c: HTMLCanvasElement) => c.width);
    const canvas1Height = await canvas1.evaluate((c: HTMLCanvasElement) => c.height);
    const canvas1HasContext = await canvas1.evaluate((c: HTMLCanvasElement) => {
      const ctx = c.getContext('2d');
      return !!ctx;
    });

    console.log('\n=== Canvas 1 (Reference) ===');
    console.log(`  Width: ${canvas1Width}px`);
    console.log(`  Height: ${canvas1Height}px`);
    console.log(`  Has 2D Context: ${canvas1HasContext}`);

    if (canvasCount > 1) {
      const canvas2 = canvases.nth(1);
      const canvas2Width = await canvas2.evaluate((c: HTMLCanvasElement) => c.width);
      const canvas2Height = await canvas2.evaluate((c: HTMLCanvasElement) => c.height);

      console.log('\n=== Canvas 2 (Evaluation) ===');
      console.log(`  Width: ${canvas2Width}px`);
      console.log(`  Height: ${canvas2Height}px`);
    }
  }

  // Check skeleton toggle button
  const skeletonToggle = page.locator('button:has-text("手技検出")');
  const skeletonToggleExists = await skeletonToggle.count() > 0;
  console.log(`\n=== Skeleton Toggle Button: ${skeletonToggleExists ? 'Found' : 'Not Found'} ===`);

  // Take screenshot
  await page.screenshot({ path: 'test-results/video-skeleton-check.png', fullPage: true });
  console.log('\n=== Screenshot saved: test-results/video-skeleton-check.png ===');
});
