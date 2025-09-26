import { test, expect } from '@playwright/test'

test.describe('Error Handling Tests', () => {
  test.beforeEach(async ({ page }) => {
    // ホームページから開始
    await page.goto('/')
  })

  test('handles network error during video upload', async ({ page, context }) => {
    // ネットワークエラーをシミュレート
    await context.route('**/api/v1/videos/upload', route => {
      route.abort('failed')
    })

    // アップロードページへ遷移
    await page.click('a[href="/upload"]')
    await page.waitForURL('/upload')

    // ファイル選択
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test-video.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('test video content')
    })

    // アップロードボタンをクリック
    await page.click('button:has-text("アップロード")')

    // エラーメッセージを確認
    await expect(page.locator('text=/ネットワークエラー|接続エラー|アップロードに失敗/i')).toBeVisible({
      timeout: 10000
    })
  })

  test('handles invalid file format upload', async ({ page }) => {
    // アップロードページへ遷移
    await page.click('a[href="/upload"]')
    await page.waitForURL('/upload')

    // 無効なファイル形式を選択
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'invalid-file.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('invalid content')
    })

    // エラーメッセージを確認（クライアントサイドバリデーション）
    const errorMessage = page.locator('text=/mp4|動画ファイル|対応していません/i')
    await expect(errorMessage.or(page.locator('.text-red-500'))).toBeVisible()
  })

  test('handles server error (500) during analysis', async ({ page, context }) => {
    // サーバーエラーをシミュレート
    await context.route('**/api/v1/analysis/*/analyze', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Internal server error'
        })
      })
    })

    // アップロードページへ遷移
    await page.click('a[href="/upload"]')
    await page.waitForURL('/upload')

    // ファイル選択とアップロード（モック）
    await context.route('**/api/v1/videos/upload', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'test-video-id',
          filename: 'test.mp4'
        })
      })
    })

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test-video.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('test video content')
    })

    await page.click('button:has-text("アップロード")')

    // 解析開始ボタンを待つ
    const analyzeButton = page.locator('button:has-text("解析開始")')
    await expect(analyzeButton).toBeVisible({ timeout: 10000 })
    await analyzeButton.click()

    // サーバーエラーメッセージを確認
    await expect(page.locator('text=/サーバーエラー|エラーが発生|500/i')).toBeVisible({
      timeout: 10000
    })
  })

  test('handles timeout during long analysis', async ({ page, context }) => {
    // タイムアウトをシミュレート
    await context.route('**/api/v1/analysis/*/status', route => {
      // 遅延レスポンス
      setTimeout(() => {
        route.fulfill({
          status: 408,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: 'Request timeout'
          })
        })
      }, 5000)
    })

    // 解析ページへ直接遷移（既存の解析を想定）
    await page.goto('/analysis/test-id')

    // タイムアウトエラーを確認
    await expect(page.locator('text=/タイムアウト|応答がありません|timeout/i')).toBeVisible({
      timeout: 15000
    })
  })

  test('handles 404 for non-existent analysis', async ({ page, context }) => {
    // 404エラーをシミュレート
    await context.route('**/api/v1/analysis/*/status', route => {
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Analysis not found'
        })
      })
    })

    // 存在しない解析ページへ遷移
    await page.goto('/analysis/non-existent-id')

    // 404エラーメッセージを確認
    await expect(page.locator('text=/見つかりません|存在しません|404/i')).toBeVisible({
      timeout: 10000
    })
  })

  test('handles WebSocket connection failure', async ({ page, context }) => {
    // WebSocket接続をブロック
    await context.route('ws://localhost:8000/ws/**', route => {
      route.abort()
    })

    // モックAPIレスポンス
    await context.route('**/api/v1/analysis/*/status', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          overall_progress: 50,
          current_step: 'processing',
          status: 'processing'
        })
      })
    })

    // 解析ページへ遷移
    await page.goto('/analysis/test-id')

    // WebSocket接続エラーインジケータを確認
    const connectionIndicator = page.locator('text=/接続待機中|オフライン|未接続/i')
    await expect(connectionIndicator).toBeVisible({ timeout: 10000 })
  })

  test('handles file size limit exceeded', async ({ page, context }) => {
    // ファイルサイズエラーをシミュレート
    await context.route('**/api/v1/videos/upload', route => {
      route.fulfill({
        status: 413,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'File size exceeds 2GB limit'
        })
      })
    })

    // アップロードページへ遷移
    await page.click('a[href="/upload"]')
    await page.waitForURL('/upload')

    // ファイル選択
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'large-video.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('test video content')
    })

    // アップロードボタンをクリック
    await page.click('button:has-text("アップロード")')

    // ファイルサイズエラーメッセージを確認
    await expect(page.locator('text=/2GB|ファイルサイズ|大きすぎます/i')).toBeVisible({
      timeout: 10000
    })
  })

  test('handles API rate limiting', async ({ page, context }) => {
    // レート制限エラーをシミュレート
    await context.route('**/api/v1/**', route => {
      route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Too many requests'
        })
      })
    })

    // ライブラリページへ遷移
    await page.click('a[href="/library"]')
    await page.waitForURL('/library')

    // レート制限エラーメッセージを確認
    await expect(page.locator('text=/しばらく待って|リクエストが多すぎます|429/i')).toBeVisible({
      timeout: 10000
    })
  })

  test('handles corrupted video file', async ({ page, context }) => {
    // 破損ファイルエラーをシミュレート
    await context.route('**/api/v1/analysis/*/analyze', route => {
      route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Video file is corrupted or unreadable'
        })
      })
    })

    // アップロード成功をモック
    await context.route('**/api/v1/videos/upload', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'corrupted-video-id',
          filename: 'corrupted.mp4'
        })
      })
    })

    // アップロードページへ遷移
    await page.click('a[href="/upload"]')
    await page.waitForURL('/upload')

    // ファイル選択とアップロード
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'corrupted-video.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('corrupted content')
    })

    await page.click('button:has-text("アップロード")')

    // 解析開始
    const analyzeButton = page.locator('button:has-text("解析開始")')
    await expect(analyzeButton).toBeVisible({ timeout: 10000 })
    await analyzeButton.click()

    // 破損ファイルエラーメッセージを確認
    await expect(page.locator('text=/破損|読み取れません|無効な動画/i')).toBeVisible({
      timeout: 10000
    })
  })

  test('handles session expiration gracefully', async ({ page, context }) => {
    // セッション期限切れをシミュレート
    await context.route('**/api/v1/**', route => {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Session expired'
        })
      })
    })

    // ライブラリページへ遷移
    await page.click('a[href="/library"]')
    await page.waitForURL('/library')

    // セッション期限切れメッセージまたはログインへのリダイレクトを確認
    const sessionError = page.locator('text=/セッション|ログイン|認証/i')
    const loginRedirect = page.url().includes('login')

    if (!loginRedirect) {
      await expect(sessionError).toBeVisible({ timeout: 10000 })
    }
  })
})