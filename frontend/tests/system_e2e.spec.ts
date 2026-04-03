import { test, expect } from '@playwright/test';
await page.goto('http://localhost:3000');
await expect(page).toHaveTitle(/MindモーションAI/);
await page.screenshot({ path: 'step1_home.png' });
        });

await test.step('2. Navigation to Upload', async () => {
    await page.click('text=アップロード');
    await expect(page).toHaveURL('http://localhost:3000/upload');
    await page.screenshot({ path: 'step2_upload_page.png' });
});

await test.step('3. Video Upload', async () => {
    const testVideoPath = path.join(__dirname, '../../backend_experimental/data/uploads/test_video.mp4');
    const fileInput = page.locator('input[data-testid="file-input"]');
    await fileInput.setInputFiles(testVideoPath);
    await expect(page.locator('text=test_video.mp4')).toBeVisible();
    await page.screenshot({ path: 'step3_file_selected.png' });

    await page.click('button[data-testid="next-button"]');
    await page.screenshot({ path: 'step3_next_clicked.png' });
});

await test.step('4. Video Type Selection', async () => {
    // Wait for buttons to appear
    await page.waitForSelector('button:has-text("外部カメラ")', { timeout: 5000 });
    await page.screenshot({ path: 'step4_type_selection.png' });

    await page.locator('button').filter({ hasText: '外部カメラ' }).filter({ hasText: '器具あり' }).click();
    await page.click('button:has-text("次へ")');
});

await test.step('5. Instrument Selection', async () => {
    await page.waitForSelector('text=使用器具の選択', { timeout: 5000 });
    await page.screenshot({ path: 'step5_instruments.png' });
    await page.click('button:has-text("次へ")');
});

await test.step('6. Annotation/Confirmation', async () => {
    await page.waitForSelector('text=解析設定の確認', { timeout: 5000 });
    await page.screenshot({ path: 'step6_confirmation.png' });
    await page.click('button:has-text("解析を開始")');
    console.log('Analysis started (clicked)');
});

await test.step('7. Monitor Progress', async () => {
    await page.waitForURL(/\/analysis\/.+/, { timeout: 30000 });
    const url = page.url();
    const analysisId = url.split('/').pop();
    console.log(`Analysis ID from URL: ${analysisId}`);

    // Poll for completion
    let isCompleted = false;
    const maxRetries = 30;
    for (let i = 0; i < maxRetries; i++) {
        if (analysisId) {
            const res = await request.get(`http://localhost:8001/api/v1/analysis/${analysisId}`);
            if (res.ok()) {
                const data = await res.json();
                console.log(`Status: ${data.status}`);
                if (data.status === 'completed') {
                    isCompleted = true;
                    break;
                }
                if (data.status === 'failed') {
                    throw new Error(`Analysis failed: ${data.error_message}`);
                }
            }
        }
        await page.waitForTimeout(2000);
    }
    expect(isCompleted).toBeTruthy();
});

await test.step('8. Verify Dashboard', async () => {
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'step8_dashboard.png' });
    await expect(page.locator('text=解析完了')).toBeVisible({ timeout: 10000 });
});
    });
});
