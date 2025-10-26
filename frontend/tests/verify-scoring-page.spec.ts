import { test, expect } from '@playwright/test'

test('スコアリングページで基準モデルが表示されることを確認', async ({ page }) => {
  // スコアリングページに移動
  await page.goto('http://localhost:3000/scoring', { waitUntil: 'networkidle' })

  // ページタイトルが表示されていることを確認
  await expect(page.locator('h1:has-text("採点モード")')).toBeVisible()

  // 基準モデル選択セクションが表示されていることを確認
  await expect(page.locator('h2:has-text("比較元モデル選択")')).toBeVisible()

  // セレクトボックスが表示されていることを確認
  const selectBox = page.locator('select').first()
  await expect(selectBox).toBeVisible()

  // セレクトボックスのオプションを取得
  const options = await selectBox.locator('option').allTextContents()

  console.log('=== 基準モデル一覧 ===')
  console.log(`合計: ${options.length}件`)
  options.forEach((option, index) => {
    console.log(`  ${index}: ${option}`)
  })

  // 最初のオプションは「ライブラリから選択してください」であることを確認
  expect(options[0]).toContain('ライブラリから選択してください')

  // 基準モデルが1つ以上存在することを確認（プレースホルダー除く）
  expect(options.length).toBeGreaterThan(1)

  // スクリーンショットを撮影
  await page.screenshot({
    path: 'test-results/scoring-page-verification.png',
    fullPage: true
  })

  console.log('\n✅ 基準モデルが正常に表示されています')
})
