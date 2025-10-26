import { test, expect } from '@playwright/test'

test('ライブラリページで基準モデル登録機能を確認', async ({ page }) => {
  // ライブラリページに移動
  await page.goto('http://localhost:3000/library', { waitUntil: 'networkidle' })

  // ページタイトルが表示されていることを確認
  await expect(page.locator('h1:has-text("手技ライブラリ")')).toBeVisible()

  // ライブラリアイテムが表示されるまで待機
  await page.waitForSelector('.bg-white.rounded-lg.shadow-sm.p-4.cursor-pointer', { timeout: 10000 })

  // 最初のライブラリアイテムを取得
  const firstItem = page.locator('.bg-white.rounded-lg.shadow-sm.p-4.cursor-pointer').first()
  await expect(firstItem).toBeVisible()

  // 基準モデル登録ボタン（Awardアイコン）が表示されていることを確認
  const registerButton = firstItem.locator('button[title="基準モデルとして登録"]')
  await expect(registerButton).toBeVisible()

  console.log('✅ 基準モデル登録ボタンが表示されています')

  // ページ全体のスクリーンショット
  await page.screenshot({
    path: 'test-results/library-page-reference-registration.png',
    fullPage: true
  })

  // 基準モデル登録ボタンをクリック
  await registerButton.click()

  // モーダルが表示されることを確認
  await expect(page.locator('h2:has-text("基準モデルとして登録")')).toBeVisible({ timeout: 5000 })

  console.log('✅ 基準モデル登録モーダルが表示されました')

  // モーダルのスクリーンショット
  await page.screenshot({
    path: 'test-results/library-reference-registration-modal.png',
    fullPage: true
  })

  // モデル名入力フィールドが表示されていることを確認
  const modelNameInput = page.locator('input[placeholder*="腹腔鏡手術"]')
  await expect(modelNameInput).toBeVisible()

  // 説明入力フィールドが表示されていることを確認
  const descriptionTextarea = page.locator('textarea[placeholder*="説明を入力"]')
  await expect(descriptionTextarea).toBeVisible()

  // 登録ボタンとキャンセルボタンが表示されていることを確認
  await expect(page.locator('button:has-text("登録")')).toBeVisible()
  await expect(page.locator('button:has-text("キャンセル")')).toBeVisible()

  console.log('✅ モーダルの全要素が正常に表示されています')
})
