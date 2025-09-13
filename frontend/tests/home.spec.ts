import { test, expect } from '@playwright/test';

test.describe('Home Page', () => {
  test('shows title and 4 navigation cards', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('AI手技モーション伝承ライブラリ');

    const cards = page.locator('.grid > a');
    await expect(cards).toHaveCount(4);

    const expectedTitles = ['新規解析', 'ライブラリ', '採点モード', '履歴'];
    for (let i = 0; i < expectedTitles.length; i++) {
      await expect(cards.nth(i).locator('h2')).toContainText(expectedTitles[i]);
    }
  });

  test('navigate to upload page', async ({ page }) => {
    await page.goto('/');
    await page.getByText('新規解析').click();
    await expect(page).toHaveURL(/\/upload/);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('動画アップロード');
  });
});
