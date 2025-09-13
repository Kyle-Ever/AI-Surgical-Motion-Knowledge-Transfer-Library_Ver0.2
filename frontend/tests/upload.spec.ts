import { test, expect } from '@playwright/test';

test.describe('Upload Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/upload');
  });

  test('shows upload form and enables Next after file selection', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1 })).toContainText('動画アップロード');

    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();

    await fileInput.setInputFiles({ name: 'test-video.mp4', mimeType: 'video/mp4', buffer: Buffer.from('test') });
    await expect(page.getByText('test-video.mp4')).toBeVisible();

    const nextBtn = page.getByRole('button', { name: '次へ' });
    await expect(nextBtn).toBeEnabled();
  });

  test('type selection step appears and buttons are clickable', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({ name: 'test-video.mp4', mimeType: 'video/mp4', buffer: Buffer.from('x') });
    await page.getByRole('button', { name: '次へ' }).click();
    await expect(page.getByRole('heading', { level: 2 })).toContainText('映像タイプ');
    await page.getByRole('button', { name: '外部（手元カメラ）' }).click();
    await expect(page.getByRole('button', { name: '次へ' })).toBeEnabled();
  });
});
