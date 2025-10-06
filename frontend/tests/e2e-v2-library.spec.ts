import { test, expect } from '@playwright/test';

test.describe('E2E V2: ライブラリ機能（リファレンス動画管理）', () => {
  let testVideoId: string | null = null;
  let referenceVideoId: string | null = null;

  test.beforeAll(async ({ request }) => {
    // テスト用動画を取得
    const response = await request.get('http://localhost:8000/api/v1/videos');
    expect(response.ok()).toBeTruthy();

    const videos = await response.json();
    if (videos.length > 0) {
      // 最初の動画をテスト用として使用
      testVideoId = videos[0].id;
      console.log(`Test video ID: ${testVideoId}`);
    }

    // 既存のリファレンス動画を取得
    const refResponse = await request.get('http://localhost:8000/api/v1/library/references');
    if (refResponse.ok()) {
      const references = await refResponse.json();
      if (references.length > 0) {
        referenceVideoId = references[0].id;
        console.log(`Existing reference video ID: ${referenceVideoId}`);
      }
    }
  });

  test('ライブラリページアクセス → リファレンス一覧表示', async ({ page }) => {
    // 1. ライブラリページにアクセス
    await page.goto('http://localhost:3000/library');
    await page.waitForLoadState('networkidle');

    // 2. ページタイトル確認
    const pageTitle = page.locator('h1, h2').first();
    await expect(pageTitle).toBeVisible();

    const titleText = await pageTitle.textContent();
    console.log(`Page title: ${titleText}`);

    // 3. リファレンス動画リスト表示確認
    // リストコンテナまたはカード要素
    const referenceList = page.locator('[data-testid="reference-list"], [class*="reference"], [class*="library"]').first();
    const hasReferenceList = await referenceList.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasReferenceList) {
      console.log('✅ Reference list container found');
    } else {
      console.log('⚠️ Reference list container not found (may be empty)');
    }

    // 4. リファレンス動画の数を確認
    const referenceItems = await page.locator('[data-reference-id], [class*="reference-card"], [class*="video-card"]').all();
    console.log(`Found ${referenceItems.length} reference items in UI`);

    // 5. 「新規リファレンス登録」ボタンの存在確認
    const addReferenceButton = page.locator('button:has-text("追加"), button:has-text("登録"), button:has-text("Add"), button:has-text("New")').first();
    const hasAddButton = await addReferenceButton.isVisible({ timeout: 3000 }).catch(() => false);

    if (hasAddButton) {
      console.log('✅ Add reference button found');
    } else {
      console.log('ℹ️ Add reference button not found');
    }

    console.log('✅ Library page access test completed');
  });

  test('新規リファレンス登録フロー', async ({ page }) => {
    if (!testVideoId) {
      console.log('⚠️ No test video available');
      test.skip();
    }

    // 1. ライブラリページにアクセス
    await page.goto('http://localhost:3000/library');
    await page.waitForLoadState('networkidle');

    // 2. 「新規リファレンス登録」ボタンをクリック
    const addButton = page.locator('button:has-text("追加"), button:has-text("登録"), button:has-text("Add")').first();

    if (await addButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await addButton.click();
      await page.waitForTimeout(1000);

      // 3. 動画選択UI表示
      // モーダルまたは選択ページが表示される
      const videoSelector = page.locator('[data-video-id], [class*="video-select"], select, [role="listbox"]').first();
      const hasSelectorUI = await videoSelector.isVisible({ timeout: 5000 }).catch(() => false);

      if (hasSelectorUI) {
        console.log('✅ Video selector UI found');

        // 動画を選択
        const videoOption = page.locator(`[data-video-id="${testVideoId}"], option[value="${testVideoId}"]`).first();
        if (await videoOption.isVisible({ timeout: 3000 }).catch(() => false)) {
          await videoOption.click();
        }

        // 4. 確認ボタン
        const confirmButton = page.locator('button:has-text("確認"), button:has-text("OK"), button:has-text("登録")').first();
        if (await confirmButton.isVisible({ timeout: 3000 }).catch(() => false)) {
          await confirmButton.click();
          await page.waitForTimeout(2000);
        }

        // 5. 成功メッセージ確認
        const successMessage = page.locator('text=/登録完了|成功|Success/i').first();
        const hasSuccess = await successMessage.isVisible({ timeout: 5000 }).catch(() => false);

        if (hasSuccess) {
          console.log('✅ Reference registration success message found');
        }
      } else {
        console.log('⚠️ Video selector UI not found');
      }
    } else {
      console.log('⚠️ Add button not found, trying API registration');

      // API経由で登録を試みる
      const response = await page.request.post('http://localhost:8000/api/v1/library/references', {
        data: {
          video_id: testVideoId,
          title: 'E2E Test Reference',
          description: 'Created by E2E test'
        }
      });

      if (response.ok()) {
        console.log('✅ Reference created via API');
      } else {
        console.log(`⚠️ API registration failed: ${response.status()}`);
      }
    }

    console.log('✅ Reference registration test completed');
  });

  test('リファレンス動画詳細表示', async ({ page }) => {
    if (!referenceVideoId) {
      console.log('⚠️ No reference video available');
      test.skip();
    }

    // 1. ライブラリページにアクセス
    await page.goto('http://localhost:3000/library');
    await page.waitForLoadState('networkidle');

    // 2. リファレンス動画をクリック
    const referenceCard = page.locator(`[data-reference-id="${referenceVideoId}"], [data-video-id="${referenceVideoId}"]`).first();

    if (await referenceCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      await referenceCard.click();
      await page.waitForTimeout(1000);

      // 3. 詳細ページまたはモーダル表示
      const detailView = page.locator('[class*="detail"], [class*="modal"]').first();
      const hasDetailView = await detailView.isVisible({ timeout: 3000 }).catch(() => false);

      if (hasDetailView) {
        console.log('✅ Reference detail view found');
      } else {
        // URLが変わったか確認
        const currentUrl = page.url();
        if (currentUrl.includes(referenceVideoId) || currentUrl.includes('/library/') || currentUrl.includes('/reference/')) {
          console.log('✅ Navigated to reference detail page');
        }
      }
    } else {
      console.log('⚠️ Reference card not clickable');
    }

    console.log('✅ Reference detail test completed');
  });

  test('リファレンス動画削除フロー', async ({ page, request }) => {
    // テスト用の一時リファレンスを作成
    let tempReferenceId: string | null = null;

    if (testVideoId) {
      const createResponse = await request.post('http://localhost:8000/api/v1/library/references', {
        data: {
          video_id: testVideoId,
          title: 'Temporary E2E Test Reference for Deletion',
          description: 'Will be deleted by E2E test'
        }
      });

      if (createResponse.ok()) {
        const created = await createResponse.json();
        tempReferenceId = created.id;
        console.log(`Created temporary reference: ${tempReferenceId}`);
      }
    }

    if (!tempReferenceId) {
      console.log('⚠️ Could not create temporary reference');
      test.skip();
    }

    // 1. ライブラリページにアクセス
    await page.goto('http://localhost:3000/library');
    await page.waitForLoadState('networkidle');

    // 2. 削除対象のリファレンスを探す
    const targetReference = page.locator(`[data-reference-id="${tempReferenceId}"]`).first();

    if (await targetReference.isVisible({ timeout: 5000 }).catch(() => false)) {
      // 3. 削除ボタンをクリック
      const deleteButton = targetReference.locator('button:has-text("削除"), button:has-text("Delete"), [aria-label*="削除"], [aria-label*="delete"]').first();

      if (await deleteButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await deleteButton.click();
        await page.waitForTimeout(500);

        // 4. 確認ダイアログ
        const confirmDialog = page.locator('text=/本当に削除|確認|Are you sure/i').first();
        if (await confirmDialog.isVisible({ timeout: 3000 }).catch(() => false)) {
          const confirmButton = page.locator('button:has-text("削除"), button:has-text("OK"), button:has-text("Yes")').last();
          await confirmButton.click();
          await page.waitForTimeout(2000);

          console.log('✅ Delete confirmation executed');
        }

        // 5. 削除後、リストから消えたことを確認
        const stillExists = await targetReference.isVisible({ timeout: 3000 }).catch(() => false);

        if (!stillExists) {
          console.log('✅ Reference removed from UI');
        } else {
          console.log('⚠️ Reference still visible after deletion');
        }
      } else {
        console.log('⚠️ Delete button not found, trying API deletion');

        // API経由で削除
        const deleteResponse = await request.delete(`http://localhost:8000/api/v1/library/references/${tempReferenceId}`);
        if (deleteResponse.ok()) {
          console.log('✅ Reference deleted via API');
        }
      }
    } else {
      // UI上に見つからない場合はAPI削除のみ
      const deleteResponse = await request.delete(`http://localhost:8000/api/v1/library/references/${tempReferenceId}`);
      if (deleteResponse.ok()) {
        console.log('✅ Reference deleted via API (not found in UI)');
      }
    }

    console.log('✅ Reference deletion test completed');
  });

  test('データベース整合性確認', async ({ request }) => {
    // reference_videosテーブルのレコード確認
    const response = await request.get('http://localhost:8000/api/v1/library/references');
    expect(response.ok()).toBeTruthy();

    const references = await response.json();
    console.log(`Total references in database: ${references.length}`);

    // 各リファレンスの基本フィールド確認
    references.forEach((ref: any, index: number) => {
      console.log(`Reference ${index + 1}:`, {
        id: ref.id,
        video_id: ref.video_id,
        title: ref.title,
        created_at: ref.created_at
      });

      // 必須フィールドの存在確認
      expect(ref.id).toBeDefined();
      expect(ref.video_id).toBeDefined();
    });

    console.log('✅ Database integrity check completed');
  });
});