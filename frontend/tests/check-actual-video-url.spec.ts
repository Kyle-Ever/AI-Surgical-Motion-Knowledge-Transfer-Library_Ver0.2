import { test } from '@playwright/test';

test('Check actual video src URLs in DOM', async ({ page }) => {
  console.log('=== Navigating to comparison page ===');
  await page.goto('http://localhost:3000/scoring/comparison/eb9c6a82-d074-4c8c-8f54-44dc0bfcb4b0', {
    waitUntil: 'networkidle',
    timeout: 60000
  });

  await page.waitForTimeout(8000);

  // Check if videos exist
  const videoCount = await page.locator('video').count();
  console.log(`\n=== Video count: ${videoCount} ===`);

  if (videoCount === 0) {
    console.log('No video elements found. Checking for error divs...');

    // Get error div content
    const errorDivs = await page.locator('div:has-text("動画ファイルが見つかりません")').all();
    console.log(`Found ${errorDivs.length} error divs`);

    // Check what's actually rendered
    const dualVideoSection = await page.locator('[class*="DualVideoSection"], [class*="grid"]').first();
    const html = await dualVideoSection.innerHTML().catch(() => 'Element not found');
    console.log('\n=== DualVideoSection HTML (first 1000 chars) ===');
    console.log(html.substring(0, 1000));
  } else {
    // Get actual video src from DOM
    for (let i = 0; i < videoCount; i++) {
      const video = page.locator('video').nth(i);
      const source = video.locator('source');
      const src = await source.getAttribute('src');
      const type = await source.getAttribute('type');

      console.log(`\n=== Video ${i + 1} ===`);
      console.log(`src: ${src}`);
      console.log(`type: ${type}`);
    }
  }

  // Check environment variables in browser
  const envVars = await page.evaluate(() => {
    return {
      NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
      windowLocation: window.location.href
    };
  });

  console.log('\n=== Environment in Browser ===');
  console.log('NEXT_PUBLIC_API_URL:', envVars.NEXT_PUBLIC_API_URL);
  console.log('Window location:', envVars.windowLocation);

  await page.screenshot({ path: 'test-results/check-video-url.png', fullPage: true });
});
