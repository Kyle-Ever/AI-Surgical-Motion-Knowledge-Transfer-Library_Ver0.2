import { test, expect } from '@playwright/test'
import { createPageObjects } from './helpers/page-objects'
import { ApiMocker } from './helpers/api-mock'
import { testData } from './helpers/test-data'

test.describe('Analysis Progress and WebSocket Tests', () => {
  let apiMocker: ApiMocker

  test.beforeEach(async ({ page }) => {
    apiMocker = new ApiMocker(page)
    await apiMocker.setupDefaultMocks()
  })

  test('displays analysis progress with status updates', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'test-analysis-1'

    // Mock progressive status updates
    await apiMocker.mockProgressiveAnalysis(analysisId)

    // Navigate to analysis page
    await pages.analysis.goto(analysisId)

    // Check initial state
    await expect(page.getByText('解析処理中')).toBeVisible()

    // Check progress updates
    let previousProgress = 0
    for (let i = 0; i < 5; i++) {
      await page.waitForTimeout(1000)
      const currentProgress = await pages.analysis.getProgress()
      expect(currentProgress).toBeGreaterThanOrEqual(previousProgress)
      previousProgress = currentProgress
    }

    // Check processing steps
    const steps = [
      'Preprocessing',
      'Video info',
      'Frame extraction',
      'Skeleton detection',
      'Motion analysis',
      'Score calculation',
      'Data saving'
    ]

    for (const step of steps) {
      const stepElement = page.getByText(step)
      await expect(stepElement).toBeVisible()
    }
  })

  test('WebSocket connection and real-time updates', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'ws-test-analysis'

    // Mock WebSocket connection
    await apiMocker.mockWebSocket()

    // Navigate to analysis page
    await pages.analysis.goto(analysisId)

    // Check WebSocket connection indicator
    const isConnected = await pages.analysis.isWebSocketConnected()
    expect(isConnected).toBe(true)

    // Wait for WebSocket messages
    await page.waitForTimeout(2000)

    // Check that progress has been updated via WebSocket
    const progress = await pages.analysis.getProgress()
    expect(progress).toBeGreaterThan(0)
  })

  test('handles analysis completion and redirect', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'completing-analysis'

    // Mock analysis that completes quickly
    let callCount = 0
    await page.route(`**/api/v1/analysis/${analysisId}/status`, async (route) => {
      callCount++
      const progress = Math.min(100, callCount * 25)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          analysis_id: analysisId,
          video_id: 'test-video-1',
          overall_progress: progress,
          steps: testData.analysis.processing.steps,
          estimated_time_remaining: Math.max(0, 300 - progress * 3)
        })
      })
    })

    // Navigate to analysis page
    await pages.analysis.goto(analysisId)

    // Wait for completion
    await pages.analysis.waitForCompletion(10000)

    // Should redirect to dashboard
    await page.waitForURL(/\/dashboard\//, { timeout: 5000 })
    expect(page.url()).toContain('/dashboard/')
  })

  test('displays estimated time remaining', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'time-estimate-analysis'

    // Mock analysis with time estimate
    await apiMocker.mockAnalysisStatus(analysisId, {
      analysis_id: analysisId,
      video_id: 'test-video-1',
      overall_progress: 30,
      steps: testData.analysis.processing.steps,
      estimated_time_remaining: 210 // 3.5 minutes
    })

    await pages.analysis.goto(analysisId)

    // Check estimated time is displayed
    const estimatedTime = await pages.analysis.getEstimatedTimeRemaining()
    expect(estimatedTime).toBeTruthy()
    expect(estimatedTime).toContain('分')
  })

  test('handles failed analysis', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'failed-analysis'

    // Mock failed analysis
    await apiMocker.mockAnalysisStatus(analysisId, {
      analysis_id: analysisId,
      video_id: 'test-video-1',
      status: 'FAILED',
      error_message: 'Video processing failed: Invalid frame format',
      overall_progress: 45,
      steps: [
        { name: 'Preprocessing', status: 'completed', progress: 100 },
        { name: 'Video info', status: 'completed', progress: 100 },
        { name: 'Frame extraction', status: 'failed' },
        { name: 'Skeleton detection', status: 'pending' }
      ]
    })

    await pages.analysis.goto(analysisId)

    // Check error message is displayed
    await expect(page.getByText('失敗')).toBeVisible()
    await expect(page.getByText('Invalid frame format')).toBeVisible()

    // Check failed step is marked
    const failedStep = await pages.analysis.getProcessingStepStatus('Frame extraction')
    expect(failedStep).toBe('failed')
  })

  test('reconnects WebSocket on connection loss', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'reconnect-test'

    // Setup WebSocket with simulated disconnection
    await page.addInitScript(() => {
      let connectionCount = 0
      (window as any).MockWebSocket = class extends WebSocket {
        constructor(url: string) {
          super(url)
          connectionCount++

          setTimeout(() => {
            this.dispatchEvent(new Event('open'))

            // Simulate disconnection after 2 seconds on first connection
            if (connectionCount === 1) {
              setTimeout(() => {
                this.dispatchEvent(new CloseEvent('close'))
              }, 2000)
            }
          }, 100)
        }
      }
      window.WebSocket = (window as any).MockWebSocket
    })

    await pages.analysis.goto(analysisId)

    // Wait for initial connection
    await page.waitForTimeout(500)
    let isConnected = await pages.analysis.isWebSocketConnected()
    expect(isConnected).toBe(true)

    // Wait for disconnection
    await page.waitForTimeout(2500)

    // Wait for reconnection
    await page.waitForTimeout(1000)
    isConnected = await pages.analysis.isWebSocketConnected()
    expect(isConnected).toBe(true)
  })

  test('updates progress bar smoothly', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'smooth-progress'

    // Mock incremental progress updates
    let progress = 0
    await page.route(`**/api/v1/analysis/${analysisId}/status`, async (route) => {
      progress = Math.min(100, progress + 5)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          analysis_id: analysisId,
          video_id: 'test-video-1',
          overall_progress: progress,
          steps: testData.analysis.processing.steps
        })
      })
    })

    await pages.analysis.goto(analysisId)

    // Check progress bar animation
    const progressBar = page.locator('[data-testid="progress-bar"]')
    await expect(progressBar).toBeVisible()

    // Take multiple measurements
    const measurements = []
    for (let i = 0; i < 5; i++) {
      await page.waitForTimeout(500)
      const width = await progressBar.evaluate(el => {
        const computed = window.getComputedStyle(el)
        return parseInt(computed.width)
      })
      measurements.push(width)
    }

    // Check that width is increasing
    for (let i = 1; i < measurements.length; i++) {
      expect(measurements[i]).toBeGreaterThanOrEqual(measurements[i - 1])
    }
  })

  test('displays all processing steps correctly', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'steps-display'

    // Mock with specific step statuses
    await apiMocker.mockAnalysisStatus(analysisId, {
      analysis_id: analysisId,
      video_id: 'test-video-1',
      overall_progress: 60,
      steps: [
        { name: 'Preprocessing', status: 'completed', progress: 100 },
        { name: 'Video info', status: 'completed', progress: 100 },
        { name: 'Frame extraction', status: 'completed', progress: 100 },
        { name: 'Skeleton detection', status: 'processing', progress: 60 },
        { name: 'Motion analysis', status: 'pending' },
        { name: 'Score calculation', status: 'pending' },
        { name: 'Data saving', status: 'pending' }
      ]
    })

    await pages.analysis.goto(analysisId)

    // Check each step status
    const completedSteps = ['Preprocessing', 'Video info', 'Frame extraction']
    for (const step of completedSteps) {
      const status = await pages.analysis.getProcessingStepStatus(step)
      expect(status).toBe('completed')
    }

    const processingStep = await pages.analysis.getProcessingStepStatus('Skeleton detection')
    expect(processingStep).toBe('processing')

    const pendingSteps = ['Motion analysis', 'Score calculation', 'Data saving']
    for (const step of pendingSteps) {
      const status = await pages.analysis.getProcessingStepStatus(step)
      expect(status).toBe('pending')
    }
  })

  test('handles rapid progress updates', async ({ page }) => {
    const pages = createPageObjects(page)
    const analysisId = 'rapid-updates'

    // Mock rapid progress updates
    let progress = 0
    await page.route(`**/api/v1/analysis/${analysisId}/status`, async (route) => {
      progress = Math.min(100, progress + 20)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          analysis_id: analysisId,
          video_id: 'test-video-1',
          overall_progress: progress,
          steps: testData.analysis.processing.steps
        })
      })
    })

    await pages.analysis.goto(analysisId)

    // Trigger multiple rapid updates
    for (let i = 0; i < 5; i++) {
      await page.waitForTimeout(100)
      await page.reload()
    }

    // Page should still be functional
    const finalProgress = await pages.analysis.getProgress()
    expect(finalProgress).toBe(100)
  })
})