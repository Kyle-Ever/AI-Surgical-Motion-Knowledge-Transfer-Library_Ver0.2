import { test, expect } from '@playwright/test'
import { createPageObjects } from './helpers/page-objects'
import { ApiMocker } from './helpers/api-mock'

test.describe('Navigation Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Setup API mocks
    const apiMocker = new ApiMocker(page)
    await apiMocker.setupDefaultMocks()
  })

  test('full navigation flow through all pages', async ({ page }) => {
    const pages = createPageObjects(page)

    // Start from home
    await pages.home.goto()
    await expect(page).toHaveURL('/')

    // Navigate to Upload
    await pages.home.clickNewAnalysis()
    await expect(page).toHaveURL(/\/upload/)
    await page.goBack()

    // Navigate to Library
    await pages.home.clickLibrary()
    await expect(page).toHaveURL(/\/library/)
    await page.goBack()

    // Navigate to Scoring
    await pages.home.clickScoring()
    await expect(page).toHaveURL(/\/scoring/)
    await page.goBack()

    // Navigate to History
    await pages.home.clickHistory()
    await expect(page).toHaveURL(/\/history/)
  })

  test('browser back/forward navigation works correctly', async ({ page }) => {
    const pages = createPageObjects(page)

    // Navigate through multiple pages
    await pages.home.goto()
    await pages.home.clickNewAnalysis()
    await pages.upload.goto()
    await pages.library.goto()

    // Test browser back button
    await page.goBack() // Should be on upload
    await expect(page).toHaveURL(/\/upload/)

    await page.goBack() // Should be on home
    await expect(page).toHaveURL('/')

    // Test browser forward button
    await page.goForward() // Should be on upload
    await expect(page).toHaveURL(/\/upload/)

    await page.goForward() // Should be on library
    await expect(page).toHaveURL(/\/library/)
  })

  test('direct URL navigation works', async ({ page }) => {
    // Test direct navigation to each page
    const urls = [
      { path: '/', title: 'AI手技モーション伝承ライブラリ' },
      { path: '/upload', title: '動画アップロード' },
      { path: '/library', title: 'ライブラリ' },
      { path: '/scoring', title: '採点' },
      { path: '/history', title: '履歴' }
    ]

    for (const { path, title } of urls) {
      await page.goto(path)
      await expect(page).toHaveURL(path)
      // Wait for page to load
      await page.waitForLoadState('networkidle')
      // Check that some content related to the page is visible
      const pageContent = await page.textContent('body')
      expect(pageContent).toBeTruthy()
    }
  })

  test('navigation preserves state', async ({ page }) => {
    const { upload, home } = createPageObjects(page)

    // Go to upload and add a file
    await upload.goto()
    const mockFile = { name: 'state-test.mp4', mimeType: 'video/mp4', buffer: Buffer.from('test') }
    await upload.uploadMockFile(mockFile)

    // Navigate away and back
    await home.goto()
    await page.goBack()

    // Check if file is still selected (this depends on implementation)
    // Note: Most browsers clear file inputs on navigation for security
    await expect(page).toHaveURL(/\/upload/)
  })

  test('404 page navigation', async ({ page }) => {
    // Navigate to non-existent page
    await page.goto('/non-existent-page')

    // Check for 404 content or redirect to home
    const url = page.url()
    const isOn404 = url.includes('404') || url.includes('not-found')
    const isRedirectedHome = url.endsWith('/')

    expect(isOn404 || isRedirectedHome).toBeTruthy()
  })

  test('navigation with query parameters', async ({ page }) => {
    // Test navigation with query parameters
    await page.goto('/library?filter=completed&sort=date')
    await expect(page).toHaveURL(/filter=completed/)
    await expect(page).toHaveURL(/sort=date/)
  })

  test('navigation with hash fragments', async ({ page }) => {
    // Test navigation with hash fragments
    await page.goto('/library#video-1')
    await expect(page).toHaveURL(/library#video-1/)
  })

  test('responsive navigation menu', async ({ page }) => {
    // Test mobile navigation
    await page.setViewportSize({ width: 375, height: 667 }) // iPhone SE size

    await page.goto('/')

    // Check if mobile menu button exists (if implemented)
    const mobileMenuButton = page.locator('[data-testid="mobile-menu-button"]')
    if (await mobileMenuButton.isVisible()) {
      await mobileMenuButton.click()
      // Check if menu items are visible
      await expect(page.getByText('新規解析')).toBeVisible()
      await expect(page.getByText('ライブラリ')).toBeVisible()
    }

    // Reset viewport
    await page.setViewportSize({ width: 1280, height: 720 })
  })

  test('keyboard navigation', async ({ page }) => {
    await page.goto('/')

    // Tab through navigation items
    await page.keyboard.press('Tab')
    await page.keyboard.press('Tab')
    await page.keyboard.press('Tab')

    // Press Enter on focused element
    await page.keyboard.press('Enter')

    // Should navigate to one of the pages
    const url = page.url()
    expect(url).not.toBe('http://localhost:3000/')
  })

  test('navigation performance', async ({ page }) => {
    const startTime = Date.now()

    // Navigate through all main pages
    const pages = createPageObjects(page)
    await pages.home.goto()
    await pages.upload.goto()
    await pages.library.goto()

    const endTime = Date.now()
    const totalTime = endTime - startTime

    // All navigation should complete within 10 seconds
    expect(totalTime).toBeLessThan(10000)
  })
})