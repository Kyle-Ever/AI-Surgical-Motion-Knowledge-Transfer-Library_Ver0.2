import { test, expect } from '@playwright/test';

/**
 * ngrok経由のアップロード状態確認テスト
 *
 * 目的: 26MB動画のアップロード後の状態を段階的に確認
 * - アップロードボタンが押せるか
 * - アップロード後にエラーメッセージが出ないか
 * - 進捗表示が正しく表示されるか
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

test.describe('ngrok アップロード状態確認', () => {
  test.setTimeout(180000); // 3分

  test('アップロードボタンクリック→初期応答確認', async ({ page }) => {
    console.log('\n=== テスト開始: アップロード初期応答確認 ===\n');

    // 1. ngrok URLへアクセス
    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);
    console.log('✓ フロントエンドアクセス');

    // 2. アップロードページへ
    const uploadLink = page.locator('a[href="/upload"]').first();
    await uploadLink.click();
    await page.waitForLoadState('networkidle');
    console.log('✓ アップロードページ表示');

    // 3. ファイル選択
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(REAL_VIDEO_PATH);
    console.log('✓ ファイル選択: 【正式】手技動画.mp4 (26MB)');
    await page.waitForTimeout(1000);

    // 4. 映像タイプ選択へ
    const nextButton1 = page.locator('button:has-text("次へ")').first();
    await nextButton1.click();
    console.log('✓ 映像タイプ選択ページへ遷移');
    await page.waitForTimeout(1000);

    // 5. 外部カメラ（器具なし）選択
    const handOnlyButton = page.locator('button').filter({ hasText: '外部カメラ' }).filter({ hasText: '器具なし' }).first();
    await handOnlyButton.click();
    console.log('✓ 映像タイプ選択');
    await page.waitForTimeout(1000);

    // 6. 解析設定ページへ
    const nextButton2 = page.locator('button:has-text("次へ"):not([disabled])').last();
    await nextButton2.click();
    console.log('✓ 解析設定ページへ遷移');
    await page.waitForTimeout(1000);

    // 7. アップロードボタンクリック
    const uploadButton = page.locator('button:has-text("アップロード"), button[type="submit"]').first();

    // ボタンの状態確認
    const isButtonVisible = await uploadButton.isVisible();
    const isButtonEnabled = await uploadButton.isEnabled();
    console.log(`📊 アップロードボタン状態: 表示=${isButtonVisible}, 有効=${isButtonEnabled}`);

    expect(isButtonVisible).toBeTruthy();
    expect(isButtonEnabled).toBeTruthy();

    await page.screenshot({ path: 'test-results/upload-check-01-before-click.png', fullPage: true });

    // コンソールエラーを監視
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
        console.log(`❌ Console Error: ${msg.text()}`);
      }
    });

    // ネットワークエラーを監視
    page.on('requestfailed', (request) => {
      console.log(`❌ Network Error: ${request.url()} - ${request.failure()?.errorText}`);
    });

    // アップロードボタンをクリック
    console.log('⏳ アップロードボタンクリック...');
    await uploadButton.click();

    // クリック直後の状態を確認（10秒待機）
    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'test-results/upload-check-02-after-click-10s.png', fullPage: true });

    // URL変化を確認
    const currentUrl = page.url();
    console.log(`📍 現在のURL: ${currentUrl}`);

    // ページコンテンツを確認
    const bodyText = await page.locator('body').textContent();

    // エラーメッセージの確認
    if (bodyText?.includes('エラー') || bodyText?.includes('Error') || bodyText?.includes('失敗')) {
      console.log('❌ エラーメッセージ検出');
      console.log(`内容: ${bodyText.substring(0, 500)}`);
    }

    // アップロード進捗の確認
    if (bodyText?.includes('アップロード中') || bodyText?.includes('%')) {
      console.log('✓ アップロード進捗表示を検出');
    }

    // 解析中の表示確認
    if (bodyText?.includes('解析中') || bodyText?.includes('処理中')) {
      console.log('✓ 解析処理開始を検出');
    }

    // 30秒後の状態を確認
    console.log('⏳ 30秒待機...');
    await page.waitForTimeout(20000);
    await page.screenshot({ path: 'test-results/upload-check-03-after-30s.png', fullPage: true });

    const urlAfter30s = page.url();
    const bodyAfter30s = await page.locator('body').textContent();
    console.log(`📍 30秒後のURL: ${urlAfter30s}`);

    // リダイレクトの確認
    if (urlAfter30s.includes('/analysis/')) {
      console.log('✅ 解析ページへのリダイレクト検出');
    } else if (urlAfter30s.includes('/upload')) {
      console.log('⚠️  まだアップロードページにいます');
    }

    // コンソールエラーのサマリ
    if (consoleErrors.length > 0) {
      console.log(`\n❌ コンソールエラー (${consoleErrors.length}件):`);
      consoleErrors.forEach((err, i) => {
        console.log(`  ${i + 1}. ${err}`);
      });
    } else {
      console.log('\n✅ コンソールエラーなし');
    }

    console.log('\n=== テスト完了: アップロード初期応答確認 ===\n');
    console.log('📝 次のステップ:');
    console.log('   1. スクリーンショットでアップロード後の状態を確認');
    console.log('   2. エラーがあれば原因を特定');
    console.log('   3. 問題なければ、ブラウザで直接アクセスして解析完了まで待機');
  });
});
