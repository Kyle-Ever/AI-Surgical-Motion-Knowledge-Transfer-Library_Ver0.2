/**
 * Phase 3 E2E: Review Deck v0.3 (めくれるフィードバックカード UI)
 */
import { expect, test, type Page } from '@playwright/test'

async function findAnalysisWithEvents(page: Page): Promise<string> {
  const res = await page.request.get('http://127.0.0.1:8001/api/v1/analysis/completed?limit=50')
  const body = await res.json()
  const list: Array<{ id: string }> = Array.isArray(body) ? body : body.analyses ?? []
  for (const row of list) {
    const r = await page.request.get(`http://127.0.0.1:8001/api/v1/analysis/${row.id}/events`)
    if (!r.ok()) continue
    const ev = await r.json()
    if (ev.has_events && ev.events.length > 0 && ev.thresholds_version?.startsWith('v0.3')) {
      return row.id
    }
  }
  throw new Error('No v0.3 analysis with events found')
}

async function findLegacyAnalysis(page: Page): Promise<string> {
  const res = await page.request.get('http://127.0.0.1:8001/api/v1/analysis/completed?limit=50')
  const body = await res.json()
  const list: Array<{ id: string }> = Array.isArray(body) ? body : body.analyses ?? []
  for (const row of list) {
    const r = await page.request.get(`http://127.0.0.1:8001/api/v1/analysis/${row.id}/events`)
    if (!r.ok()) continue
    const ev = await r.json()
    if (!ev.has_events) return row.id
  }
  throw new Error('No legacy analysis found')
}

test.describe('Review Deck v0.3', () => {
  test('タブ切替と URL 同期 (タブ名がフィードバック)', async ({ page }) => {
    const aid = await findAnalysisWithEvents(page)
    await page.goto(`http://localhost:3000/dashboard/${aid}`)

    await expect(page.getByRole('heading', { name: '解析結果' })).toBeVisible({ timeout: 15000 })

    const dashboardTab = page.getByRole('tab', { name: /ダッシュボード/ })
    const feedbackTab = page.getByRole('tab', { name: /フィードバック/ })
    await expect(dashboardTab).toHaveAttribute('aria-selected', 'true')

    await feedbackTab.click()
    await expect(feedbackTab).toHaveAttribute('aria-selected', 'true')
    await expect(page).toHaveURL(/view=review-deck/)

    await dashboardTab.click()
    await expect(page).not.toHaveURL(/view=review-deck/)
  })

  test('件数上限とカード 3 段 (起きていたこと/どうして気にするか/次に意識すること)', async ({ page }) => {
    const aid = await findAnalysisWithEvents(page)
    await page.goto(`http://localhost:3000/dashboard/${aid}?view=review-deck`)

    await expect(page.getByRole('heading', { name: 'フィードバック' })).toBeVisible({ timeout: 20000 })

    const countText = await page.locator('text=/\\d+ \\/ \\d+ 件/').first().textContent()
    const match = countText!.match(/(\d+) \/ (\d+) 件/)
    const total = parseInt(match![2])
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThanOrEqual(15)

    // 3 段の新見出し
    await expect(page.getByText('起きていたこと')).toBeVisible()
    await expect(page.getByText('どうして気にするか')).toBeVisible()
    await expect(page.getByText('次に意識すること')).toBeVisible()

    // 動画ジャンプボタン
    await expect(page.getByRole('button', { name: /この時刻から動画を再生/ })).toBeVisible()
  })

  test('「前へ」「次へ」でカードをめくれる', async ({ page }) => {
    const aid = await findAnalysisWithEvents(page)
    await page.goto(`http://localhost:3000/dashboard/${aid}?view=review-deck`)
    await expect(page.getByRole('heading', { name: 'フィードバック' })).toBeVisible({ timeout: 20000 })

    const firstId = await page.evaluate(
      (a) => window.sessionStorage.getItem('review-deck-selection:' + a),
      aid
    )

    await page.getByRole('button', { name: /次のフィードバック/ }).first().click()
    await page.waitForTimeout(200)

    const afterNext = await page.evaluate(
      (a) => window.sessionStorage.getItem('review-deck-selection:' + a),
      aid
    )
    expect(afterNext).not.toBe(firstId)

    await page.getByRole('button', { name: /前のフィードバック/ }).first().click()
    await page.waitForTimeout(200)

    const afterPrev = await page.evaluate(
      (a) => window.sessionStorage.getItem('review-deck-selection:' + a),
      aid
    )
    expect(afterPrev).toBe(firstId)
  })

  test('ミニタイムラインのドットクリックでカードが切り替わる', async ({ page }) => {
    const aid = await findAnalysisWithEvents(page)
    await page.goto(`http://localhost:3000/dashboard/${aid}?view=review-deck`)
    await expect(page.getByRole('heading', { name: 'フィードバック' })).toBeVisible({ timeout: 20000 })

    const dots = page.locator('[data-event-id]')
    const count = await dots.count()
    expect(count).toBeGreaterThan(1)

    const secondId = await dots.nth(1).getAttribute('data-event-id')
    await dots.nth(1).click()
    await page.waitForTimeout(200)

    const selected = await page.evaluate(
      (a) => window.sessionStorage.getItem('review-deck-selection:' + a),
      aid
    )
    expect(selected).toBe(secondId)
  })

  test('キーボード ← → でめくれる', async ({ page }) => {
    const aid = await findAnalysisWithEvents(page)
    await page.goto(`http://localhost:3000/dashboard/${aid}?view=review-deck`)
    await expect(page.getByRole('heading', { name: 'フィードバック' })).toBeVisible({ timeout: 20000 })

    const before = await page.evaluate(
      (a) => window.sessionStorage.getItem('review-deck-selection:' + a),
      aid
    )

    await page.keyboard.press('ArrowRight')
    await page.waitForTimeout(200)

    const after = await page.evaluate(
      (a) => window.sessionStorage.getItem('review-deck-selection:' + a),
      aid
    )
    expect(after).not.toBe(before)
  })

  test('旧解析: フォールバック UI (新用語)', async ({ page }) => {
    const legacy = await findLegacyAnalysis(page)
    await page.goto(`http://localhost:3000/dashboard/${legacy}?view=review-deck`)
    await expect(
      page.getByText('この解析にはフィードバックが生成されていません')
    ).toBeVisible({ timeout: 20000 })
  })
})
