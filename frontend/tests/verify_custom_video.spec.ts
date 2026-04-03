import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Custom Video Verification: 【正式】手技動画.mp4', () => {
    test.setTimeout(600000); // 10 minutes

    test('Upload and Analyze Custom Video', async ({ page, request }) => {
        // 1. Go to upload page
        await page.goto('http://localhost:3000/upload');
        await page.waitForLoadState('networkidle');

        // 2. Upload video
        // Path: root/data/uploads/【正式】手技動画.mp4
        // Relative to frontend/tests/: ../../data/uploads/【正式】手技動画.mp4
        const videoFilename = '【正式】手技動画.mp4';
        const testVideoPath = path.join(__dirname, '../../data/uploads', videoFilename);

        console.log(`Uploading video from: ${testVideoPath}`);

        const fileInput = page.locator('input[type="file"]');
        await fileInput.setInputFiles(testVideoPath);

        // Select video type
        await page.selectOption('select[name="videoType"]', 'external_with_instruments');

        // Click upload
        await page.click('button:has-text("アップロード")');

        // Wait for upload completion
        await page.waitForSelector('text=アップロード完了', { timeout: 120000 }); // 2 mins for upload

        // Get video ID from response
        const uploadResponse = await page.waitForResponse(
            response => response.url().includes('/api/v1/videos/upload') && response.status() === 200
        );
        const uploadData = await uploadResponse.json();
        const videoId = uploadData.id;
        console.log('Uploaded video ID:', videoId);

        // 3. Go to dashboard and start analysis
        await page.goto(`http://localhost:3000/dashboard/${videoId}`);
        await page.waitForLoadState('networkidle');

        // Click analyze button
        await page.click('button:has-text("解析開始")');
        console.log('Analysis started');

        // 4. Poll API for completion (Bypassing UI WebSocket issues)
        let isCompleted = false;
        let analysisId = '';

        // First, get the analysis ID
        // We can get it by listing analyses or checking the analysis endpoint for the video
        // But the UI might have triggered it. Let's poll the analysis endpoint for the video.
        // The endpoint POST /analysis/{video_id}/analyze returns the analysis object.
        // But we clicked the button, so we didn't capture that response easily unless we waitForResponse.

        try {
            const analyzeResponse = await page.waitForResponse(
                response => response.url().includes('/analyze') && response.status() === 200,
                { timeout: 10000 }
            );
            const analyzeData = await analyzeResponse.json();
            analysisId = analyzeData.id;
            console.log('Analysis ID:', analysisId);
        } catch (e) {
            console.log('Could not capture analyze response, trying to find analysis by video ID...');
            // Fallback: List analyses or query by video? 
            // The backend doesn't have a direct "get analysis by video id" easily exposed in the list without filtering?
            // Actually GET /api/v1/analysis/{analysis_id} requires ID.
            // GET /api/v1/analysis/completed lists completed ones.
            // Let's try to wait a bit and assume it's processing.
        }

        // Polling loop
        const maxRetries = 60; // 60 * 5s = 5 minutes
        for (let i = 0; i < maxRetries; i++) {
            // If we don't have analysisId, we might need to find it. 
            // But let's assume we caught it or we can check the status via the UI text as a fallback?
            // No, UI is unreliable.

            // If we missed the ID, we are kind of stuck unless we query the DB or list endpoint.
            // Let's try to get the latest analysis for this video if possible.
            // For now, rely on capturing the response.

            if (!analysisId) {
                console.log('Waiting for analysis ID...');
                await page.waitForTimeout(2000);
                continue;
            }

            const response = await request.get(`http://localhost:8001/api/v1/analysis/${analysisId}`);
            if (response.ok()) {
                const data = await response.json();
                console.log(`Status (${i + 1}/${maxRetries}): ${data.status}, Progress: ${data.progress || 0}%`);

                if (data.status === 'completed') {
                    isCompleted = true;

                    // Verify Data
                    expect(data.skeleton_data).toBeDefined();
                    expect(data.skeleton_data.length).toBeGreaterThan(0);
                    expect(data.instrument_data).toBeDefined();

                    console.log(`Skeleton frames: ${data.skeleton_data.length}`);
                    console.log(`Instrument frames: ${data.instrument_data ? data.instrument_data.length : 0}`);
                    break;
                } else if (data.status === 'failed') {
                    throw new Error(`Analysis failed: ${data.error_message}`);
                }
            }

            await page.waitForTimeout(5000);
        }

        expect(isCompleted).toBeTruthy();
    });
});
