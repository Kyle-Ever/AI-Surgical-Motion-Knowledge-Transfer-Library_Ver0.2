import { test, expect } from '@playwright/test'
import path from 'path'

test.describe('実験版SAM2統合テスト', () => {
  test('動画アップロード→器具選択→解析実行→35%突破確認', async ({ page }) => {
    // テストビデオファイルのパス
    const videoPath = path.join(__dirname, '../../backend/data/uploads/00a2baec-b2f0-4b74-abe1-3305d66f75f9.mp4')

    console.log('=== テスト開始 ===')
    console.log(`使用するビデオ: ${videoPath}`)

    // 1. アップロードページに移動
    await page.goto('http://localhost:3000/upload')
    await page.waitForLoadState('networkidle')

    console.log('1. アップロードページに移動完了')

    // 実験版バッジが表示されているか確認
    const experimentalBadge = page.locator('text=実験版モード')
    await expect(experimentalBadge).toBeVisible()
    console.log('✓ 実験版モード確認')

    // 2. ファイルアップロード
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles(videoPath)
    console.log('2. ファイル選択完了')

    // アップロード完了を待つ（プログレスバーまたは完了メッセージ）
    await page.waitForTimeout(3000)
    console.log('3. アップロード待機完了')

    // 3. 動画タイプ選択（external_with_instruments）
    const videoTypeSelect = page.locator('select[name="video_type"], select').first()
    if (await videoTypeSelect.isVisible()) {
      await videoTypeSelect.selectOption('external_with_instruments')
      console.log('4. 動画タイプ選択: external_with_instruments')
    }

    // 4. 器具選択モードに進む
    const instrumentButton = page.getByText('器具を選択')
    if (await instrumentButton.isVisible()) {
      await instrumentButton.click()
      console.log('5. 器具選択モードに移行')
      await page.waitForTimeout(2000)

      // キャンバス上でクリック（器具の位置）
      const canvas = page.locator('canvas').first()
      await canvas.click({ position: { x: 400, y: 300 } })
      await page.waitForTimeout(500)
      await canvas.click({ position: { x: 410, y: 320 } })
      await page.waitForTimeout(500)
      await canvas.click({ position: { x: 420, y: 340 } })
      console.log('6. 器具選択（3点クリック）完了')

      // 確定ボタン
      const confirmButton = page.getByText('確定')
      if (await confirmButton.isVisible()) {
        await confirmButton.click()
        console.log('7. 器具選択を確定')
        await page.waitForTimeout(1000)
      }
    }

    // 5. 解析開始
    const analyzeButton = page.getByText('解析を開始')
    await expect(analyzeButton).toBeVisible({ timeout: 10000 })
    await analyzeButton.click()
    console.log('8. 解析開始ボタンをクリック')

    // 6. 解析ページに遷移したことを確認
    await page.waitForURL(/\/analysis\//, { timeout: 15000 })
    const currentUrl = page.url()
    console.log(`9. 解析ページに遷移: ${currentUrl}`)

    // 7. 解析進行状況を監視
    console.log('10. 解析進行状況を監視開始...')

    let progress = 0
    let maxProgress = 0
    const startTime = Date.now()
    const maxWaitTime = 120000 // 2分

    while (Date.now() - startTime < maxWaitTime) {
      // プログレスバーまたはステータステキストから進行状況を取得
      const progressElement = page.locator('[data-testid="analysis-progress"], .progress, text=/\\d+%/')

      if (await progressElement.isVisible()) {
        const progressText = await progressElement.textContent()
        const match = progressText?.match(/(\d+)%/)
        if (match) {
          progress = parseInt(match[1])
          if (progress > maxProgress) {
            maxProgress = progress
            console.log(`   進行状況: ${progress}%`)
          }

          // 35%を突破したか確認
          if (progress > 35) {
            console.log(`✅ SUCCESS: 35%を突破しました！現在 ${progress}%`)
            break
          }

          // 100%完了
          if (progress >= 100) {
            console.log(`✅ SUCCESS: 解析が100%完了しました！`)
            break
          }
        }
      }

      // エラーチェック
      const errorElement = page.locator('text=/エラー|Error|失敗|failed/i')
      if (await errorElement.isVisible()) {
        const errorText = await errorElement.textContent()
        console.error(`❌ エラー検出: ${errorText}`)
        break
      }

      await page.waitForTimeout(2000)
    }

    // 最終結果
    console.log('\n=== テスト結果 ===')
    console.log(`最大進行状況: ${maxProgress}%`)
    console.log(`経過時間: ${((Date.now() - startTime) / 1000).toFixed(1)}秒`)

    // アサーション
    expect(maxProgress).toBeGreaterThan(35)

    console.log('\n✅ テスト成功: SAM2 Video APIが正常に動作しています')
  })
})
