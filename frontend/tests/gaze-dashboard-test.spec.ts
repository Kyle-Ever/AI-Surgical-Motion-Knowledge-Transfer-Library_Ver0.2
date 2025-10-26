import { test, expect } from '@playwright/test'

test.describe('Gaze Dashboard E2E Test', () => {
  const analysisId = '9f6d853e-b70f-430a-9d44-423f7e26d148'
  const dashboardUrl = `http://localhost:3000/dashboard/${analysisId}`

  test('should load gaze dashboard without errors', async ({ page }) => {
    // Listen for console errors
    const consoleErrors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    // Listen for page errors
    const pageErrors: Error[] = []
    page.on('pageerror', error => {
      pageErrors.push(error)
    })

    // Navigate to dashboard
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Wait for dashboard to load
    await page.waitForSelector('h1:has-text("視線解析ダッシュボード")', { timeout: 10000 })

    // Check for errors
    console.log('Console Errors:', consoleErrors)
    console.log('Page Errors:', pageErrors.map(e => e.message))

    // Take screenshot of current state
    await page.screenshot({ path: 'gaze-dashboard-initial.png', fullPage: true })

    // Report errors
    if (consoleErrors.length > 0 || pageErrors.length > 0) {
      throw new Error(`Dashboard has errors:\nConsole: ${consoleErrors.join('\n')}\nPage: ${pageErrors.map(e => e.message).join('\n')}`)
    }
  })

  test('should display summary statistics', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })
    await page.waitForSelector('h1:has-text("視線解析ダッシュボード")')

    // Check for summary stats
    await expect(page.locator('text=総フレーム数')).toBeVisible()
    await expect(page.locator('text=総固視点数')).toBeVisible()
    await expect(page.locator('text=平均固視点数/フレーム')).toBeVisible()
    await expect(page.locator('text=動画時間')).toBeVisible()
  })

  test('should display video player with overlay canvas', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })
    await page.waitForSelector('h1:has-text("視線解析ダッシュボード")')

    // Check video element
    const video = page.locator('video')
    await expect(video).toBeVisible()

    // Check overlay canvas
    const canvas = page.locator('canvas').first()
    await expect(canvas).toBeVisible()
  })

  test('should display timeline charts', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })
    await page.waitForSelector('h1:has-text("視線解析ダッシュボード")')

    // Check for chart titles
    await expect(page.locator('text=固視点座標の時系列変化')).toBeVisible()
    await expect(page.locator('text=注目度の時系列変化')).toBeVisible()
  })

  test('should display hotspot heatmap', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })
    await page.waitForSelector('h1:has-text("視線解析ダッシュボード")')

    // Check for heatmap section
    await expect(page.locator('text=注目ホットスポットマップ（全フレーム集計）')).toBeVisible()

    // Check heatmap canvas
    const heatmapCanvas = page.locator('canvas').nth(1)
    await expect(heatmapCanvas).toBeVisible()
  })

  test('should have playback controls', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })
    await page.waitForSelector('h1:has-text("視線解析ダッシュボード")')

    // Check for play/pause button
    const playButton = page.locator('button:has-text("再生")')
    await expect(playButton).toBeVisible()

    // Check for range slider
    const slider = page.locator('input[type="range"]')
    await expect(slider).toBeVisible()
  })
})
