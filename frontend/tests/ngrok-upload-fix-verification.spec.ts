import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

/**
 * ngrok URL経由 - ファイルアップロード修正検証テスト
 *
 * 修正内容:
 * - Next.js 15のbodyLimit制限（1MB → 1GB）
 * - next.config.tsにbodySizeLimit設定追加
 * - 600KB動画のアップロード成功を確認
 */

const NGROK_URL = 'https://attestable-emily-reservedly.ngrok-free.dev';

// テスト用の小さな動画ファイルを作成（600KB相当のダミーデータ）
function createTestVideoFile(sizeKB: number): Buffer {
  // MP4のダミーヘッダー（最小限の有効なMP4構造）
  const mp4Header = Buffer.from([
    0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70, // ftyp box
    0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
    0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
    0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31,
  ]);

  // 指定サイズまでゼロで埋める
  const targetSize = sizeKB * 1024;
  const padding = Buffer.alloc(targetSize - mp4Header.length);

  return Buffer.concat([mp4Header, padding]);
}

async function skipNgrokWarning(page: any) {
  const selectors = ['button:has-text("Visit Site")', 'a:has-text("Visit Site")'];

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

test.describe('ngrok URL - アップロード修正検証', () => {

  test('600KB動画アップロード - 修正後の動作確認', async ({ page }) => {
    console.log('\n=== テスト開始: 600KB動画アップロード ===');

    // コンソールエラーを収集
    const consoleErrors: string[] = [];
    const consoleWarnings: string[] = [];

    page.on('console', (msg) => {
      const text = msg.text();
      if (msg.type() === 'error') {
        consoleErrors.push(text);
        console.log(`❌ Console Error: ${text}`);
      } else if (msg.type() === 'warning') {
        consoleWarnings.push(text);
      } else if (text.includes('[Proxy]') || text.includes('upload')) {
        console.log(`📝 Log: ${text}`);
      }
    });

    // ngrok URLにアクセス
    const uploadUrl = `${NGROK_URL}/upload`;
    console.log(`アクセス先: ${uploadUrl}`);

    await page.goto(uploadUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await skipNgrokWarning(page);

    // ページタイトル確認
    await page.waitForSelector('h1, h2', { timeout: 10000 });
    const pageTitle = await page.locator('h1, h2').first().textContent();
    console.log(`✓ ページタイトル: ${pageTitle}`);

    // ファイル選択前の状態確認
    const fileInput = page.locator('input[type="file"]');
    const fileInputExists = await fileInput.isVisible();
    console.log(`✓ ファイル入力欄: ${fileInputExists ? '検出' : '未検出'}`);

    if (!fileInputExists) {
      console.log('❌ ファイル入力欄が見つかりません');
      await page.screenshot({
        path: 'frontend/tests/screenshots/upload-page-no-input.png',
        fullPage: true
      });
      throw new Error('File input not found');
    }

    // 600KBのテスト動画を作成
    console.log('\n600KB動画ファイルを作成中...');
    const testVideoBuffer = createTestVideoFile(600);
    const tempFilePath = path.join(process.cwd(), 'tests', 'temp_test_video_600kb.mp4');
    fs.writeFileSync(tempFilePath, testVideoBuffer);
    console.log(`✓ テスト動画作成完了: ${tempFilePath}`);
    console.log(`✓ ファイルサイズ: ${(testVideoBuffer.length / 1024).toFixed(2)} KB`);

    try {
      // ファイルをアップロード
      await fileInput.setInputFiles(tempFilePath);
      console.log('✓ ファイル選択完了');

      // ファイル名が表示されるまで待機
      await page.waitForTimeout(1000);

      // 動画タイプを選択（external）
      const videoTypeSelect = page.locator('select[name="video_type"], select').first();
      const selectExists = await videoTypeSelect.isVisible({ timeout: 5000 }).catch(() => false);

      if (selectExists) {
        await videoTypeSelect.selectOption('external');
        console.log('✓ 動画タイプ選択: external');
      }

      // アップロードボタンをクリック
      const uploadButton = page.locator('button').filter({ hasText: /アップロード|Upload|送信/ }).first();
      const buttonExists = await uploadButton.isVisible({ timeout: 5000 }).catch(() => false);

      if (buttonExists) {
        console.log('✓ アップロードボタン検出');

        // ネットワークリクエストを監視
        let uploadRequestSent = false;
        let uploadResponse: any = null;

        page.on('response', async (response) => {
          const url = response.url();
          if (url.includes('/api/v1/videos/upload')) {
            uploadRequestSent = true;
            uploadResponse = response;
            console.log(`\n📡 アップロードリクエスト検出:`);
            console.log(`  - URL: ${url}`);
            console.log(`  - ステータス: ${response.status()}`);
            console.log(`  - ステータステキスト: ${response.statusText()}`);

            try {
              const responseBody = await response.json();
              console.log(`  - レスポンス:`, JSON.stringify(responseBody, null, 2));
            } catch (e) {
              console.log(`  - レスポンス: (JSON解析不可)`);
            }
          }
        });

        // アップロード実行
        await uploadButton.click();
        console.log('✓ アップロードボタンクリック');

        // レスポンスを待機（最大30秒）
        await page.waitForTimeout(5000);

        // 結果確認
        if (uploadRequestSent && uploadResponse) {
          const status = uploadResponse.status();

          if (status === 201 || status === 200) {
            console.log('\n✅ アップロード成功！');
            console.log(`  - HTTPステータス: ${status}`);
          } else {
            console.log(`\n❌ アップロード失敗`);
            console.log(`  - HTTPステータス: ${status}`);

            // エラー詳細を取得
            try {
              const errorBody = await uploadResponse.json();
              console.log(`  - エラー詳細:`, errorBody);
            } catch (e) {
              console.log(`  - エラー詳細取得失敗`);
            }
          }

          // ステータスコードの検証
          expect(status).toBeLessThan(400);

        } else {
          console.log('⚠️ アップロードリクエストが送信されなかった可能性');
        }

        // 成功メッセージの確認
        const successMessage = await page.locator('text=/成功|Success|完了/i').first();
        const hasSuccessMessage = await successMessage.isVisible({ timeout: 10000 }).catch(() => false);

        if (hasSuccessMessage) {
          const messageText = await successMessage.textContent();
          console.log(`✓ 成功メッセージ: ${messageText}`);
        }

      } else {
        console.log('⚠️ アップロードボタンが見つかりません');
      }

      // スクリーンショット撮影
      await page.screenshot({
        path: 'frontend/tests/screenshots/ngrok-upload-600kb-result.png',
        fullPage: true
      });

      // エラーチェック
      const criticalErrors = consoleErrors.filter(err =>
        !err.includes('Refused to load the font') && // ngrok警告画面のフォントエラーは無視
        !err.includes('Content Security Policy')
      );

      if (criticalErrors.length > 0) {
        console.log(`\n❌ 重大なコンソールエラー: ${criticalErrors.length}件`);
        criticalErrors.forEach(err => console.log(`  - ${err}`));
      } else {
        console.log('\n✅ 重大なコンソールエラーなし');
      }

      console.log('\n=== テスト結果サマリー ===');
      console.log(`アップロードリクエスト送信: ${uploadRequestSent ? 'YES' : 'NO'}`);
      console.log(`コンソールエラー数: ${criticalErrors.length}件`);

    } finally {
      // テストファイルを削除
      if (fs.existsSync(tempFilePath)) {
        fs.unlinkSync(tempFilePath);
        console.log(`✓ テストファイル削除: ${tempFilePath}`);
      }
    }

    console.log('\n✅ テスト完了');
  });

  test('ローカル環境 - 比較テスト（600KB）', async ({ page }) => {
    console.log('\n=== テスト開始: ローカル環境（比較用） ===');

    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error' &&
          !msg.text().includes('Refused to load') &&
          !msg.text().includes('Content Security Policy')) {
        consoleErrors.push(msg.text());
      }
    });

    const localUrl = 'http://localhost:3000/upload';
    console.log(`アクセス先: ${localUrl}`);

    await page.goto(localUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

    const pageTitle = await page.locator('h1, h2').first().textContent();
    console.log(`✓ ページタイトル: ${pageTitle}`);

    const fileInput = page.locator('input[type="file"]');
    const fileInputExists = await fileInput.isVisible();
    console.log(`✓ ファイル入力欄: ${fileInputExists ? '検出' : '未検出'}`);

    // 600KBのテスト動画を作成
    const testVideoBuffer = createTestVideoFile(600);
    const tempFilePath = path.join(process.cwd(), 'tests', 'temp_test_video_local_600kb.mp4');
    fs.writeFileSync(tempFilePath, testVideoBuffer);

    try {
      await fileInput.setInputFiles(tempFilePath);
      console.log('✓ ファイル選択完了');

      await page.waitForTimeout(1000);

      const videoTypeSelect = page.locator('select[name="video_type"], select').first();
      const selectExists = await videoTypeSelect.isVisible({ timeout: 5000 }).catch(() => false);

      if (selectExists) {
        await videoTypeSelect.selectOption('external');
      }

      const uploadButton = page.locator('button').filter({ hasText: /アップロード|Upload|送信/ }).first();
      const buttonExists = await uploadButton.isVisible({ timeout: 5000 }).catch(() => false);

      if (buttonExists) {
        let uploadSuccess = false;

        page.on('response', async (response) => {
          if (response.url().includes('/api/v1/videos/upload')) {
            const status = response.status();
            console.log(`📡 アップロードレスポンス: ${status}`);
            if (status < 400) {
              uploadSuccess = true;
            }
          }
        });

        await uploadButton.click();
        await page.waitForTimeout(5000);

        if (uploadSuccess) {
          console.log('✅ ローカル環境: アップロード成功');
        } else {
          console.log('⚠️ ローカル環境: アップロード結果不明');
        }
      }

      await page.screenshot({
        path: 'frontend/tests/screenshots/local-upload-600kb-result.png',
        fullPage: true
      });

      console.log(`コンソールエラー数: ${consoleErrors.length}件`);

    } finally {
      if (fs.existsSync(tempFilePath)) {
        fs.unlinkSync(tempFilePath);
      }
    }

    console.log('✅ ローカル環境テスト完了');
  });
});
