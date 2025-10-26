import { test, expect } from '@playwright/test'

test.describe('視線解析ダッシュボード - 独自デザイン検証', () => {
  const ANALYSIS_ID = '56eeeff2-62cb-42c1-aad2-0c4331ee94bc'
  const DASHBOARD_URL = `http://localhost:3002/dashboard/${ANALYSIS_ID}`

  test('独自デザインの全要素が正しく表示される', async ({ page }) => {
    // ダッシュボードにアクセス
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    // ページタイトル確認
    await expect(page.locator('h1')).toContainText('視線解析結果')

    // === 1. Canvas要素の確認 ===
    console.log('✓ Canvas要素を確認中...')

    // 左Canvas: ゲーズプロットオーバーレイ
    const leftCanvas = page.locator('canvas').first()
    await expect(leftCanvas).toBeVisible()
    console.log('✓ 左Canvas（ゲーズプロット）: 表示確認')

    // 右Canvas: リアルタイムヒートマップ
    const rightCanvas = page.locator('canvas').nth(1)
    await expect(rightCanvas).toBeVisible()
    console.log('✓ 右Canvas（ヒートマップ）: 表示確認')

    // Canvas解像度確認（362x260であるべき）
    const leftWidth = await leftCanvas.getAttribute('width')
    const leftHeight = await leftCanvas.getAttribute('height')
    expect(leftWidth).toBe('362')
    expect(leftHeight).toBe('260')
    console.log(`✓ 左Canvas解像度: ${leftWidth}x${leftHeight}`)

    const rightWidth = await rightCanvas.getAttribute('width')
    const rightHeight = await rightCanvas.getAttribute('height')
    expect(rightWidth).toBe('362')
    expect(rightHeight).toBe('260')
    console.log(`✓ 右Canvas解像度: ${rightWidth}x${rightHeight}`)

    // === 2. Chart.jsグラフの確認 ===
    console.log('✓ Chart.jsグラフを確認中...')

    // Chart.jsはCanvasを使用するので、3つ目のCanvasがグラフ
    const chartCanvas = page.locator('canvas').nth(2)
    await expect(chartCanvas).toBeVisible()
    console.log('✓ Chart.jsグラフ（時系列）: 表示確認')

    // === 3. 用語「ゲーズプロット」の確認 ===
    console.log('✓ 用語「ゲーズプロット」を確認中...')

    // 「ゲーズプロット」が表示されることを確認
    await expect(page.getByText('ゲーズプロット')).toBeVisible()
    console.log('✓ 用語「ゲーズプロット」: 表示確認')

    // 「総ゲーズプロット数」が表示されることを確認
    await expect(page.getByText('総ゲーズプロット数')).toBeVisible()
    console.log('✓ 統計カード「総ゲーズプロット数」: 表示確認')

    // 「平均ゲーズプロット数/フレーム」が表示されることを確認
    await expect(page.getByText('平均ゲーズプロット数/フレーム')).toBeVisible()
    console.log('✓ 統計カード「平均ゲーズプロット数/フレーム」: 表示確認')

    // 「固視点」という古い用語が表示されないことを確認
    const oldTermCount = await page.getByText('固視点').count()
    expect(oldTermCount).toBe(0)
    console.log('✓ 旧用語「固視点」: 非表示確認（0件）')

    // === 4. ビデオコントロールの確認 ===
    console.log('✓ ビデオコントロールを確認中...')

    // 再生/一時停止ボタン
    const playButton = page.getByRole('button', { name: /再生|一時停止/ })
    await expect(playButton).toBeVisible()
    console.log('✓ 再生/一時停止ボタン: 表示確認')

    // スライダー（シークバー）
    const slider = page.locator('input[type="range"]')
    await expect(slider).toBeVisible()
    console.log('✓ シークバー: 表示確認')

    // === 5. ヒートマップ時間窓の表示確認 ===
    const heatmapWindowText = page.getByText(/±\d+秒/)
    await expect(heatmapWindowText).toBeVisible()
    console.log('✓ ヒートマップ時間窓表示: 確認')

    // === 6. グラフタイトルの確認 ===
    await expect(page.getByText('ゲーズプロット座標の時系列変化')).toBeVisible()
    console.log('✓ グラフタイトル: 表示確認')

    console.log('\n=== 全ての検証が完了しました ===')
  })

  test('スクリーンショットを撮影', async ({ page }) => {
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    // ページ全体のスクリーンショット
    await page.screenshot({
      path: 'test-results/gaze-dashboard-full.png',
      fullPage: true
    })
    console.log('✓ フルページスクリーンショット保存: test-results/gaze-dashboard-full.png')

    // 左Canvasのスクリーンショット
    const leftCanvas = page.locator('canvas').first()
    await leftCanvas.screenshot({
      path: 'test-results/gaze-dashboard-left-canvas.png'
    })
    console.log('✓ 左Canvas（ゲーズプロット）保存: test-results/gaze-dashboard-left-canvas.png')

    // 右Canvasのスクリーンショット
    const rightCanvas = page.locator('canvas').nth(1)
    await rightCanvas.screenshot({
      path: 'test-results/gaze-dashboard-right-canvas.png'
    })
    console.log('✓ 右Canvas（ヒートマップ）保存: test-results/gaze-dashboard-right-canvas.png')

    // Chart.jsグラフのスクリーンショット
    const chartCanvas = page.locator('canvas').nth(2)
    await chartCanvas.screenshot({
      path: 'test-results/gaze-dashboard-chart.png'
    })
    console.log('✓ Chart.jsグラフ保存: test-results/gaze-dashboard-chart.png')
  })

  test('ビデオ再生とCanvas同期を確認', async ({ page }) => {
    await page.goto(DASHBOARD_URL, { waitUntil: 'networkidle' })

    // 再生ボタンをクリック
    const playButton = page.getByRole('button', { name: /再生/ })
    await playButton.click()
    console.log('✓ 再生ボタンクリック')

    // 2秒待機
    await page.waitForTimeout(2000)

    // Canvasが更新されていることを確認（スナップショット比較）
    const leftCanvas = page.locator('canvas').first()
    await expect(leftCanvas).toHaveScreenshot('gaze-plot-playing.png', {
      maxDiffPixels: 1000 // ある程度の変化を許容
    })
    console.log('✓ ビデオ再生中のCanvas更新: 確認')
  })
})
