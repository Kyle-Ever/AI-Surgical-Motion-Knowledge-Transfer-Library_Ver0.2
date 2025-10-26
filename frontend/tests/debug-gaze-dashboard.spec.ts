import { test, expect } from '@playwright/test';

test('debug gaze dashboard rendering', async ({ page }) => {
  const analysisId = '9f6d853e-b70f-430a-9d44-423f7e26d148';
  const dashboardUrl = `http://localhost:3000/dashboard/${analysisId}`;

  // Capture console messages and errors
  const consoleMessages: string[] = [];
  const errors: string[] = [];

  page.on('console', msg => {
    const text = `[${msg.type()}] ${msg.text()}`;
    consoleMessages.push(text);
    console.log(text);
  });

  page.on('pageerror', error => {
    const text = `PAGE ERROR: ${error.message}`;
    errors.push(text);
    console.error(text);
  });

  // Navigate to dashboard
  await page.goto(dashboardUrl, { waitUntil: 'networkidle' });

  // Wait for page to load
  await page.waitForTimeout(3000);

  // Check if video element exists and has src
  const videoElement = page.locator('video');
  const videoExists = await videoElement.count();
  console.log(`Video element count: ${videoExists}`);

  if (videoExists > 0) {
    const videoSrc = await videoElement.getAttribute('src');
    console.log(`Video src: ${videoSrc}`);

    const videoReadyState = await videoElement.evaluate((v: HTMLVideoElement) => v.readyState);
    console.log(`Video readyState: ${videoReadyState}`);
  }

  // Check if canvases exist
  const leftCanvas = page.locator('canvas').first();
  const rightCanvas = page.locator('canvas').last();

  const leftCanvasExists = await leftCanvas.count();
  const rightCanvasExists = await rightCanvas.count();

  console.log(`Left canvas exists: ${leftCanvasExists > 0}`);
  console.log(`Right canvas exists: ${rightCanvasExists > 0}`);

  // Check canvas dimensions
  if (leftCanvasExists > 0) {
    const leftWidth = await leftCanvas.evaluate((c: HTMLCanvasElement) => c.width);
    const leftHeight = await leftCanvas.evaluate((c: HTMLCanvasElement) => c.height);
    console.log(`Left canvas: ${leftWidth}x${leftHeight}`);
  }

  // Check if analysis data is loaded
  const h1Text = await page.locator('h1').textContent();
  console.log(`H1 text: ${h1Text}`);

  // Wait for animation frame to render
  await page.waitForTimeout(2000);

  // Check if there are any errors
  console.log(`\n=== Console Messages (${consoleMessages.length}) ===`);
  consoleMessages.forEach(msg => console.log(msg));

  console.log(`\n=== Errors (${errors.length}) ===`);
  errors.forEach(err => console.log(err));

  // Take final screenshot
  await page.screenshot({ path: 'debug-dashboard.png', fullPage: true });
  console.log('Debug screenshot saved: debug-dashboard.png');
});
