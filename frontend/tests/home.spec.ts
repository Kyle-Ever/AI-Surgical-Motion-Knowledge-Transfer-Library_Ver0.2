import { test, expect } from '@playwright/test'
import { createPageObjects } from './helpers/page-objects'
import { ApiMocker } from './helpers/api-mock'

test.describe('Home Page', () => {
  test.beforeEach(async ({ page }) => {
    // Setup API mocks
    const apiMocker = new ApiMocker(page)
    await apiMocker.setupDefaultMocks()
  })

  test('shows title and 4 navigation cards', async ({ page }) => {
    const { home } = createPageObjects(page)
    await home.goto()

    // Check main title
    const title = await home.getMainTitle()
    expect(title).toContain('AI手技モーション伝承ライブラリ')

    // Check navigation cards
    const cardCount = await home.getCardCount()
    expect(cardCount).toBe(4)

    // Verify card titles
    const cards = page.locator('.grid > a')
    const expectedTitles = ['新規解析', 'ライブラリ', '採点モード', '履歴']
    for (let i = 0; i < expectedTitles.length; i++) {
      await expect(cards.nth(i)).toContainText(expectedTitles[i])
    }
  })

  test('navigate to upload page', async ({ page }) => {
    const { home } = createPageObjects(page)
    await home.goto()

    await Promise.all([
      page.waitForURL('**/upload'),
      home.clickNewAnalysis()
    ])

    await expect(page).toHaveURL(/\/upload/)
    await expect(page.locator('main h1')).toContainText('動画アップロード')
  })

  test('navigate to library page', async ({ page }) => {
    const { home } = createPageObjects(page)
    await home.goto()

    await Promise.all([
      page.waitForURL('**/library'),
      home.clickLibrary()
    ])

    await expect(page).toHaveURL(/\/library/)
  })

  test('navigate to scoring page', async ({ page }) => {
    const { home } = createPageObjects(page)
    await home.goto()

    await Promise.all([
      page.waitForURL('**/scoring'),
      home.clickScoring()
    ])

    await expect(page).toHaveURL(/\/scoring/)
  })

  test('navigate to history page', async ({ page }) => {
    const { home } = createPageObjects(page)
    await home.goto()

    await Promise.all([
      page.waitForURL('**/history'),
      home.clickHistory()
    ])

    await expect(page).toHaveURL(/\/history/)
  })
})
