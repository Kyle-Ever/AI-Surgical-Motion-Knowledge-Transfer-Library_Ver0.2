import { test, expect } from '@playwright/test'

const NGROK_URL = 'https://attestable-emily-reservedly.ngrok-free.dev'

test.describe('ngrok URL動作確認', () => {
  test('ホームページが表示される', async ({ page }) => {
    // ngrok URLにアクセス
    await page.goto(NGROK_URL)

    // ngrokの警告画面が出る場合は「Visit Site」をクリック
    const visitButton = page.locator('button:has-text("Visit Site")')
    if (await visitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await visitButton.click()
      await page.waitForLoadState('networkidle')
    }

    // タイトルを確認
    await expect(page).toHaveTitle(/MindモーションAI/)

    // ホームページのタイトルが表示されることを確認
    const homeTitle = page.locator('[data-testid="home-title"]')
    await expect(homeTitle).toBeVisible()

    console.log('✅ ホームページが正常に表示されました')
  })

  test('ライブラリページにアクセスできる', async ({ page }) => {
    // ngrok URLにアクセス
    await page.goto(NGROK_URL)

    // ngrokの警告画面をスキップ
    const visitButton = page.locator('button:has-text("Visit Site")')
    if (await visitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await visitButton.click()
      await page.waitForLoadState('networkidle')
    }

    // ライブラリページに移動
    await page.goto(`${NGROK_URL}/library`)
    await page.waitForLoadState('networkidle')

    // ページタイトルを確認
    const pageTitle = page.locator('h1')
    await expect(pageTitle).toContainText(/ライブラリ|解析データ/)

    console.log('✅ ライブラリページが正常に表示されました')
  })

  test('APIプロキシ経由でバックエンドにアクセスできる', async ({ page }) => {
    // コンソールエラーをキャプチャ
    const consoleErrors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    // ネットワークエラーをキャプチャ
    const networkErrors: string[] = []
    page.on('requestfailed', request => {
      networkErrors.push(`${request.url()} - ${request.failure()?.errorText}`)
    })

    // ngrok URLにアクセス
    await page.goto(NGROK_URL)

    // ngrokの警告画面をスキップ
    const visitButton = page.locator('button:has-text("Visit Site")')
    if (await visitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await visitButton.click()
    }

    // ライブラリページに移動してAPIコールを待つ
    await page.goto(`${NGROK_URL}/library`)

    // APIレスポンスを待つ
    await page.waitForTimeout(5000) // データ読み込み待機

    // エラーがないことを確認
    const hasBackendError = consoleErrors.some(err =>
      err.includes('バックエンドに接続できません') ||
      err.includes('Network Error')
    )

    if (hasBackendError) {
      console.log('❌ バックエンド接続エラーが発生しました:')
      consoleErrors.forEach(err => console.log('  -', err))
    }

    if (networkErrors.length > 0) {
      console.log('❌ ネットワークエラーが発生しました:')
      networkErrors.forEach(err => console.log('  -', err))
    }

    // スクリーンショットを撮影
    await page.screenshot({
      path: 'tests/screenshots/ngrok-library-page.png',
      fullPage: true
    })

    // エラーがないことをアサート
    expect(hasBackendError).toBe(false)
    expect(networkErrors.length).toBe(0)

    console.log('✅ APIプロキシ経由でバックエンドに正常にアクセスできました')
  })

  test('動画アップロードページが表示される', async ({ page }) => {
    // ngrok URLにアクセス
    await page.goto(NGROK_URL)

    // ngrokの警告画面をスキップ
    const visitButton = page.locator('button:has-text("Visit Site")')
    if (await visitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await visitButton.click()
    }

    // アップロードページに移動
    await page.goto(`${NGROK_URL}/upload`)
    await page.waitForLoadState('networkidle')

    // ファイル入力が表示されることを確認
    const fileInput = page.locator('input[type="file"]')
    await expect(fileInput).toBeVisible()

    console.log('✅ 動画アップロードページが正常に表示されました')
  })
})
