import { test, expect } from '@playwright/test';

/**
 * Contour表示修正の検証テスト
 *
 * 目的: `convert_numpy_types` → `compress` の順序バグ修正を検証
 * 期待: 新規解析でcontour配列が生成され、UIで形状表示される
 */

test.describe('Contour Fix Verification', () => {
  test('新規解析でcontourが生成されることを確認', async ({ page }) => {
    // フロントエンドにアクセス
    await page.goto('http://localhost:3000');
    await expect(page.locator('h1')).toContainText('AI Surgical Motion');

    // アップロードページに移動
    await page.click('text=アップロード');
    await expect(page).toHaveURL(/.*upload/);

    // テスト動画をアップロード
    const videoPath = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend_experimental\\data\\uploads\\ad6de8d5-af49-470a-96f9-36b1925028dc.mp4';

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(videoPath);

    // 動画タイプ選択: external_with_instruments
    await page.click('text=体外器具追跡');

    // アップロード実行
    await page.click('button:has-text("アップロード")');

    // アップロード完了待機 (最大60秒)
    await expect(page.locator('text=アップロードが完了しました')).toBeVisible({ timeout: 60000 });

    // 動画IDを取得 (URLまたはUI要素から)
    const videoId = await page.evaluate(() => {
      const url = window.location.href;
      const match = url.match(/video\/([a-f0-9-]+)/);
      return match ? match[1] : null;
    });

    console.log(`Uploaded video ID: ${videoId}`);

    // 器具選択ページに移動
    await page.click('text=器具を選択');

    // 器具マスクを描画 (簡易的にクリック座標で選択)
    const canvas = page.locator('canvas').first();
    await canvas.click({ position: { x: 400, y: 300 } });
    await canvas.click({ position: { x: 410, y: 310 } });
    await canvas.click({ position: { x: 420, y: 320 } });

    // 器具を保存
    await page.click('button:has-text("器具を保存")');
    await expect(page.locator('text=器具が保存されました')).toBeVisible();

    // 解析を開始
    await page.click('button:has-text("解析を開始")');
    await expect(page.locator('text=解析を開始しました')).toBeVisible();

    // 解析完了待機 (最大300秒 = 5分)
    await page.waitForTimeout(5000); // 初期待機

    let analysisCompleted = false;
    for (let i = 0; i < 60; i++) {
      const status = await page.locator('text=解析中').isVisible();
      if (!status) {
        analysisCompleted = true;
        break;
      }
      await page.waitForTimeout(5000);
    }

    expect(analysisCompleted).toBe(true);

    // ダッシュボードに移動
    await expect(page).toHaveURL(/.*dashboard/);

    // 解析IDを取得
    const analysisId = await page.evaluate(() => {
      const url = window.location.href;
      const match = url.match(/dashboard\/([a-f0-9-]+)/);
      return match ? match[1] : null;
    });

    console.log(`Analysis ID: ${analysisId}`);

    // APIから解析結果を取得してcontourを検証
    const apiResponse = await page.evaluate(async (id) => {
      const response = await fetch(`http://localhost:8001/api/v1/analysis/${id}`);
      return await response.json();
    }, analysisId);

    console.log('API Response keys:', Object.keys(apiResponse));

    // instrument_dataの存在確認
    expect(apiResponse).toHaveProperty('instrument_data');
    expect(Array.isArray(apiResponse.instrument_data)).toBe(true);
    expect(apiResponse.instrument_data.length).toBeGreaterThan(0);

    // 最初のフレームのdetectionsを確認
    const firstFrame = apiResponse.instrument_data[0];
    expect(firstFrame).toHaveProperty('detections');
    expect(Array.isArray(firstFrame.detections)).toBe(true);
    expect(firstFrame.detections.length).toBeGreaterThan(0);

    // contourフィールドの存在と内容を確認
    const firstDetection = firstFrame.detections[0];
    expect(firstDetection).toHaveProperty('contour');
    console.log('First contour type:', typeof firstDetection.contour);
    console.log('First contour length:', firstDetection.contour?.length || 0);
    console.log('First contour sample:', firstDetection.contour?.slice(0, 3));

    // ✅ 修正後の期待: contourが空配列でない
    expect(Array.isArray(firstDetection.contour)).toBe(true);
    expect(firstDetection.contour.length).toBeGreaterThan(0);

    // contourの各要素が座標配列であることを確認
    const firstPoint = firstDetection.contour[0];
    expect(Array.isArray(firstPoint)).toBe(true);
    expect(firstPoint.length).toBe(2); // [x, y]
    expect(typeof firstPoint[0]).toBe('number');
    expect(typeof firstPoint[1]).toBe('number');

    console.log('✅ Contour validation passed!');
    console.log(`   - Contour points: ${firstDetection.contour.length}`);
    console.log(`   - First point: [${firstPoint[0]}, ${firstPoint[1]}]`);

    // UIで形状表示を確認 (Canvasに描画されているか)
    const canvasVisible = await page.locator('canvas').isVisible();
    expect(canvasVisible).toBe(true);

    console.log('✅ Test completed successfully!');
  });
});
