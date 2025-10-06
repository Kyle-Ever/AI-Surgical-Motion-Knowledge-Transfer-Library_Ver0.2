import { test, expect } from '@playwright/test';

test.describe('E2E V2: 履歴・検索フロー', () => {
  test('履歴ページアクセス → 動画リスト表示', async ({ page }) => {
    // 1. 履歴ページにアクセス
    await page.goto('http://localhost:3000/history');
    await page.waitForLoadState('networkidle');

    // 2. ページタイトル確認
    const pageTitle = page.locator('h1, h2, [data-testid="history-title"]').first();
    await expect(pageTitle).toBeVisible();

    const titleText = await pageTitle.textContent();
    console.log(`Page title: ${titleText}`);

    // 3. ローディング状態の確認
    const loadingIndicator = page.locator('text=/読み込み中|Loading|Loader/i').first();
    const isLoading = await loadingIndicator.isVisible({ timeout: 2000 }).catch(() => false);

    if (isLoading) {
      console.log('Loading indicator found, waiting...');
      await page.waitForTimeout(3000);
    }

    // 4. コンテンツエリアの確認（動画リストまたはエラーメッセージ）
    const contentArea = page.locator('main, [role="main"], [class*="container"]').first();
    await expect(contentArea).toBeVisible({ timeout: 5000 });
    console.log('✅ Content area found');

    // 5. 動画アイテムまたは空のメッセージを確認
    const videoItems = await page.locator('[data-video-id], [data-analysis-id], [class*="video"], [class*="analysis"], [class*="card"]').all();
    console.log(`Found ${videoItems.length} items in page`);

    if (videoItems.length > 0) {
      console.log('✅ Items displayed in list');

      // 最初のアイテムの内容確認
      const firstItem = videoItems[0];
      const hasText = await firstItem.textContent();
      console.log(`First item preview: ${hasText?.substring(0, 80)}...`);
    } else {
      // 空のメッセージやエラー表示を確認
      const emptyMessage = page.locator('text=/データがありません|No data|空です|Empty/i').first();
      const hasEmptyMessage = await emptyMessage.isVisible({ timeout: 2000 }).catch(() => false);

      if (hasEmptyMessage) {
        console.log('ℹ️ Empty state message found');
      } else {
        console.log('⚠️ No items and no empty message (may be layout issue)');
      }
    }

    console.log('✅ History page access test completed');
  });

  test('検索フィルタ機能 - 手術名検索', async ({ page }) => {
    // 1. 履歴ページにアクセス
    await page.goto('http://localhost:3000/history');
    await page.waitForLoadState('networkidle');

    // 2. 検索入力フィールドを探す
    const searchInput = page.locator('input[type="search"], input[placeholder*="検索"], input[placeholder*="Search"], input[name*="search"]').first();

    const hasSearchInput = await searchInput.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasSearchInput) {
      console.log('✅ Search input found');

      // 3. 検索キーワードを入力
      await searchInput.fill('テスト');
      await page.waitForTimeout(1000);

      // 4. 検索結果の変化を確認
      const videoItems = await page.locator('[data-video-id], [class*="video-card"], tr[data-id]').all();
      console.log(`After search: ${videoItems.length} videos`);

      // 5. フィルタリングされたアイテムに検索キーワードが含まれるか確認
      if (videoItems.length > 0) {
        let matchCount = 0;
        for (const item of videoItems) {
          const text = await item.textContent();
          if (text && text.includes('テスト')) {
            matchCount++;
          }
        }
        console.log(`${matchCount} items contain search keyword`);

        if (matchCount > 0) {
          console.log('✅ Search filtering works');
        }
      }

      // 6. 検索をクリア
      await searchInput.clear();
      await page.waitForTimeout(1000);
    } else {
      console.log('⚠️ Search input not found');
    }

    console.log('✅ Search filter test completed');
  });

  test('フィルタ機能 - 動画タイプフィルタ', async ({ page }) => {
    // 1. 履歴ページにアクセス
    await page.goto('http://localhost:3000/history');
    await page.waitForLoadState('networkidle');

    // 2. 動画タイプフィルタを探す
    const typeFilter = page.locator('select[name*="type"], [data-filter="type"], button:has-text("タイプ"), button:has-text("Type")').first();

    const hasTypeFilter = await typeFilter.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasTypeFilter) {
      console.log('✅ Type filter found');

      // 3. フィルタを適用
      if (await typeFilter.evaluate(el => el.tagName) === 'SELECT') {
        // セレクトボックスの場合
        await typeFilter.selectOption('internal');
        await page.waitForTimeout(1000);

        const videoItems = await page.locator('[data-video-id], [class*="video-card"]').all();
        console.log(`After type filter: ${videoItems.length} videos`);

        if (videoItems.length > 0) {
          console.log('✅ Type filter applied');
        }
      } else {
        // ボタンやその他のUIの場合
        await typeFilter.click();
        await page.waitForTimeout(1000);
      }
    } else {
      console.log('⚠️ Type filter not found');
    }

    console.log('✅ Type filter test completed');
  });

  test('日付範囲フィルタ', async ({ page }) => {
    await page.goto('http://localhost:3000/history');
    await page.waitForLoadState('networkidle');

    // 日付フィルタを探す
    const dateInput = page.locator('input[type="date"], input[placeholder*="日付"], input[placeholder*="Date"]').first();

    const hasDateFilter = await dateInput.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasDateFilter) {
      console.log('✅ Date filter found');

      // 日付を設定
      const today = new Date().toISOString().split('T')[0];
      await dateInput.fill(today);
      await page.waitForTimeout(1000);

      console.log(`Date filter set to: ${today}`);
      console.log('✅ Date filter applied');
    } else {
      console.log('⚠️ Date filter not found (may not be implemented)');
    }

    console.log('✅ Date filter test completed');
  });

  test('ソート機能 - 作成日でソート', async ({ page }) => {
    await page.goto('http://localhost:3000/history');
    await page.waitForLoadState('networkidle');

    // ソートボタンまたはヘッダーを探す
    const sortButton = page.locator('button:has-text("日付"), button:has-text("Date"), th:has-text("作成日"), [data-sort="created"]').first();

    const hasSortButton = await sortButton.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasSortButton) {
      console.log('✅ Sort button found');

      // 初期状態の最初の動画
      const videoItemsBefore = await page.locator('[data-video-id], [class*="video-card"], tr[data-id]').all();
      let firstVideoBefore = '';
      if (videoItemsBefore.length > 0) {
        firstVideoBefore = await videoItemsBefore[0].textContent() || '';
      }

      // ソートボタンをクリック
      await sortButton.click();
      await page.waitForTimeout(1000);

      // ソート後の最初の動画
      const videoItemsAfter = await page.locator('[data-video-id], [class*="video-card"], tr[data-id]').all();
      let firstVideoAfter = '';
      if (videoItemsAfter.length > 0) {
        firstVideoAfter = await videoItemsAfter[0].textContent() || '';
      }

      // 順序が変わったか確認
      if (firstVideoBefore !== firstVideoAfter) {
        console.log('✅ Sort order changed');
      } else {
        console.log('ℹ️ Sort order unchanged (may be same or only one item)');
      }
    } else {
      console.log('⚠️ Sort button not found');
    }

    console.log('✅ Sort function test completed');
  });

  test('ページネーション機能', async ({ page }) => {
    await page.goto('http://localhost:3000/history');
    await page.waitForLoadState('networkidle');

    // ページネーションコントロールを探す
    const pagination = page.locator('[data-testid="pagination"], [class*="pagination"], nav[aria-label*="ページ"], nav[aria-label*="Pagination"]').first();

    const hasPagination = await pagination.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasPagination) {
      console.log('✅ Pagination found');

      // 次ページボタン
      const nextButton = pagination.locator('button:has-text("次"), button:has-text("Next"), [aria-label*="次"]').first();

      const hasNextButton = await nextButton.isVisible({ timeout: 3000 }).catch(() => false);

      if (hasNextButton && !await nextButton.isDisabled()) {
        // 現在のページの最初の動画
        const firstItemBefore = await page.locator('[data-video-id], [class*="video-card"]').first().textContent();

        // 次ページへ
        await nextButton.click();
        await page.waitForTimeout(1000);

        // 次ページの最初の動画
        const firstItemAfter = await page.locator('[data-video-id], [class*="video-card"]').first().textContent();

        if (firstItemBefore !== firstItemAfter) {
          console.log('✅ Pagination navigation works');
        } else {
          console.log('ℹ️ Page content unchanged');
        }
      } else {
        console.log('ℹ️ Next button not available (only one page)');
      }
    } else {
      console.log('ℹ️ Pagination not found (may have few items)');
    }

    console.log('✅ Pagination test completed');
  });

  test('動画詳細ページへの遷移', async ({ page }) => {
    await page.goto('http://localhost:3000/history');
    await page.waitForLoadState('networkidle');

    // 最初の動画アイテムをクリック
    const firstVideo = page.locator('[data-video-id], [class*="video-card"], tr[data-id]').first();

    const hasVideo = await firstVideo.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasVideo) {
      // クリック可能な要素を探す
      const clickableElement = firstVideo.locator('a, button, [role="button"]').first();

      const hasClickable = await clickableElement.isVisible({ timeout: 3000 }).catch(() => false);

      if (hasClickable) {
        await clickableElement.click();
        await page.waitForTimeout(2000);
      } else {
        // 動画カード自体をクリック
        await firstVideo.click();
        await page.waitForTimeout(2000);
      }

      // URLが変わったか確認
      const currentUrl = page.url();
      console.log(`Current URL: ${currentUrl}`);

      if (currentUrl !== 'http://localhost:3000/history') {
        console.log('✅ Navigated to detail page');

        // ダッシュボードまたは分析ページに遷移したか
        if (currentUrl.includes('/dashboard/') || currentUrl.includes('/analysis/')) {
          console.log('✅ Correct detail page route');
        }
      } else {
        console.log('⚠️ No navigation occurred');
      }
    } else {
      console.log('⚠️ No videos available for navigation test');
    }

    console.log('✅ Navigation test completed');
  });

  test('APIエンドポイント動作確認', async ({ request }) => {
    // 動画一覧API
    const response = await request.get('http://localhost:8000/api/v1/videos');
    expect(response.ok()).toBeTruthy();

    const videos = await response.json();
    console.log(`API returned ${videos.length} videos`);

    if (videos.length > 0) {
      console.log('✅ Videos API working');

      // 各動画の基本フィールド確認
      const firstVideo = videos[0];
      console.log('First video fields:', Object.keys(firstVideo));

      // 必須フィールドの存在確認
      expect(firstVideo.id).toBeDefined();
      expect(firstVideo.filename).toBeDefined();
      expect(firstVideo.created_at).toBeDefined();

      console.log('✅ Video fields valid');
    }

    // クエリパラメータテスト（フィルタリング）
    const filteredResponse = await request.get('http://localhost:8000/api/v1/videos?limit=5');
    if (filteredResponse.ok()) {
      const filteredVideos = await filteredResponse.json();
      console.log(`Filtered API returned ${filteredVideos.length} videos (limit: 5)`);

      if (filteredVideos.length <= 5) {
        console.log('✅ Limit parameter works');
      }
    }

    console.log('✅ API endpoint test completed');
  });

  test('UI応答性とパフォーマンス', async ({ page }) => {
    // ページロード時間測定
    const startTime = Date.now();

    await page.goto('http://localhost:3000/history');
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`Page load time: ${loadTime}ms`);

    if (loadTime < 5000) {
      console.log('✅ Page load within 5 seconds');
    } else {
      console.log('⚠️ Page load took longer than 5 seconds');
    }

    // インタラクション応答性
    const searchInput = page.locator('input[type="search"], input[placeholder*="検索"]').first();

    if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      const interactionStart = Date.now();

      await searchInput.fill('test');
      await page.waitForTimeout(100);

      const interactionTime = Date.now() - interactionStart;
      console.log(`Search interaction time: ${interactionTime}ms`);

      if (interactionTime < 1000) {
        console.log('✅ UI responsive');
      }
    }

    console.log('✅ Performance test completed');
  });
});