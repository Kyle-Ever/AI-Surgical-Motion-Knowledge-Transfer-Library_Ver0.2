import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

/**
 * ngrok URL経由での完全ワークフローE2Eテスト
 *
 * テスト対象:
 * 1. 新規解析（手技のみ）
 * 2. 新規解析（器具あり）
 * 3. 新規解析（視線解析）
 * 4. 採点モード
 *
 * URL: https://mindmotionai.ngrok-free.dev
 * API: https://dev.mindmotionai.ngrok-free.dev
 */

const NGROK_FRONTEND_URL = 'https://mindmotionai.ngrok-free.dev';
const TEST_TIMEOUT = 480000; // 8分タイムアウト（ngrokの遅延を考慮）

/**
 * テスト用の小さな動画ファイルを作成（600KB）
 */
function createTestVideo(filename: string, sizeKB: number = 600): string {
  const outputPath = path.join(process.cwd(), 'test-results', filename);
  const dir = path.dirname(outputPath);

  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  // MP4ヘッダー + 繰り返しデータで指定サイズのファイルを作成
  const mp4Header = Buffer.from([
    0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
    0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
    0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
    0x6D, 0x70, 0x34, 0x31
  ]);

  const targetSize = sizeKB * 1024;
  const fillSize = targetSize - mp4Header.length;
  const fillData = Buffer.alloc(fillSize, 0x00);

  const videoBuffer = Buffer.concat([mp4Header, fillData]);
  fs.writeFileSync(outputPath, videoBuffer);

  console.log(`✓ テスト動画作成: ${filename} (${sizeKB}KB)`);
  return outputPath;
}

/**
 * ngrok警告画面をスキップ
 */
async function skipNgrokWarning(page: any) {
  try {
    const title = await page.title();
    if (title.includes('ngrok') || title.includes('Visit Site')) {
      await page.click('button:has-text("Visit Site")');
      await page.waitForLoadState('networkidle');
      console.log('✅ ngrok警告画面をスキップ');
    }
  } catch (e) {
    // 警告画面がない場合は何もしない
  }
}

/**
 * 解析完了を待機（WebSocket進捗監視）
 */
async function waitForAnalysisComplete(page: any, maxWaitTime: number = 120000) {
  console.log('⏳ 解析完了を待機中...');

  const startTime = Date.now();

  while (Date.now() - startTime < maxWaitTime) {
    // ページ上の進捗表示を確認
    const statusText = await page.locator('body').textContent();

    if (statusText.includes('完了') || statusText.includes('Complete')) {
      console.log('✅ 解析完了を確認');
      return true;
    }

    if (statusText.includes('エラー') || statusText.includes('Error') || statusText.includes('失敗')) {
      console.log('❌ 解析エラーを検出');
      return false;
    }

    // URLが変わったか確認（結果ページへのリダイレクト）
    if (page.url().includes('/analysis/') || page.url().includes('/dashboard/')) {
      console.log('✅ 結果ページへリダイレクト');
      await page.waitForLoadState('networkidle');
      return true;
    }

    await page.waitForTimeout(2000); // 2秒ごとにチェック
  }

  console.log('⚠️  タイムアウト: 解析完了を確認できませんでした');
  return false;
}

test.describe('ngrok URL - 完全ワークフローE2Eテスト', () => {

  test.beforeEach(async ({ page }) => {
    // コンソールログを監視
    page.on('console', msg => {
      const text = msg.text();
      if (msg.type() === 'error' && !text.includes('ngrok-skip-browser-warning')) {
        console.log(`❌ Console Error: ${text}`);
      }
      if (text.includes('WebSocket') || text.includes('progress')) {
        console.log(`📡 ${text}`);
      }
    });
  });

  // ========================================
  // テスト1: 新規解析（手技のみ）
  // ========================================
  test('ワークフロー1: 新規解析（手技のみ）', async ({ page }) => {
    test.setTimeout(TEST_TIMEOUT);

    console.log('\n=== ワークフロー開始: 新規解析（手技のみ） ===\n');

    // 1. アップロードページへ移動
    await page.goto(`${NGROK_FRONTEND_URL}/upload`);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    console.log('✓ アップロードページ表示');
    await page.screenshot({ path: 'test-results/workflow-01-upload-page.png', fullPage: true });

    // 2. 解析タイプ選択（手技のみ）
    const handOnlyOption = page.locator('input[value="external/external_no_instruments"], label:has-text("手技のみ")').first();
    if (await handOnlyOption.count() > 0) {
      await handOnlyOption.click();
      console.log('✓ 解析タイプ選択: 手技のみ');
    } else {
      console.log('⚠️  手技のみオプション未検出 - デフォルト設定で続行');
    }

    // 3. 動画ファイルをアップロード
    const testVideoPath = createTestVideo('test-hand-only.mp4', 600);
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(testVideoPath);
    console.log('✓ 動画ファイル選択完了');

    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'test-results/workflow-01-file-selected.png', fullPage: true });

    // 4. 「次へ」ボタンをクリックして映像タイプ選択へ
    const nextButton = page.locator('button:has-text("次へ")').first();
    await nextButton.click();
    console.log('✓ 次へボタンクリック（映像タイプ選択へ）');
    await page.waitForTimeout(1000);

    // 5. 映像タイプを選択（外部カメラ・器具なし）
    const handOnlyTypeButton = page.locator('button:has-text("外部カメラ"), button:has-text("器具なし")').first();
    await handOnlyTypeButton.click();
    console.log('✓ 映像タイプ選択: 外部カメラ（器具なし）');
    await page.waitForTimeout(1000);

    // 6. 解析設定ページへ「次へ」をクリック
    await page.waitForSelector('button:has-text("次へ")', { state: 'visible', timeout: 5000 });
    const nextButton2 = page.locator('button:has-text("次へ"):not([disabled])').last();
    await nextButton2.click();
    console.log('✓ 次へボタンクリック（解析設定へ）');
    await page.waitForTimeout(1000);

    // 7. アップロード実行
    const uploadButton = page.locator('button:has-text("アップロード"), button[type="submit"]').first();
    await uploadButton.click();
    console.log('✓ アップロード実行');
    await page.waitForTimeout(3000); // ngrok経由のアップロード処理を待つ

    // 8. 解析完了を待機（ngrok遅延を考慮して4分）
    const completed = await waitForAnalysisComplete(page, 240000);
    expect(completed).toBeTruthy();

    await page.screenshot({ path: 'test-results/workflow-01-analysis-result.png', fullPage: true });

    console.log('\n✅ ワークフロー完了: 新規解析（手技のみ）\n');
  });

  // ========================================
  // テスト2: 新規解析（器具あり）
  // ========================================
  test('ワークフロー2: 新規解析（器具あり）', async ({ page }) => {
    test.setTimeout(TEST_TIMEOUT);

    console.log('\n=== ワークフロー開始: 新規解析（器具あり） ===\n');

    await page.goto(`${NGROK_FRONTEND_URL}/upload`);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    console.log('✓ アップロードページ表示');

    // 解析タイプ選択（器具あり）
    const instrumentOption = page.locator('input[value="external_with_instruments"], label:has-text("器具あり")').first();
    if (await instrumentOption.count() > 0) {
      await instrumentOption.click();
      console.log('✓ 解析タイプ選択: 器具あり');
    } else {
      console.log('⚠️  器具ありオプション未検出 - デフォルト設定で続行');
    }

    // 動画アップロード
    const testVideoPath = createTestVideo('test-with-instruments.mp4', 600);
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(testVideoPath);
    console.log('✓ 動画ファイル選択完了');

    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'test-results/workflow-02-file-selected.png', fullPage: true });

    // 「次へ」ボタンをクリックして映像タイプ選択へ
    const nextButton = page.locator('button:has-text("次へ")').first();
    await nextButton.click();
    console.log('✓ 次へボタンクリック（映像タイプ選択へ）');
    await page.waitForTimeout(1000);

    // 映像タイプを選択（外部カメラ・器具あり）
    const withInstrumentsTypeButton = page.locator('button').filter({ hasText: '外部カメラ' }).filter({ hasText: '器具あり' }).first();
    await withInstrumentsTypeButton.click();
    console.log('✓ 映像タイプ選択: 外部カメラ（器具あり）');
    await page.waitForTimeout(1000);

    // 器具選択ページへ「次へ」をクリック
    await page.waitForSelector('button:has-text("次へ")', { state: 'visible', timeout: 5000 });
    const nextButton2 = page.locator('button:has-text("次へ"):not([disabled])').last();
    await nextButton2.click();
    console.log('✓ 次へボタンクリック（器具選択へ）');
    await page.waitForTimeout(2000);

    // 器具選択はスキップして解析設定へ「次へ」
    await page.waitForSelector('button:has-text("次へ")', { state: 'visible', timeout: 5000 });
    const nextButton3 = page.locator('button:has-text("次へ"):not([disabled])').last();
    await nextButton3.click();
    console.log('✓ 次へボタンクリック（解析設定へ）');
    await page.waitForTimeout(1000);

    // アップロード実行
    const uploadButton = page.locator('button:has-text("アップロード"), button[type="submit"]').first();
    await uploadButton.click();
    console.log('✓ アップロード実行');
    await page.waitForTimeout(3000); // ngrok経由のアップロード処理を待つ

    // 解析完了を待機（ngrok遅延を考慮して4分）
    const completed = await waitForAnalysisComplete(page, 240000);
    expect(completed).toBeTruthy();

    await page.screenshot({ path: 'test-results/workflow-02-analysis-result.png', fullPage: true });

    console.log('\n✅ ワークフロー完了: 新規解析（器具あり）\n');
  });

  // ========================================
  // テスト3: 新規解析（視線解析）
  // ========================================
  test('ワークフロー3: 新規解析（視線解析）', async ({ page }) => {
    test.setTimeout(TEST_TIMEOUT);

    console.log('\n=== ワークフロー開始: 新規解析（視線解析） ===\n');

    await page.goto(`${NGROK_FRONTEND_URL}/upload`);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    console.log('✓ アップロードページ表示');

    // 視線解析オプションを有効化
    const gazeOption = page.locator('input[type="checkbox"][name*="gaze"], label:has-text("視線")').first();
    if (await gazeOption.count() > 0) {
      await gazeOption.click();
      console.log('✓ 視線解析オプション有効化');
    } else {
      console.log('⚠️  視線解析オプション未検出 - スキップ');
    }

    // 動画アップロード
    const testVideoPath = createTestVideo('test-gaze-analysis.mp4', 600);
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(testVideoPath);
    console.log('✓ 動画ファイル選択完了');

    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'test-results/workflow-03-file-selected.png', fullPage: true });

    // 「次へ」ボタンをクリックして映像タイプ選択へ
    const nextButton = page.locator('button:has-text("次へ")').first();
    await nextButton.click();
    console.log('✓ 次へボタンクリック（映像タイプ選択へ）');
    await page.waitForTimeout(1000);

    // 映像タイプを選択（視線解析）
    const gazeTypeButton = page.locator('button[data-testid="eye-gaze-button"]').first();
    await gazeTypeButton.click();
    console.log('✓ 映像タイプ選択: 視線解析（DeepGaze III）');
    await page.waitForTimeout(1000);

    // 解析設定ページへ「次へ」をクリック
    await page.waitForSelector('button:has-text("次へ")', { state: 'visible', timeout: 5000 });
    const nextButton2 = page.locator('button:has-text("次へ"):not([disabled])').last();
    await nextButton2.click();
    console.log('✓ 次へボタンクリック（解析設定へ）');
    await page.waitForTimeout(1000);

    // アップロード実行
    const uploadButton = page.locator('button:has-text("アップロード"), button[type="submit"]').first();
    await uploadButton.click();
    console.log('✓ アップロード実行');
    await page.waitForTimeout(3000); // ngrok経由のアップロード処理を待つ

    // 解析完了を待機（ngrok遅延を考慮して4分）
    const completed = await waitForAnalysisComplete(page, 240000);
    expect(completed).toBeTruthy();

    await page.screenshot({ path: 'test-results/workflow-03-analysis-result.png', fullPage: true });

    // 視線解析ダッシュボードへのリダイレクト確認
    if (page.url().includes('/dashboard/')) {
      console.log('✓ 視線解析ダッシュボードへ自動リダイレクト');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: 'test-results/workflow-03-gaze-dashboard.png', fullPage: true });
      console.log('✓ 視線解析ダッシュボード表示');
    }

    console.log('\n✅ ワークフロー完了: 新規解析（視線解析）\n');
  });

  // ========================================
  // テスト4: 採点モード
  // ========================================
  test('ワークフロー4: 採点モード', async ({ page }) => {
    test.setTimeout(TEST_TIMEOUT);

    console.log('\n=== ワークフロー開始: 採点モード ===\n');

    // 1. ライブラリページへ移動
    await page.goto(`${NGROK_FRONTEND_URL}/library`);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    console.log('✓ ライブラリページ表示');
    await page.screenshot({ path: 'test-results/workflow-04-library.png', fullPage: true });

    // 2. リファレンス動画を確認
    const referenceVideos = await page.locator('[data-testid="reference-video"], .reference-video, h3:has-text("リファレンス"), h3:has-text("Reference")').count();
    console.log(`✓ リファレンス動画セクション: ${referenceVideos > 0 ? '検出' : '未検出'}`);

    // 3. 採点モードボタンを探す
    const scoringButton = page.locator('button:has-text("採点"), button:has-text("Scoring"), a[href*="/scoring"]').first();

    if (await scoringButton.count() > 0) {
      console.log('✓ 採点モードボタン検出');
      await scoringButton.click();
      await page.waitForLoadState('networkidle');

      console.log('✓ 採点モードページ表示');
      await page.screenshot({ path: 'test-results/workflow-04-scoring-page.png', fullPage: true });

      // 4. 採点モードで動画を選択
      const videoSelectors = await page.locator('select, [role="combobox"], button:has-text("選択")').count();
      console.log(`✓ 動画選択UI: ${videoSelectors}個検出`);

      if (videoSelectors > 0) {
        // 最初のセレクタを操作
        const firstSelector = page.locator('select, [role="combobox"]').first();
        if (await firstSelector.count() > 0) {
          await firstSelector.click();
          await page.waitForTimeout(500);

          // オプションを選択（2番目のオプションを選択）
          const options = await page.locator('option, [role="option"]').count();
          if (options > 1) {
            await page.locator('option, [role="option"]').nth(1).click();
            console.log('✓ 動画選択完了');
          }
        }
      }

      await page.screenshot({ path: 'test-results/workflow-04-video-selected.png', fullPage: true });

      // 5. 比較実行ボタン
      const compareButton = page.locator('button:has-text("比較"), button:has-text("Compare"), button[type="submit"]').first();
      if (await compareButton.count() > 0) {
        await compareButton.click();
        console.log('✓ 比較実行');

        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(3000);

        await page.screenshot({ path: 'test-results/workflow-04-scoring-result.png', fullPage: true });

        // スコア表示の確認
        const scoreElements = await page.locator('[data-testid="score"], .score, text=/\\d+%/, text=/\\d+\\.\\d+/').count();
        console.log(`✓ スコア表示要素: ${scoreElements}個検出`);
      }

      console.log('\n✅ ワークフロー完了: 採点モード\n');
    } else {
      console.log('⚠️  採点モードボタン未検出 - テストスキップ');
    }
  });

});
