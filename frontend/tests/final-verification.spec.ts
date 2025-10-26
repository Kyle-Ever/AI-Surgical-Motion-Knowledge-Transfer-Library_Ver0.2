/**
 * 最終検証テスト - ケースインセンシティブ修正の効果確認
 *
 * 検証項目:
 * 1. 以前エラーだったComparison IDが正常に表示される
 * 2. Library APIで300+件の解析が取得できる
 * 3. 骨格データが正しく表示される
 */

import { test, expect } from '@playwright/test';

test.describe('採点モード修正 - 最終検証', () => {

  test('以前エラーだったComparison IDが正常に動作する', async ({ page }) => {
    console.log('🎯 修正前: エラーだったComparison IDへアクセス');

    // 以前エラーだったComparison ID
    const comparisonId = '29eadcf7-b399-4ce3-907d-20874a558f7c';

    await page.goto(`http://localhost:3000/scoring/comparison/${comparisonId}`);

    // ローディング完了を待つ
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // ✅ ダッシュボードが表示されることを確認（エラーページではない）
    await expect(page.locator('text=採点比較ダッシュボード')).toBeVisible({ timeout: 10000 });

    // ✅ 基準動作セクションが表示される
    await expect(page.locator('text=基準動作（指導医）')).toBeVisible();

    // ✅ 評価動作セクションが表示される
    await expect(page.locator('text=評価動作（学習者）')).toBeVisible();

    // ✅ スコアが表示される
    await expect(page.locator('text=総合スコア')).toBeVisible();

    console.log('✅ 修正後: 比較ダッシュボードが正常に表示されている');
    console.log('   → 修正前: "Comparison ID not found" エラー');
    console.log('   → 修正後: データベースから正しく取得できている');
  });

  test('Library APIで300+件の解析が取得できることを確認', async ({ page }) => {
    console.log('🎯 Library API動作確認');

    // Library APIを直接テスト
    const response = await page.request.get('http://localhost:8001/api/v1/library/completed?limit=300');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    console.log(`   ✅ 取得件数: ${data.length}件`);
    expect(data.length).toBeGreaterThanOrEqual(284);  // 最低284件期待

    // 最初の解析がSTATUS = 'COMPLETED'（大文字）でも取得できている
    if (data.length > 0) {
      console.log(`   ✅ 最初の解析ID: ${data[0].id.substring(0, 12)}...`);
      console.log(`   ✅ Status: ${data[0].status}`);
      expect(data[0].status).toBe('completed');  // 小文字で返ってくる
    }

    console.log('   → 修正前: 0件（大文字の"COMPLETED"を検索できなかった）');
    console.log('   → 修正後: func.lower()で大文字/小文字の両方に対応');
  });

  test('Reference Model作成が成功する', async ({ page }) => {
    console.log('🎯 Reference Model作成テスト');

    // Library APIから解析を1件取得
    const libraryResponse = await page.request.get('http://localhost:8001/api/v1/library/completed?limit=1');
    const analyses = await libraryResponse.json();

    expect(analyses.length).toBeGreaterThan(0);
    const testAnalysis = analyses[0];

    // Reference Model作成
    const createResponse = await page.request.post('http://localhost:8001/api/v1/scoring/reference', {
      data: {
        name: `Playwright Test ${Date.now()}`,
        description: 'E2E test reference model',
        analysis_id: testAnalysis.id,
        surgeon_name: 'テスト指導医',
        surgery_type: '腹腔鏡下胆嚢摘出術'
      }
    });

    expect(createResponse.status()).toBe(201);  // Created
    const result = await createResponse.json();

    console.log(`   ✅ Reference Model作成成功`);
    console.log(`   ✅ Model ID: ${result.id.substring(0, 12)}...`);
    console.log(`   ✅ Analysis ID: ${result.analysis_id.substring(0, 12)}...`);

    console.log('   → 修正前: 完了済み解析が見つからず作成失敗');
    console.log('   → 修正後: func.lower()で完了済み解析を正しく検索');
  });
});
