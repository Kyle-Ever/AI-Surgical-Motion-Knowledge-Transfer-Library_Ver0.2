import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const NGROK_FRONTEND_URL = 'https://mindmotionai.ngrok-free.dev';

function createTestVideo(filename: string, sizeKB: number = 500): string {
  const outputPath = path.join(process.cwd(), 'test-results', filename);
  const dir = path.dirname(outputPath);
  if (!fs.existsSync(dir)) { fs.mkdirSync(dir, { recursive: true }); }
  const mp4Header = Buffer.from([0x00,0x00,0x00,0x20,0x66,0x74,0x79,0x70,0x69,0x73,0x6F,0x6D,0x00,0x00,0x02,0x00,0x69,0x73,0x6F,0x6D,0x69,0x73,0x6F,0x32,0x6D,0x70,0x34,0x31]);
  const targetSize = sizeKB * 1024;
  const fillSize = targetSize - mp4Header.length;
  const fillData = Buffer.alloc(fillSize, 0x00);
  const videoBuffer = Buffer.concat([mp4Header, fillData]);
  fs.writeFileSync(outputPath, videoBuffer);
  console.log('テスト動画作成:', filename);
  return outputPath;
}

async function skipNgrokWarning(page: any) {
  try {
    await page.waitForTimeout(1000);
    const title = await page.title();
    if (title.includes('ngrok') || title.includes('Visit Site')) {
      const visitButton = page.locator('button:has-text("Visit Site")');
      if (await visitButton.count() > 0) {
        await visitButton.click();
        await page.waitForLoadState('networkidle');
      }
    }
  } catch (e) {}
}

test.describe('ngrok完全ワークフロー', () => {
  test('アップロード→解析→結果表示', async ({ page }) => {
    test.setTimeout(300000);
    console.log('完全ワークフロー開始');
    
    await page.goto(NGROK_FRONTEND_URL + '/upload');
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/wf-01-upload.png', fullPage: true });
    
    const testVideoPath = createTestVideo('wf-test.mp4', 500);
    await page.locator('input[type="file"]').first().setInputFiles(testVideoPath);
    await page.waitForTimeout(2000);
    
    await page.locator('button:has-text("次へ")').first().click();
    await page.waitForTimeout(2000);
    
    const extBtn = page.locator('button').filter({ hasText: '外部カメラ' }).filter({ hasText: '器具なし' });
    await extBtn.first().click();
    await page.waitForTimeout(1000);
    
    await page.locator('button:has-text("次へ")').first().click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/wf-02-settings.png', fullPage: true });
    
    const startBtn = page.locator('button:has-text("解析を開始")');
    await startBtn.first().click();
    console.log('解析開始ボタンクリック');
    await page.waitForTimeout(5000);
    await page.screenshot({ path: 'test-results/wf-03-analyzing.png', fullPage: true });
    
    console.log('解析完了待機中...');
    const startTime = Date.now();
    while (Date.now() - startTime < 240000) {
      const url = page.url();
      if (url.includes('/analysis/') || url.includes('/dashboard/')) {
        console.log('結果ページへリダイレクト:', url);
        break;
      }
      await page.waitForTimeout(3000);
    }
    
    await page.screenshot({ path: 'test-results/wf-04-result.png', fullPage: true });
    console.log('最終URL:', page.url());
    console.log('ワークフロー完了');
  });
});
