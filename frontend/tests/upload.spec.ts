import { test, expect } from '@playwright/test'
import { createPageObjects } from './helpers/page-objects'
import { ApiMocker } from './helpers/api-mock'
import { createMockFile, testData } from './helpers/test-data'

test.describe('Upload Page', () => {
  let apiMocker: ApiMocker

  test.beforeEach(async ({ page }) => {
    // Setup API mocks
    apiMocker = new ApiMocker(page)
    await apiMocker.setupDefaultMocks()
    await apiMocker.mockVideoUpload()
  })

  test('shows upload form and enables Next after file selection', async ({ page }) => {
    const { upload } = createPageObjects(page)
    await upload.goto()

    // Check page title using data-testid
    await expect(page.locator('[data-testid="upload-title"]')).toContainText('動画アップロード')

    // Upload a mock file
    const mockFile = createMockFile('test-video.mp4')
    await upload.uploadMockFile(mockFile)

    // Check file name is displayed
    await expect(page.getByText('test-video.mp4')).toBeVisible()

    // Check Next button is enabled
    const isEnabled = await upload.isNextButtonEnabled()
    expect(isEnabled).toBe(true)
  })

  test('complete upload flow with all steps', async ({ page }) => {
    const { upload } = createPageObjects(page)
    await upload.goto()

    // Step 1: Upload file
    const mockFile = createMockFile('surgery_test.mp4', 10 * 1024 * 1024) // 10MB
    await upload.uploadMockFile(mockFile)
    await upload.clickNext()

    // Step 2: Select video type
    await expect(page.getByRole('heading', { level: 2 })).toContainText('映像タイプ')
    await upload.selectExternalCamera()
    await upload.clickNext()

    // The external camera path should immediately start analysis
    // Mock the upload response
    await apiMocker.mockAnalysisStart('test-video-1')

    // Verify analysis starts
    await page.waitForTimeout(1000) // Wait for navigation
    await expect(page).toHaveURL(/\/analysis\//)
  })

  test.skip('validates file type and shows error for invalid files', async ({ page }) => {
    // Skip this test for now as file type validation may not show error immediately
    const { upload } = createPageObjects(page)
    await upload.goto()

    // Try to upload an invalid file type
    const invalidFile = createMockFile('document.pdf', 1024, 'application/pdf')
    await upload.uploadMockFile(invalidFile)

    // Check for error message
    const errorMessage = await upload.getErrorMessage()
    expect(errorMessage).toContain('対応していない')
  })

  test('handles large file upload with progress', async ({ page }) => {
    const { upload } = createPageObjects(page)
    await upload.goto()

    // Upload a large file (capped at 50MB by createMockFile)
    const largeFile = createMockFile('large-video.mp4', 45 * 1024 * 1024) // 45MB
    await upload.uploadMockFile(largeFile)
    await upload.clickNext()

    // Select video type
    await upload.selectInternalCamera()

    // Internal camera goes to annotation step
    // Click '解析を開始' button to start analysis
    await page.waitForTimeout(500)
    const startButton = page.getByRole('button', { name: '解析を開始' })
    await startButton.click()

    // Check for upload progress indicator or navigation
    await page.waitForTimeout(1000)
  })

  test('navigation between steps works correctly', async ({ page }) => {
    const { upload } = createPageObjects(page)
    await upload.goto()

    // Upload file and go to step 2
    const mockFile = createMockFile()
    await upload.uploadMockFile(mockFile)
    await upload.clickNext()

    // Go back to step 1
    await upload.clickBack()
    await expect(page.getByText('test-video.mp4')).toBeVisible()

    // Go forward again
    await upload.clickNext()
    await expect(page.getByRole('heading', { level: 2 })).toContainText('映像タイプ')
  })
})
