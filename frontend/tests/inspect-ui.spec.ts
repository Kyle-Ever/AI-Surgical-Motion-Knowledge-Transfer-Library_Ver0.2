import { test, expect } from '@playwright/test'

/**
 * UI要素の調査用スクリプト
 * ホームページのボタンやリンクを確認
 */

test('ホームページUI調査', async ({ page }) => {
  // ngrok URLにアクセス
  await page.goto('https://mindmotionai.ngrok-free.dev', { waitUntil: 'networkidle' })

  // スクリーンショット撮影
  await page.screenshot({ path: 'test-results/home-page.png', fullPage: true })

  // すべてのボタンを取得
  const buttons = await page.locator('button').all()
  console.log(`Found ${buttons.length} buttons`)

  for (let i = 0; i < buttons.length; i++) {
    const text = await buttons[i].textContent()
    const visible = await buttons[i].isVisible()
    console.log(`Button ${i}: "${text}" (visible: ${visible})`)
  }

  // すべてのリンクを取得
  const links = await page.locator('a').all()
  console.log(`\nFound ${links.length} links`)

  for (let i = 0; i < links.length; i++) {
    const text = await links[i].textContent()
    const href = await links[i].getAttribute('href')
    const visible = await links[i].isVisible()
    console.log(`Link ${i}: "${text}" href="${href}" (visible: ${visible})`)
  }

  // HTML全体を出力
  const html = await page.content()
  console.log('\n=== HTML Content ===')
  console.log(html.substring(0, 2000)) // 最初の2000文字
})
