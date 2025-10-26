/**
 * 特定のComparison IDの表示確認
 */

import { test, expect } from '@playwright/test';

test('Comparison ID: 69b982ad-fe69-40f6-b41a-85f2c369d853 の表示確認', async ({ page }) => {
  const comparisonId = '69b982ad-fe69-40f6-b41a-85f2c369d853';

  // コンソールログを記録
  page.on('console', (msg) => {
    console.log(`[Browser ${msg.type()}]: ${msg.text()}`);
  });

  console.log(`🔍 Accessing: http://localhost:3000/scoring/comparison/${comparisonId}`);

  await page.goto(`http://localhost:3000/scoring/comparison/${comparisonId}`);

  // ページ読み込み完了を待つ
  await page.waitForTimeout(3000);

  // スクリーンショット
  await page.screenshot({
    path: `test-results/comparison-${comparisonId.substring(0, 8)}.png`,
    fullPage: true
  });

  // ページのテキストコンテンツを取得
  const bodyText = await page.locator('body').textContent();
  console.log('\n===== Page Content =====');
  console.log(bodyText?.substring(0, 500));

  // エラーメッセージが表示されているか確認
  const errorHeading = page.locator('h2:has-text("比較データが見つかりません")');
  const isErrorPageVisible = await errorHeading.isVisible().catch(() => false);

  if (isErrorPageVisible) {
    console.log('❌ エラーページが表示されています');
    console.log('   → エラーメッセージ: 比較データが見つかりません');

    // Comparison IDが表示されているか確認
    const codeElements = await page.locator('code').allTextContents();
    console.log(`   → 表示されているID: ${codeElements.join(', ')}`);
  } else {
    // ダッシュボードが表示されているか確認
    const dashboardTitle = page.locator('text=採点比較ダッシュボード');
    const isDashboardVisible = await dashboardTitle.isVisible().catch(() => false);

    if (isDashboardVisible) {
      console.log('✅ ダッシュボードが表示されています');

      // スコアセクションが表示されているか
      const scoreSection = page.locator('text=総合スコア');
      const hasScore = await scoreSection.isVisible().catch(() => false);
      console.log(`   → スコア表示: ${hasScore ? 'あり' : 'なし'}`);
    } else {
      console.log('⚠️  ローディング中または不明な状態');
    }
  }

  // APIリクエストを直接確認
  console.log('\n===== API Direct Check =====');
  const apiResponse = await page.request.get(
    `http://localhost:8001/api/v1/scoring/comparison/${comparisonId}?include_details=true`
  );

  console.log(`API Status: ${apiResponse.status()}`);

  if (apiResponse.ok()) {
    const data = await apiResponse.json();
    console.log(`✅ API Success - Comparison found`);
    console.log(`   ID: ${data.id}`);
    console.log(`   Status: ${data.status}`);
    console.log(`   Reference Model ID: ${data.reference_model_id || 'N/A'}`);
    console.log(`   Learner Analysis ID: ${data.learner_analysis_id || 'N/A'}`);
  } else {
    const errorText = await apiResponse.text();
    console.log(`❌ API Error: ${errorText.substring(0, 300)}`);
  }
});
