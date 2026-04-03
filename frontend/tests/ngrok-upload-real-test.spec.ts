import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const NGROK_FRONTEND_URL = 'https://mindmotionai.ngrok-free.dev';

function createTestVideo(filename: string, sizeKB: number = 500): string {
  const outputPath = path.join(process.cwd(), 'test-results', filename);
  const dir = path.dirname(outputPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const mp4Header = Buffer.from([
    0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
    0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
    0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
    0x6D, 0x70, 0x34, 0x31
  ]);
  const targetSize = sizeKB * 1024;
  const fillSize = targetSize - mp4Header.length;
  const fillData = Buffer.alloc(fillSize, 0x00);
  const videoBuffer = Buffer.concat([mp4Header, fillData]);
  fs.writeFileSync(outputPath, videoBuffer);
  console.log(`テスト動画作成: ${filename} (${sizeKB}KB)`);
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

test.describe('ngrok実環境ファイルアップロード', () => {
  test('完全なアップロードフロー', async ({ page }) => {
    test.setTimeout(120000);
    console.log('テスト開始: ngrok環境でのファイルアップロード');
    
    await page.goto(`${NGROK_FRONTEND_URL}/upload`);
    await skipNgrokWarning(page);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/upload-01-initial.png', fullPage: true });
    
    const fileInput = page.locator('input[type="file"]');
    expect(await fileInput.count()).toBeGreaterThan(0);
    
    const testVideoPath = createTestVideo('ngrok-upload-test.mp4', 500);
    await fileInput.first().setInputFiles(testVideoPath);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/upload-02-file-selected.png', fullPage: true });
    
    const nextButton = page.locator('button:has-text("次へ")');
    if (await nextButton.count() > 0) {
      await nextButton.first().click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/upload-03-video-type.png', fullPage: true });
      
      const externalNoInst = page.locator('button').filter({ hasText: '外部カメラ' }).filter({ hasText: '器具なし' }).first();
      if (await externalNoInst.count() > 0) {
        await externalNoInst.click();
        await page.waitForTimeout(1000);
        
        const nextButton2 = page.locator('button:has-text("次へ")');
        if (await nextButton2.count() > 0) {
          await nextButton2.click();
          await page.waitForTimeout(2000);
          await page.screenshot({ path: 'test-results/upload-04-settings.png', fullPage: true });
          
          const uploadBtn = page.locator('button:has-text("アップロード"), button[type="submit"]');
          if (await uploadBtn.count() > 0) {
            console.log('アップロードボタン発見!');
            await uploadBtn.first().screenshot({ path: 'test-results/upload-05-button.png' });
            
            if (!await uploadBtn.first().isDisabled()) {
              await uploadBtn.first().click();
              await page.waitForTimeout(5000);
              await page.screenshot({ path: 'test-results/upload-06-after-click.png', fullPage: true });
              console.log('最終URL:', page.url());
            }
          }
        }
      }
    }
    console.log('テスト完了');
  });
});
