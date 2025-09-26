import { Page, Locator, expect } from '@playwright/test'

// Base Page Object
export class BasePage {
  constructor(protected page: Page) {}

  async navigate(path: string) {
    await this.page.goto(path)
  }

  async waitForPageLoad() {
    await this.page.waitForLoadState('networkidle')
  }

  async getTitle(): Promise<string> {
    return await this.page.title()
  }

  async takeScreenshot(name: string) {
    await this.page.screenshot({ path: `tests/screenshots/${name}.png`, fullPage: true })
  }
}

// Home Page Object
export class HomePage extends BasePage {
  private readonly title = this.page.locator('[data-testid="home-title"]')
  private readonly navigationCards = this.page.locator('[data-testid="navigation-cards"] > a')
  private readonly newAnalysisCard = this.page.locator('[data-testid="nav-card-upload"]')
  private readonly libraryCard = this.page.locator('[data-testid="nav-card-library"]')
  private readonly scoringCard = this.page.locator('[data-testid="nav-card-scoring"]')
  private readonly historyCard = this.page.locator('[data-testid="nav-card-history"]')

  async goto() {
    await this.navigate('/')
  }

  async getMainTitle(): Promise<string> {
    return await this.title.textContent() || ''
  }

  async getCardCount(): Promise<number> {
    return await this.navigationCards.count()
  }

  async clickNewAnalysis() {
    await this.newAnalysisCard.click()
  }

  async clickLibrary() {
    await this.libraryCard.click()
  }

  async clickScoring() {
    await this.scoringCard.click()
  }

  async clickHistory() {
    await this.historyCard.click()
  }
}

// Upload Page Object
export class UploadPage extends BasePage {
  private readonly title = this.page.locator('[data-testid="upload-title"]')
  private readonly fileInput = this.page.locator('[data-testid="file-input"]')
  private readonly dropZone = this.page.locator('[data-testid="drop-zone"]')
  private readonly nextButton = this.page.locator('[data-testid="next-button"]')
  private readonly backButton = this.page.getByRole('button', { name: '戻る' })
  private readonly uploadProgress = this.page.locator('[data-testid="upload-progress"]')
  private readonly errorMessage = this.page.locator('[data-testid="error-message"]')

  // Step 2: Video Type Selection
  private readonly videoTypeTitle = this.page.getByRole('heading', { name: '映像タイプ' })
  private readonly externalCameraButton = this.page.getByRole('button', { name: '外部（手元カメラ）' })
  private readonly internalCameraButton = this.page.getByRole('button', { name: '内視鏡' })

  // Step 3: Metadata
  private readonly surgeryNameInput = this.page.locator('input[name="surgery_name"]')
  private readonly surgeonNameInput = this.page.locator('input[name="surgeon_name"]')
  private readonly surgeryDateInput = this.page.locator('input[name="surgery_date"]')
  private readonly memoTextarea = this.page.locator('textarea[name="memo"]')

  async goto() {
    await this.navigate('/upload')
  }

  async uploadFile(filePath: string) {
    await this.fileInput.setInputFiles(filePath)
  }

  async uploadMockFile(file: { name: string; mimeType: string; buffer: Buffer }) {
    await this.fileInput.setInputFiles(file)
  }

  async dragAndDropFile(filePath: string) {
    // Simulate drag and drop
    const dataTransfer = await this.page.evaluateHandle(() => new DataTransfer())
    await this.dropZone.dispatchEvent('drop', { dataTransfer })
  }

  async clickNext() {
    await this.nextButton.click()
  }

  async clickBack() {
    await this.backButton.click()
  }

  async selectExternalCamera() {
    await this.externalCameraButton.click()
  }

  async selectInternalCamera() {
    await this.internalCameraButton.click()
  }

  async fillMetadata(data: {
    surgeryName?: string
    surgeonName?: string
    surgeryDate?: string
    memo?: string
  }) {
    if (data.surgeryName) await this.surgeryNameInput.fill(data.surgeryName)
    if (data.surgeonName) await this.surgeonNameInput.fill(data.surgeonName)
    if (data.surgeryDate) await this.surgeryDateInput.fill(data.surgeryDate)
    if (data.memo) await this.memoTextarea.fill(data.memo)
  }

  async isNextButtonEnabled(): Promise<boolean> {
    return await this.nextButton.isEnabled()
  }

  async getErrorMessage(): Promise<string | null> {
    if (await this.errorMessage.isVisible()) {
      return await this.errorMessage.textContent()
    }
    return null
  }

  async waitForUploadComplete() {
    await this.page.waitForSelector('[data-testid="upload-complete"]', { timeout: 30000 })
  }
}

// Library Page Object
export class LibraryPage extends BasePage {
  private readonly title = this.page.locator('h1')
  private readonly searchInput = this.page.locator('input[placeholder*="検索"]')
  private readonly filterButton = this.page.getByRole('button', { name: 'フィルター' })
  private readonly videoItems = this.page.locator('[data-testid="video-item"]')
  private readonly loadingSpinner = this.page.locator('[data-testid="loading"]')
  private readonly emptyState = this.page.locator('[data-testid="empty-state"]')
  private readonly errorState = this.page.locator('[data-testid="error-state"]')

  async goto() {
    await this.navigate('/library')
  }

  async search(query: string) {
    await this.searchInput.fill(query)
    await this.page.keyboard.press('Enter')
  }

  async openFilter() {
    await this.filterButton.click()
  }

  async getVideoCount(): Promise<number> {
    return await this.videoItems.count()
  }

  async clickVideoItem(index: number) {
    await this.videoItems.nth(index).click()
  }

  async deleteVideo(index: number) {
    const deleteButton = this.videoItems.nth(index).locator('button:has-text("削除")')
    await deleteButton.click()
    await this.page.getByRole('button', { name: '削除を確認' }).click()
  }

  async waitForVideosToLoad() {
    await this.loadingSpinner.waitFor({ state: 'hidden' })
  }

  async isEmptyStateVisible(): Promise<boolean> {
    return await this.emptyState.isVisible()
  }

  async isErrorStateVisible(): Promise<boolean> {
    return await this.errorState.isVisible()
  }
}

// Analysis Page Object
export class AnalysisPage extends BasePage {
  private readonly title = this.page.locator('[data-testid="analysis-title"]')
  private readonly progressBar = this.page.locator('[data-testid="progress-bar"]')
  private readonly progressPercentage = this.page.locator('[data-testid="progress-percentage"]')
  private readonly processingSteps = this.page.locator('[data-testid="processing-step"]')
  private readonly estimatedTime = this.page.locator('[data-testid="estimated-time"]')
  private readonly wsConnectionStatus = this.page.locator('[data-testid="ws-connection-indicator"]')
  private readonly errorMessage = this.page.locator('[data-testid="error-message"]')

  async goto(analysisId: string) {
    await this.navigate(`/analysis/${analysisId}`)
  }

  async getProgress(): Promise<number> {
    const text = await this.progressPercentage.textContent()
    const match = text?.match(/(\d+)%/)
    return match ? parseInt(match[1]) : 0
  }

  async getProcessingStepStatus(stepName: string): Promise<string> {
    const step = this.page.locator(`[data-testid="processing-step"]:has-text("${stepName}")`)
    const statusIcon = step.locator('[data-testid="step-status"]')
    return await statusIcon.getAttribute('data-status') || 'pending'
  }

  async waitForCompletion(timeout: number = 60000) {
    await this.page.waitForFunction(
      () => {
        const progressEl = document.querySelector('[data-testid="progress-percentage"]')
        return progressEl?.textContent?.includes('100%')
      },
      { timeout }
    )
  }

  async isWebSocketConnected(): Promise<boolean> {
    return await this.wsConnectionStatus.isVisible()
  }

  async getEstimatedTimeRemaining(): Promise<string | null> {
    return await this.estimatedTime.textContent()
  }
}

// Dashboard Page Object
export class DashboardPage extends BasePage {
  private readonly title = this.page.locator('h1')
  private readonly videoPlayer = this.page.locator('[data-testid="video-player"]')
  private readonly motionChart = this.page.locator('[data-testid="motion-chart"]')
  private readonly velocityChart = this.page.locator('[data-testid="velocity-chart"]')
  private readonly trajectoryHeatmap = this.page.locator('[data-testid="trajectory-heatmap"]')
  private readonly scoreRadar = this.page.locator('[data-testid="score-radar"]')
  private readonly exportButton = this.page.getByRole('button', { name: 'エクスポート' })
  private readonly annotateButton = this.page.getByRole('button', { name: 'アノテーション' })

  async goto(analysisId: string) {
    await this.navigate(`/dashboard/${analysisId}`)
  }

  async playVideo() {
    await this.videoPlayer.locator('button[aria-label="Play"]').click()
  }

  async pauseVideo() {
    await this.videoPlayer.locator('button[aria-label="Pause"]').click()
  }

  async exportData() {
    await this.exportButton.click()
  }

  async openAnnotation() {
    await this.annotateButton.click()
  }

  async getScores(): Promise<{ [key: string]: number }> {
    const scoreElements = await this.page.locator('[data-testid="score-item"]').all()
    const scores: { [key: string]: number } = {}

    for (const element of scoreElements) {
      const label = await element.locator('[data-testid="score-label"]').textContent()
      const value = await element.locator('[data-testid="score-value"]').textContent()
      if (label && value) {
        scores[label] = parseInt(value)
      }
    }

    return scores
  }

  async isChartVisible(chartType: 'motion' | 'velocity' | 'trajectory' | 'score'): Promise<boolean> {
    const chartMap = {
      motion: this.motionChart,
      velocity: this.velocityChart,
      trajectory: this.trajectoryHeatmap,
      score: this.scoreRadar
    }
    return await chartMap[chartType].isVisible()
  }
}

// Helper function to create page objects
export function createPageObjects(page: Page) {
  return {
    home: new HomePage(page),
    upload: new UploadPage(page),
    library: new LibraryPage(page),
    analysis: new AnalysisPage(page),
    dashboard: new DashboardPage(page)
  }
}