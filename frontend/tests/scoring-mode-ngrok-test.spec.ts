import { test, expect } from '@playwright/test';

/**
 * 採点モード - ngrok URL経由テスト
 *
 * 目的: 別PCからngrok経由で採点モードページにアクセスし、
 *      動画が正常に読み込まれることを確認
 *
 * 修正内容:
 * - 絶対パス (http://localhost:8001) → 相対パス (/api/v1)
 * - Next.js APIプロキシ経由で動画ストリーミング
 */

const NGROK_URL = 'https://attestable-emily-reservedly.ngrok-free.dev';

// ngrok警告画面をスキップするヘルパー関数
async function skipNgrokWarning(page: any) {
  console.log('=== ngrok警告画面スキップ試行 ===');

  const selectors = [
    'button:has-text("Visit Site")',
    'a:has-text("Visit Site")',
    '[href="#"]',
    'button',
  ];

  for (const selector of selectors) {
    try {
      const button = page.locator(selector).first();
      const isVisible = await button.isVisible({ timeout: 2000 }).catch(() => false);

      if (isVisible) {
        console.log(`✓ 警告画面の「Visit Site」ボタンを検出: ${selector}`);
        await button.click();
        await page.waitForLoadState('networkidle');
        console.log('✓ 警告画面をスキップしました');
        return true;
      }
    } catch (e) {
      // 次のセレクターを試行
      continue;
    }
  }

  console.log('⚠ 警告画面が見つからない（すでにスキップ済みの可能性）');
  return false;
}

test.describe('採点モード - ngrok動作確認', () => {

  test('採点モードページ - 動画読み込み確認（ngrok経由）', async ({ page }) => {
    console.log('=== テスト開始: 採点モード（ngrok） ===');

    // コンソールエラーを収集
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const errorText = msg.text();
        console.log(`❌ Console Error: ${errorText}`);
        consoleErrors.push(errorText);
      }
    });

    // 既存の比較結果IDを使用（テストデータとして）
    // 注意: 実際のIDはデータベース内容に依存
    const comparisonId = 'eb9c6a82-d074-4c8c-8f54-44dc0bfcb4b0'; // 既存の比較ID
    const targetUrl = `${NGROK_URL}/scoring/comparison/${comparisonId}`;

    console.log(`アクセス先: ${targetUrl}`);

    // ページにアクセス
    await page.goto(targetUrl, { waitUntil: 'networkidle' });

    // ngrok警告画面をスキップ
    await skipNgrokWarning(page);

    // ページタイトル確認
    await page.waitForSelector('h1', { timeout: 10000 });
    const title = await page.locator('h1').first().textContent();
    console.log(`✓ ページタイトル: ${title}`);

    // 動画プレイヤー要素の存在確認
    const videoElements = await page.locator('video').count();
    console.log(`✓ 動画プレイヤー数: ${videoElements}`);
    expect(videoElements).toBeGreaterThanOrEqual(2); // 基準動画 + 評価動画

    // 動画のsrc属性を確認（相対パスになっているか）
    const videoSources = await page.locator('video source').evaluateAll((sources) =>
      sources.map((source) => source.getAttribute('src'))
    );
    console.log('動画ソース:', videoSources);

    // 相対パスであることを確認
    videoSources.forEach((src, index) => {
      if (src) {
        console.log(`動画${index + 1}: ${src}`);
        expect(src).toMatch(/^\/api\/v1\/videos\/.*\/stream$/);
      }
    });

    // VideoPlayerのコンソールエラーチェック
    const videoLoadErrors = consoleErrors.filter(err => err.includes('[VideoPlayer] Video load error'));
    if (videoLoadErrors.length > 0) {
      console.log(`❌ 動画読み込みエラー検出: ${videoLoadErrors.length}件`);
      videoLoadErrors.forEach(err => console.log(`  - ${err}`));

      // エラーが発生した場合はテスト失敗
      expect(videoLoadErrors.length).toBe(0);
    } else {
      console.log('✅ 動画読み込みエラーなし');
    }

    // DualVideoSection コンポーネントの表示確認
    const dualVideoSection = await page.locator('.bg-white.rounded-lg').count();
    console.log(`✓ DualVideoSection表示数: ${dualVideoSection}`);
    expect(dualVideoSection).toBeGreaterThanOrEqual(2);

    // スクリーンショット撮影
    await page.screenshot({
      path: 'frontend/tests/screenshots/scoring-mode-ngrok.png',
      fullPage: true
    });
    console.log('✅ スクリーンショット保存: scoring-mode-ngrok.png');

    console.log('✅ 採点モード（ngrok）テスト完了');
  });

  test('採点モードページ - 動画再生確認（ngrok経由）', async ({ page }) => {
    console.log('=== テスト開始: 動画再生（ngrok） ===');

    const comparisonId = 'eb9c6a82-d074-4c8c-8f54-44dc0bfcb4b0';
    const targetUrl = `${NGROK_URL}/scoring/comparison/${comparisonId}`;

    await page.goto(targetUrl, { waitUntil: 'networkidle' });
    await skipNgrokWarning(page);

    // 動画プレイヤーの取得
    const videos = page.locator('video');
    const videoCount = await videos.count();
    console.log(`動画要素数: ${videoCount}`);

    if (videoCount >= 2) {
      // 最初の動画の状態確認
      const firstVideo = videos.first();

      // 動画のreadyState確認（メタデータ読み込み完了）
      const readyState = await firstVideo.evaluate((video: HTMLVideoElement) => video.readyState);
      console.log(`✓ 動画readyState: ${readyState} (0=nothing, 1=metadata, 2=currentData, 3=futureData, 4=enoughData)`);

      // readyStateが1以上なら、メタデータ読み込み成功
      expect(readyState).toBeGreaterThanOrEqual(1);

      // 動画の長さ（duration）確認
      const duration = await firstVideo.evaluate((video: HTMLVideoElement) => video.duration);
      console.log(`✓ 動画の長さ: ${duration}秒`);

      if (!isNaN(duration) && duration > 0) {
        console.log('✅ 動画メタデータ読み込み成功');
      } else {
        console.log('⚠ 動画の長さが取得できません（まだ読み込み中の可能性）');
      }
    } else {
      console.log('⚠ 動画要素が2つ未満です');
    }

    // 再生ボタンの存在確認
    const playButton = page.locator('button').filter({ hasText: /再生|Play/ }).first();
    const playButtonVisible = await playButton.isVisible().catch(() => false);

    if (playButtonVisible) {
      console.log('✓ 再生ボタン検出');
    } else {
      console.log('⚠ 再生ボタンが見つかりません');
    }

    await page.screenshot({
      path: 'frontend/tests/screenshots/scoring-mode-playback-ngrok.png',
      fullPage: true
    });

    console.log('✅ 動画再生テスト完了');
  });

  test('採点モードページ - ローカル環境比較', async ({ page }) => {
    console.log('=== テスト開始: ローカル環境 ===');

    const comparisonId = 'eb9c6a82-d074-4c8c-8f54-44dc0bfcb4b0';
    const localUrl = `http://localhost:3000/scoring/comparison/${comparisonId}`;

    // コンソールエラーを収集
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto(localUrl, { waitUntil: 'networkidle' });

    // 動画プレイヤー確認
    const videoElements = await page.locator('video').count();
    console.log(`✓ ローカル環境 - 動画プレイヤー数: ${videoElements}`);
    expect(videoElements).toBeGreaterThanOrEqual(2);

    // 動画のsrc属性確認
    const videoSources = await page.locator('video source').evaluateAll((sources) =>
      sources.map((source) => source.getAttribute('src'))
    );
    console.log('ローカル環境 - 動画ソース:', videoSources);

    // 相対パスであることを確認
    videoSources.forEach((src) => {
      if (src) {
        expect(src).toMatch(/^\/api\/v1\/videos\/.*\/stream$/);
      }
    });

    // エラーチェック
    const videoLoadErrors = consoleErrors.filter(err => err.includes('[VideoPlayer] Video load error'));
    expect(videoLoadErrors.length).toBe(0);

    console.log('✅ ローカル環境テスト完了');
  });
});
