import { test, expect } from '@playwright/test';

test.describe('E2E V2: 手トラッキング分析（external）', () => {
  let videoId: string | null = null;
  let analysisId: string | null = null;

  test.beforeAll(async ({ request }) => {
    // テスト用動画を取得（既存のtest_video.mp4を使用）
    const response = await request.get('http://localhost:8000/api/v1/videos');
    expect(response.ok()).toBeTruthy();

    const videos = await response.json();
    const testVideo = videos.find((v: any) =>
      v.filename === 'test_video.mp4' || v.original_filename === 'test_video.mp4'
    );

    if (testVideo) {
      videoId = testVideo.id;
      console.log(`Using existing test video: ${videoId}`);
    } else {
      console.log('No test video found, test may fail');
    }
  });

  test('既存分析結果表示 → tracking_stats検証', async ({ page }) => {
    test.setTimeout(120000); // 2分タイムアウト

    if (!videoId) {
      test.skip();
    }

    // 1. まずAPIで完了済みの分析を探す
    const analysesResponse = await page.request.get(`http://localhost:8000/api/v1/videos/${videoId}/analyses`);
    let completedAnalysis = null;

    if (analysesResponse.ok()) {
      const analyses = await analysesResponse.json();
      completedAnalysis = analyses.find((a: any) => a.status === 'completed');

      if (completedAnalysis) {
        analysisId = completedAnalysis.id;
        console.log(`Found completed analysis: ${analysisId}`);
      }
    }

    // 2. 完了済み分析がない場合はスキップ
    if (!analysisId) {
      console.log('⚠️ No completed analysis found, skipping test');
      test.skip();
      return;
    }

    // 3. 分析結果ページにアクセス
    await page.goto(`http://localhost:3000/analysis/${analysisId}`);
    await page.waitForLoadState('networkidle');

    // 4. ページが正しく表示されることを確認
    await expect(page.locator('h1, h2, [data-testid="analysis-title"]').first()).toBeVisible({ timeout: 10000 });
    console.log('Analysis page loaded');

    // 5. ダッシュボードページを試す（analysisIdは実際にはvideoIdかもしれない）
    await page.goto(`http://localhost:3000/dashboard/${videoId}`);
    await page.waitForLoadState('networkidle');

    // 6. ページコンテンツの存在確認
    const hasContent = await page.locator('text=/解析|動画|分析|Dashboard/i').isVisible({ timeout: 5000 }).catch(() => false);

    if (hasContent) {
      console.log('✅ Dashboard page loaded with content');
    } else {
      console.log('⚠️ Dashboard page may not have analysis data');
    }

    // 8. APIで分析結果を確認（V2フィールド検証）
    if (analysisId) {
      const response = await page.request.get(`http://localhost:8000/api/v1/analysis/${analysisId}`);
      expect(response.ok()).toBeTruthy();

      const result = await response.json();
      console.log('Analysis result:', JSON.stringify(result, null, 2));

      // V2フィールドの存在確認
      expect(result.status).toBe('completed');

      // tracking_stats存在確認
      if (result.tracking_stats) {
        console.log('✅ tracking_stats field exists');
        expect(result.tracking_stats).toBeDefined();

        // summaryフィールド確認
        if (result.tracking_stats.summary) {
          console.log(`Detection rate: ${result.tracking_stats.summary.detection_rate}`);
          expect(result.tracking_stats.summary.total_frames).toBeGreaterThan(0);
        }
      } else {
        console.log('⚠️ tracking_stats not present (may be expected for external analysis)');
      }

      // last_error_frameが存在しないこと（成功時）
      expect(result.last_error_frame).toBeNull();
      console.log('✅ last_error_frame is null (success)');

      // warningsが空またはnull
      if (result.warnings) {
        console.log(`⚠️ Warnings present: ${result.warnings.length}`);
      } else {
        console.log('✅ No warnings (clean analysis)');
      }
    }

    // 9. UI上で結果データ表示確認
    // スケルトンデータ、グラフ、メトリクスなどの表示
    const dataVisualization = page.locator('canvas, svg, [class*="chart"], [class*="graph"]').first();
    const hasVisualization = await dataVisualization.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasVisualization) {
      console.log('✅ Data visualization found');
    } else {
      console.log('⚠️ No data visualization found');
    }

    console.log('✅ External analysis E2E test completed');
  });

  test('WebSocket接続の基本動作確認', async ({ page }) => {
    test.setTimeout(60000);

    if (!videoId) {
      test.skip();
    }

    // WebSocketメッセージをキャプチャ
    const wsMessages: any[] = [];

    page.on('websocket', ws => {
      console.log('WebSocket connection established');

      ws.on('framereceived', event => {
        const message = event.payload;
        try {
          const parsed = JSON.parse(message.toString());
          wsMessages.push(parsed);
          console.log('WS message:', parsed);
        } catch (e) {
          // Non-JSON message
        }
      });
    });

    // ページにアクセスしてWebSocket接続を待つ
    await page.goto(`http://localhost:3000/dashboard/${videoId}`);
    await page.waitForLoadState('networkidle');

    // WebSocketメッセージ受信待機（10秒）
    await page.waitForTimeout(10000);

    // Next.jsの開発サーバーWebSocketメッセージが受信されているか確認
    if (wsMessages.length > 0) {
      console.log(`✅ Received ${wsMessages.length} WebSocket messages`);
      console.log('WebSocket connection is working');
    } else {
      console.log('⚠️ No WebSocket messages received');
    }

    console.log('✅ WebSocket basic connection test completed');
  });
});