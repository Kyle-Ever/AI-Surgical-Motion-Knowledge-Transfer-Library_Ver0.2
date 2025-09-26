import { Page, Route } from '@playwright/test'
import { testData } from './test-data'

export class ApiMocker {
  constructor(private page: Page) {}

  // Setup default mocks for all API endpoints
  async setupDefaultMocks() {
    await this.mockVideosList()
    await this.mockAnalysisCompleted()
    await this.mockHealth()
  }

  // Mock video upload endpoint
  async mockVideoUpload(response?: any) {
    await this.page.route('**/api/v1/videos/upload', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(response || testData.videos.valid)
      })
    })
  }

  // Mock videos list endpoint
  async mockVideosList(videos?: any[]) {
    await this.page.route('**/api/v1/videos', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(videos || [testData.videos.valid])
      })
    })
  }

  // Mock single video endpoint
  async mockVideoDetail(videoId: string, video?: any) {
    await this.page.route(`**/api/v1/videos/${videoId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(video || testData.videos.valid)
      })
    })
  }

  // Mock analysis start endpoint
  async mockAnalysisStart(videoId: string, analysis?: any) {
    await this.page.route(`**/api/v1/analysis/${videoId}/analyze`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(analysis || testData.analysis.pending)
      })
    })
  }

  // Mock analysis status endpoint
  async mockAnalysisStatus(analysisId: string, statusData?: any) {
    await this.page.route(`**/api/v1/analysis/${analysisId}/status`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(statusData || {
          analysis_id: analysisId,
          video_id: 'test-video-1',
          overall_progress: 50,
          steps: testData.analysis.processing.steps,
          estimated_time_remaining: 150
        })
      })
    })
  }

  // Mock analysis result endpoint
  async mockAnalysisResult(analysisId: string, result?: any) {
    await this.page.route(`**/api/v1/analysis/${analysisId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(result || testData.analysis.completed)
      })
    })
  }

  // Mock completed analyses endpoint
  async mockAnalysisCompleted(analyses?: any[]) {
    await this.page.route('**/api/v1/analysis/completed', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(analyses || [testData.analysis.completed])
      })
    })
  }

  // Mock health check endpoint
  async mockHealth() {
    await this.page.route('**/api/v1/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'healthy', version: '0.1.0' })
      })
    })
  }

  // Mock error response
  async mockError(endpoint: string, error: any) {
    await this.page.route(endpoint, async (route) => {
      await route.fulfill({
        status: error.status || 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: error.detail || 'Error occurred' })
      })
    })
  }

  // Mock network failure
  async mockNetworkFailure(endpoint: string) {
    await this.page.route(endpoint, async (route) => {
      await route.abort('failed')
    })
  }

  // Mock slow response
  async mockSlowResponse(endpoint: string, delay: number, response: any) {
    await this.page.route(endpoint, async (route) => {
      await new Promise(resolve => setTimeout(resolve, delay))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(response)
      })
    })
  }

  // Mock progressive status updates
  async mockProgressiveAnalysis(analysisId: string) {
    let progress = 0
    await this.page.route(`**/api/v1/analysis/${analysisId}/status`, async (route) => {
      progress = Math.min(100, progress + 10)

      const steps = [
        'Preprocessing',
        'Video info',
        'Frame extraction',
        'Skeleton detection',
        'Motion analysis',
        'Score calculation',
        'Data saving'
      ]

      const currentStepIndex = Math.floor((progress / 100) * steps.length)

      const stepStatuses = steps.map((step, index) => {
        if (index < currentStepIndex) {
          return { name: step, status: 'completed', progress: 100 }
        } else if (index === currentStepIndex) {
          const stepProgress = ((progress % (100 / steps.length)) / (100 / steps.length)) * 100
          return { name: step, status: 'processing', progress: Math.round(stepProgress) }
        } else {
          return { name: step, status: 'pending' }
        }
      })

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          analysis_id: analysisId,
          video_id: 'test-video-1',
          overall_progress: progress,
          steps: stepStatuses,
          estimated_time_remaining: Math.max(0, 300 - progress * 3)
        })
      })
    })
  }

  // Mock WebSocket connection
  async mockWebSocket() {
    await this.page.addInitScript(() => {
      // Override WebSocket constructor
      (window as any).MockWebSocket = class extends WebSocket {
        constructor(url: string) {
          super(url)

          // Simulate connection after 100ms
          setTimeout(() => {
            this.dispatchEvent(new Event('open'))

            // Send progress updates every second
            let progress = 0
            const interval = setInterval(() => {
              progress += 10
              if (progress <= 100) {
                this.dispatchEvent(new MessageEvent('message', {
                  data: JSON.stringify({
                    type: 'progress',
                    progress,
                    step: `Processing step ${progress / 10}`,
                    message: `Analysis in progress: ${progress}%`
                  })
                }))
              } else {
                clearInterval(interval)
                this.dispatchEvent(new MessageEvent('message', {
                  data: JSON.stringify({
                    type: 'completed',
                    status: 'success',
                    message: 'Analysis completed successfully'
                  })
                }))
              }
            }, 1000)
          }, 100)
        }

        send(data: string) {
          console.log('WebSocket send:', data)
        }

        close() {
          console.log('WebSocket closed')
        }
      }

      // Replace global WebSocket
      window.WebSocket = (window as any).MockWebSocket
    })
  }

  // Clear all mocks
  async clearMocks() {
    await this.page.unroute('**/*')
  }
}