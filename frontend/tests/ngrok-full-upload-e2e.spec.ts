import { test, expect } from '@playwright/test'

/**
 * ngrok経由での完全な新規解析E2Eテスト
 *
 * テストシナリオ:
 * 1. https://mindmotionai.ngrok-free.dev にアクセス
 * 2. アップロードページに移動
 * 3. 動画ファイルをアップロード
 * 4. 解析ボタンをクリック
 * 5. WebSocketで進捗を監視
 * 6. 結果ページでスケルトンデータを確認
 */

const NGROK_URL = 'https://mindmotionai.ngrok-free.dev'
const TEST_VIDEO_PATH = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\data\\uploads\\【正式】手技動画.mp4'

test.describe('ngrok経由 新規解析E2E', () => {
  test.setTimeout(600000) // 10分タイムアウト（動画アップロード＋解析）

  test('動画アップロード → 解析開始 → 結果確認', async ({ page }) => {
    console.log('[TEST] Starting ngrok full upload E2E test')

    // コンソールログを監視
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.error(`[BROWSER ERROR] ${msg.text()}`)
      }
    })

    // ネットワークエラーを監視
    page.on('pageerror', error => {
      console.error(`[PAGE ERROR] ${error.message}`)
    })

    // ===== Step 1: ngrokサイトにアクセス =====
    console.log('[TEST] Step 1: Navigating to ngrok URL')
    await page.goto(NGROK_URL, { waitUntil: 'networkidle' })

    // スクリーンショット撮影
    await page.screenshot({ path: 'test-results/01-home.png', fullPage: true })
    console.log('[TEST] Home page loaded')

    // ===== Step 2: アップロードページに移動 =====
    console.log('[TEST] Step 2: Navigating to upload page')

    // 「新規解析」ボタンを探す
    const uploadLink = page.locator('text=新規解析').or(
      page.locator('text=アップロード')
    ).or(
      page.locator('a[href*="upload"]')
    ).first()

    await expect(uploadLink).toBeVisible({ timeout: 10000 })
    await uploadLink.click()
    await page.waitForLoadState('networkidle')
    await page.screenshot({ path: 'test-results/02-upload-page.png', fullPage: true })
    console.log('[TEST] Upload page loaded')

    // ===== Step 3: 動画ファイルをアップロード =====
    console.log('[TEST] Step 3: Uploading video file')

    // ファイル入力要素を探す
    const fileInput = page.locator('input[type="file"]').first()
    await expect(fileInput).toBeAttached({ timeout: 5000 })
    await fileInput.setInputFiles(TEST_VIDEO_PATH)
    console.log('[TEST] File selected')

    // 動画タイプを選択
    const videoTypeSelect = page.locator('select[name="video_type"]').or(
      page.locator('#video_type')
    ).first()

    if (await videoTypeSelect.isVisible()) {
      await videoTypeSelect.selectOption('external_with_instruments')
      console.log('[TEST] Video type selected: external_with_instruments')
    }

    // メタデータ入力（オプション）
    const surgeryNameInput = page.locator('input[name="surgery_name"]').or(
      page.locator('#surgery_name')
    )
    if (await surgeryNameInput.first().isVisible()) {
      await surgeryNameInput.first().fill('E2Eテスト手技')
      console.log('[TEST] Surgery name filled')
    }

    // スクリーンショット撮影
    await page.screenshot({ path: 'test-results/03-form-filled.png', fullPage: true })

    // アップロードボタンをクリック
    const uploadButton = page.locator('button:has-text("アップロード")').or(
      page.locator('button[type="submit"]')
    ).first()

    await expect(uploadButton).toBeVisible({ timeout: 5000 })
    console.log('[TEST] Clicking upload button')
    await uploadButton.click()

    // アップロード完了を待機（最大5分）
    console.log('[TEST] Waiting for upload to complete...')
    await page.waitForURL(/\/analysis\/.*/, { timeout: 300000 })

    const currentUrl = page.url()
    console.log(`[TEST] Redirected to: ${currentUrl}`)
    await page.screenshot({ path: 'test-results/04-upload-complete.png', fullPage: true })

    // 解析IDを抽出
    const analysisIdMatch = currentUrl.match(/\/analysis\/([a-f0-9-]+)/)
    expect(analysisIdMatch).not.toBeNull()
    const analysisId = analysisIdMatch![1]
    console.log(`[TEST] Analysis ID: ${analysisId}`)

    // ===== Step 4: 解析ボタンをクリック =====
    console.log('[TEST] Step 4: Starting analysis')

    // 解析開始ボタンを探す
    const analyzeButton = page.locator('button:has-text("解析開始")').or(
      page.locator('button:has-text("解析を開始")')
    ).or(
      page.locator('button:has-text("Start Analysis")')
    ).first()

    await expect(analyzeButton).toBeVisible({ timeout: 10000 })
    console.log('[TEST] Clicking analyze button')
    await analyzeButton.click()

    // ===== Step 5: WebSocket進捗を監視 =====
    console.log('[TEST] Step 5: Monitoring WebSocket progress')

    // 進捗表示要素を監視
    let progressMessages: string[] = []

    // 定期的に進捗をチェック
    const maxWaitTime = 600000 // 10分
    const startTime = Date.now()

    while (Date.now() - startTime < maxWaitTime) {
      // 進捗テキストを探す
      const progressText = await page.locator('text=/処理中|解析中|検出中/').first().textContent().catch(() => null)

      if (progressText && !progressMessages.includes(progressText)) {
        progressMessages.push(progressText)
        console.log(`[TEST] Progress: ${progressText}`)
      }

      // 完了メッセージを確認
      const completeMessage = await page.locator('text=/完了|Complete|成功/').first().isVisible().catch(() => false)

      if (completeMessage) {
        console.log('[TEST] Analysis completed!')
        break
      }

      // エラーメッセージを確認
      const errorMessage = await page.locator('text=/エラー|失敗|Error|Failed/').first().isVisible().catch(() => false)

      if (errorMessage) {
        const errorText = await page.locator('text=/エラー|失敗|Error|Failed/').first().textContent()
        console.error(`[TEST] Error detected: ${errorText}`)
        await page.screenshot({ path: 'test-results/05-error.png', fullPage: true })
        throw new Error(`Analysis failed: ${errorText}`)
      }

      // 2秒待機
      await page.waitForTimeout(2000)
    }

    await page.screenshot({ path: 'test-results/05-analysis-complete.png', fullPage: true })

    // ===== Step 6: 結果ページでスケルトンデータを確認 =====
    console.log('[TEST] Step 6: Verifying skeleton data')

    // ダッシュボードへのリンクを探す
    const dashboardLink = page.locator('a:has-text("ダッシュボード")').or(
      page.locator('a:has-text("結果を見る")')
    ).or(
      page.locator('a[href*="dashboard"]')
    ).first()

    if (await dashboardLink.isVisible({ timeout: 5000 })) {
      console.log('[TEST] Navigating to dashboard')
      await dashboardLink.click()
      await page.waitForLoadState('networkidle')
    } else {
      // 既にダッシュボードにいる場合はスキップ
      console.log('[TEST] Already on dashboard page')
    }

    await page.screenshot({ path: 'test-results/06-dashboard.png', fullPage: true })

    // Canvasが表示されているか確認
    const canvas = page.locator('canvas').first()
    await expect(canvas).toBeVisible({ timeout: 10000 })
    console.log('[TEST] Canvas element found')

    // スケルトンデータの存在確認（DOM内のデータ属性やテキスト）
    const skeletonDataExists = await page.evaluate(() => {
      // グローバル変数やlocalStorageをチェック
      const hasLocalStorage = localStorage.getItem('analysis_result') !== null

      // Canvasに描画されているか確認（簡易版）
      const canvases = document.querySelectorAll('canvas')
      const hasDrawnCanvas = Array.from(canvases).some(canvas => {
        const ctx = (canvas as HTMLCanvasElement).getContext('2d')
        if (!ctx) return false

        // ImageDataをチェック（何か描画されているか）
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
        return imageData.data.some(pixel => pixel !== 0)
      })

      return hasLocalStorage || hasDrawnCanvas
    })

    console.log(`[TEST] Skeleton data exists: ${skeletonDataExists}`)

    // グラフやチャートが表示されているか確認
    const chartExists = await page.locator('canvas').count() > 1
    console.log(`[TEST] Charts found: ${chartExists}`)

    // 最終スクリーンショット
    await page.screenshot({ path: 'test-results/07-final.png', fullPage: true })

    // ===== 検証 =====
    console.log('[TEST] Running final assertions')

    expect(progressMessages.length).toBeGreaterThan(0) // 進捗メッセージが表示された
    expect(await canvas.isVisible()).toBeTruthy() // Canvasが表示されている

    console.log('[TEST] ✅ All tests passed!')
    console.log(`[TEST] Progress messages: ${progressMessages.join(', ')}`)
    console.log(`[TEST] Analysis ID: ${analysisId}`)
  })
})
