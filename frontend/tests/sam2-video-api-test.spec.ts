import { test, expect } from '@playwright/test';

/**
 * SAM2 Video API 完全動作テスト
 *
 * 目的：
 * 1. 新規動画アップロード
 * 2. 器具選択（EXTERNAL_WITH_INSTRUMENTS）
 * 3. 解析実行
 * 4. 進捗が35%を超えて100%まで完了するか確認
 * 5. エラーメッセージが適切に表示されるか確認
 */

test.describe('SAM2 Video API E2E Test', () => {
  test.beforeEach(async ({ page }) => {
    // ホームページに移動
    await page.goto('http://localhost:3000');
  });

  test('新規動画アップロード→解析完了までの完全フロー', async ({ page }) => {
    test.setTimeout(600000); // 10分タイムアウト（解析に時間がかかる）

    // Step 1: アップロードページに移動
    await page.goto('http://localhost:3000/upload');
    await expect(page.locator('h1')).toContainText('動画アップロード');

    // Step 2: テスト動画を選択
    const fileInput = page.locator('input[type="file"]');
    const testVideoPath = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend_experimental\\data\\uploads\\test_surgical_video.mp4';

    // ファイルが存在するか確認
    await fileInput.setInputFiles(testVideoPath);
    console.log('✅ テスト動画選択完了');

    // Step 3: 基本情報入力
    await page.fill('input[name="surgeryName"]', 'Playwright SAM2 Test');
    await page.fill('input[name="surgeonName"]', 'Dr. Test');

    // Step 4: 動画タイプ選択（EXTERNAL_WITH_INSTRUMENTS）
    await page.selectOption('select[name="videoType"]', 'external_with_instruments');
    console.log('✅ EXTERNAL_WITH_INSTRUMENTS 選択完了');

    // Step 5: アップロード実行
    await page.click('button:has-text("アップロード")');

    // アップロード完了まで待機（最大60秒）
    await expect(page.locator('text=アップロード完了')).toBeVisible({ timeout: 60000 });
    console.log('✅ アップロード完了');

    // Step 6: ダッシュボードに遷移
    const currentUrl = page.url();
    expect(currentUrl).toContain('/dashboard/');
    const videoId = currentUrl.split('/dashboard/')[1];
    console.log(`✅ 動画ID取得: ${videoId}`);

    // Step 7: 器具選択（最低1つ）
    await page.waitForSelector('canvas', { timeout: 10000 });

    // キャンバス上でクリックして器具領域を選択
    const canvas = page.locator('canvas').first();
    await canvas.click({ position: { x: 320, y: 240 } }); // 中央付近
    console.log('✅ 器具選択完了');

    // Step 8: 解析開始
    await page.click('button:has-text("解析開始")');
    console.log('✅ 解析開始ボタンクリック');

    // Step 9: 進捗監視（35%を超えるか確認）
    let progress = 0;
    let analysisId = '';

    // 解析IDを取得
    await page.waitForTimeout(2000);
    const analysisUrl = page.url();
    if (analysisUrl.includes('/analysis/')) {
      analysisId = analysisUrl.split('/analysis/')[1];
      console.log(`✅ 解析ID取得: ${analysisId}`);
    }

    // 進捗を監視（最大5分）
    const startTime = Date.now();
    const maxWaitTime = 300000; // 5分

    while (Date.now() - startTime < maxWaitTime) {
      // APIから進捗を取得
      const response = await page.request.get(`http://localhost:8001/api/v1/analysis/${analysisId}`);
      const data = await response.json();

      progress = data.progress || 0;
      const status = data.status;
      const errorMessage = data.error_message;

      console.log(`⏳ 進捗: ${progress}% | ステータス: ${status}`);

      // エラーが発生した場合
      if (status === 'failed') {
        console.error(`❌ 解析失敗: ${errorMessage}`);

        // error_messageが取得できているか確認
        expect(errorMessage).toBeTruthy();
        expect(errorMessage).not.toBe(null);

        throw new Error(`解析失敗: ${errorMessage}`);
      }

      // 35%を超えたことを確認
      if (progress > 35) {
        console.log(`✅ 進捗35%超え達成: ${progress}%`);
      }

      // 完了した場合
      if (status === 'completed') {
        console.log(`🎉 解析完了: ${progress}%`);

        // 必須データの検証
        expect(data.skeleton_data).toBeTruthy();
        expect(data.instrument_data).toBeTruthy();
        console.log(`✅ skeleton_data: ${data.skeleton_data?.length || 0} frames`);
        console.log(`✅ instrument_data: ${data.instrument_data?.length || 0} items`);

        break;
      }

      // 3秒待機
      await page.waitForTimeout(3000);
    }

    // タイムアウトチェック
    if (Date.now() - startTime >= maxWaitTime) {
      throw new Error(`タイムアウト: 5分以内に完了しませんでした（最終進捗: ${progress}%）`);
    }

    // 最終確認：進捗100%
    expect(progress).toBe(100);
    console.log('🎉 すべてのテスト完了！');
  });

  test('失敗した解析のエラーメッセージ表示確認', async ({ page }) => {
    // 既知の失敗解析ID
    const failedAnalysisId = '5b4cebec-6cb4-4dfc-a4b2-255d594c1c7c';

    // APIから直接確認
    const response = await page.request.get(`http://localhost:8001/api/v1/analysis/${failedAnalysisId}`);
    const data = await response.json();

    console.log('失敗解析データ:', JSON.stringify(data, null, 2));

    // 必須フィールドの検証
    expect(data.status).toBe('failed');
    expect(data.progress).toBe(35);
    expect(data.current_step).toBe('skeleton_detection');
    expect(data.error_message).toBeTruthy();
    expect(data.error_message).toContain('decord');

    console.log(`✅ エラーメッセージ表示確認: "${data.error_message}"`);

    // UIでも確認
    await page.goto(`http://localhost:3000/analysis/${failedAnalysisId}`);
    await page.waitForSelector('text=failed', { timeout: 5000 });

    // エラーメッセージがUIに表示されているか確認
    const errorText = await page.textContent('body');
    expect(errorText).toContain('decord');

    console.log('✅ UIでもエラーメッセージ表示確認完了');
  });
});
