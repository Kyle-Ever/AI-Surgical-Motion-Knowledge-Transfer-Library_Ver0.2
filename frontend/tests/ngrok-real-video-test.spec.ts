import { test, expect } from '@playwright/test';
import * as path from 'path';

/**
 * 実際の動画ファイルを使用したngrok経由の完全ワークフローテスト
 *
 * 目的: 展示会環境で別のPCからアクセスした場合の動作確認
 * 動画: 【正式】手技動画.mp4 (26MB)
 * URL: https://mindmotionai.ngrok-free.dev
 * API: https://dev.mindmotionai.ngrok-free.dev
 */

const NGROK_FRONTEND_URL = 'https://mindmotionai.ngrok-free.dev';
const TEST_TIMEOUT = 600000; // 10分タイムアウト（26MB動画 + ngrok遅延）
const REAL_VIDEO_PATH = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\data\\uploads\\【正式】手技動画.mp4';

/**
 * ngrokの警告画面をスキップ
 */
async function skipNgrokWarning(page: any) {
  try {
    await page.waitForTimeout(2000);
    const title = await page.title();
    if (title.includes('ngrok') || title.includes('Visit Site')) {
      console.log('⚠️  ngrok警告画面を検出 - スキップ');
      const visitButton = page.locator('button:has-text("Visit Site")');
      if (await visitButton.count() > 0) {
        await visitButton.click();
        await page.waitForLoadState('networkidle');
        console.log('✓ ngrok警告画面スキップ完了');
      }
    }
  } catch (e) {
    // 警告画面がなければスキップ
  }
}

/**
 * 解析完了を待機（リダイレクト検知）
 */
async function waitForAnalysisComplete(page: any, maxWaitTime: number = 300000) {
  console.log(`⏳ 解析完了を待機中（最大${maxWaitTime / 1000}秒）...`);
  const startTime = Date.now();
  let lastProgress = '';

  while (Date.now() - startTime < maxWaitTime) {
    // URL変化を確認（/analysis/ → /analysis/または/dashboard/へのリダイレクト）
    const currentUrl = page.url();

    // 完了状態の検知
    if (currentUrl.includes('/analysis/') || currentUrl.includes('/dashboard/')) {
      try {
        // ページの読み込み完了を待つ
        await page.waitForLoadState('networkidle', { timeout: 10000 });

        // 「完了」または結果表示を確認
        const bodyText = await page.locator('body').textContent();
        if (bodyText.includes('完了') || bodyText.includes('Complete') ||
            bodyText.includes('解析結果') || bodyText.includes('骨格検出')) {
          console.log('✅ 解析完了を検出');
          return true;
        }

        // 進捗メッセージの取得
        const progressText = bodyText.match(/進捗: \d+%|\d+%完了|処理中/);
        if (progressText && progressText[0] !== lastProgress) {
          lastProgress = progressText[0];
          console.log(`📊 進捗: ${lastProgress}`);
        }
      } catch (e) {
        // 一時的なエラーは無視
      }
    }

    await page.waitForTimeout(3000); // 3秒ごとにチェック
  }

  console.log('⚠️  タイムアウト: 解析完了を確認できませんでした');
  return false;
}

test.describe('ngrok URL - 実際の動画でのE2Eテスト', () => {
  test.setTimeout(TEST_TIMEOUT);

  test('実動画アップロード→解析完了まで確認', async ({ page }) => {
    console.log('\n=== ワークフロー開始: 実動画（26MB）での完全テスト ===\n');

    // 1. ngrok URLへアクセス
    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);
    console.log('✓ ngrokフロントエンドへアクセス');

    // 2. アップロードページへ移動
    await page.waitForLoadState('networkidle');
    const uploadLink = page.locator('a[href="/upload"]').first();
    await uploadLink.click();
    await page.waitForLoadState('networkidle');
    console.log('✓ アップロードページ表示');
    await page.screenshot({ path: 'test-results/real-video-01-upload-page.png', fullPage: true });

    // 3. 実動画ファイルを選択
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(REAL_VIDEO_PATH);
    console.log('✓ 実動画ファイル選択完了: 【正式】手技動画.mp4 (26MB)');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/real-video-02-file-selected.png', fullPage: true });

    // 4. ステップ1: 映像タイプ選択へ
    const nextButton1 = page.locator('button:has-text("次へ")').first();
    await nextButton1.click();
    console.log('✓ 次へボタンクリック（映像タイプ選択へ）');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/real-video-03-type-selection.png', fullPage: true });

    // 5. 映像タイプを選択（外部カメラ・器具なし）
    const handOnlyButton = page.locator('button').filter({ hasText: '外部カメラ' }).filter({ hasText: '器具なし' }).first();
    await handOnlyButton.click();
    console.log('✓ 映像タイプ選択: 外部カメラ（器具なし）');
    await page.waitForTimeout(1000);

    // 6. ステップ2: 解析設定へ
    await page.waitForSelector('button:has-text("次へ")', { state: 'visible', timeout: 5000 });
    const nextButton2 = page.locator('button:has-text("次へ"):not([disabled])').last();
    await nextButton2.click();
    console.log('✓ 次へボタンクリック（解析設定へ）');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/real-video-04-annotation-settings.png', fullPage: true });

    // 7. アップロード実行
    console.log('⏳ アップロード実行中... (26MB動画、ngrok経由のため時間がかかります)');
    const uploadButton = page.locator('button:has-text("アップロード"), button[type="submit"]').first();
    await uploadButton.click();
    console.log('✓ アップロードボタンクリック');

    // アップロード進捗を監視
    await page.waitForTimeout(5000); // 初期待機
    await page.screenshot({ path: 'test-results/real-video-05-uploading.png', fullPage: true });

    // 8. 解析完了を待機（最大5分）
    const completed = await waitForAnalysisComplete(page, 300000);

    if (completed) {
      console.log('✅ 解析完了確認');
      await page.screenshot({ path: 'test-results/real-video-06-analysis-complete.png', fullPage: true });

      // 結果ページのURLを記録
      const resultUrl = page.url();
      console.log(`📍 解析結果URL: ${resultUrl}`);

      // 解析結果の確認
      const bodyText = await page.locator('body').textContent();
      console.log('✓ ページコンテンツ取得成功');

      if (bodyText.includes('骨格検出') || bodyText.includes('解析結果')) {
        console.log('✅ 解析結果データ確認');
      }
    } else {
      console.log('⚠️  解析完了を待機中にタイムアウトしました');
      await page.screenshot({ path: 'test-results/real-video-timeout.png', fullPage: true });

      // タイムアウト時の詳細情報
      const currentUrl = page.url();
      const bodyText = await page.locator('body').textContent();
      console.log(`📍 現在のURL: ${currentUrl}`);
      console.log(`📄 ページ内容の一部: ${bodyText.substring(0, 500)}...`);
    }

    expect(completed).toBeTruthy();
    console.log('\n✅ ワークフロー完了: 実動画での完全テスト\n');
  });
});
