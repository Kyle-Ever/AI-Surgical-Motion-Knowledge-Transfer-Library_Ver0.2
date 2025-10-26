import { test } from '@playwright/test';

test('Chromium-specific debug for eb9c6a82', async ({ page }) => {
  const logs: string[] = [];
  const errors: string[] = [];
  const networkRequests: string[] = [];
  const networkResponses: Map<string, any> = new Map();

  // Capture all console logs
  page.on('console', msg => {
    const text = msg.text();
    logs.push(`[${msg.type()}] ${text}`);
    if (msg.type() === 'error') {
      errors.push(text);
    }
  });

  // Capture network requests
  page.on('request', request => {
    if (request.url().includes('localhost:8001')) {
      networkRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  // Capture network responses
  page.on('response', async response => {
    if (response.url().includes('localhost:8001')) {
      const status = response.status();
      const url = response.url();
      try {
        const body = await response.text();
        networkResponses.set(url, { status, body: body.substring(0, 200) });
      } catch (e) {
        networkResponses.set(url, { status, body: 'Could not read body' });
      }
    }
  });

  page.on('pageerror', err => {
    errors.push(`PageError: ${err.message}`);
  });

  console.log('=== Navigating to comparison page (Chromium only) ===');
  await page.goto('http://localhost:3000/scoring/comparison/eb9c6a82-d074-4c8c-8f54-44dc0bfcb4b0', {
    waitUntil: 'domcontentloaded',
    timeout: 60000
  });

  // Wait for data to load
  await page.waitForTimeout(8000);

  // Log network activity
  console.log('\n=== Network Requests to Backend ===');
  networkRequests.forEach(req => console.log(req));

  console.log('\n=== Network Responses ===');
  for (const [url, data] of networkResponses.entries()) {
    console.log(`${data.status} ${url}`);
    console.log(`  Body preview: ${data.body}`);
  }

  // Check page elements
  const videoCount = await page.locator('video').count();
  const canvasCount = await page.locator('canvas').count();
  const errorDivs = await page.locator('div:has-text("動画ファイルが見つかりません")').count();

  console.log(`\n=== Page Elements ===`);
  console.log(`Video Elements: ${videoCount}`);
  console.log(`Canvas Elements: ${canvasCount}`);
  console.log(`Error Divs: ${errorDivs}`);

  // Check for comparison result logs
  const comparisonLogs = logs.filter(log => log.includes('Comparison result'));
  console.log(`\n=== Comparison Result Logs ===`);
  comparisonLogs.forEach(log => console.log(log));

  // Check for useScoring hook logs
  const useScoringLogs = logs.filter(log =>
    log.includes('Full comparison data') ||
    log.includes('Learner analysis') ||
    log.includes('Reference analysis')
  );
  console.log(`\n=== useScoring Hook Logs ===`);
  useScoringLogs.forEach(log => console.log(log));

  // All errors
  console.log(`\n=== All Errors (${errors.length}) ===`);
  errors.forEach(err => console.log(err));

  // Take screenshot
  await page.screenshot({ path: 'test-results/chromium-debug.png', fullPage: true });
  console.log('\n=== Screenshot: test-results/chromium-debug.png ===');
});
