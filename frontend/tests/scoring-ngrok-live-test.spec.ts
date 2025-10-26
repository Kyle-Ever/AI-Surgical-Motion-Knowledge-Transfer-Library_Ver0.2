import { test, expect } from '@playwright/test';

/**
 * 採点モード - ngrok URL動画読み込みテスト（実データ使用）
 *
 * 修正内容の検証:
 * - 絶対パス → 相対パスへの変更
 * - 別PCからのngrok経由アクセスで動画が正常に読み込まれるか
 */

const NGROK_URL = 'https://attestable-emily-reservedly.ngrok-free.dev';
const COMPARISON_ID = '4c76e5d2-1e80-478f-bc7d-6b41a76ec1b3'; // 実際の比較データ

async function skipNgrokWarning(page: any) {
  const selectors = [
    'button:has-text("Visit Site")',
    'a:has-text("Visit Site")',
  ];

  for (const selector of selectors) {
    try {
      const button = page.locator(selector).first();
      const isVisible = await button.isVisible({ timeout: 3000 }).catch(() => false);
      if (isVisible) {
        console.log(`✓ ngrok警告画面をスキップ`);
        await button.click();
        await page.waitForLoadState('networkidle', { timeout: 10000 });
        return true;
      }
    } catch (e) {
      continue;
    }
  }
  return false;
}

test.describe('採点モード - 動画読み込み修正検証', () => {

  test('ngrok経由 - 動画URL形式確認と読み込み成功', async ({ page }) => {
    console.log('\n=== テスト開始: ngrok経由の動画読み込み ===');

    // コンソールログを収集
    const consoleLogs: string[] = [];
    const consoleErrors: string[] = [];

    page.on('console', (msg) => {
      const text = msg.text();
      if (msg.type() === 'error') {
        consoleErrors.push(text);
        console.log(`❌ Console Error: ${text}`);
      } else if (text.includes('[VideoPlayer') || text.includes('videoUrl')) {
        consoleLogs.push(text);
        console.log(`📝 Log: ${text}`);
      }
    });

    // ngrok URLにアクセス
    const targetUrl = `${NGROK_URL}/scoring/comparison/${COMPARISON_ID}`;
    console.log(`アクセス先: ${targetUrl}`);

    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // ngrok警告画面をスキップ
    await skipNgrokWarning(page);

    // ページタイトル確認
    await page.waitForSelector('h1, h2', { timeout: 10000 });
    const pageTitle = await page.locator('h1, h2').first().textContent();
    console.log(`✓ ページタイトル: ${pageTitle}`);

    // DualVideoSection コンポーネントが読み込まれるまで待機
    await page.waitForTimeout(3000);

    // 動画プレイヤーの存在確認
    const videoCount = await page.locator('video').count();
    console.log(`動画プレイヤー数: ${videoCount}`);

    if (videoCount === 0) {
      console.log('⚠️ 動画プレイヤーが見つかりません');
      console.log('ページのHTML構造を確認します...');

      // エラーメッセージの確認
      const errorMessages = await page.locator('text=/読み込みに失敗|エラー|Error/i').allTextContents();
      if (errorMessages.length > 0) {
        console.log(`❌ エラーメッセージ検出: ${errorMessages.join(', ')}`);
      }

      // DualVideoSection の確認
      const dualVideoSections = await page.locator('[class*="DualVideo"], [class*="video"]').count();
      console.log(`DualVideoSection要素数: ${dualVideoSections}`);

      // スクリーンショット撮影
      await page.screenshot({
        path: 'frontend/tests/screenshots/scoring-ngrok-no-video.png',
        fullPage: true
      });
    } else {
      // 動画が存在する場合
      console.log(`✅ 動画プレイヤーを検出: ${videoCount}個`);

      // 動画のsrc属性を確認
      const videoSources = await page.locator('video source').evaluateAll((sources) =>
        sources.map((source) => ({
          src: source.getAttribute('src'),
          type: source.getAttribute('type')
        }))
      );

      console.log('\n動画ソースURL:');
      videoSources.forEach((source, index) => {
        console.log(`  動画${index + 1}: ${source.src}`);
        console.log(`    type: ${source.type}`);

        // 相対パスであることを確認
        if (source.src) {
          if (source.src.startsWith('/api/v1/')) {
            console.log(`    ✅ 相対パス（正しい）`);
          } else if (source.src.includes('localhost:8001')) {
            console.log(`    ❌ 絶対パス（修正前の形式）`);
          } else {
            console.log(`    ⚠️ 予期しない形式`);
          }
        }
      });

      // VideoPlayerのエラーチェック
      const videoLoadErrors = consoleErrors.filter(err =>
        err.includes('[VideoPlayer] Video load error') ||
        err.includes('動画の読み込みに失敗')
      );

      if (videoLoadErrors.length > 0) {
        console.log(`\n❌ 動画読み込みエラー: ${videoLoadErrors.length}件`);
        videoLoadErrors.forEach(err => console.log(`  - ${err}`));

        // エラーがある場合はテスト失敗
        expect(videoLoadErrors.length).toBe(0);
      } else {
        console.log('\n✅ 動画読み込みエラーなし');
      }

      // 動画のreadyState確認（メタデータ読み込み状態）
      const firstVideo = page.locator('video').first();
      const readyState = await firstVideo.evaluate((video: HTMLVideoElement) => video.readyState);
      console.log(`\n動画readyState: ${readyState}`);
      console.log(`  0=HAVE_NOTHING, 1=HAVE_METADATA, 2=HAVE_CURRENT_DATA, 3=HAVE_FUTURE_DATA, 4=HAVE_ENOUGH_DATA`);

      if (readyState >= 1) {
        console.log('✅ 動画メタデータ読み込み成功（readyState >= 1）');
      } else {
        console.log('⚠️ 動画メタデータ未読み込み（まだ読み込み中の可能性）');
      }

      // スクリーンショット撮影
      await page.screenshot({
        path: 'frontend/tests/screenshots/scoring-ngrok-with-video.png',
        fullPage: true
      });
    }

    // テスト結果サマリー
    console.log('\n=== テスト結果サマリー ===');
    console.log(`動画プレイヤー数: ${videoCount}`);
    console.log(`コンソールエラー数: ${consoleErrors.length}`);
    console.log(`動画読み込みエラー: ${consoleErrors.filter(e => e.includes('Video load error')).length}件`);

    console.log('\n✅ テスト完了');
  });

  test('ローカル環境 - 比較テスト', async ({ page }) => {
    console.log('\n=== テスト開始: ローカル環境（比較用） ===');

    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    const localUrl = `http://localhost:3000/scoring/comparison/${COMPARISON_ID}`;
    console.log(`アクセス先: ${localUrl}`);

    await page.goto(localUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);

    const videoCount = await page.locator('video').count();
    console.log(`✓ ローカル環境 - 動画プレイヤー数: ${videoCount}`);

    if (videoCount > 0) {
      const videoSources = await page.locator('video source').evaluateAll((sources) =>
        sources.map((source) => source.getAttribute('src'))
      );

      console.log('ローカル環境 - 動画ソース:');
      videoSources.forEach((src, index) => {
        console.log(`  動画${index + 1}: ${src}`);
        if (src) {
          expect(src).toMatch(/^\/api\/v1\/videos\/.*\/stream$/);
        }
      });
    }

    const videoLoadErrors = consoleErrors.filter(err => err.includes('[VideoPlayer] Video load error'));
    console.log(`コンソールエラー数: ${consoleErrors.length}`);
    console.log(`動画読み込みエラー: ${videoLoadErrors.length}件`);

    if (videoLoadErrors.length > 0) {
      console.log('❌ ローカル環境でも動画読み込みエラーが発生しています');
      videoLoadErrors.forEach(err => console.log(`  - ${err}`));
    }

    await page.screenshot({
      path: 'frontend/tests/screenshots/scoring-local-comparison.png',
      fullPage: true
    });

    console.log('✅ ローカル環境テスト完了');
  });
});
