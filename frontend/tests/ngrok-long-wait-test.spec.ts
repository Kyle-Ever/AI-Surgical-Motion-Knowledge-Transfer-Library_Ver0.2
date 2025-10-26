import { test, expect } from '@playwright/test';

/**
 * ngrok経由の実動画アップロード - 超長時間待機版
 *
 * タイムアウト: 30分
 * 戦略: アップロード後、30分間URL変化とコンテンツ変化を監視
 */

const NGROK_FRONTEND_URL = 'https://mindmotionai.ngrok-free.dev';
const REAL_VIDEO_PATH = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\data\\uploads\\【正式】手技動画.mp4';

async function skipNgrokWarning(page: any) {
  try {
    await page.waitForTimeout(2000);
    const title = await page.title();
    if (title.includes('ngrok') || title.includes('Visit Site')) {
      const visitButton = page.locator('button:has-text("Visit Site")');
      if (await visitButton.count() > 0) {
        await visitButton.click();
        await page.waitForLoadState('networkidle');
      }
    }
  } catch (e) { }
}

test.describe('ngrok 超長時間待機テスト', () => {
  test.setTimeout(1800000); // 30分

  test('実動画アップロード - 30分監視', async ({ page }) => {
    console.log('\n=== 超長時間待機テスト開始 ===');
    console.log('タイムアウト: 30分\n');

    // ステップ1-6: アップロードページまで到達
    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);

    const uploadLink = page.locator('a[href="/upload"]').first();
    await uploadLink.click();
    await page.waitForLoadState('networkidle');

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(REAL_VIDEO_PATH);
    console.log('✓ ファイル選択完了');

    await page.waitForTimeout(1000);
    await page.locator('button:has-text("次へ")').first().click();
    console.log('✓ 映像タイプ選択へ');

    await page.waitForTimeout(1000);
    await page.locator('button').filter({ hasText: '外部カメラ' }).filter({ hasText: '器具なし' }).first().click();
    console.log('✓ 外部カメラ（器具なし）選択');

    await page.waitForTimeout(1000);
    await page.waitForSelector('button:has-text("次へ")', { state: 'visible', timeout: 10000 });
    await page.locator('button:has-text("次へ"):not([disabled])').last().click();
    console.log('✓ 解析設定ページへ');

    // ステップ7: アップロードボタンをクリック
    await page.waitForTimeout(2000);
    console.log('\n⏳ アップロードボタンを探しています...');

    // ボタンが表示されるまで待機（最大60秒）
    try {
      await page.waitForSelector('button:has-text("アップロード"), button[type="submit"]', {
        state: 'visible',
        timeout: 60000
      });
      console.log('✓ アップロードボタン検出');
    } catch (e) {
      console.log('❌ アップロードボタンが見つかりません');
      await page.screenshot({ path: 'test-results/long-wait-no-button.png', fullPage: true });
      throw e;
    }

    const uploadButton = page.locator('button:has-text("アップロード"), button[type="submit"]').first();

    await page.screenshot({ path: 'test-results/long-wait-01-before-upload.png', fullPage: true });

    console.log('⏳ アップロードボタンをクリック...');
    await uploadButton.click();
    console.log('✓ クリック完了');

    // ステップ8: 30分間監視
    const startTime = Date.now();
    const maxWaitTime = 1800000; // 30分
    let checkCount = 0;
    let lastUrl = page.url();
    let lastBodyHash = '';

    console.log('\n📊 30分間の状態監視を開始...\n');

    while (Date.now() - startTime < maxWaitTime) {
      checkCount++;
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const currentUrl = page.url();

      try {
        const bodyText = await page.locator('body').textContent({ timeout: 5000 });
        const bodyHash = bodyText?.substring(0, 100) || '';

        // URL変化を検出
        if (currentUrl !== lastUrl) {
          console.log(`\n🔄 URL変化検出 (${elapsed}秒経過):`);
          console.log(`   前: ${lastUrl}`);
          console.log(`   後: ${currentUrl}`);
          lastUrl = currentUrl;

          await page.screenshot({
            path: `test-results/long-wait-url-change-${elapsed}s.png`,
            fullPage: true
          });
        }

        // コンテンツ変化を検出
        if (bodyHash !== lastBodyHash) {
          lastBodyHash = bodyHash;

          // 重要なキーワードを探す
          if (bodyText?.includes('完了') || bodyText?.includes('Complete')) {
            console.log(`\n✅ 解析完了を検出 (${elapsed}秒経過)`);
            await page.screenshot({
              path: `test-results/long-wait-complete-${elapsed}s.png`,
              fullPage: true
            });
            return; // 成功終了
          }

          if (bodyText?.includes('エラー') || bodyText?.includes('Error') || bodyText?.includes('失敗')) {
            console.log(`\n❌ エラー検出 (${elapsed}秒経過)`);
            console.log(`内容: ${bodyText.substring(0, 300)}`);
            await page.screenshot({
              path: `test-results/long-wait-error-${elapsed}s.png`,
              fullPage: true
            });
            throw new Error('アップロード/解析エラー');
          }

          // 進捗表示
          const progressMatch = bodyText?.match(/(\d+)%/);
          if (progressMatch) {
            console.log(`📊 進捗: ${progressMatch[1]}% (${elapsed}秒経過)`);
          }
        }

        // 5分ごとにスクリーンショット
        if (elapsed > 0 && elapsed % 300 === 0) {
          console.log(`\n📸 定期スクリーンショット (${elapsed}秒経過)`);
          await page.screenshot({
            path: `test-results/long-wait-${elapsed}s.png`,
            fullPage: true
          });
        }

        // 30秒ごとにログ
        if (checkCount % 10 === 0) {
          console.log(`⏳ 監視中... ${elapsed}秒経過 / 1800秒 (URL: ${currentUrl.substring(0, 50)}...)`);
        }

      } catch (e) {
        console.log(`⚠️  ページ読み取りエラー (${elapsed}秒経過): ${e}`);
      }

      await page.waitForTimeout(3000); // 3秒ごとにチェック
    }

    console.log('\n⏰ 30分経過 - タイムアウト');
    await page.screenshot({ path: 'test-results/long-wait-timeout.png', fullPage: true });

    const finalUrl = page.url();
    console.log(`📍 最終URL: ${finalUrl}`);

    throw new Error('30分以内に解析完了を確認できませんでした');
  });
});
