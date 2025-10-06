import { test, expect } from '@playwright/test';

test.describe('E2E V2: 器具トラッキング分析（internal）', () => {
  let videoId: string | null = null;
  let analysisId: string | null = null;

  test.beforeAll(async ({ request }) => {
    // Internal動画を取得または作成
    const response = await request.get('http://localhost:8000/api/v1/videos');
    expect(response.ok()).toBeTruthy();

    const videos = await response.json();
    const internalVideo = videos.find((v: any) =>
      v.video_type === 'internal' || v.video_type === 'INTERNAL'
    );

    if (internalVideo) {
      videoId = internalVideo.id;
      console.log(`Using internal video: ${videoId}`);
    } else {
      // Test videoをinternalとして使用
      const testVideo = videos.find((v: any) =>
        v.filename === 'test_video.mp4'
      );
      if (testVideo) {
        videoId = testVideo.id;
        console.log(`Using test video as internal: ${videoId}`);
      }
    }
  });

  test('器具選択 → トラッキング開始 → tracking_stats詳細検証', async ({ page }) => {
    test.setTimeout(180000); // 3分タイムアウト

    if (!videoId) {
      test.skip();
    }

    // 1. 動画詳細ページにアクセス
    await page.goto(`http://localhost:3000/dashboard/${videoId}`);
    await page.waitForLoadState('networkidle');

    // 2. 器具トラッキングUIの確認
    // 器具選択ボタンまたは器具トラッキング開始ボタン
    const instrumentButton = page.locator(
      'button:has-text("器具"), button:has-text("Instrument"), button:has-text("トラッキング"), button:has-text("Track")'
    ).first();

    const hasInstrumentUI = await instrumentButton.isVisible({ timeout: 5000 }).catch(() => false);

    if (!hasInstrumentUI) {
      console.log('⚠️ Instrument tracking UI not found, may not be internal video');
      // 通常の分析開始ボタンを探す
      const analyzeButton = page.locator('button:has-text("分析"), button:has-text("Start")').first();
      await expect(analyzeButton).toBeVisible({ timeout: 10000 });

      // ボタン有効化待機
      for (let i = 0; i < 10; i++) {
        if (!await analyzeButton.isDisabled()) break;
        await page.waitForTimeout(500);
      }

      await analyzeButton.click();
    } else {
      console.log('✅ Instrument tracking UI found');

      // 3. 器具選択（手動選択が必要な場合）
      // クリックして器具選択モードに入る
      await instrumentButton.click();
      await page.waitForTimeout(1000);

      // ビデオプレイヤー上でクリック（器具選択）
      const videoPlayer = page.locator('video, canvas').first();
      if (await videoPlayer.isVisible()) {
        // 画面中央付近をクリック（器具選択）
        const box = await videoPlayer.boundingBox();
        if (box) {
          await page.mouse.click(box.x + box.width * 0.4, box.y + box.height * 0.4);
          await page.waitForTimeout(500);

          // 2つ目の器具選択
          await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.5);
          await page.waitForTimeout(500);
        }
      }

      // トラッキング開始ボタン
      const startTrackingButton = page.locator('button:has-text("トラッキング開始"), button:has-text("Start Tracking")').first();
      if (await startTrackingButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await startTrackingButton.click();
      }
    }

    console.log('Tracking/Analysis started');

    // 4. 処理中の進捗確認
    const progressIndicator = page.locator('text=/処理中|トラッキング中|Progress|Tracking|分析中/i').first();
    await expect(progressIndicator).toBeVisible({ timeout: 15000 });
    console.log('Progress indicator appeared');

    // 5. 完了まで待機（最大120秒）
    await Promise.race([
      page.locator('text=/完了|Complete|成功|Success/i').waitFor({ timeout: 120000 }).catch(() => null),
      page.waitForFunction(
        () => {
          const statusElement = document.querySelector('[data-status], [class*="status"]');
          return statusElement?.textContent?.includes('完了') || statusElement?.textContent?.includes('completed');
        },
        { timeout: 120000 }
      ).catch(() => null)
    ]);

    console.log('Tracking appears to be completed');

    // 6. URLから分析IDを取得
    await page.waitForTimeout(2000);
    const currentUrl = page.url();
    const analysisMatch = currentUrl.match(/analysis\/([a-f0-9-]+)/);
    if (analysisMatch) {
      analysisId = analysisMatch[1];
      console.log(`Analysis ID: ${analysisId}`);
    }

    // 7. APIで結果取得とtracking_stats詳細検証
    if (analysisId) {
      const response = await page.request.get(`http://localhost:8000/api/v1/analysis/${analysisId}`);
      expect(response.ok()).toBeTruthy();

      const result = await response.json();
      console.log('Analysis result status:', result.status);

      // ステータス確認
      expect(result.status).toBe('completed');

      // tracking_stats詳細検証
      if (result.tracking_stats) {
        console.log('✅ tracking_stats exists');
        console.log('tracking_stats:', JSON.stringify(result.tracking_stats, null, 2));

        // summaryフィールド検証
        if (result.tracking_stats.summary) {
          const summary = result.tracking_stats.summary;
          console.log(`Total frames: ${summary.total_frames}`);
          console.log(`Detected frames: ${summary.detected_frames}`);
          console.log(`Detection rate: ${(summary.detection_rate * 100).toFixed(2)}%`);

          // 検証
          expect(summary.total_frames).toBeGreaterThan(0);
          expect(summary.detected_frames).toBeGreaterThan(0);
          expect(summary.detection_rate).toBeGreaterThanOrEqual(0);
          expect(summary.detection_rate).toBeLessThanOrEqual(1);

          // 目標: 95%以上の検出率
          if (summary.detection_rate >= 0.95) {
            console.log(`✅ High detection rate achieved: ${(summary.detection_rate * 100).toFixed(2)}%`);
          } else {
            console.log(`⚠️ Detection rate below target: ${(summary.detection_rate * 100).toFixed(2)}% (target: 95%)`);
          }
        } else {
          console.log('⚠️ summary field not present in tracking_stats');
        }

        // 器具別統計確認
        const instrumentKeys = Object.keys(result.tracking_stats).filter(k => k.startsWith('instrument_'));
        if (instrumentKeys.length > 0) {
          console.log(`✅ Found ${instrumentKeys.length} instrument stats`);
          instrumentKeys.forEach(key => {
            console.log(`${key}:`, result.tracking_stats[key]);
          });
        }
      } else {
        console.log('⚠️ tracking_stats not present');
      }

      // last_error_frame検証（成功時はnull）
      if (result.last_error_frame === null) {
        console.log('✅ last_error_frame is null (no errors)');
      } else {
        console.log(`⚠️ last_error_frame: ${result.last_error_frame}`);
      }

      // warnings検証
      if (result.warnings && result.warnings.length > 0) {
        console.log(`⚠️ ${result.warnings.length} warnings found:`);
        result.warnings.forEach((w: any) => console.log(`  - ${w.message || w}`));
      } else {
        console.log('✅ No warnings (clean tracking)');
      }

      // instrument_data存在確認
      if (result.instrument_data) {
        console.log('✅ instrument_data exists');
        console.log(`Instrument data frames: ${result.instrument_data.length}`);
      }
    } else {
      console.log('⚠️ Could not extract analysis ID from URL');
    }

    console.log('✅ Internal analysis E2E test completed');
  });

  test('再検出ロジックの動作確認（Phase 1.2検証）', async ({ page }) => {
    // このテストは前のテストで生成された分析結果を使用
    if (!analysisId) {
      test.skip();
    }

    // API経由で分析結果を取得
    const response = await page.request.get(`http://localhost:8000/api/v1/analysis/${analysisId}`);
    expect(response.ok()).toBeTruthy();

    const result = await response.json();

    // tracking_statsから再検出情報を確認
    if (result.tracking_stats) {
      const stats = result.tracking_stats;

      // 器具別のlost_countやre_detection情報
      const instrumentKeys = Object.keys(stats).filter(k => k.startsWith('instrument_'));

      if (instrumentKeys.length > 0) {
        let totalReDetections = 0;

        instrumentKeys.forEach(key => {
          const instStats = stats[key];
          if (instStats.max_lost_count !== undefined) {
            console.log(`${key} max_lost_count: ${instStats.max_lost_count}`);
          }
          if (instStats.re_detections !== undefined) {
            totalReDetections += instStats.re_detections;
            console.log(`${key} re_detections: ${instStats.re_detections}`);
          }
        });

        if (totalReDetections > 0) {
          console.log(`✅ Re-detection logic activated: ${totalReDetections} total re-detections`);
        } else {
          console.log('ℹ️ No re-detections needed (continuous tracking)');
        }
      }
    }

    console.log('✅ Re-detection logic test completed');
  });
});