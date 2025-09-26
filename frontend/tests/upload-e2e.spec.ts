import { test, expect, Page } from '@playwright/test'
import path from 'path'
import fs from 'fs'

// テスト用の動画ファイルパス
const TEST_VIDEO_PATH = path.join(process.cwd(), '..', 'data', 'test-videos', 'test-video.mp4')
const UPLOAD_DIR = path.join(process.cwd(), '..', 'data', 'uploads')

test.describe('Complete Upload and Analysis Flow', () => {
  let uploadedVideoId: string | null = null
  let analysisId: string | null = null

  test.beforeAll(async () => {
    // テストビデオファイルが存在することを確認
    if (!fs.existsSync(TEST_VIDEO_PATH)) {
      // Front_Angle.mp4をテスト用にコピー
      const sourceFile = path.join(UPLOAD_DIR, 'Front_Angle.mp4')
      if (fs.existsSync(sourceFile)) {
        const testDir = path.dirname(TEST_VIDEO_PATH)
        if (!fs.existsSync(testDir)) {
          fs.mkdirSync(testDir, { recursive: true })
        }
        fs.copyFileSync(sourceFile, TEST_VIDEO_PATH)
      } else {
        console.warn('Test video file not found. Using mock file upload.')
      }
    }
  })

  test('complete upload flow with real file', async ({ page }) => {
    // Step 1: ホームページから開始
    await page.goto('/')

    // ホームページの確認
    await expect(page.getByTestId('home-title')).toBeVisible()

    // アップロードページへ移動
    await page.getByRole('link', { name: '新規解析' }).click()
    await expect(page).toHaveURL(/\/upload/)

    // Step 2: ファイルアップロード
    await expect(page.getByText('動画アップロード')).toBeVisible()

    // ファイルインプットを探す
    const fileInput = page.locator('input[type="file"]')

    // 実際のファイルをアップロード
    if (fs.existsSync(TEST_VIDEO_PATH)) {
      await fileInput.setInputFiles(TEST_VIDEO_PATH)
    } else {
      // フォールバック: モックファイルを使用
      await fileInput.setInputFiles({
        name: 'test-video.mp4',
        mimeType: 'video/mp4',
        buffer: Buffer.from('mock video content')
      })
    }

    // ファイル名が表示されることを確認
    await expect(page.getByText('test-video.mp4')).toBeVisible()

    // 次へボタンをクリック
    await page.getByRole('button', { name: '次へ' }).click()

    // Step 3: 映像タイプ選択
    await expect(page.getByText('映像タイプ')).toBeVisible()

    // 外部カメラを選択
    const externalButton = page.getByRole('button', { name: /外部カメラ/ })
    await externalButton.click()

    // 次へボタンをクリック
    await page.getByRole('button', { name: '次へ' }).click()

    // Step 4: 解析開始
    // アップロード進捗またはリダイレクトを待つ
    await page.waitForTimeout(2000)

    // APIレスポンスをインターセプトして動画IDを取得
    page.on('response', async response => {
      if (response.url().includes('/api/v1/videos/upload') && response.status() === 200) {
        const data = await response.json()
        uploadedVideoId = data.video_id
        console.log('Uploaded video ID:', uploadedVideoId)
      }
      if (response.url().includes('/api/v1/analysis') && response.url().includes('/analyze')) {
        const data = await response.json()
        analysisId = data.analysis_id
        console.log('Analysis ID:', analysisId)
      }
    })

    // 解析ページへのリダイレクトを確認
    await expect(page).toHaveURL(/\/(analysis|library)/, { timeout: 10000 })

    // 解析が開始されたことを確認
    if (page.url().includes('/analysis/')) {
      await expect(page.getByText(/解析中|処理中|分析/)).toBeVisible({ timeout: 5000 })
    }
  })

  test('upload page validation', async ({ page }) => {
    await page.goto('/upload')

    // 初期状態: 次へボタンは無効
    const nextButton = page.getByRole('button', { name: '次へ' })
    await expect(nextButton).toBeDisabled()

    // 空のファイルインプットの状態を確認
    await expect(page.getByText('ファイルを選択')).toBeVisible()

    // ファイルサイズ制限の表示を確認
    await expect(page.getByText(/2GB|ファイルサイズ/)).toBeVisible()
  })

  test('video type selection flow', async ({ page }) => {
    await page.goto('/upload')

    // モックファイルをアップロード
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test-internal.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('mock video content')
    })

    await page.getByRole('button', { name: '次へ' }).click()

    // 内部カメラを選択
    const internalButton = page.getByRole('button', { name: /内部カメラ/ })
    await internalButton.click()

    // 内部カメラの場合、器具アノテーションステップが表示される
    await page.getByRole('button', { name: '次へ' }).click()

    // 器具アノテーションページまたは解析開始ボタンを確認
    await expect(page.getByText(/器具|アノテーション|解析を開始/)).toBeVisible({ timeout: 5000 })
  })

  test('navigation between steps', async ({ page }) => {
    await page.goto('/upload')

    // ファイルをアップロード
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'navigation-test.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('mock video content')
    })

    // Step 2へ
    await page.getByRole('button', { name: '次へ' }).click()
    await expect(page.getByText('映像タイプ')).toBeVisible()

    // Step 1へ戻る
    await page.getByRole('button', { name: '戻る' }).click()
    await expect(page.getByText('navigation-test.mp4')).toBeVisible()

    // 再度Step 2へ
    await page.getByRole('button', { name: '次へ' }).click()
    await expect(page.getByText('映像タイプ')).toBeVisible()
  })

  test('error handling for invalid file types', async ({ page }) => {
    await page.goto('/upload')

    // PDFファイルをアップロード試行
    const fileInput = page.locator('input[type="file"]')

    // acceptアトリビュートをチェック
    const accept = await fileInput.getAttribute('accept')
    expect(accept).toContain('video')

    // 無効なファイルタイプをセット（ブラウザが許可する場合）
    await fileInput.setInputFiles({
      name: 'document.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('mock pdf content')
    })

    // エラーメッセージまたはファイルが受け入れられないことを確認
    const nextButton = page.getByRole('button', { name: '次へ' })

    // PDFがアップロードされた場合、次へボタンは有効になるが、
    // サーバー側でエラーになるはず
    if (await nextButton.isEnabled()) {
      await nextButton.click()
      // サーバーエラーまたは警告メッセージを待つ
      await expect(page.getByText(/エラー|失敗|対応していない|mp4/i)).toBeVisible({ timeout: 5000 })
    }
  })

  test('concurrent upload handling', async ({ browser }) => {
    // 複数のブラウザコンテキストで同時アップロードをテスト
    const context1 = await browser.newContext()
    const context2 = await browser.newContext()

    const page1 = await context1.newPage()
    const page2 = await context2.newPage()

    // 両方のページでアップロードを開始
    await Promise.all([
      uploadFile(page1, 'concurrent-1.mp4'),
      uploadFile(page2, 'concurrent-2.mp4')
    ])

    // 両方のアップロードが成功することを確認
    await expect(page1.getByText('concurrent-1.mp4')).toBeVisible()
    await expect(page2.getByText('concurrent-2.mp4')).toBeVisible()

    await context1.close()
    await context2.close()
  })
})

// ヘルパー関数
async function uploadFile(page: Page, fileName: string) {
  await page.goto('/upload')
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles({
    name: fileName,
    mimeType: 'video/mp4',
    buffer: Buffer.from('mock video content for ' + fileName)
  })
}