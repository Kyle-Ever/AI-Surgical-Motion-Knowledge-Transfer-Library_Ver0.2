/**
 * リアルタイムバーテスト
 * 3つのパラメータ（速度・滑らかさ・正確性）がビデオ再生に合わせて動くことを確認
 */

import { test, expect } from '@playwright/test'

test.describe('リアルタイムバー表示テスト', () => {
  test.beforeEach(async ({ page }) => {
    // ダッシュボードページに移動
    await page.goto('http://localhost:3000/dashboard/b7ca3c81-148b-4339-884a-6e96aac2bcd0')
    await page.waitForLoadState('networkidle')
  })

  test('3つのバーが表示される', async ({ page }) => {
    // 「手技の動き」セクションを確認
    const section = page.locator('text=手技の動き').locator('..')
    await expect(section).toBeVisible()

    // 3つのバーラベルを確認
    await expect(section.locator('text=速度')).toBeVisible()
    await expect(section.locator('text=滑らかさ')).toBeVisible()
    await expect(section.locator('text=正確性')).toBeVisible()

    // プログレスバーが表示されていることを確認
    const progressBars = section.locator('.bg-gray-200.rounded-full')
    await expect(progressBars).toHaveCount(3)
  })

  test('バーの初期値が表示される', async ({ page }) => {
    // 初期値（数値）が表示されることを確認
    const section = page.locator('text=手技の動き').locator('..')

    // 各パラメータの数値が表示される（0以上100以下）
    const speedValue = section.locator('text=速度').locator('..').locator('.text-lg.font-bold')
    const smoothnessValue = section.locator('text=滑らかさ').locator('..').locator('.text-lg.font-bold')
    const accuracyValue = section.locator('text=正確性').locator('..').locator('.text-lg.font-bold')

    await expect(speedValue).toBeVisible()
    await expect(smoothnessValue).toBeVisible()
    await expect(accuracyValue).toBeVisible()

    // 初期値は0または実際の値が入る
    const speedText = await speedValue.textContent()
    console.log('[TEST] Initial speed:', speedText)
  })

  test('ビデオ再生時にバーが動く', async ({ page }) => {
    // ページロード完了を待つ
    await page.waitForTimeout(2000)

    // 初期値を記録（数値を取得）
    const section = page.locator('text=手技の動き').locator('..')
    const speedValue = section.locator('text=速度').locator('..').locator('.text-lg.font-bold')
    const smoothnessValue = section.locator('text=滑らかさ').locator('..').locator('.text-lg.font-bold')
    const accuracyValue = section.locator('text=正確性').locator('..').locator('.text-lg.font-bold')

    const initialSpeed = parseFloat(await speedValue.textContent() || '0')
    const initialSmoothness = parseFloat(await smoothnessValue.textContent() || '0')
    const initialAccuracy = parseFloat(await accuracyValue.textContent() || '0')

    console.log('[TEST] Initial values:', {
      speed: initialSpeed,
      smoothness: initialSmoothness,
      accuracy: initialAccuracy
    })

    // 再生ボタンをクリック（ビデオプレイヤーのplayボタン）
    const videoPlayer = page.locator('video')
    await expect(videoPlayer).toBeVisible()

    // ビデオを再生
    await page.click('button[aria-label="Play"]').catch(() => {
      // Play button may not exist, try alternative method
      return videoPlayer.evaluate(video => {
        const v = video as HTMLVideoElement
        if (v.paused) v.play()
      })
    })

    // 2秒待ってバーの変化を確認
    await page.waitForTimeout(2000)

    const newSpeed = parseFloat(await speedValue.textContent() || '0')
    const newSmoothness = parseFloat(await smoothnessValue.textContent() || '0')
    const newAccuracy = parseFloat(await accuracyValue.textContent() || '0')

    console.log('[TEST] New values:', {
      speed: newSpeed,
      smoothness: newSmoothness,
      accuracy: newAccuracy
    })

    // 少なくとも1つのバーが変化していることを確認
    const hasChanged =
      newSpeed !== initialSpeed ||
      newSmoothness !== initialSmoothness ||
      newAccuracy !== initialAccuracy

    expect(hasChanged).toBe(true)
  })

  test('滑らかさが100で固定されていない', async ({ page }) => {
    // ページロード完了を待つ
    await page.waitForTimeout(2000)

    // 滑らかさの値を取得
    const section = page.locator('text=手技の動き').locator('..')
    const smoothnessValue = section.locator('text=滑らかさ').locator('..').locator('.text-lg.font-bold')

    const smoothnessText = await smoothnessValue.textContent()
    const smoothnessNumber = parseFloat(smoothnessText || '0')

    console.log('[TEST] Smoothness value:', smoothnessNumber)

    // ビデオを再生
    const videoPlayer = page.locator('video')
    await page.click('button[aria-label="Play"]').catch(() => {
      return videoPlayer.evaluate(video => {
        const v = video as HTMLVideoElement
        if (v.paused) v.play()
      })
    })

    // 3秒再生
    await page.waitForTimeout(3000)

    // 滑らかさの値を再取得
    const newSmoothnessText = await smoothnessValue.textContent()
    const newSmoothnessNumber = parseFloat(newSmoothnessText || '0')

    console.log('[TEST] New smoothness value:', newSmoothnessNumber)

    // 滑らかさが100で固定されていないことを確認
    // （実際の手技の動きによって変動するはず）
    // 少なくとも初期値と再生後の値が異なるか、100ではないことを確認
    const isNotFixed = newSmoothnessNumber !== 100.0 || newSmoothnessNumber !== smoothnessNumber

    expect(isNotFixed).toBe(true)
  })

  test('コンソールログに正しいデータが出力される', async ({ page }) => {
    const consoleLogs: string[] = []

    page.on('console', msg => {
      const text = msg.text()
      if (text.includes('[REALTIME]')) {
        consoleLogs.push(text)
        console.log('[TEST]', text)
      }
    })

    // ページロード
    await page.waitForTimeout(2000)

    // ビデオを再生
    const videoPlayer = page.locator('video')
    await page.click('button[aria-label="Play"]').catch(() => {
      return videoPlayer.evaluate(video => {
        const v = video as HTMLVideoElement
        if (v.paused) v.play()
      })
    })

    // 3秒再生して複数のログを取得
    await page.waitForTimeout(3000)

    // REALTIMEログが少なくとも1つ出力されていることを確認
    expect(consoleLogs.length).toBeGreaterThan(0)

    // ログに "Valid positions:" が含まれることを確認（データが正しく取得されている）
    const hasValidPositions = consoleLogs.some(log => log.includes('Valid positions:'))
    expect(hasValidPositions).toBe(true)
  })
})
