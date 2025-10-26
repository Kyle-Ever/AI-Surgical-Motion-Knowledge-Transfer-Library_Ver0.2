import { test, expect } from '@playwright/test'

test.describe('Gaze Dashboard Split View E2E Test', () => {
  const dashboardUrl = 'http://localhost:3000/dashboard/9f6d853e-b70f-430a-9d44-423f7e26d148'

  test('should load dashboard with split view layout', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Check title
    await expect(page.locator('h1')).toContainText('視線解析ダッシュボード')

    // Check header text for split view
    await expect(page.locator('h2').filter({ hasText: '左: 固視点 / 右: ヒートマップ' })).toBeVisible()

    // Should not have console errors
    expect(consoleErrors).toHaveLength(0)
  })

  test('should display two canvas elements for left and right views', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Check for 2-column grid
    const gridContainer = page.locator('div.grid.grid-cols-2').first()
    await expect(gridContainer).toBeVisible()

    // Check for left canvas caption (unique to canvas, not legend)
    const leftCaption = page.locator('p').filter({ hasText: '固視点の動き' }).first()
    await expect(leftCaption).toBeVisible()

    // Check for right canvas caption
    const rightCaption = page.locator('p').filter({ hasText: '視線ヒートマップ' }).first()
    await expect(rightCaption).toBeVisible()
  })

  test('should display time in seconds format', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Wait for video to load
    await page.waitForTimeout(2000)

    // Check time display format (should be "X.XX秒 / Y.Y秒")
    const timeDisplay = page.locator('text=/\\d+\\.\\d+秒 \\/ \\d+\\.\\d+秒/')
    await expect(timeDisplay).toBeVisible()

    // Should not display frame count format
    const frameCountFormat = page.locator('text=/\\d+ \\/ \\d+フレーム/')
    await expect(frameCountFormat).not.toBeVisible()
  })

  test('should have heatmap time window selector', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Check for time window label
    await expect(page.locator('text=ヒートマップ時間窓:')).toBeVisible()

    // Check for select element with options
    const select = page.locator('select').filter({ hasText: /±\d+秒/ })
    await expect(select).toBeVisible()

    // Should have 4 options (±1s, ±2s, ±3s, ±5s)
    const options = await select.locator('option').count()
    expect(options).toBe(4)

    // Default should be ±2秒
    const selectedValue = await select.inputValue()
    expect(selectedValue).toBe('2')
  })

  test('should change heatmap time window', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    const select = page.locator('select').filter({ hasText: /±\d+秒/ })

    // Change to ±3秒
    await select.selectOption('3')
    await page.waitForTimeout(500)

    // Caption should update
    await expect(page.locator('text=視線ヒートマップ（±3秒）')).toBeVisible()

    // Change to ±1秒
    await select.selectOption('1')
    await page.waitForTimeout(500)

    await expect(page.locator('text=視線ヒートマップ（±1秒）')).toBeVisible()
  })

  test('should have working playback controls with time slider', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Check play button
    const playButton = page.locator('button').filter({ hasText: '再生' })
    await expect(playButton).toBeVisible()

    // Check time slider (should use time, not frame index)
    const slider = page.locator('input[type="range"]')
    await expect(slider).toBeVisible()

    // Slider max should be total duration in seconds (around 22.5)
    const maxValue = await slider.getAttribute('max')
    const max = parseFloat(maxValue || '0')
    expect(max).toBeGreaterThan(20)
    expect(max).toBeLessThan(25)

    // Step should be 0.1 seconds
    const stepValue = await slider.getAttribute('step')
    expect(stepValue).toBe('0.1')
  })

  test('should update time display when seeking', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    await page.waitForTimeout(2000)

    // Get initial time
    const timeDisplay = page.locator('span').filter({ hasText: /秒 \/ / }).first()
    const initialText = await timeDisplay.textContent()

    // Seek to middle
    const slider = page.locator('input[type="range"]')
    await slider.fill('10')
    await page.waitForTimeout(1000)

    // Time should have changed
    const newText = await timeDisplay.textContent()
    expect(newText).not.toBe(initialText)
    expect(newText).toMatch(/10\.\d+秒/)
  })

  test('should display current frame stats', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Check for stats grid (in current frame stats section)
    const statsGrid = page.locator('div.grid.grid-cols-4.gap-4').filter({ has: page.locator('text=フレーム時刻') })
    await expect(statsGrid.locator('text=フレーム時刻')).toBeVisible()
    await expect(statsGrid.locator('text=固視点数').last()).toBeVisible()
    await expect(statsGrid.locator('text=平均注目度')).toBeVisible()
    await expect(statsGrid.locator('text=高注目領域比率')).toBeVisible()
  })

  test('should display helpful legend information', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Check for legend section
    await expect(page.locator('text=表示の見方')).toBeVisible()
    await expect(page.locator('text=ヒートマップカラー:')).toBeVisible()

    // Check for left video explanation
    await expect(page.locator('text=左動画（固視点の動き）:')).toBeVisible()
    await expect(page.locator('text=緑色の円')).toBeVisible()

    // Check for right video explanation
    await expect(page.locator('text=右動画（ヒートマップ）:')).toBeVisible()
    await expect(page.locator('text=赤色: 視線が最も集中している領域')).toBeVisible()
  })

  test('should still display timeline charts', async ({ page }) => {
    await page.goto(dashboardUrl, { waitUntil: 'networkidle' })

    // Check for coordinate chart
    await expect(page.locator('h2').filter({ hasText: '固視点座標の時系列変化' })).toBeVisible()

    // Check for attention chart
    await expect(page.locator('h2').filter({ hasText: '注目度の時系列変化' })).toBeVisible()
  })
})
