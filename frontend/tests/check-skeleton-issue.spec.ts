/**
 * 骨格検出問題の調査
 * Comparison ID: 55653dc2-33eb-4a3c-8b6f-8892a3eb94a5
 */

import { test } from '@playwright/test';

test('骨格検出問題の詳細調査', async ({ page }) => {
  const comparisonId = '55653dc2-33eb-4a3c-8b6f-8892a3eb94a5';

  console.log(`🔍 Investigating: ${comparisonId}`);

  // APIから直接データを取得
  const apiResponse = await page.request.get(
    `http://localhost:8001/api/v1/scoring/comparison/${comparisonId}?include_details=true`
  );

  if (apiResponse.ok()) {
    const comparisonData = await apiResponse.json();
    console.log('\n=== Comparison Data ===');
    console.log(`ID: ${comparisonData.id}`);
    console.log(`Status: ${comparisonData.status}`);
    console.log(`Reference Model ID: ${comparisonData.reference_model_id}`);
    console.log(`Learner Analysis ID: ${comparisonData.learner_analysis_id}`);

    // Learner Analysis の詳細を取得
    if (comparisonData.learner_analysis_id) {
      const learnerResponse = await page.request.get(
        `http://localhost:8001/api/v1/analysis/${comparisonData.learner_analysis_id}`
      );

      if (learnerResponse.ok()) {
        const learnerData = await learnerResponse.json();
        console.log('\n=== Learner Analysis ===');
        console.log(`ID: ${learnerData.id}`);
        console.log(`Status: ${learnerData.status}`);
        console.log(`Video ID: ${learnerData.video_id}`);

        // 骨格データの有無を確認
        const skeletonData = learnerData.skeleton_data;
        if (skeletonData) {
          console.log(`✅ Skeleton Data: ${skeletonData.length} frames`);

          // 最初のフレームの詳細を確認
          if (skeletonData.length > 0) {
            const firstFrame = skeletonData[0];
            console.log(`\n=== First Frame Sample ===`);
            console.log(JSON.stringify(firstFrame, null, 2).substring(0, 500));
          }
        } else {
          console.log(`❌ Skeleton Data: MISSING (null or undefined)`);
        }

        // その他の解析データ
        console.log(`\n=== Other Analysis Data ===`);
        console.log(`Instrument Data: ${learnerData.instrument_data ? learnerData.instrument_data.length + ' items' : 'MISSING'}`);
        console.log(`Motion Analysis: ${learnerData.motion_analysis ? 'EXISTS' : 'MISSING'}`);
        console.log(`Scores: ${learnerData.scores ? JSON.stringify(learnerData.scores) : 'MISSING'}`);
        console.log(`Total Frames: ${learnerData.total_frames || 'N/A'}`);
      }
    }

    // Reference Model の詳細を取得
    if (comparisonData.reference_model_id) {
      const refModelResponse = await page.request.get(
        `http://localhost:8001/api/v1/scoring/reference/${comparisonData.reference_model_id}`
      );

      if (refModelResponse.ok()) {
        const refModelData = await refModelResponse.json();
        console.log('\n=== Reference Model ===');
        console.log(`ID: ${refModelData.id}`);
        console.log(`Analysis ID: ${refModelData.analysis_id}`);

        // Reference Analysisを取得
        if (refModelData.analysis_id) {
          const refAnalysisResponse = await page.request.get(
            `http://localhost:8001/api/v1/analysis/${refModelData.analysis_id}`
          );

          if (refAnalysisResponse.ok()) {
            const refAnalysisData = await refAnalysisResponse.json();
            console.log('\n=== Reference Analysis ===');
            console.log(`ID: ${refAnalysisData.id}`);
            console.log(`Status: ${refAnalysisData.status}`);
            console.log(`Video ID: ${refAnalysisData.video_id}`);

            // 骨格データの有無を確認
            const refSkeletonData = refAnalysisData.skeleton_data;
            if (refSkeletonData) {
              console.log(`✅ Skeleton Data: ${refSkeletonData.length} frames`);
            } else {
              console.log(`❌ Skeleton Data: MISSING (null or undefined)`);
            }
          }
        }
      }
    }

  } else {
    console.log(`❌ API Error: ${apiResponse.status()}`);
    const errorText = await apiResponse.text();
    console.log(errorText);
  }

  // フロントエンドでの表示を確認
  await page.goto(`http://localhost:3000/scoring/comparison/${comparisonId}`);
  await page.waitForTimeout(3000);

  // コンソールログを監視
  page.on('console', (msg) => {
    const text = msg.text();
    if (text.includes('skeleton') || text.includes('Skeleton')) {
      console.log(`[Browser]: ${text}`);
    }
  });

  await page.waitForTimeout(2000);

  // スクリーンショット
  await page.screenshot({
    path: `test-results/skeleton-issue-${comparisonId.substring(0, 8)}.png`,
    fullPage: true
  });

  console.log('\n✅ Investigation complete. Check screenshot and logs above.');
});
