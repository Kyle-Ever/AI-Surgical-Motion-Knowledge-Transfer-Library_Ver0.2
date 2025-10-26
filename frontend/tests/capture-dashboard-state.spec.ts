import { test } from '@playwright/test';

test('capture dashboard state with long wait', async ({ page }) => {
  // Capture all console messages
  const consoleMessages: string[] = [];
  page.on('console', msg => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
  });

  // Capture page errors
  const pageErrors: string[] = [];
  page.on('pageerror', err => {
    pageErrors.push(`[ERROR] ${err.message}\n${err.stack}`);
  });

  // Navigate to dashboard
  const dashboardUrl = 'http://localhost:3000/dashboard/9f6d853e-b70f-430a-9d44-423f7e26d148';
  console.log(`Navigating to: ${dashboardUrl}`);

  await page.goto(dashboardUrl, { waitUntil: 'networkidle' });

  // Wait 10 seconds to see if anything changes
  console.log('Waiting 10 seconds for page to render...');
  await page.waitForTimeout(10000);

  // Take screenshot
  await page.screenshot({ path: 'dashboard-state.png', fullPage: true });
  console.log('Screenshot saved: dashboard-state.png');

  // Check page content
  const bodyText = await page.textContent('body');
  console.log('\n===== Page Body Text =====');
  console.log(bodyText?.substring(0, 500));

  // Check if loading state is visible
  const loadingText = await page.locator('text=解析データを読み込んでいます').count();
  console.log(`\nLoading text visible: ${loadingText > 0}`);

  // Check if GazeDashboardClient rendered
  const dashboardTitle = await page.locator('h1:has-text("視線解析ダッシュボード")').count();
  console.log(`Dashboard title visible: ${dashboardTitle > 0}`);

  // Check network activity
  console.log('\n===== Network Requests =====');
  const requests = [];
  page.on('request', req => requests.push(req.url()));
  await page.waitForTimeout(2000);
  console.log(`Total requests: ${requests.length}`);
  requests.forEach(url => {
    if (url.includes('analysis') || url.includes('dashboard')) {
      console.log(`  ${url}`);
    }
  });

  // Output console messages
  console.log('\n===== Console Messages =====');
  console.log(`Total messages: ${consoleMessages.length}`);
  consoleMessages.slice(0, 20).forEach(msg => console.log(msg));

  // Output errors
  if (pageErrors.length > 0) {
    console.log('\n===== Page Errors =====');
    pageErrors.forEach(err => console.log(err));
  } else {
    console.log('\n===== No Page Errors =====');
  }
});
