import { test, expect } from '@playwright/test';

test.describe('Library Page', () => {
  test.beforeEach(async ({ page }) => {
    // APIモックを設定
    await page.route('**/api/v1/videos', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'video-1',
            filename: 'surgery-1.mp4',
            upload_date: '2025-01-13T10:00:00',
            duration: 600,
            status: 'analyzed',
            analysis: {
              id: 'analysis-1',
              status: 'completed',
              created_at: '2025-01-13T10:30:00'
            }
          },
          {
            id: 'video-2',
            filename: 'surgery-2.mp4',
            upload_date: '2025-01-13T11:00:00',
            duration: 450,
            status: 'processing',
            analysis: {
              id: 'analysis-2',
              status: 'processing',
              created_at: '2025-01-13T11:30:00'
            }
          }
        ])
      });
    });

    await page.goto('/library');
  });

  test('should display library title', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('解析結果ライブラリ');
  });

  test('should display video list', async ({ page }) => {
    // 動画リストが表示されるのを待つ
    await page.waitForSelector('[data-testid="video-item"]');

    // 動画アイテムが2つ表示されることを確認
    const videoItems = page.locator('[data-testid="video-item"]');
    await expect(videoItems).toHaveCount(2);

    // 最初の動画の詳細を確認
    const firstVideo = videoItems.first();
    await expect(firstVideo).toContainText('surgery-1.mp4');
    await expect(firstVideo).toContainText('完了');
  });

  test('should filter videos by status', async ({ page }) => {
    // フィルターボタンが存在することを確認
    const filterButton = page.locator('button:has-text("フィルター")');
    await expect(filterButton).toBeVisible();

    // フィルターを開く
    await filterButton.click();

    // 「完了」のみを選択
    await page.click('label:has-text("完了")');

    // フィルターを適用
    await page.click('button:has-text("適用")');

    // 完了した動画のみが表示されることを確認
    const videoItems = page.locator('[data-testid="video-item"]');
    await expect(videoItems).toHaveCount(1);
    await expect(videoItems.first()).toContainText('surgery-1.mp4');
  });

  test('should navigate to analysis page', async ({ page }) => {
    // 動画リストが表示されるのを待つ
    await page.waitForSelector('[data-testid="video-item"]');

    // 最初の動画をクリック
    await page.click('[data-testid="video-item"]:first-child');

    // 解析ページに遷移することを確認
    await expect(page).toHaveURL(/\/analysis\/video-1/);
  });

  test('should delete video', async ({ page }) => {
    // 削除APIのモックを設定
    await page.route('**/api/v1/videos/video-1', async route => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ message: 'Deleted successfully' })
        });
      }
    });

    // 動画リストが表示されるのを待つ
    await page.waitForSelector('[data-testid="video-item"]');

    // 削除ボタンをクリック
    const deleteButton = page.locator('[data-testid="video-item"]:first-child button:has-text("削除")');
    await deleteButton.click();

    // 確認ダイアログが表示されることを確認
    await page.click('button:has-text("削除を確認")');

    // 削除成功メッセージが表示されることを確認
    await expect(page.locator('text=削除しました')).toBeVisible();
  });

  test('should search videos', async ({ page }) => {
    // 検索ボックスに入力
    const searchInput = page.locator('input[placeholder*="検索"]');
    await searchInput.fill('surgery-1');

    // 検索結果が更新されることを確認
    const videoItems = page.locator('[data-testid="video-item"]');
    await expect(videoItems).toHaveCount(1);
    await expect(videoItems.first()).toContainText('surgery-1.mp4');
  });
});