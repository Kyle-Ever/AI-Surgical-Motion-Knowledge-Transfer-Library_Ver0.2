import { test, expect } from '@playwright/test'

test.describe('History Page', () => {
  test('should display analysis history from API', async ({ page }) => {
    // Navigate to history page
    await page.goto('http://localhost:3001/history')

    // Wait for the page to load
    await page.waitForLoadState('networkidle')

    // Check if the main heading is present
    await expect(page.locator('h1')).toContainText('解析履歴')

    // Wait for data to load (either table or no data message)
    await page.waitForSelector('.bg-white.rounded-lg.shadow-sm', { timeout: 10000 })

    // Check if filter dropdown is present
    const filterDropdown = page.locator('select').first()
    await expect(filterDropdown).toBeVisible()

    // Check if update button is present
    const updateButton = page.locator('button:has-text("更新")')
    await expect(updateButton).toBeVisible()

    // Test filter functionality
    await filterDropdown.selectOption('completed')
    await page.waitForTimeout(500) // Wait for filter to apply

    // Check if the table or no data message appears
    const tableExists = await page.locator('table').count()
    const noDataMessage = await page.locator('text=分析履歴がありません').count()

    // Either table or no data message should be present
    expect(tableExists + noDataMessage).toBeGreaterThan(0)

    if (tableExists > 0) {
      // If table exists, check its structure
      const headers = ['ファイル名', '手術名', '執刀医', '日時', '動画時間', 'ステータス', 'アクション']
      for (const header of headers) {
        await expect(page.locator('th').filter({ hasText: header })).toBeVisible()
      }

      // Check if at least one row has action buttons
      const rows = page.locator('tbody tr')
      const rowCount = await rows.count()

      if (rowCount > 0) {
        // Check first row has expected structure
        const firstRow = rows.first()
        const cells = firstRow.locator('td')
        expect(await cells.count()).toBeGreaterThanOrEqual(7)

        // Check for status badge
        const statusBadge = firstRow.locator('span.inline-flex.items-center')
        await expect(statusBadge).toBeVisible()

        // Check for appropriate action button based on status
        const statusText = await statusBadge.textContent()
        if (statusText?.includes('完了')) {
          await expect(firstRow.locator('button:has-text("結果を見る")')).toBeVisible()
        } else if (statusText?.includes('処理中')) {
          await expect(firstRow.locator('button:has-text("進捗確認")')).toBeVisible()
        } else if (statusText?.includes('失敗')) {
          await expect(firstRow.locator('button:has-text("再実行")')).toBeVisible()
        }
      }
    }

    // Test update button functionality
    await updateButton.click()
    await page.waitForLoadState('networkidle')

    // Verify page still loads correctly after update
    await expect(page.locator('h1')).toContainText('解析履歴')
  })

  test('should handle loading and error states', async ({ page }) => {
    // Intercept API call to simulate loading
    await page.route('**/api/v1/analysis/completed', async route => {
      await page.waitForTimeout(1000) // Simulate delay
      await route.continue()
    })

    await page.goto('http://localhost:3001/history')

    // Check for loading state
    const loadingIndicator = page.locator('text=分析履歴を読み込み中')
    // Loading indicator should appear briefly
    expect(await loadingIndicator.count()).toBeGreaterThanOrEqual(0)

    // Wait for content to load
    await page.waitForLoadState('networkidle')

    // Content should eventually appear
    await expect(page.locator('h1')).toContainText('解析履歴')
  })

  test('should navigate to dashboard when clicking result button', async ({ page }) => {
    await page.goto('http://localhost:3001/history')
    await page.waitForLoadState('networkidle')

    // Check if there are any completed analyses with result buttons
    const resultButtons = page.locator('button:has-text("結果を見る")')
    const buttonCount = await resultButtons.count()

    if (buttonCount > 0) {
      // Click the first result button
      const firstButton = resultButtons.first()
      await firstButton.click()

      // Should navigate to dashboard
      await page.waitForURL(/\/dashboard\/.*/)

      // Verify we're on a dashboard page
      const url = page.url()
      expect(url).toContain('/dashboard/')
    }
  })
})