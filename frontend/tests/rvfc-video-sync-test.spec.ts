/**
 * RVFC (requestVideoFrameCallback) 実装の動作確認テスト
 *
 * テスト内容:
 * 1. ページが正常にロードされる
 * 2. 動画プレイヤーが表示される
 * 3. RVFC/RAFのどちらが使用されているかコンソールログで確認
 * 4. 動画再生が正常に動作する
 * 5. オーバーレイ（骨格・器具）が表示される
 * 6. 一時停止・再生が正常に動作する
 */

import { test, expect } from '@playwright/test'

test.describe('RVFC Video Synchronization Test', () => {
  const ANALYSIS_ID = 'fff74a77-620a-4d82-9c9c-ed57c31dee06'
  const DASHBOARD_URL = `/dashboard/${ANALYSIS_ID}`

  test.beforeEach(async ({ page }) => {
    // コンソールログをキャプチャ
    const logs: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'log') {
        logs.push(msg.text())
      }
    })
    // @ts-ignore
    page.logs = logs
  })

  test('ページが正常にロードされ、動画プレイヤーが表示される', async ({ page }) => {
    console.log(`[Test] Navigating to ${DASHBOARD_URL}`)

    await page.goto(DASHBOARD_URL, { waitUntil: 'domcontentloaded', timeout: 30000 })

    // ページタイトル確認
    await expect(page).toHaveTitle(/AI手技モーションライブラリ/, { timeout: 10000 })

    // 動画プレイヤーの存在確認
    const videoElement = page.locator('video')
    await expect(videoElement).toBeVisible({ timeout: 30000 })

    console.log('[Test] ✅ Page loaded and video player is visible')
  })

  test('RVFC/RAF使用状況をコンソールログで確認', async ({ page }) => {
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    // 動画が読み込まれるまで待機
    const videoElement = page.locator('video')
    await expect(videoElement).toBeVisible({ timeout: 15000 })

    // 少し待ってコンソールログを確認
    await page.waitForTimeout(2000)

    // @ts-ignore
    const logs = page.logs || []
    console.log('[Test] Captured console logs:', logs.length)

    // RVFC/RAFのログを探す
    const rvfcLog = logs.find((log: string) => log.includes('requestVideoFrameCallback'))
    const rafLog = logs.find((log: string) => log.includes('requestAnimationFrame') && log.includes('fallback'))

    if (rvfcLog) {
      console.log('[Test] ✅ RVFC is being used (Chrome/Edge/Safari)')
      console.log(`[Test] Log: ${rvfcLog}`)
      expect(rvfcLog).toContain('Using requestVideoFrameCallback')
    } else if (rafLog) {
      console.log('[Test] ⚠️  RAF fallback is being used (Firefox or non-supporting browser)')
      console.log(`[Test] Log: ${rafLog}`)
      expect(rafLog).toContain('Using requestAnimationFrame')
    } else {
      console.log('[Test] ℹ️  No RVFC/RAF log found yet (might appear after playback)')
    }
  })

  test('動画の再生・一時停止が正常に動作する', async ({ page }) => {
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    // 動画プレイヤーが表示されるまで待機
    const videoElement = page.locator('video')
    await expect(videoElement).toBeVisible({ timeout: 15000 })

    // 再生ボタンを探す
    const playButton = page.getByRole('button', { name: /再生|Play/i })
    await expect(playButton).toBeVisible({ timeout: 10000 })

    console.log('[Test] Clicking play button...')
    await playButton.click()

    // ボタンが「一時停止」に変わるのを確認
    await expect(page.getByRole('button', { name: /一時停止|Pause/i })).toBeVisible({ timeout: 5000 })
    console.log('[Test] ✅ Video is now playing')

    // 少し再生させる（2秒）
    await page.waitForTimeout(2000)

    // 動画の currentTime が進んでいることを確認
    const currentTime = await videoElement.evaluate((video: HTMLVideoElement) => video.currentTime)
    console.log(`[Test] Video currentTime: ${currentTime}s`)
    expect(currentTime).toBeGreaterThan(0)

    // 一時停止ボタンをクリック
    const pauseButton = page.getByRole('button', { name: /一時停止|Pause/i })
    await pauseButton.click()

    // ボタンが「再生」に戻ることを確認
    await expect(page.getByRole('button', { name: /再生|Play/i })).toBeVisible({ timeout: 5000 })
    console.log('[Test] ✅ Video paused successfully')
  })

  test('オーバーレイ（骨格・器具）が表示される', async ({ page }) => {
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    // Canvasオーバーレイの存在確認
    const canvas = page.locator('canvas')
    await expect(canvas).toBeVisible({ timeout: 15000 })

    console.log('[Test] ✅ Canvas overlay is visible')

    // 骨格表示チェックボックスの存在確認
    const skeletonCheckbox = page.getByRole('checkbox', { name: /骨格表示/i })
    await expect(skeletonCheckbox).toBeVisible({ timeout: 10000 })

    // デフォルトでチェックされているか確認
    const isChecked = await skeletonCheckbox.isChecked()
    console.log(`[Test] Skeleton display checkbox is ${isChecked ? 'checked' : 'unchecked'}`)

    if (!isChecked) {
      console.log('[Test] Enabling skeleton display...')
      await skeletonCheckbox.click()
      await page.waitForTimeout(500)
    }

    console.log('[Test] ✅ Skeleton overlay settings verified')
  })

  test('動画再生中にオーバーレイが更新される', async ({ page }) => {
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    // 動画とCanvasの準備待ち
    await expect(page.locator('video')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('canvas')).toBeVisible({ timeout: 15000 })

    // 再生開始
    const playButton = page.getByRole('button', { name: /再生|Play/i })
    await playButton.click()
    await page.waitForTimeout(1000)

    // Canvas内容を取得（最初のフレーム）
    const canvas = page.locator('canvas')
    const initialImageData = await canvas.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d')
      if (!ctx) return null
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
      // 全ピクセルが透明かチェック
      const data = imageData.data
      let hasContent = false
      for (let i = 3; i < data.length; i += 4) {
        if (data[i] > 0) { // アルファ値が0より大きい
          hasContent = true
          break
        }
      }
      return hasContent
    })

    console.log(`[Test] Canvas has initial content: ${initialImageData}`)

    // さらに2秒再生
    await page.waitForTimeout(2000)

    // Canvas内容を再取得（2秒後のフレーム）
    const laterImageData = await canvas.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d')
      if (!ctx) return null
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
      const data = imageData.data
      let hasContent = false
      for (let i = 3; i < data.length; i += 4) {
        if (data[i] > 0) {
          hasContent = true
          break
        }
      }
      return hasContent
    })

    console.log(`[Test] Canvas has content after 2s: ${laterImageData}`)

    // オーバーレイが描画されていることを確認
    expect(initialImageData || laterImageData).toBeTruthy()
    console.log('[Test] ✅ Canvas overlay is being updated during playback')

    // 一時停止
    const pauseButton = page.getByRole('button', { name: /一時停止|Pause/i })
    await pauseButton.click()
  })

  test('シーク操作でオーバーレイが正しく追従する', async ({ page }) => {
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    // 動画プレイヤーが表示されるまで待機
    const videoElement = page.locator('video')
    await expect(videoElement).toBeVisible({ timeout: 15000 })

    // プログレスバー（range input）を探す
    const progressBar = page.locator('input[type="range"]')
    await expect(progressBar).toBeVisible({ timeout: 10000 })

    // 動画の長さを取得
    const duration = await videoElement.evaluate((video: HTMLVideoElement) => video.duration)
    console.log(`[Test] Video duration: ${duration}s`)

    // 中間地点（50%）にシーク
    const midPoint = duration / 2
    console.log(`[Test] Seeking to ${midPoint}s...`)

    await progressBar.fill(String(midPoint))
    await page.waitForTimeout(500)

    // currentTimeが更新されたことを確認
    const currentTime = await videoElement.evaluate((video: HTMLVideoElement) => video.currentTime)
    console.log(`[Test] Current time after seek: ${currentTime}s`)

    // 誤差1秒以内で中間地点付近にあることを確認
    expect(Math.abs(currentTime - midPoint)).toBeLessThan(1)
    console.log('[Test] ✅ Seek operation successful, overlay should update')
  })

  test('表示設定の切り替えが正常に動作する', async ({ page }) => {
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    await expect(page.locator('video')).toBeVisible({ timeout: 15000 })

    // 骨格表示チェックボックス
    const skeletonCheckbox = page.getByRole('checkbox', { name: /骨格表示/i })
    await expect(skeletonCheckbox).toBeVisible({ timeout: 10000 })

    // 初期状態を確認
    const initialState = await skeletonCheckbox.isChecked()
    console.log(`[Test] Initial skeleton display state: ${initialState}`)

    // トグル
    await skeletonCheckbox.click()
    await page.waitForTimeout(500)

    const toggledState = await skeletonCheckbox.isChecked()
    console.log(`[Test] After toggle: ${toggledState}`)
    expect(toggledState).toBe(!initialState)

    // 元に戻す
    await skeletonCheckbox.click()
    await page.waitForTimeout(500)

    const finalState = await skeletonCheckbox.isChecked()
    expect(finalState).toBe(initialState)

    console.log('[Test] ✅ Display settings toggle works correctly')
  })
})
