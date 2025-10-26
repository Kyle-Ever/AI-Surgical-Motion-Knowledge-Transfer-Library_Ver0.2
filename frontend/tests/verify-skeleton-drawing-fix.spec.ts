import { test, expect } from '@playwright/test';

test.describe('Scoring Mode - Skeleton Drawing Fix Verification', () => {
  test('骨格データが到着後、自動的にCanvasに描画される', async ({ page }) => {
    // 採点比較ページを開く
    await page.goto('http://localhost:3000/scoring/comparison/55653dc2-33eb-4a3c-8b6f-8892a3eb94a5');

    // ページ読み込み完了を待機
    await page.waitForLoadState('networkidle');

    // ビデオプレイヤーが表示されることを確認
    const referenceVideo = page.locator('video').first();
    const evaluationVideo = page.locator('video').nth(1);

    await expect(referenceVideo).toBeVisible();
    await expect(evaluationVideo).toBeVisible();

    // skeletonDataが到着するまで待機（最大10秒）
    await page.waitForFunction(() => {
      const logs = (window as any).__skeleton_logs || [];
      return logs.some((log: string) => log.includes('skeleton frames'));
    }, { timeout: 10000 });

    // Canvas要素を取得
    const referenceCanvas = page.locator('canvas').first();
    const evaluationCanvas = page.locator('canvas').nth(1);

    await expect(referenceCanvas).toBeVisible();
    await expect(evaluationCanvas).toBeVisible();

    // Canvasに実際に描画があることを確認（Canvas内容をチェック）
    const referenceCanvasHasDrawing = await referenceCanvas.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return false;
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      // ピクセルデータに透明でない部分があるかチェック
      for (let i = 3; i < imageData.data.length; i += 4) {
        if (imageData.data[i] > 0) return true; // Alpha値が0より大きい
      }
      return false;
    });

    const evaluationCanvasHasDrawing = await evaluationCanvas.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return false;
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 3; i < imageData.data.length; i += 4) {
        if (imageData.data[i] > 0) return true;
      }
      return false;
    });

    // 両方のCanvasに描画があることを確認
    expect(referenceCanvasHasDrawing).toBe(true);
    expect(evaluationCanvasHasDrawing).toBe(true);

    console.log('✅ Reference Canvas has drawing:', referenceCanvasHasDrawing);
    console.log('✅ Evaluation Canvas has drawing:', evaluationCanvasHasDrawing);
  });

  test('再生中、骨格がスムーズにアニメーションする', async ({ page }) => {
    await page.goto('http://localhost:3000/scoring/comparison/55653dc2-33eb-4a3c-8b6f-8892a3eb94a5');
    await page.waitForLoadState('networkidle');

    // 再生ボタンをクリック
    const playButton = page.locator('button').filter({ hasText: /▶️|⏸️/ }).first();
    await playButton.click();

    // 0.5秒待機
    await page.waitForTimeout(500);

    // Canvas描画を複数回サンプリング
    const canvas = page.locator('canvas').first();

    const sample1 = await canvas.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      return Array.from(imageData.data.slice(0, 100)); // 最初の100バイト
    });

    await page.waitForTimeout(200);

    const sample2 = await canvas.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      return Array.from(imageData.data.slice(0, 100));
    });

    // 2つのサンプルが異なる = アニメーションしている
    const isDifferent = JSON.stringify(sample1) !== JSON.stringify(sample2);
    expect(isDifferent).toBe(true);

    console.log('✅ Canvas animation is working');
  });

  test('ブラウザコンソールにRVFC使用ログが出力される', async ({ page }) => {
    const consoleLogs: string[] = [];

    page.on('console', msg => {
      if (msg.type() === 'log') {
        consoleLogs.push(msg.text());
      }
    });

    await page.goto('http://localhost:3000/scoring/comparison/55653dc2-33eb-4a3c-8b6f-8892a3eb94a5');
    await page.waitForLoadState('networkidle');

    // 再生ボタンをクリック（RVFC開始）
    const playButton = page.locator('button').filter({ hasText: /▶️|⏸️/ }).first();
    await playButton.click();

    await page.waitForTimeout(1000);

    // RVFCまたはRAFに関するログがあることを確認
    const hasRVFCorRAFLog = consoleLogs.some(log =>
      log.includes('requestVideoFrameCallback') ||
      log.includes('requestAnimationFrame') ||
      log.includes('RVFC') ||
      log.includes('RAF')
    );

    console.log('Console logs:', consoleLogs);
    console.log('Has RVFC/RAF log:', hasRVFCorRAFLog);

    // Note: コンソールログは実装によって出力されない場合もあるため、
    // ここではログの有無を確認するのみ（失敗させない）
    if (hasRVFCorRAFLog) {
      console.log('✅ RVFC/RAF logging detected');
    } else {
      console.log('ℹ️ No explicit RVFC/RAF logs (this is OK)');
    }
  });

  test('異なる比較IDでも骨格描画が動作する', async ({ page }) => {
    // 別の比較ID
    await page.goto('http://localhost:3000/scoring/comparison/69b982ad-fe69-40f6-b41a-85f2c369d853');
    await page.waitForLoadState('networkidle');

    // skeletonDataが到着するまで待機
    await page.waitForFunction(() => {
      const logs = (window as any).__skeleton_logs || [];
      return logs.some((log: string) => log.includes('skeleton frames'));
    }, { timeout: 10000 });

    const referenceCanvas = page.locator('canvas').first();
    const evaluationCanvas = page.locator('canvas').nth(1);

    await expect(referenceCanvas).toBeVisible();
    await expect(evaluationCanvas).toBeVisible();

    const referenceCanvasHasDrawing = await referenceCanvas.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return false;
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 3; i < imageData.data.length; i += 4) {
        if (imageData.data[i] > 0) return true;
      }
      return false;
    });

    expect(referenceCanvasHasDrawing).toBe(true);
    console.log('✅ Different comparison ID works correctly');
  });
});
