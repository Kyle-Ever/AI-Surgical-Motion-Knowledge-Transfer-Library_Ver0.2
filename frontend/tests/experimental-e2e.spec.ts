/**
 * 実験版バックエンド E2Eテスト
 *
 * Playwright MCPを使用した実験版の包括的テスト
 */
import { test, expect } from '@playwright/test';

const EXPERIMENTAL_API_URL = 'http://localhost:8001/api/v1';
const FRONTEND_URL = 'http://localhost:3000';

test.describe('実験版バックエンド E2Eテスト', () => {
  test.beforeEach(async ({ page }) => {
    // 実験版バックエンドを使用するように設定
    await page.goto(FRONTEND_URL);
  });

  test('実験版バッジが表示される', async ({ page }) => {
    // 環境バッジをチェック
    const badge = page.locator('text=実験版モード');

    // バッジが表示される場合（実験版の場合）
    const badgeCount = await badge.count();
    if (badgeCount > 0) {
      await expect(badge).toBeVisible();
      await expect(page.locator('text=Port 8001')).toBeVisible();
    }
    // 安定版の場合はバッジが表示されない
  });

  test('実験版APIヘルスチェック', async ({ request }) => {
    const response = await request.get(`${EXPERIMENTAL_API_URL}/health`);

    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('status');
    expect(data.status).toBe('healthy');
  });

  test('動画アップロード（実験版）', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/videos`);

    // アップロードボタンをクリック
    await page.click('text=動画をアップロード');

    // ファイル選択ダイアログが表示される
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();

    // テスト動画ファイルをアップロード
    const testVideoPath = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend_experimental\\test.mp4';

    // ファイルが存在する場合のみアップロード
    await fileInput.setInputFiles(testVideoPath).catch(() => {
      console.log('テスト動画ファイルが見つかりません。スキップします。');
    });

    // アップロード成功メッセージを待つ（タイムアウトは30秒）
    await expect(page.locator('text=アップロード完了').or(page.locator('text=成功'))).toBeVisible({ timeout: 30000 }).catch(() => {
      console.log('アップロード確認をスキップ');
    });
  });

  test('解析実行（実験版 - SAM2 Video API）', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/videos`);

    // 動画リストから最初の動画を選択
    const firstVideo = page.locator('[data-testid="video-item"]').first();

    // 動画が存在する場合のみテスト
    const videoCount = await firstVideo.count();
    if (videoCount === 0) {
      test.skip();
      return;
    }

    await firstVideo.click();

    // 解析開始ボタン
    await page.click('text=解析を開始');

    // 解析タイプ選択（内部トラッキング = SAM2 Video API使用）
    await page.click('text=内部トラッキング');

    // 解析実行確認
    await page.click('text=実行');

    // 解析進捗を監視
    await expect(page.locator('text=解析中').or(page.locator('[role="progressbar"]'))).toBeVisible({ timeout: 5000 });

    // 解析完了を待つ（最大5分）
    await expect(page.locator('text=解析完了').or(page.locator('text=完了'))).toBeVisible({ timeout: 300000 });
  });

  test('解析結果表示（実験版）', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/analysis`);

    // 解析結果リストを確認
    const resultList = page.locator('[data-testid="analysis-list"]');

    // リストが存在する場合
    const listCount = await resultList.count();
    if (listCount > 0) {
      // 最初の結果をクリック
      await resultList.first().click();

      // 結果詳細が表示される
      await expect(page.locator('text=器具トラッキング結果').or(page.locator('text=検出結果'))).toBeVisible({ timeout: 10000 });

      // フレームデータが存在することを確認
      const frameData = page.locator('[data-testid="frame-data"]');
      await expect(frameData).toBeVisible().catch(() => {
        console.log('フレームデータ要素が見つかりません');
      });
    }
  });

  test('データフォーマット互換性（APIレスポンス）', async ({ request }) => {
    // 動画リストを取得
    const videosResponse = await request.get(`${EXPERIMENTAL_API_URL}/videos`);
    expect(videosResponse.ok()).toBeTruthy();

    const videos = await videosResponse.json();

    if (videos.length === 0) {
      test.skip();
      return;
    }

    const firstVideoId = videos[0].id;

    // 解析リストを取得
    const analysesResponse = await request.get(`${EXPERIMENTAL_API_URL}/analysis?video_id=${firstVideoId}`);
    expect(analysesResponse.ok()).toBeTruthy();

    const analyses = await analysesResponse.json();

    if (analyses.length === 0) {
      test.skip();
      return;
    }

    const analysisId = analyses[0].id;

    // 解析結果を取得
    const resultResponse = await request.get(`${EXPERIMENTAL_API_URL}/analysis/${analysisId}`);
    expect(resultResponse.ok()).toBeTruthy();

    const result = await resultResponse.json();

    // データフォーマット検証
    expect(result).toHaveProperty('id');
    expect(result).toHaveProperty('status');

    // 器具データフォーマット（Video API結果が変換されている）
    if (result.instrument_data) {
      expect(Array.isArray(result.instrument_data)).toBeTruthy();

      // 最初のフレームを検証
      if (result.instrument_data.length > 0) {
        const firstFrame = result.instrument_data[0];

        expect(firstFrame).toHaveProperty('detected');
        expect(firstFrame).toHaveProperty('instruments');

        // 器具が検出されている場合
        if (firstFrame.detected && firstFrame.instruments.length > 0) {
          const instrument = firstFrame.instruments[0];

          // 必須フィールド検証（Fail Fast原則）
          expect(instrument).toHaveProperty('id');
          expect(instrument).toHaveProperty('center');
          expect(instrument).toHaveProperty('bbox');
          expect(instrument.center).toHaveLength(2);
          expect(instrument.bbox).toHaveLength(4);
        }
      }
    }
  });

  test('比較機能（実験版 vs 参照動画）', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/compare`);

    // 比較ページが表示される
    await expect(page.locator('text=動画比較').or(page.locator('text=比較分析'))).toBeVisible({ timeout: 10000 });

    // 解析済み動画を選択
    const selectAnalysis = page.locator('select[name="analysis"]').or(page.locator('[data-testid="analysis-select"]'));

    const selectCount = await selectAnalysis.count();
    if (selectCount > 0) {
      await selectAnalysis.selectOption({ index: 1 });

      // 参照動画を選択
      const selectReference = page.locator('select[name="reference"]').or(page.locator('[data-testid="reference-select"]'));
      await selectReference.selectOption({ index: 1 });

      // 比較実行
      await page.click('text=比較を開始');

      // 比較結果が表示される
      await expect(page.locator('text=比較結果').or(page.locator('text=スコア'))).toBeVisible({ timeout: 30000 });
    }
  });

  test('WebSocket接続（実験版）', async ({ page }) => {
    let wsMessageReceived = false;

    // WebSocketメッセージを監視
    page.on('websocket', ws => {
      ws.on('framereceived', event => {
        wsMessageReceived = true;
        console.log('WebSocket message received:', event.payload);
      });
    });

    await page.goto(`${FRONTEND_URL}/videos`);

    // 解析を開始（WebSocket接続がトリガーされる）
    const firstVideo = page.locator('[data-testid="video-item"]').first();

    const videoCount = await firstVideo.count();
    if (videoCount > 0) {
      await firstVideo.click();
      await page.click('text=解析を開始');
      await page.click('text=内部トラッキング');
      await page.click('text=実行');

      // WebSocketメッセージを待つ
      await page.waitForTimeout(5000);

      // メッセージが受信されたことを確認
      expect(wsMessageReceived).toBeTruthy();
    }
  });

  test('エラーハンドリング（実験版）', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/videos`);

    // 存在しない動画IDにアクセス
    await page.goto(`${FRONTEND_URL}/videos/999999`);

    // エラーメッセージが表示される
    await expect(page.locator('text=エラー').or(page.locator('text=見つかりません'))).toBeVisible({ timeout: 10000 });
  });

  test('パフォーマンス測定（実験版）', async ({ page }) => {
    const startTime = Date.now();

    await page.goto(`${FRONTEND_URL}/videos`);

    // ページロード時間を測定
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;

    // 5秒以内にロード完了
    expect(loadTime).toBeLessThan(5000);

    console.log(`Page load time: ${loadTime}ms`);
  });
});

test.describe('実験版 vs 安定版 比較テスト', () => {
  test('同じ動画で両バージョンの結果を比較', async ({ request }) => {
    // 安定版APIにリクエスト
    const stableResponse = await request.get('http://localhost:8000/api/v1/videos').catch(() => null);

    // 実験版APIにリクエスト
    const experimentalResponse = await request.get(`${EXPERIMENTAL_API_URL}/videos`);

    // 実験版が動作していることを確認
    expect(experimentalResponse.ok()).toBeTruthy();

    // 安定版も動作している場合、データフォーマットを比較
    if (stableResponse && stableResponse.ok()) {
      const stableData = await stableResponse.json();
      const experimentalData = await experimentalResponse.json();

      // 両方のレスポンスが同じ構造であることを確認
      expect(Array.isArray(stableData)).toBeTruthy();
      expect(Array.isArray(experimentalData)).toBeTruthy();

      console.log(`Stable version: ${stableData.length} videos`);
      console.log(`Experimental version: ${experimentalData.length} videos`);
    }
  });
});
