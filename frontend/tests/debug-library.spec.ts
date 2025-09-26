import { test, expect } from '@playwright/test'

test('library page loads and fetches data', async ({ page }) => {
  // コンソールログを監視
  page.on('console', msg => {
    console.log('Browser console:', msg.type(), msg.text())
  })

  // ネットワークエラーを監視
  page.on('requestfailed', request => {
    console.log('Request failed:', request.url(), request.failure()?.errorText)
  })

  // APIレスポンスを監視
  page.on('response', response => {
    if (response.url().includes('/api/')) {
      console.log('API Response:', response.url(), response.status())
    }
  })

  // ライブラリページへ移動
  await page.goto('http://localhost:3000/library')

  // ページ読み込みを待つ
  await page.waitForLoadState('networkidle')

  // タイトルの確認
  const title = page.locator('h1')
  await expect(title).toContainText('ライブラリ')

  // データ取得を少し待つ
  await page.waitForTimeout(3000)

  // テーブルまたはリストの存在を確認
  const listItems = page.locator('[data-testid^="library-item-"]')
  const itemCount = await listItems.count()

  console.log(`Found ${itemCount} library items`)

  // 少なくとも1つのアイテムがあることを期待
  if (itemCount === 0) {
    // エラーメッセージやローディング状態を確認
    const errorMessage = page.locator('text=/エラー|失敗|見つかりません/')
    const hasError = await errorMessage.isVisible().catch(() => false)

    const loadingMessage = page.locator('text=/読み込み中|Loading/')
    const isLoading = await loadingMessage.isVisible().catch(() => false)

    console.log('Has error:', hasError)
    console.log('Is loading:', isLoading)

    // 空の状態メッセージを確認
    const emptyMessage = page.locator('text=/データがありません|解析結果がありません/')
    const isEmpty = await emptyMessage.isVisible().catch(() => false)
    console.log('Is empty:', isEmpty)
  }

  // スクリーンショットを撮る
  await page.screenshot({ path: 'library-debug.png', fullPage: true })
})