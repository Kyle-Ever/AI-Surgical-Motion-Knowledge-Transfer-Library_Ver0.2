import { test } from '@playwright/test';

test('Check video URLs being used', async ({ page }) => {
  const logs: string[] = [];

  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('videoUrl') || text.includes('Comparison result') || text.includes('video ID')) {
      logs.push(text);
    }
  });

  await page.goto('http://localhost:3000/scoring/comparison/cddd1e9c-1c83-4011-a99f-79be18d5f547', {
    waitUntil: 'domcontentloaded',
    timeout: 60000
  });

  await page.waitForTimeout(3000);

  // Extract video source URLs from the page
  const videoSources = await page.evaluate(() => {
    const videos = Array.from(document.querySelectorAll('video'));
    return videos.map(v => {
      const source = v.querySelector('source');
      return {
        src: source?.src || v.src,
        readyState: v.readyState,
        error: v.error?.message || null
      };
    });
  });

  console.log('\n=== Video Source URLs ===');
  videoSources.forEach((v, i) => {
    console.log(`Video ${i + 1}:`);
    console.log(`  src: ${v.src}`);
    console.log(`  readyState: ${v.readyState}`);
    console.log(`  error: ${v.error}`);
  });

  console.log('\n=== Console Logs with videoUrl/ID ===');
  logs.forEach(log => console.log(log));
});
