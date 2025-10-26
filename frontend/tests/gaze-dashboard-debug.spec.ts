import { test } from '@playwright/test'

test('debug gaze dashboard error', async ({ page }) => {
  const analysisId = '9f6d853e-b70f-430a-9d44-423f7e26d148'
  const dashboardUrl = `http://localhost:3000/dashboard/${analysisId}`

  // Collect all console messages
  page.on('console', msg => {
    console.log(`[BROWSER ${msg.type()}]:`, msg.text())
  })

  // Collect errors
  page.on('pageerror', error => {
    console.log('[PAGE ERROR]:', error.message)
    console.log('[STACK]:', error.stack)
  })

  // Navigate and wait
  console.log('Navigating to:', dashboardUrl)
  const response = await page.goto(dashboardUrl, { waitUntil: 'networkidle', timeout: 30000 })

  console.log('Response status:', response?.status())
  console.log('Response headers:', await response?.allHeaders())

  // Get page content
  const content = await page.content()
  console.log('Page HTML (first 1000 chars):', content.substring(0, 1000))

  // Take screenshot
  await page.screenshot({ path: 'debug-gaze-dashboard.png', fullPage: true })

  // Wait a bit to see what happens
  await page.waitForTimeout(3000)
})
