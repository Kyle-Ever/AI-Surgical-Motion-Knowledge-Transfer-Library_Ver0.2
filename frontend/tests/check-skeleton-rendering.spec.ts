/**
 * 骨格描画の詳細確認
 */

import { test } from '@playwright/test';

test('骨格描画の状態確認', async ({ page }) => {
  const comparisonId = '55653dc2-33eb-4a3c-8b6f-8892a3eb94a5';

  // コンソールログを全てキャプチャ
  const logs: string[] = [];
  page.on('console', (msg) => {
    const text = msg.text();
    logs.push(`[${msg.type()}] ${text}`);
  });

  console.log(`🎬 Loading comparison page...`);
  await page.goto(`http://localhost:3000/scoring/comparison/${comparisonId}`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);

  // 骨格関連のログを抽出
  console.log('\n=== Skeleton-related Console Logs ===');
  const skeletonLogs = logs.filter(log =>
    log.toLowerCase().includes('skeleton') ||
    log.toLowerCase().includes('hand') ||
    log.toLowerCase().includes('frame')
  );

  skeletonLogs.forEach(log => console.log(log));

  // Canvasが存在するか確認
  const canvasElements = await page.locator('canvas').count();
  console.log(`\n=== Canvas Elements ===`);
  console.log(`Canvas count: ${canvasElements}`);

  // 骨格検出トグルの状態を確認
  const skeletonToggle = page.locator('text=手技検出').first();
  const isToggleVisible = await skeletonToggle.isVisible().catch(() => false);
  console.log(`\n=== Skeleton Toggle ===`);
  console.log(`Toggle visible: ${isToggleVisible}`);

  if (isToggleVisible) {
    // トグルの状態を確認
    const toggleParent = skeletonToggle.locator('..');
    const toggleText = await toggleParent.textContent();
    console.log(`Toggle text: ${toggleText}`);
  }

  // スクリーンショットを撮る
  await page.screenshot({
    path: 'test-results/skeleton-rendering-check.png',
    fullPage: true
  });

  // ビデオプレイヤーのエラーがあるか確認
  const videoErrors = logs.filter(log =>
    log.includes('Video') ||
    log.includes('video') ||
    log.includes('load error')
  );

  if (videoErrors.length > 0) {
    console.log(`\n=== Video Errors ===`);
    videoErrors.forEach(err => console.log(err));
  }

  // 解析データが読み込まれたか確認
  const analysisLogs = logs.filter(log =>
    log.includes('analysis') ||
    log.includes('Analysis')
  );

  console.log(`\n=== Analysis Loading Logs (sample) ===`);
  analysisLogs.slice(0, 10).forEach(log => console.log(log));

  console.log(`\n✅ Total console logs: ${logs.length}`);
});
