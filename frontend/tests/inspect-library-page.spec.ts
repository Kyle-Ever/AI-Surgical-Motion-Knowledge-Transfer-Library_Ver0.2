import { test, expect } from '@playwright/test'

test('ライブラリページのUI状態を確認', async ({ page }) => {
  // ライブラリページに移動
  await page.goto('http://localhost:3000/library', { waitUntil: 'networkidle' })

  // ページタイトルを確認
  const title = await page.locator('h1').textContent()
  console.log(`ページタイトル: ${title}`)

  // スクリーンショットを撮影
  await page.screenshot({
    path: 'test-results/library-page-full.png',
    fullPage: true
  })

  // ページ内の全要素を確認
  const bodyText = await page.locator('body').textContent()
  console.log(`\nページ内容:\n${bodyText?.substring(0, 500)}...`)

  // エラーメッセージがあるか確認
  const errorMessages = await page.locator('text=/エラー|失敗|Error/i').count()
  console.log(`\nエラーメッセージ数: ${errorMessages}`)

  // ローディング状態か確認
  const loadingElements = await page.locator('text=/読み込み|Loading/i').count()
  console.log(`ローディング表示数: ${loadingElements}`)

  // ライブラリアイテムの数を確認
  const items = await page.locator('.bg-white.rounded-lg.shadow-sm.p-4').count()
  console.log(`\nライブラリアイテム数: ${items}`)
})
