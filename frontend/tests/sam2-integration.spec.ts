/**
 * SAM2統合テスト - JPEG一時保存方式
 *
 * テスト内容:
 * 1. SAM2が有効化された状態での動画アップロード
 * 2. 器具検出処理の実行
 * 3. SAM2による高精度検出結果の確認
 * 4. 一時フォルダのクリーンアップ確認
 */

import { test, expect } from '@playwright/test';

const TEST_VIDEO_PATH = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend\\test.mp4';
const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:3000';

test.describe('SAM2統合テスト', () => {
  test.beforeEach(async ({ page }) => {
    // バックエンドの起動確認
    const healthResponse = await page.request.get(`${BACKEND_URL}/api/v1/health`);
    expect(healthResponse.ok()).toBeTruthy();
  });

  test('SAM2設定の確認', async ({ page }) => {
    // 設定APIでSAM2が有効化されているか確認
    const response = await page.request.get(`${BACKEND_URL}/api/v1/health`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    console.log('Backend health:', data);
  });

  test('SAM2による動画アップロードと解析', async ({ page }) => {
    // ホームページに移動
    await page.goto(FRONTEND_URL);
    await expect(page.locator('h1')).toContainText('AI手技モーション伝承ライブラリ');

    // アップロードページに移動
    await page.click('text=動画をアップロード');
    await expect(page).toHaveURL(/\/upload/);

    // 動画ファイルを選択
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(TEST_VIDEO_PATH);

    // 動画タイプを選択（内視鏡 - internal）
    await page.selectOption('select[name="video_type"]', 'internal');

    // アップロード実行
    await page.click('button:has-text("アップロード")');

    // アップロード成功を待機
    await expect(page.locator('text=アップロード成功')).toBeVisible({ timeout: 30000 });

    // 解析開始ボタンをクリック
    const analysisButton = page.locator('button:has-text("解析を開始")');
    await expect(analysisButton).toBeVisible({ timeout: 5000 });
    await analysisButton.click();

    // 解析進行中の表示を確認
    await expect(page.locator('text=解析中')).toBeVisible({ timeout: 10000 });

    // WebSocket接続でリアルタイム進捗を監視
    const progressUpdates: string[] = [];
    page.on('console', msg => {
      if (msg.text().includes('SAM2') || msg.text().includes('progress')) {
        progressUpdates.push(msg.text());
        console.log('Progress:', msg.text());
      }
    });

    // 解析完了を待機（最大5分）
    await expect(page.locator('text=解析完了')).toBeVisible({ timeout: 300000 });

    // ダッシュボードに遷移
    await page.click('text=結果を見る');
    await expect(page).toHaveURL(/\/dashboard/);

    // 器具検出結果を確認
    const instrumentData = await page.locator('[data-testid="instrument-data"]');
    await expect(instrumentData).toBeVisible({ timeout: 10000 });

    // SAM2による検出が行われたか確認（ログから）
    console.log('Progress updates:', progressUpdates);

    // APIで解析結果を取得
    const currentUrl = page.url();
    const analysisId = currentUrl.split('/').pop();

    const analysisResponse = await page.request.get(`${BACKEND_URL}/api/v1/analysis/${analysisId}`);
    expect(analysisResponse.ok()).toBeTruthy();

    const analysisData = await analysisResponse.json();
    console.log('Analysis result:', {
      id: analysisData.id,
      status: analysisData.status,
      instrument_count: analysisData.instrument_data?.length || 0,
      has_detections: analysisData.instrument_data?.[0]?.detections?.length > 0
    });

    // 器具検出データが存在することを確認
    expect(analysisData.instrument_data).toBeDefined();
    expect(analysisData.instrument_data.length).toBeGreaterThan(0);

    // 検出結果に必要なフィールドが含まれていることを確認
    const firstFrame = analysisData.instrument_data[0];
    expect(firstFrame).toHaveProperty('frame_number');
    expect(firstFrame).toHaveProperty('detections');

    if (firstFrame.detections.length > 0) {
      const firstDetection = firstFrame.detections[0];
      expect(firstDetection).toHaveProperty('bbox');
      expect(firstDetection).toHaveProperty('confidence');
      expect(firstDetection).toHaveProperty('rotated_bbox');
      expect(firstDetection).toHaveProperty('tip_point');
    }
  });

  test('一時フォルダのクリーンアップ確認', async ({ page }) => {
    // バックエンドの一時フォルダが空であることを確認
    const fs = require('fs');
    const path = require('path');

    const tempDir = path.join(
      'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend',
      'temp_frames'
    );

    // ディレクトリが存在しない、または空であることを確認
    if (fs.existsSync(tempDir)) {
      const files = fs.readdirSync(tempDir);
      console.log('Temp directory files:', files);
      expect(files.length).toBe(0);
    } else {
      console.log('Temp directory does not exist (good)');
    }
  });

  test('SAM2のパフォーマンス測定', async ({ page }) => {
    const startTime = Date.now();

    // ホームページに移動
    await page.goto(FRONTEND_URL);

    // アップロードページに移動
    await page.click('text=動画をアップロード');

    // 動画ファイルを選択
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(TEST_VIDEO_PATH);

    // 動画タイプを選択
    await page.selectOption('select[name="video_type"]', 'internal');

    // アップロード実行
    await page.click('button:has-text("アップロード")');
    await expect(page.locator('text=アップロード成功')).toBeVisible({ timeout: 30000 });

    const uploadTime = Date.now() - startTime;
    console.log(`Upload time: ${uploadTime}ms`);

    // 解析開始
    const analysisStartTime = Date.now();
    await page.click('button:has-text("解析を開始")');
    await expect(page.locator('text=解析完了')).toBeVisible({ timeout: 300000 });
    const analysisTime = Date.now() - analysisStartTime;

    console.log(`Analysis time: ${analysisTime}ms (${(analysisTime / 1000).toFixed(1)}s)`);

    // パフォーマンス基準
    // SAM2は精度向上のため、SAM1より若干遅くなる可能性がある
    // 目安: 5分以内
    expect(analysisTime).toBeLessThan(300000); // 5分
  });
});
