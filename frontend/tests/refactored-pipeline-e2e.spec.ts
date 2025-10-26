import { test, expect } from '@playwright/test';
import path from 'path';

/**
 * リファクタリング後のパイプラインE2Eテスト
 *
 * テスト内容:
 * 1. 新規動画アップロードと解析（FrameExtractionService使用）
 * 2. フレーム抽出がround()を使用して正しく動作
 * 3. タイムスタンプの精度確認
 * 4. 採点モードのテスト
 */

test.describe('リファクタリング後のパイプライン E2E テスト', () => {
  // タイムアウトを延長
  test.setTimeout(600000); // 10分

  test.beforeEach(async ({ page }) => {
    // 実験版バックエンド（ポート8001）に接続
    await page.goto('http://localhost:3000', { timeout: 60000 });

    // ページが読み込まれるまで待機
    await page.waitForLoadState('networkidle', { timeout: 60000 });
  });

  test('新規動画アップロードと解析 - FrameExtractionService使用', async ({ page }) => {
    // 既存の動画を使用してテスト
    const testVideoPath = path.join(__dirname, '../../backend_experimental/data/uploads/043483f6-f932-41ee-a28f-f0d9da1f959c.mp4');

    // アップロードページに移動
    await page.goto('http://localhost:3000/upload');
    await page.waitForLoadState('networkidle');

    // ファイル入力要素を探す
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testVideoPath);

    // 動画タイプを選択（external_with_instruments）
    await page.selectOption('select[name="videoType"]', 'external_with_instruments');

    // アップロードボタンをクリック
    await page.click('button:has-text("アップロード")');

    // アップロード完了を待機
    await page.waitForSelector('text=アップロード完了', { timeout: 30000 });

    // アップロード後の動画IDを取得
    const uploadResponse = await page.waitForResponse(
      response => response.url().includes('/api/v1/videos/upload') && response.status() === 200
    );
    const uploadData = await uploadResponse.json();
    const videoId = uploadData.id;

    console.log('✅ Video uploaded:', videoId);

    // 動画一覧ページに移動
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // アップロードした動画を見つける
    await page.click(`text=${uploadData.filename || 'test_video.mp4'}`);

    // ダッシュボードページに遷移
    await page.waitForURL(/\/dashboard\/.+/);

    // 解析開始ボタンをクリック
    await page.click('button:has-text("解析開始")');

    // 解析完了を待機（最大5分）
    await page.waitForSelector('text=解析完了', { timeout: 300000 });

    console.log('✅ Analysis completed');

    // コンソールログで新しいFrameExtractionServiceのログを確認
    page.on('console', msg => {
      if (msg.text().includes('[FRAME_EXTRACTION]')) {
        console.log('📊 Frame extraction log:', msg.text());
      }
    });

    // 解析結果を取得
    const analysisResponse = await page.waitForResponse(
      response => response.url().includes('/api/v1/analysis/') && response.status() === 200
    );
    const analysisData = await analysisResponse.json();

    // 検証: skeleton_dataが存在
    expect(analysisData.skeleton_data).toBeDefined();
    expect(analysisData.skeleton_data.length).toBeGreaterThan(0);

    console.log(`✅ Skeleton data frames: ${analysisData.skeleton_data.length}`);

    // 検証: タイムスタンプが正確
    const firstFrame = analysisData.skeleton_data[0];
    const secondFrame = analysisData.skeleton_data[1];

    expect(firstFrame.timestamp).toBeCloseTo(0, 2);

    // 25fps動画、target_fps=15、round(25/15)=2なので、2フレームスキップ
    // 期待されるタイムスタンプ差: 2/25 = 0.08秒
    const timestampDiff = secondFrame.timestamp - firstFrame.timestamp;
    expect(timestampDiff).toBeCloseTo(0.08, 2);

    console.log(`✅ Timestamp accuracy verified: ${timestampDiff}s between frames`);

    // 検証: データ構造の妥当性
    expect(firstFrame).toHaveProperty('frame_number');
    expect(firstFrame).toHaveProperty('timestamp');
    expect(firstFrame).toHaveProperty('hands');

    // 検証: 4秒以降のデータも存在（以前は4秒で止まっていた）
    const framesAfter4s = analysisData.skeleton_data.filter(
      (frame: any) => frame.timestamp > 4.0
    );
    expect(framesAfter4s.length).toBeGreaterThan(0);

    console.log(`✅ Frames after 4 seconds: ${framesAfter4s.length}`);
  });

  test('フレーム抽出の詳細検証 - round() vs int()', async ({ page }) => {
    // バックエンドAPIから直接動画情報を取得
    const response = await page.request.get('http://localhost:8001/api/v1/videos');
    const videos = await response.json();

    // 最新の動画を取得
    const latestVideo = videos[0];

    if (!latestVideo) {
      console.log('⚠️  No videos found, skipping test');
      return;
    }

    console.log('📹 Testing video:', latestVideo.id, latestVideo.filename);

    // 解析結果を取得
    const analysisResponse = await page.request.get(
      `http://localhost:8001/api/v1/analysis/${latestVideo.id}`
    );
    const analysisData = await analysisResponse.json();

    if (analysisData.status !== 'completed') {
      console.log('⚠️  Analysis not completed, skipping test');
      return;
    }

    // 動画のFPSを確認
    const videoFps = latestVideo.fps || 25;
    const targetFps = 15;

    // 期待されるframe_skip（round使用）
    const expectedFrameSkip = Math.round(videoFps / targetFps);

    console.log(`📊 Video FPS: ${videoFps}`);
    console.log(`📊 Target FPS: ${targetFps}`);
    console.log(`📊 Expected frame_skip (round): ${expectedFrameSkip}`);

    // タイムスタンプ間隔から実際のframe_skipを推定
    if (analysisData.skeleton_data.length >= 2) {
      const timestampInterval = analysisData.skeleton_data[1].timestamp -
                                 analysisData.skeleton_data[0].timestamp;
      const actualFrameSkip = Math.round(timestampInterval * videoFps);

      console.log(`📊 Actual timestamp interval: ${timestampInterval}s`);
      console.log(`📊 Actual frame_skip: ${actualFrameSkip}`);

      // 検証: round()を使用しているか
      expect(actualFrameSkip).toBe(expectedFrameSkip);

      // 25fps動画の場合、round(25/15)=2である必要がある（int(25/15)=1ではない）
      if (videoFps === 25 && targetFps === 15) {
        expect(actualFrameSkip).toBe(2);
        console.log('✅ Confirmed: Using round() instead of int() for 25fps video');
      }
    }
  });

  test('採点モード - 参照動画との比較', async ({ page }) => {
    // 参照動画として使用
    const referenceVideoPath = path.join(__dirname, '../../backend_experimental/data/uploads/059a80b9-b8d6-42c3-ad74-93c1595de6c7.mp4');

    // まず、参照動画をアップロード
    await page.goto('http://localhost:3000/upload');
    await page.waitForLoadState('networkidle');

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(referenceVideoPath);

    await page.selectOption('select[name="videoType"]', 'external');

    // 参照動画としてマーク
    const isReferenceCheckbox = page.locator('input[type="checkbox"][name="isReference"]');
    if (await isReferenceCheckbox.isVisible()) {
      await isReferenceCheckbox.check();
    }

    await page.click('button:has-text("アップロード")');
    await page.waitForSelector('text=アップロード完了', { timeout: 30000 });

    const referenceResponse = await page.waitForResponse(
      response => response.url().includes('/api/v1/videos/upload') && response.status() === 200
    );
    const referenceData = await referenceResponse.json();
    const referenceVideoId = referenceData.id;

    console.log('✅ Reference video uploaded:', referenceVideoId);

    // 参照動画の解析を実行
    await page.goto(`http://localhost:3000/dashboard/${referenceVideoId}`);
    await page.waitForLoadState('networkidle');

    await page.click('button:has-text("解析開始")');
    await page.waitForSelector('text=解析完了', { timeout: 300000 });

    console.log('✅ Reference video analyzed');

    // 次に、評価対象の動画をアップロード
    await page.goto('http://localhost:3000/upload');
    await page.waitForLoadState('networkidle');

    const targetVideoPath = path.join(__dirname, '../../backend_experimental/data/uploads/077b763e-1f50-4fa3-b85f-7474f6767249.mp4');

    await fileInput.setInputFiles(targetVideoPath);
    await page.selectOption('select[name="videoType"]', 'external');
    await page.click('button:has-text("アップロード")');
    await page.waitForSelector('text=アップロード完了', { timeout: 30000 });

    const targetResponse = await page.waitForResponse(
      response => response.url().includes('/api/v1/videos/upload') && response.status() === 200
    );
    const targetData = await targetResponse.json();
    const targetVideoId = targetData.id;

    console.log('✅ Target video uploaded:', targetVideoId);

    // 評価対象動画の解析を実行
    await page.goto(`http://localhost:3000/dashboard/${targetVideoId}`);
    await page.waitForLoadState('networkidle');

    await page.click('button:has-text("解析開始")');
    await page.waitForSelector('text=解析完了', { timeout: 300000 });

    console.log('✅ Target video analyzed');

    // 採点モードに切り替え
    await page.click('button:has-text("採点モード")');
    await page.waitForLoadState('networkidle');

    // 参照動画を選択
    await page.selectOption('select[name="referenceVideo"]', referenceVideoId);

    // 比較実行ボタンをクリック
    await page.click('button:has-text("比較実行")');

    // 比較結果を待機
    await page.waitForSelector('text=比較完了', { timeout: 60000 });

    console.log('✅ Comparison completed');

    // 比較結果APIから取得
    const comparisonResponse = await page.request.post(
      'http://localhost:8001/api/v1/scoring/compare',
      {
        data: {
          target_video_id: targetVideoId,
          reference_video_id: referenceVideoId
        }
      }
    );

    expect(comparisonResponse.ok()).toBeTruthy();

    const comparisonData = await comparisonResponse.json();

    console.log('📊 Comparison result:', JSON.stringify(comparisonData, null, 2));

    // 検証: スコアが計算されている
    expect(comparisonData).toHaveProperty('similarity_score');
    expect(comparisonData.similarity_score).toBeGreaterThanOrEqual(0);
    expect(comparisonData.similarity_score).toBeLessThanOrEqual(100);

    // 検証: 各種メトリクスが存在
    expect(comparisonData).toHaveProperty('path_similarity');
    expect(comparisonData).toHaveProperty('speed_similarity');
    expect(comparisonData).toHaveProperty('smoothness_similarity');

    console.log(`✅ Similarity score: ${comparisonData.similarity_score}%`);
    console.log(`✅ Path similarity: ${comparisonData.path_similarity}`);
    console.log(`✅ Speed similarity: ${comparisonData.speed_similarity}`);
    console.log(`✅ Smoothness similarity: ${comparisonData.smoothness_similarity}`);

    // UIで結果が表示されているか確認
    await expect(page.locator('text=類似度')).toBeVisible();
    await expect(page.locator(`text=${comparisonData.similarity_score}%`)).toBeVisible();
  });

  test('データパイプライン整合性 - タイムスタンプとフレーム番号', async ({ page }) => {
    // 最新の解析結果を取得
    const response = await page.request.get('http://localhost:8001/api/v1/videos');
    const videos = await response.json();

    if (videos.length === 0) {
      console.log('⚠️  No videos found, skipping test');
      return;
    }

    const latestVideo = videos[0];
    const analysisResponse = await page.request.get(
      `http://localhost:8001/api/v1/analysis/${latestVideo.id}`
    );
    const analysisData = await analysisResponse.json();

    if (analysisData.status !== 'completed') {
      console.log('⚠️  Analysis not completed, skipping test');
      return;
    }

    // 検証: skeleton_dataとinstrument_dataのタイムスタンプ整合性
    const skeletonData = analysisData.skeleton_data || [];
    const instrumentData = analysisData.instrument_data || [];

    console.log(`📊 Skeleton data frames: ${skeletonData.length}`);
    console.log(`📊 Instrument data frames: ${instrumentData.length}`);

    // 両方のデータが同じフレーム数であるべき
    expect(skeletonData.length).toBe(instrumentData.length);

    // タイムスタンプが一致しているか確認
    for (let i = 0; i < Math.min(10, skeletonData.length); i++) {
      const skelFrame = skeletonData[i];
      const instFrame = instrumentData[i];

      expect(skelFrame.timestamp).toBeCloseTo(instFrame.timestamp, 3);
      expect(skelFrame.frame_number).toBe(instFrame.frame_number);

      console.log(`Frame ${i}: timestamp=${skelFrame.timestamp.toFixed(3)}s, frame_number=${skelFrame.frame_number}`);
    }

    console.log('✅ Timestamp alignment verified between skeleton and instrument data');

    // 検証: タイムスタンプが単調増加
    for (let i = 1; i < skeletonData.length; i++) {
      expect(skeletonData[i].timestamp).toBeGreaterThan(skeletonData[i - 1].timestamp);
    }

    console.log('✅ Timestamps are monotonically increasing');

    // 検証: フレーム番号が正しいスキップパターン
    if (skeletonData.length >= 3) {
      const frameSkip = skeletonData[1].frame_number - skeletonData[0].frame_number;

      for (let i = 2; i < Math.min(10, skeletonData.length); i++) {
        const actualSkip = skeletonData[i].frame_number - skeletonData[i - 1].frame_number;
        expect(actualSkip).toBe(frameSkip);
      }

      console.log(`✅ Consistent frame skip pattern: ${frameSkip}`);
    }
  });
});
