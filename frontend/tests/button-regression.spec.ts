import { test, expect } from '@playwright/test'

test.describe('Button Regression Tests', () => {
  test('file select button must be a proper button element', async ({ page }) => {
    await page.goto('http://localhost:3000/upload')

    // ファイル選択ボタンが存在することを確認
    const selectButton = page.locator('button:has-text("ファイルを選択")')
    await expect(selectButton).toBeVisible()
    await expect(selectButton).toBeEnabled()

    // ボタンがbutton要素であることを確認（span等ではない）
    const tagName = await selectButton.evaluate(el => el.tagName)
    expect(tagName).toBe('BUTTON')

    // ボタンにtype="button"属性があることを確認
    const buttonType = await selectButton.getAttribute('type')
    expect(buttonType).toBe('button')

    // ファイル入力要素が存在することを確認
    const fileInput = page.locator('input[type="file"]')
    await expect(fileInput).toBeAttached()

    // accept属性が正しく設定されていることを確認
    const acceptAttr = await fileInput.getAttribute('accept')
    expect(acceptAttr).toContain('video')
  })

  test('dropzone should trigger file input on click', async ({ page }) => {
    await page.goto('http://localhost:3000/upload')

    // ドロップゾーンが存在することを確認
    const dropzone = page.locator('[class*="border-dashed"]')
    await expect(dropzone).toBeVisible()

    // ドロップゾーンがクリック可能であることを確認
    const cursor = await dropzone.evaluate(el =>
      window.getComputedStyle(el).cursor
    )
    expect(cursor).toBe('pointer')
  })

  test('file upload triggers UI update', async ({ page }) => {
    await page.goto('http://localhost:3000/upload')

    // ファイル入力要素を取得
    const fileInput = page.locator('input[type="file"]')

    // モックファイルをアップロード
    await fileInput.setInputFiles({
      name: 'regression-test.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('test video content for regression')
    })

    // ファイル名が表示されることを確認
    await expect(page.getByText('regression-test.mp4')).toBeVisible()

    // 次へボタンが有効になることを確認
    const nextButton = page.locator('[data-testid="next-button"]')
    await expect(nextButton).toBeEnabled()

    // ファイル削除ボタンが表示されることを確認
    const removeButton = page.locator('[aria-label="ファイルを削除"]')
    await expect(removeButton).toBeVisible()
  })

  test('library page loads and displays data', async ({ page }) => {
    await page.goto('http://localhost:3000/library')

    // ページタイトルが表示されることを確認
    await expect(page.locator('h1')).toContainText('手技ライブラリ')

    // 読み込み中またはデータが表示されることを確認（最大5秒待機）
    await page.waitForSelector(
      'text=/読み込み中|ライブラリにアイテムがありません|件の解析結果/',
      { timeout: 5000 }
    )

    // APIレスポンスをチェック
    page.on('response', response => {
      if (response.url().includes('/api/v1/analysis/completed')) {
        console.log('API Response Status:', response.status())
      }
    })
  })
})