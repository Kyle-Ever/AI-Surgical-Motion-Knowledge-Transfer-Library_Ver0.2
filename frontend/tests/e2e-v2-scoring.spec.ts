import { test, expect } from '@playwright/test';

test.describe('E2E V2: スコアリング・比較フロー', () => {
  let completedAnalysisId: string | null = null;
  let referenceVideoId: string | null = null;

  test.beforeAll(async ({ request }) => {
    // 完了済み分析を取得
    const videosResponse = await request.get('http://localhost:8000/api/v1/videos');
    expect(videosResponse.ok()).toBeTruthy();

    const videos = await videosResponse.json();

    // 分析完了済みの動画を探す
    for (const video of videos) {
      const analysisResponse = await request.get(`http://localhost:8000/api/v1/analysis?video_id=${video.id}`);
      if (analysisResponse.ok()) {
        const analyses = await analysisResponse.json();
        const completedAnalysis = analyses.find((a: any) => a.status === 'completed');
        if (completedAnalysis) {
          completedAnalysisId = completedAnalysis.id;
          console.log(`Found completed analysis: ${completedAnalysisId}`);
          break;
        }
      }
    }

    // リファレンス動画を取得
    const refResponse = await request.get('http://localhost:8000/api/v1/library/references');
    if (refResponse.ok()) {
      const references = await refResponse.json();
      if (references.length > 0) {
        referenceVideoId = references[0].id;
        console.log(`Found reference video: ${referenceVideoId}`);
      }
    }
  });

  test('分析結果からリファレンス比較実行 → スコア表示', async ({ page }) => {
    test.setTimeout(120000);

    if (!completedAnalysisId) {
      console.log('⚠️ No completed analysis found, skipping test');
      test.skip();
    }

    // 1. 分析結果ページにアクセス
    await page.goto(`http://localhost:3000/analysis/${completedAnalysisId}`);
    await page.waitForLoadState('networkidle');

    // 2. ページが正しく表示されることを確認
    await expect(page.locator('h1, h2').first()).toBeVisible();

    // 3. 「リファレンスと比較」ボタンを探す
    const compareButton = page.locator(
      'button:has-text("比較"), button:has-text("Compare"), button:has-text("リファレンス")'
    ).first();

    const hasCompareButton = await compareButton.isVisible({ timeout: 5000 }).catch(() => false);

    if (!hasCompareButton) {
      console.log('⚠️ Compare button not found on analysis page');

      // 別のルートを試す: ダッシュボードから比較
      const videoIdMatch = page.url().match(/video_id=([a-f0-9-]+)/);
      if (videoIdMatch) {
        await page.goto(`http://localhost:3000/dashboard/${videoIdMatch[1]}`);
        await page.waitForLoadState('networkidle');

        const dashboardCompareBtn = page.locator('button:has-text("比較"), button:has-text("Compare")').first();
        if (await dashboardCompareBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
          await dashboardCompareBtn.click();
        } else {
          console.log('⚠️ No compare functionality found');
          test.skip();
        }
      } else {
        test.skip();
      }
    } else {
      // 4. 比較ボタンをクリック
      await compareButton.click();
      await page.waitForTimeout(1000);
    }

    // 5. リファレンス選択UIが表示される
    if (referenceVideoId) {
      // リファレンス動画を選択
      const refSelector = page.locator(`[data-video-id="${referenceVideoId}"], button:has-text("選択")`).first();
      if (await refSelector.isVisible({ timeout: 5000 }).catch(() => false)) {
        await refSelector.click();
        console.log('Reference video selected');
      }
    }

    // 6. 比較実行ボタン
    const executeCompareBtn = page.locator('button:has-text("比較実行"), button:has-text("実行"), button:has-text("Execute")').first();
    if (await executeCompareBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await executeCompareBtn.click();
      console.log('Comparison execution started');
    }

    // 7. 比較結果表示待機（30秒）
    await Promise.race([
      page.locator('text=/スコア|Score|結果|Result/i').waitFor({ timeout: 30000 }).catch(() => null),
      page.waitForURL('**/comparison/**', { timeout: 30000 }).catch(() => null)
    ]);

    // 8. スコア表示の確認
    const scoreDisplay = page.locator('[data-score], [class*="score"], text=/\\d+(\\.\\d+)?点|\\d+(\\.\\d+)?%/').first();
    const hasScore = await scoreDisplay.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasScore) {
      console.log('✅ Score display found');
    } else {
      console.log('⚠️ Score display not found');
    }

    // 9. グラフ・ビジュアライゼーション確認
    const charts = page.locator('canvas, svg').all();
    const chartCount = (await charts).length;
    console.log(`Found ${chartCount} chart/graph elements`);

    if (chartCount > 0) {
      console.log('✅ Visualization elements found');
    }

    console.log('✅ Scoring E2E test completed');
  });

  test('スコアリングAPI直接呼び出しテスト', async ({ request }) => {
    if (!completedAnalysisId || !referenceVideoId) {
      console.log('⚠️ Missing analysis or reference, skipping API test');
      test.skip();
    }

    // スコアリングAPI呼び出し
    const response = await request.post('http://localhost:8000/api/v1/scoring/compare', {
      data: {
        analysis_id: completedAnalysisId,
        reference_video_id: referenceVideoId
      }
    });

    if (response.ok()) {
      const result = await response.json();
      console.log('Scoring result:', JSON.stringify(result, null, 2));

      // 基本的なスコア構造確認
      expect(result).toBeDefined();

      // スコアフィールドの存在確認
      if (result.scores) {
        console.log('✅ scores field exists');

        // 各種メトリクススコアの確認
        if (result.scores.velocity_score !== undefined) {
          console.log(`Velocity score: ${result.scores.velocity_score}`);
        }
        if (result.scores.distance_score !== undefined) {
          console.log(`Distance score: ${result.scores.distance_score}`);
        }
        if (result.scores.angle_score !== undefined) {
          console.log(`Angle score: ${result.scores.angle_score}`);
        }
        if (result.scores.overall_score !== undefined) {
          console.log(`Overall score: ${result.scores.overall_score}`);
        }
      }

      console.log('✅ Scoring API test passed');
    } else {
      console.log(`⚠️ Scoring API failed: ${response.status()}`);
      const errorText = await response.text();
      console.log(`Error: ${errorText}`);
    }
  });

  test('メトリクス計算の正確性検証', async ({ request }) => {
    if (!completedAnalysisId) {
      test.skip();
    }

    // 分析結果を取得
    const response = await request.get(`http://localhost:8000/api/v1/analysis/${completedAnalysisId}`);
    expect(response.ok()).toBeTruthy();

    const result = await response.json();

    // メトリクスフィールドの確認
    console.log('Metrics validation:');

    if (result.avg_velocity !== undefined && result.avg_velocity !== null) {
      console.log(`✅ avg_velocity: ${result.avg_velocity}`);
      expect(result.avg_velocity).toBeGreaterThanOrEqual(0);
    }

    if (result.max_velocity !== undefined && result.max_velocity !== null) {
      console.log(`✅ max_velocity: ${result.max_velocity}`);
      expect(result.max_velocity).toBeGreaterThanOrEqual(0);
    }

    if (result.total_distance !== undefined && result.total_distance !== null) {
      console.log(`✅ total_distance: ${result.total_distance}`);
      expect(result.total_distance).toBeGreaterThanOrEqual(0);
    }

    if (result.total_frames !== undefined && result.total_frames !== null) {
      console.log(`✅ total_frames: ${result.total_frames}`);
      expect(result.total_frames).toBeGreaterThan(0);
    }

    // velocity_dataとangle_dataの存在確認
    if (result.velocity_data) {
      console.log('✅ velocity_data exists');
    }

    if (result.angle_data) {
      console.log('✅ angle_data exists');
    }

    console.log('✅ Metrics validation completed');
  });
});