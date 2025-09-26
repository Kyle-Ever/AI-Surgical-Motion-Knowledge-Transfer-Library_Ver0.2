import { test, expect } from '@playwright/test';

test.describe('Library Export Functionality', () => {
  test('should export analysis data as CSV', async ({ page }) => {
    // Navigate to library page
    await page.goto('http://localhost:3000/library');

    // Wait for library items to load
    await page.waitForSelector('.border-b.border-gray-200', { timeout: 10000 });

    // Get the first analysis item
    const firstItem = page.locator('.border-b.border-gray-200').first();

    // Click on the first item to go to dashboard
    await firstItem.click();

    // Wait for dashboard to load
    await page.waitForURL(/\/dashboard\/[a-f0-9-]+/, { timeout: 10000 });

    // Look for export button
    const exportButton = page.locator('button:has-text("エクスポート")');

    // Check if export button exists
    const exportButtonExists = await exportButton.count() > 0;
    console.log('Export button exists:', exportButtonExists);

    if (exportButtonExists) {
      // Set up download handler before clicking
      const downloadPromise = page.waitForEvent('download', { timeout: 10000 });

      // Click export button
      await exportButton.click();

      try {
        // Wait for download to start
        const download = await downloadPromise;

        // Get download info
        const filename = download.suggestedFilename();
        console.log('Downloaded file:', filename);

        // Verify filename format
        expect(filename).toMatch(/analysis_[a-f0-9-]+\.csv/);

        // Save the file to check content
        const path = await download.path();
        console.log('Download path:', path);

      } catch (error) {
        console.error('Download failed:', error);

        // Check for any error messages on the page
        const errorMessages = await page.locator('.text-red-500, .text-red-600').allTextContents();
        if (errorMessages.length > 0) {
          console.error('Error messages on page:', errorMessages);
        }

        // Check browser console for errors
        page.on('console', msg => {
          if (msg.type() === 'error') {
            console.error('Browser console error:', msg.text());
          }
        });

        // Take screenshot for debugging
        await page.screenshot({ path: 'export-error.png', fullPage: true });
        throw error;
      }
    } else {
      console.error('Export button not found on dashboard');
      await page.screenshot({ path: 'no-export-button.png', fullPage: true });
      throw new Error('Export button not found');
    }
  });

  test('should handle export API errors gracefully', async ({ page }) => {
    // Test direct API call
    const response = await page.request.get('http://localhost:8000/api/v1/analysis/completed');

    console.log('API Response Status:', response.status());

    if (!response.ok()) {
      const errorText = await response.text();
      console.error('API Error Response:', errorText);
    } else {
      const data = await response.json();
      console.log('API Response Data:', data);

      if (data.length > 0) {
        // Try to export the first analysis
        const analysisId = data[0].id;
        const exportResponse = await page.request.get(
          `http://localhost:8000/api/v1/analysis/${analysisId}/export`
        );

        console.log('Export API Status:', exportResponse.status());

        if (!exportResponse.ok()) {
          const errorText = await exportResponse.text();
          console.error('Export API Error:', errorText);
        } else {
          const contentType = exportResponse.headers()['content-type'];
          console.log('Export Content-Type:', contentType);
          expect(contentType).toContain('text/csv');
        }
      }
    }
  });
});