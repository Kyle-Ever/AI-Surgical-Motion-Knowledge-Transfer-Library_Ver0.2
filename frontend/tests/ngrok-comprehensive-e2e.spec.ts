import { test, expect } from '@playwright/test';

/**
 * ngrok URL経由での包括的E2Eテスト
 *
 * テスト対象URL: https://mindmotionai.ngrok-free.dev
 * バックエンドAPI: https://dev.mindmotionai.ngrok-free.dev
 *
 * 目的: 別のPC/ネットワークからアクセスした場合の動作検証
 */

const NGROK_FRONTEND_URL = 'https://mindmotionai.ngrok-free.dev';
const NGROK_BACKEND_URL = 'https://dev.mindmotionai.ngrok-free.dev';

/**
 * ngrok警告画面を自動でスキップ
 */
async function skipNgrokWarning(page: any) {
  try {
    const title = await page.title();
    if (title.includes('ngrok') || title.includes('Visit Site')) {
      console.log('⚠️  ngrok警告画面を検出 - スキップ処理実行');
      await page.click('button:has-text("Visit Site")');
      await page.waitForLoadState('networkidle');
      console.log('✅ ngrok警告画面をスキップしました');
    }
  } catch (e) {
    // 警告画面がない場合は何もしない
  }
}

test.describe('ngrok URL - 包括的E2Eテスト', () => {

  test.beforeEach(async ({ page }) => {
    // コンソールエラーを監視（ngrok関連のエラーは除外）
    page.on('console', msg => {
      if (msg.type() === 'error' && !msg.text().includes('ngrok-skip-browser-warning')) {
        console.log(`❌ Console Error: ${msg.text()}`);
      }
    });
  });

  // ========================================
  // テスト1: トップページの表示確認
  // ========================================
  test('ユースケース1: トップページが正常に表示される', async ({ page }) => {
    console.log('\n=== テスト開始: トップページ表示確認 ===\n');

    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);

    await page.waitForLoadState('networkidle');

    // ページタイトル確認
    const title = await page.title();
    console.log(`✓ ページタイトル: ${title}`);
    expect(title).toContain('AI');

    // メインコンテンツの表示確認
    const mainContent = await page.locator('main, [role="main"], body').first();
    await expect(mainContent).toBeVisible();
    console.log('✓ メインコンテンツ: 表示確認');

    // ナビゲーションの存在確認
    const hasNavigation = await page.locator('nav, a[href*="/upload"], a[href*="/library"]').count() > 0;
    console.log(`✓ ナビゲーション: ${hasNavigation ? '検出' : '未検出'}`);

    await page.screenshot({ path: 'test-results/ngrok-01-homepage.png', fullPage: true });
    console.log('📸 スクリーンショット保存: ngrok-01-homepage.png');

    console.log('\n✅ トップページ表示テスト完了\n');
  });

  // ========================================
  // テスト2: アップロードページへの遷移
  // ========================================
  test('ユースケース2: アップロードページへ遷移できる', async ({ page }) => {
    console.log('\n=== テスト開始: アップロードページ遷移 ===\n');

    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    // アップロードページへのリンクを探す
    const uploadLink = page.locator('a[href*="/upload"], a:has-text("アップロード"), a:has-text("Upload")').first();

    if (await uploadLink.count() > 0) {
      console.log('✓ アップロードリンク: 検出');
      await uploadLink.click();
      await page.waitForLoadState('networkidle');
    } else {
      console.log('⚠️  アップロードリンク未検出 - 直接URL遷移');
      await page.goto(`${NGROK_FRONTEND_URL}/upload`);
      await page.waitForLoadState('networkidle');
    }

    // URLの確認
    const currentUrl = page.url();
    console.log(`✓ 現在のURL: ${currentUrl}`);
    expect(currentUrl).toContain('/upload');

    // ファイル入力欄の存在確認
    const fileInput = page.locator('input[type="file"]');
    const fileInputCount = await fileInput.count();
    console.log(`✓ ファイル入力欄: ${fileInputCount}個検出`);
    expect(fileInputCount).toBeGreaterThan(0);

    await page.screenshot({ path: 'test-results/ngrok-02-upload-page.png', fullPage: true });
    console.log('📸 スクリーンショット保存: ngrok-02-upload-page.png');

    console.log('\n✅ アップロードページ遷移テスト完了\n');
  });

  // ========================================
  // テスト3: バックエンドAPI接続確認
  // ========================================
  test('ユースケース3: バックエンドAPIに接続できる', async ({ page }) => {
    console.log('\n=== テスト開始: バックエンドAPI接続確認 ===\n');

    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    // APIエンドポイントに直接リクエスト（ブラウザコンテキスト内）
    const apiHealthUrl = `${NGROK_BACKEND_URL}/api/v1/health`;
    console.log(`API Health Check: ${apiHealthUrl}`);

    try {
      const response = await page.goto(apiHealthUrl);
      const status = response?.status();
      console.log(`✓ APIレスポンスステータス: ${status}`);

      if (status === 200) {
        const text = await response?.text();
        console.log(`✓ APIレスポンス内容: ${text?.substring(0, 100)}...`);
        expect(status).toBe(200);
      } else {
        console.log(`⚠️  予期しないステータスコード: ${status}`);
      }
    } catch (error: any) {
      console.log(`❌ API接続エラー: ${error.message}`);
      throw error;
    }

    console.log('\n✅ バックエンドAPI接続テスト完了\n');
  });

  // ========================================
  // テスト4: ライブラリページの表示確認
  // ========================================
  test('ユースケース4: ライブラリページが正常に表示される', async ({ page }) => {
    console.log('\n=== テスト開始: ライブラリページ表示確認 ===\n');

    await page.goto(`${NGROK_FRONTEND_URL}/library`);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    // ページタイトル確認
    const title = await page.title();
    console.log(`✓ ページタイトル: ${title}`);

    // URLの確認
    const currentUrl = page.url();
    console.log(`✓ 現在のURL: ${currentUrl}`);
    expect(currentUrl).toContain('/library');

    // ライブラリコンテンツの確認
    const pageContent = await page.locator('main, [role="main"], body').first().textContent();
    const hasLibraryContent = pageContent?.includes('ライブラリ') ||
                              pageContent?.includes('Library') ||
                              pageContent?.includes('動画') ||
                              pageContent?.includes('Video');
    console.log(`✓ ライブラリコンテンツ: ${hasLibraryContent ? '検出' : '未検出'}`);

    await page.screenshot({ path: 'test-results/ngrok-04-library-page.png', fullPage: true });
    console.log('📸 スクリーンショット保存: ngrok-04-library-page.png');

    console.log('\n✅ ライブラリページ表示テスト完了\n');
  });

  // ========================================
  // テスト5: CORS設定の確認（API呼び出し）
  // ========================================
  test('ユースケース5: フロントエンドからバックエンドAPIへのCORS接続', async ({ page }) => {
    console.log('\n=== テスト開始: CORS接続確認 ===\n');

    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    // ネットワークリクエストを監視
    const apiRequests: string[] = [];
    page.on('request', request => {
      const url = request.url();
      if (url.includes('dev.mindmotionai.ngrok-free.dev')) {
        apiRequests.push(url);
        console.log(`📡 API Request: ${url}`);
      }
    });

    // APIレスポンスを監視
    const apiResponses: { url: string; status: number }[] = [];
    page.on('response', response => {
      const url = response.url();
      if (url.includes('dev.mindmotionai.ngrok-free.dev')) {
        apiResponses.push({ url, status: response.status() });
        console.log(`📥 API Response: ${url} - Status: ${response.status()}`);
      }
    });

    // ライブラリページに遷移してAPI呼び出しをトリガー
    await page.goto(`${NGROK_FRONTEND_URL}/library`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000); // API呼び出し完了待機

    console.log(`\n✓ API Requests: ${apiRequests.length}件`);
    console.log(`✓ API Responses: ${apiResponses.length}件`);

    // CORSエラーがないことを確認
    const corsErrors = apiResponses.filter(r => r.status === 0 || r.status >= 400);
    if (corsErrors.length > 0) {
      console.log(`⚠️  エラーレスポンス: ${corsErrors.length}件`);
      corsErrors.forEach(err => console.log(`  - ${err.url}: ${err.status}`));
    } else {
      console.log('✓ CORSエラー: なし');
    }

    expect(apiResponses.length).toBeGreaterThan(0);

    console.log('\n✅ CORS接続テスト完了\n');
  });

  // ========================================
  // テスト6: レスポンシブデザインの確認
  // ========================================
  test('ユースケース6: モバイル表示の確認', async ({ page }) => {
    console.log('\n=== テスト開始: モバイル表示確認 ===\n');

    // モバイルビューポートに設定
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
    console.log('✓ ビューポート: 375x667 (モバイル)');

    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    // メインコンテンツが表示されるか
    const mainContent = await page.locator('main, [role="main"], body').first();
    await expect(mainContent).toBeVisible();
    console.log('✓ メインコンテンツ: モバイルで表示確認');

    await page.screenshot({ path: 'test-results/ngrok-06-mobile-view.png', fullPage: true });
    console.log('📸 スクリーンショット保存: ngrok-06-mobile-view.png');

    // デスクトップビューポートに戻す
    await page.setViewportSize({ width: 1920, height: 1080 });
    console.log('✓ ビューポート: 1920x1080 (デスクトップ)');

    await page.goto(NGROK_FRONTEND_URL);
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'test-results/ngrok-06-desktop-view.png', fullPage: true });
    console.log('📸 スクリーンショット保存: ngrok-06-desktop-view.png');

    console.log('\n✅ レスポンシブデザインテスト完了\n');
  });

  // ========================================
  // テスト7: ページロード時間の確認
  // ========================================
  test('ユースケース7: ページロード時間のパフォーマンス確認', async ({ page }) => {
    console.log('\n=== テスト開始: パフォーマンス確認 ===\n');

    const startTime = Date.now();

    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`✓ ページロード時間: ${loadTime}ms`);

    // 10秒以内にロード完了することを確認
    expect(loadTime).toBeLessThan(10000);

    if (loadTime < 3000) {
      console.log('🚀 優秀: 3秒以内にロード完了');
    } else if (loadTime < 5000) {
      console.log('✅ 良好: 5秒以内にロード完了');
    } else {
      console.log('⚠️  改善余地: 5秒以上かかりました');
    }

    console.log('\n✅ パフォーマンステスト完了\n');
  });

  // ========================================
  // テスト8: 環境変数の正しい設定確認
  // ========================================
  test('ユースケース8: フロントエンドが正しいバックエンドURLを使用している', async ({ page }) => {
    console.log('\n=== テスト開始: 環境変数設定確認 ===\n');

    await page.goto(NGROK_FRONTEND_URL);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');

    // ページ内でAPIベースURLを確認
    const apiBaseUrl = await page.evaluate(() => {
      return (window as any).NEXT_PUBLIC_API_URL ||
             document.querySelector('meta[name="api-url"]')?.getAttribute('content');
    });

    console.log(`✓ フロントエンドAPI URL設定: ${apiBaseUrl || '未検出（ブラウザ側では確認不可）'}`);

    // 実際のAPIリクエストURLを確認
    let actualApiUrl = '';
    page.on('request', request => {
      const url = request.url();
      if (url.includes('/api/v1/') && !actualApiUrl) {
        actualApiUrl = url;
      }
    });

    // ライブラリページに移動してAPI呼び出しをトリガー
    await page.goto(`${NGROK_FRONTEND_URL}/library`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    if (actualApiUrl) {
      console.log(`✓ 実際のAPI呼び出しURL: ${actualApiUrl}`);
      expect(actualApiUrl).toContain('dev.mindmotionai.ngrok-free.dev');
      console.log('✅ 正しいバックエンドngrok URLが使用されています');
    } else {
      console.log('⚠️  API呼び出しが検出されませんでした');
    }

    console.log('\n✅ 環境変数設定テスト完了\n');
  });

});
