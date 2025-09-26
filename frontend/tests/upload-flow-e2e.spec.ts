import { test, expect } from '@playwright/test'
import { createPageObjects } from './helpers/page-objects'
import { ApiMocker } from './helpers/api-mock'
import { createMockFile, testData } from './helpers/test-data'

test.describe('Upload Flow E2E Tests', () => {
  let apiMocker: ApiMocker

  test.beforeEach(async ({ page }) => {
    apiMocker = new ApiMocker(page)
    await apiMocker.setupDefaultMocks()
  })

  test('complete upload flow from home to analysis', async ({ page }) => {
    const pages = createPageObjects(page)

    // Step 1: Start from home page
    await pages.home.goto()
    await pages.home.clickNewAnalysis()
    await expect(page).toHaveURL(/\/upload/)

    // Step 2: Upload video file
    const mockFile = createMockFile('surgery_2025.mp4', 100 * 1024 * 1024) // 100MB
    await pages.upload.uploadMockFile(mockFile)
    await expect(page.getByText('surgery_2025.mp4')).toBeVisible()
    await expect(page.getByText('100')).toBeVisible() // File size indicator

    // Step 3: Proceed to video type selection
    await pages.upload.clickNext()
    await expect(page.getByRole('heading', { level: 2 })).toContainText('映像タイプ')

    // Step 4: Select external camera type
    await pages.upload.selectExternalCamera()
    await expect(page.getByRole('button', { name: '外部（手元カメラ）' })).toHaveClass(/selected|active/)
    await pages.upload.clickNext()

    // Step 5: Fill in metadata
    await pages.upload.fillMetadata({
      surgeryName: '腹腔鏡下胆嚢摘出術',
      surgeonName: '山田太郎',
      surgeryDate: '2025-01-14',
      memo: 'トレーニング用ビデオ'
    })

    // Mock the upload and analysis start
    await apiMocker.mockVideoUpload({
      ...testData.videos.valid,
      id: 'uploaded-video-1'
    })
    await apiMocker.mockAnalysisStart('uploaded-video-1', {
      ...testData.analysis.pending,
      id: 'new-analysis-1'
    })

    // Step 6: Start upload and analysis
    await pages.upload.clickNext()

    // Should redirect to analysis page
    await page.waitForURL(/\/analysis\//, { timeout: 10000 })
    expect(page.url()).toContain('/analysis/')
  })

  test('upload multiple files in sequence', async ({ page }) => {
    const pages = createPageObjects(page)

    // Upload first video
    await pages.upload.goto()
    const file1 = createMockFile('video1.mp4', 50 * 1024 * 1024)
    await pages.upload.uploadMockFile(file1)
    await pages.upload.clickNext()
    await pages.upload.selectExternalCamera()
    await pages.upload.clickNext()
    await pages.upload.fillMetadata({ surgeryName: 'Surgery 1' })

    await apiMocker.mockVideoUpload({ ...testData.videos.valid, id: 'video-1' })
    await apiMocker.mockAnalysisStart('video-1', { ...testData.analysis.pending, id: 'analysis-1' })
    await pages.upload.clickNext()

    // Go back to upload another video
    await pages.home.goto()
    await pages.home.clickNewAnalysis()

    // Upload second video
    const file2 = createMockFile('video2.mp4', 75 * 1024 * 1024)
    await pages.upload.uploadMockFile(file2)
    await pages.upload.clickNext()
    await pages.upload.selectInternalCamera()
    await pages.upload.clickNext()
    await pages.upload.fillMetadata({ surgeryName: 'Surgery 2' })

    await apiMocker.mockVideoUpload({ ...testData.videos.valid, id: 'video-2' })
    await apiMocker.mockAnalysisStart('video-2', { ...testData.analysis.pending, id: 'analysis-2' })
    await pages.upload.clickNext()

    // Should have started second analysis
    expect(page.url()).toContain('/analysis/')
  })

  test('upload flow with validation errors', async ({ page }) => {
    const pages = createPageObjects(page)
    await pages.upload.goto()

    // Try to proceed without selecting a file
    const isNextEnabled = await pages.upload.isNextButtonEnabled()
    expect(isNextEnabled).toBe(false)

    // Upload invalid file type
    const invalidFile = createMockFile('document.txt', 1024, 'text/plain')
    await pages.upload.uploadMockFile(invalidFile)

    // Should show error
    const errorMessage = await pages.upload.getErrorMessage()
    expect(errorMessage).toBeTruthy()

    // Upload valid file
    const validFile = createMockFile('valid.mp4')
    await pages.upload.uploadMockFile(validFile)
    await pages.upload.clickNext()

    // Try to proceed without selecting video type
    await pages.upload.clickNext()
    // Should still be on video type selection
    await expect(page.getByRole('heading', { level: 2 })).toContainText('映像タイプ')

    // Select video type and proceed
    await pages.upload.selectExternalCamera()
    await pages.upload.clickNext()

    // Try to submit with empty required fields
    await pages.upload.clickNext()
    // Should show validation errors or stay on the same page
    const currentUrl = page.url()
    expect(currentUrl).toContain('/upload')
  })

  test('upload flow with network interruption', async ({ page }) => {
    const pages = createPageObjects(page)
    await pages.upload.goto()

    // Upload file and fill all required information
    const mockFile = createMockFile('network-test.mp4', 200 * 1024 * 1024)
    await pages.upload.uploadMockFile(mockFile)
    await pages.upload.clickNext()
    await pages.upload.selectExternalCamera()
    await pages.upload.clickNext()
    await pages.upload.fillMetadata({ surgeryName: 'Network Test' })

    // Simulate network failure during upload
    await apiMocker.mockNetworkFailure('**/api/v1/videos/upload')
    await pages.upload.clickNext()

    // Should show error message
    const errorMessage = await pages.upload.getErrorMessage()
    expect(errorMessage).toContain('ネットワーク')
  })

  test('upload flow with slow network', async ({ page }) => {
    const pages = createPageObjects(page)
    await pages.upload.goto()

    // Setup slow response mock
    await apiMocker.mockSlowResponse('**/api/v1/videos/upload', 3000, testData.videos.valid)

    // Upload file
    const mockFile = createMockFile('slow-upload.mp4', 50 * 1024 * 1024)
    await pages.upload.uploadMockFile(mockFile)
    await pages.upload.clickNext()
    await pages.upload.selectInternalCamera()
    await pages.upload.clickNext()
    await pages.upload.fillMetadata({ surgeryName: 'Slow Upload Test' })
    await pages.upload.clickNext()

    // Should show upload progress
    await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible()

    // Wait for upload to complete
    await page.waitForURL(/\/analysis\//, { timeout: 15000 })
  })

  test('cancel upload and start over', async ({ page }) => {
    const pages = createPageObjects(page)
    await pages.upload.goto()

    // Start upload process
    const mockFile = createMockFile('cancel-test.mp4')
    await pages.upload.uploadMockFile(mockFile)
    await pages.upload.clickNext()
    await pages.upload.selectExternalCamera()
    await pages.upload.clickNext()

    // Go back to first step
    await pages.upload.clickBack()
    await pages.upload.clickBack()

    // Upload a different file
    const newFile = createMockFile('new-file.mp4')
    await pages.upload.uploadMockFile(newFile)
    await expect(page.getByText('new-file.mp4')).toBeVisible()
  })

  test('upload with maximum file size', async ({ page }) => {
    const pages = createPageObjects(page)
    await pages.upload.goto()

    // Try to upload file at maximum size (2GB)
    const maxFile = createMockFile('max-size.mp4', 2 * 1024 * 1024 * 1024 - 1)
    await pages.upload.uploadMockFile(maxFile)

    // Should accept the file
    await expect(page.getByText('max-size.mp4')).toBeVisible()
    const isNextEnabled = await pages.upload.isNextButtonEnabled()
    expect(isNextEnabled).toBe(true)

    // Try to upload file over maximum size
    const oversizedFile = createMockFile('oversized.mp4', 2 * 1024 * 1024 * 1024 + 1)
    await pages.upload.uploadMockFile(oversizedFile)

    // Should show error
    const errorMessage = await pages.upload.getErrorMessage()
    expect(errorMessage).toContain('サイズ')
  })

  test('preserve metadata when navigating back', async ({ page }) => {
    const pages = createPageObjects(page)
    await pages.upload.goto()

    // Fill in all steps
    const mockFile = createMockFile('metadata-test.mp4')
    await pages.upload.uploadMockFile(mockFile)
    await pages.upload.clickNext()
    await pages.upload.selectInternalCamera()
    await pages.upload.clickNext()

    const metadata = {
      surgeryName: 'Preserved Surgery',
      surgeonName: 'Dr. Preserve',
      surgeryDate: '2025-01-14',
      memo: 'This should be preserved'
    }
    await pages.upload.fillMetadata(metadata)

    // Go back and forward
    await pages.upload.clickBack()
    await pages.upload.clickNext()

    // Check if metadata is preserved
    const surgeryNameValue = await page.locator('input[name="surgery_name"]').inputValue()
    const surgeonNameValue = await page.locator('input[name="surgeon_name"]').inputValue()
    const memoValue = await page.locator('textarea[name="memo"]').inputValue()

    expect(surgeryNameValue).toBe(metadata.surgeryName)
    expect(surgeonNameValue).toBe(metadata.surgeonName)
    expect(memoValue).toBe(metadata.memo)
  })
})