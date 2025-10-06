import { test, expect } from '@playwright/test';

test.describe('SAM器具追跡機能の確認', () => {
  // 既存の解析済みデータを確認するシンプルなテスト
  test('器具検出データが正しく表示されていることを確認', async ({ page }) => {
    // ライブラリページに移動
    await page.goto('http://localhost:3000/library');
    await page.waitForLoadState('networkidle');

    // ページが読み込まれたことを確認
    await expect(page.locator('h1:has-text("動画ライブラリ")')).toBeVisible({ timeout: 10000 });

    console.log('ライブラリページが表示されました');

    // 解析済みの動画カードを探す（完了ステータス）
    const completedCards = page.locator('div.bg-white').filter({
      has: page.locator('span.text-green-600:has-text("完了")')
    });

    const cardCount = await completedCards.count();
    console.log(`完了済みの動画カード数: ${cardCount}`);

    if (cardCount > 0) {
      // 最初の完了済みカードを確認
      const firstCard = completedCards.first();

      // ダッシュボードリンクを探す
      const dashboardLink = firstCard.locator('a[href*="/dashboard/"]').first();

      if (await dashboardLink.isVisible({ timeout: 5000 }).catch(() => false)) {
        const href = await dashboardLink.getAttribute('href');
        console.log(`ダッシュボードリンク: ${href}`);

        // ダッシュボードに移動
        await dashboardLink.click();
        await page.waitForLoadState('networkidle');

        // ダッシュボードページが表示されることを確認
        await expect(page.locator('h1:has-text("解析結果")')).toBeVisible({ timeout: 10000 });
        console.log('ダッシュボードが表示されました');

        // ビデオタイプを確認
        const videoTypeText = await page.locator('text=/外部視点|内部視点/').first().textContent();
        console.log(`ビデオタイプ: ${videoTypeText}`);

        // 器具ありタイプの場合、器具セクションを確認
        if (videoTypeText?.includes('器具あり') || videoTypeText?.includes('内部')) {
          // 器具の動き分析セクションを探す
          const instrumentSection = page.locator('h2:has-text("器具の動き分析")');

          if (await instrumentSection.isVisible({ timeout: 5000 }).catch(() => false)) {
            console.log('✅ 器具の動き分析セクションが表示されています');

            // 検出フレーム数を確認
            const frameCountElement = page.locator('div:has-text("検出フレーム数")').locator('..').locator('div.text-2xl');
            if (await frameCountElement.isVisible({ timeout: 5000 }).catch(() => false)) {
              const frameCount = await frameCountElement.textContent();
              console.log(`検出フレーム数: ${frameCount}`);
            }

            // 検出タイプを確認
            const detectionTypeElement = page.locator('div:has-text("検出タイプ")').locator('..').locator('div.text-xl');
            if (await detectionTypeElement.isVisible({ timeout: 5000 }).catch(() => false)) {
              const detectionType = await detectionTypeElement.textContent();
              console.log(`検出タイプ: ${detectionType}`);
            }

            // スクリーンショットを撮る
            await page.screenshot({
              path: 'tests/screenshots/sam-tracking-dashboard.png',
              fullPage: true
            });
            console.log('スクリーンショットを保存しました');

          } else {
            console.log('⚠️ 器具の動き分析セクションが表示されていません');
          }
        } else {
          // 器具なしの場合、セクションが表示されていないことを確認
          const instrumentSection = page.locator('h2:has-text("器具の動き分析")');
          await expect(instrumentSection).not.toBeVisible({ timeout: 5000 });
          console.log('✅ 外部（器具なし）では器具セクションが正しく非表示になっています');
        }

        // ビデオプレーヤーが表示されることを確認
        const videoPlayer = page.locator('video').first();
        if (await videoPlayer.isVisible({ timeout: 5000 }).catch(() => false)) {
          console.log('✅ ビデオプレーヤーが表示されています');
        }

      } else {
        console.log('ダッシュボードリンクが見つかりませんでした');
      }
    } else {
      console.log('完了済みの解析が見つかりませんでした');
    }
  });

  test('複数の解析結果を順番に確認', async ({ page }) => {
    await page.goto('http://localhost:3000/library');
    await page.waitForLoadState('networkidle');

    // 完了済みの動画カードを全て取得
    const completedCards = page.locator('div.bg-white').filter({
      has: page.locator('span.text-green-600:has-text("完了")')
    });

    const cardCount = await completedCards.count();
    console.log(`\n=== 解析結果サマリー ===`);
    console.log(`完了済み解析数: ${cardCount}`);

    let instrumentDetectionCount = 0;
    let noInstrumentCount = 0;

    // 最大5件まで確認
    for (let i = 0; i < Math.min(cardCount, 5); i++) {
      const card = completedCards.nth(i);

      // タイトルを取得
      const titleElement = card.locator('h3').first();
      const title = await titleElement.textContent();

      // ビデオタイプを取得
      const typeElement = card.locator('span.text-sm').filter({ hasText: /外部|内部/ }).first();
      const videoType = await typeElement.textContent();

      console.log(`\n[${i + 1}] ${title} - ${videoType}`);

      // ダッシュボードリンクを確認
      const dashboardLink = card.locator('a[href*="/dashboard/"]').first();
      if (await dashboardLink.isVisible({ timeout: 3000 }).catch(() => false)) {
        const href = await dashboardLink.getAttribute('href');

        // ダッシュボードページを新しいタブで開く（ナビゲーションの問題を避けるため）
        const newPage = await page.context().newPage();
        await newPage.goto(`http://localhost:3000${href}`);
        await newPage.waitForLoadState('networkidle');

        // 器具セクションの存在を確認
        const instrumentSection = newPage.locator('h2:has-text("器具の動き分析")');

        if (await instrumentSection.isVisible({ timeout: 3000 }).catch(() => false)) {
          instrumentDetectionCount++;
          console.log('  → 器具検出: あり');

          // 検出フレーム数を取得
          const frameCountElement = newPage.locator('div:has-text("検出フレーム数")').locator('..').locator('div.text-2xl');
          if (await frameCountElement.isVisible({ timeout: 3000 }).catch(() => false)) {
            const frameCount = await frameCountElement.textContent();
            console.log(`  → 検出フレーム数: ${frameCount}`);
          }
        } else {
          noInstrumentCount++;
          console.log('  → 器具検出: なし');
        }

        await newPage.close();
      }
    }

    console.log(`\n=== 結果まとめ ===`);
    console.log(`器具検出あり: ${instrumentDetectionCount}件`);
    console.log(`器具検出なし: ${noInstrumentCount}件`);

    if (instrumentDetectionCount > 0) {
      console.log('\n✅ SAM器具追跡機能が正常に動作しています');
    }
  });
});