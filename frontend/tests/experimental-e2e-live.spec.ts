import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

test.describe('Experimental Backend E2E Test', () => {
  test('Upload video, draw mask, analyze, and get analysis ID', async ({ page }) => {
    // Navigate to frontend
    await page.goto('http://localhost:3000');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Check if we can see the environment badge showing experimental backend
    console.log('Checking for experimental backend indicator...');

    // Go to upload page
    await page.goto('http://localhost:3000/upload');
    await page.waitForLoadState('networkidle');

    // Find a test video
    const testVideoPath = path.join(
      'C:', 'Users', 'ajksk', 'Desktop', 'Dev',
      'AI Surgical Motion Knowledge Transfer Library_Ver0.2',
      'backend_experimental', 'data', 'uploads',
      '5d83bfd5-42dd-40e7-a0a9-c383cecd06b9.mp4'
    );

    console.log('Using test video:', testVideoPath);
    console.log('Video exists:', fs.existsSync(testVideoPath));

    // Upload video
    console.log('Looking for file input...');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testVideoPath);

    console.log('File uploaded, waiting for video info...');
    await page.waitForTimeout(2000); // Wait for video to be processed

    // Select video type: external_with_instruments
    console.log('Selecting video type...');
    const videoTypeSelect = page.locator('select[name="videoType"], #videoType, select').first();
    await videoTypeSelect.selectOption('external_with_instruments');

    console.log('Video type selected, submitting form...');

    // Look for submit button (might be in Japanese)
    const submitButton = page.locator('button[type="submit"]').or(
      page.locator('button:has-text("アップロード")')
    ).or(
      page.locator('button:has-text("送信")')
    ).first();

    await submitButton.click();

    console.log('Upload submitted, waiting for redirect...');
    await page.waitForTimeout(3000);

    // Should redirect to dashboard or mask drawing page
    console.log('Current URL after upload:', page.url());

    // If we're on the mask drawing page, draw a mask
    if (page.url().includes('/mask') || page.url().includes('instrument')) {
      console.log('On mask drawing page, drawing mask...');

      // Wait for canvas to load
      const canvas = page.locator('canvas').first();
      await canvas.waitFor({ state: 'visible' });

      // Draw a simple mask by clicking and dragging
      const box = await canvas.boundingBox();
      if (box) {
        // Draw a rectangular mask in the center
        const centerX = box.x + box.width / 2;
        const centerY = box.y + box.height / 2;
        const size = 50;

        await page.mouse.move(centerX - size, centerY - size);
        await page.mouse.down();
        await page.mouse.move(centerX + size, centerY - size);
        await page.mouse.move(centerX + size, centerY + size);
        await page.mouse.move(centerX - size, centerY + size);
        await page.mouse.move(centerX - size, centerY - size);
        await page.mouse.up();

        console.log('Mask drawn');
      }

      // Look for confirm/start analysis button
      await page.waitForTimeout(1000);
      const confirmButton = page.locator('button:has-text("確認")').or(
        page.locator('button:has-text("解析開始")')
      ).or(
        page.locator('button:has-text("Start")')
      ).or(
        page.locator('button[type="submit"]')
      ).first();

      await confirmButton.click();
      console.log('Analysis started');
    }

    // Wait for redirect to dashboard
    await page.waitForTimeout(3000);
    console.log('Current URL:', page.url());

    // Extract analysis ID from URL
    let analysisId = '';
    const urlMatch = page.url().match(/dashboard\/([a-f0-9-]+)/);
    if (urlMatch) {
      analysisId = urlMatch[1];
      console.log('Found analysis ID in URL:', analysisId);
    }

    // If not in URL, try to get it from the page
    if (!analysisId) {
      // Wait for analysis to start and look for the ID in the page
      await page.waitForTimeout(2000);
      const idElement = page.locator('[data-analysis-id]').or(
        page.locator('text=/[a-f0-9-]{36}/')
      ).first();

      if (await idElement.count() > 0) {
        const idText = await idElement.textContent();
        if (idText) {
          analysisId = idText.trim();
          console.log('Found analysis ID in page:', analysisId);
        }
      }
    }

    // Monitor status
    if (analysisId) {
      console.log('\n=== ANALYSIS STARTED ===');
      console.log('Analysis ID:', analysisId);
      console.log('Dashboard URL:', `http://localhost:3000/dashboard/${analysisId}`);

      // Wait for analysis to complete or timeout after 2 minutes
      const maxWaitTime = 120000; // 2 minutes
      const startTime = Date.now();

      while (Date.now() - startTime < maxWaitTime) {
        // Check for completion indicators
        const completedIndicator = page.locator('text=/完了|completed|Complete/i').first();
        const failedIndicator = page.locator('text=/失敗|failed|Error/i').first();

        if (await completedIndicator.count() > 0) {
          console.log('\n=== ANALYSIS COMPLETED ===');
          break;
        }

        if (await failedIndicator.count() > 0) {
          console.log('\n=== ANALYSIS FAILED ===');
          break;
        }

        // Log progress if available
        const progressElement = page.locator('[data-progress]').or(
          page.locator('text=/%/')
        ).first();

        if (await progressElement.count() > 0) {
          const progressText = await progressElement.textContent();
          console.log('Progress:', progressText);
        }

        await page.waitForTimeout(5000); // Check every 5 seconds
      }

      // Take a screenshot of the final state
      await page.screenshot({
        path: 'experimental-test-result.png',
        fullPage: true
      });
      console.log('Screenshot saved to experimental-test-result.png');

      // Return the analysis ID
      expect(analysisId).toBeTruthy();
      expect(analysisId).toMatch(/[a-f0-9-]{36}/);

      console.log('\n=== TEST COMPLETE ===');
      console.log('Analysis ID:', analysisId);
    } else {
      throw new Error('Could not find analysis ID');
    }
  });
});
