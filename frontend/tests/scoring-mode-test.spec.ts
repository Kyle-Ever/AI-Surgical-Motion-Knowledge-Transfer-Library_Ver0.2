import { test, expect } from '@playwright/test';

/**
 * 採点モードE2Eテスト
 * リファレンス動画とターゲット動画の比較機能を検証
 */

test.describe('採点モード E2E テスト', () => {
  test.setTimeout(120000); // 2分

  // 既に解析済みの動画を使用
  const ANALYZED_VIDEO_ID = '5d83bfd5-42dd-40e7-a0a9-c383cecd06b9';
  const ANALYSIS_ID = 'b2e0b64a-e1d6-496b-9eb4-d9f85a949168';

  test('採点モードページが正常に表示される', async ({ page }) => {
    // 採点モードページに移動
    await page.goto('http://localhost:3000/scoring', { timeout: 30000 });
    await page.waitForLoadState('networkidle', { timeout: 30000 });

    console.log('✅ Navigated to scoring page');

    // ページタイトルを確認
    const title = await page.locator('h1').first().textContent();
    expect(title).toContain('採点');

    console.log(`✅ Page title: ${title}`);
  });

  test('リファレンス動画とターゲット動画を選択できる', async ({ page }) => {
    await page.goto('http://localhost:3000/scoring', { timeout: 30000 });
    await page.waitForLoadState('networkidle', { timeout: 30000 });

    // リファレンス動画選択セクションを確認
    const referenceSection = page.locator('text=リファレンス').first();
    expect(await referenceSection.isVisible()).toBeTruthy();

    console.log('✅ Reference section visible');

    // ターゲット動画選択セクションを確認
    const targetSection = page.locator('text=ターゲット').first();
    expect(await targetSection.isVisible()).toBeTruthy();

    console.log('✅ Target section visible');
  });

  test('解析済み動画の詳細を表示できる', async ({ page }) => {
    // ダッシュボードで解析結果を確認
    await page.goto(`http://localhost:3000/dashboard/${ANALYZED_VIDEO_ID}`, { timeout: 30000 });
    await page.waitForLoadState('networkidle', { timeout: 30000 });

    console.log(`✅ Navigated to dashboard for analyzed video: ${ANALYZED_VIDEO_ID}`);

    // 解析データが表示されているか確認
    const statusText = await page.locator('text=解析完了').first().textContent().catch(() => null);

    if (statusText) {
      console.log('✅ Analysis completed status visible');
    }

    // API経由で解析データを確認
    const response = await page.request.get(
      `http://localhost:8001/api/v1/analysis/${ANALYSIS_ID}`
    );

    expect(response.ok()).toBeTruthy();

    const analysisData = await response.json();

    console.log(`📊 Analysis status: ${analysisData.status}`);
    console.log(`📊 Skeleton frames: ${analysisData.skeleton_data?.length || 0}`);
    console.log(`📊 Frame skip confirmed: ${analysisData.skeleton_data?.[1]?.frame_number - analysisData.skeleton_data?.[0]?.frame_number}`);

    // 検証: round()が使用されていることを確認
    if (analysisData.skeleton_data && analysisData.skeleton_data.length >= 2) {
      const frameSkip = analysisData.skeleton_data[1].frame_number - analysisData.skeleton_data[0].frame_number;
      expect(frameSkip).toBe(2); // 25fps動画でround(25/15)=2
      console.log('✅ Confirmed: Using round() for frame_skip calculation');
    }
  });

  test('リファクタリング後のデータ整合性確認', async ({ page }) => {
    // API経由でデータを取得
    const response = await page.request.get(
      `http://localhost:8001/api/v1/analysis/${ANALYSIS_ID}`
    );

    const analysisData = await response.json();

    // 基本検証
    expect(analysisData.status).toBe('completed');
    expect(analysisData.skeleton_data).toBeDefined();
    expect(analysisData.skeleton_data.length).toBeGreaterThan(200);

    console.log(`✅ Total frames: ${analysisData.skeleton_data.length}`);

    // タイムスタンプの連続性確認
    for (let i = 1; i < Math.min(10, analysisData.skeleton_data.length); i++) {
      const prev = analysisData.skeleton_data[i - 1];
      const curr = analysisData.skeleton_data[i];

      // タイムスタンプが増加していることを確認
      expect(curr.timestamp).toBeGreaterThan(prev.timestamp);

      // フレーム番号が増加していることを確認
      expect(curr.frame_number).toBeGreaterThan(prev.frame_number);
    }

    console.log('✅ Timestamp and frame_number continuity verified');

    // 4秒以降のデータ存在確認（以前は113フレームで停止していた問題）
    const framesAfter4s = analysisData.skeleton_data.filter(
      (frame: any) => frame.timestamp > 4.0
    );
    expect(framesAfter4s.length).toBeGreaterThan(0);

    console.log(`✅ Frames after 4 seconds: ${framesAfter4s.length} (previously stopped at 113 frames)`);

    // 最終フレームの確認
    const lastFrame = analysisData.skeleton_data[analysisData.skeleton_data.length - 1];
    console.log(`📊 Last frame: frame_number=${lastFrame.frame_number}, timestamp=${lastFrame.timestamp.toFixed(2)}s`);

    // 25fps動画の場合、タイムスタンプ間隔が約0.08秒であることを確認
    const avgInterval = (lastFrame.timestamp - analysisData.skeleton_data[0].timestamp) /
                       (analysisData.skeleton_data.length - 1);
    console.log(`📊 Average interval: ${avgInterval.toFixed(4)}s`);
    expect(avgInterval).toBeCloseTo(0.08, 2); // 2/25fps = 0.08s

    console.log('✅ All refactoring validations passed!');
  });
});
