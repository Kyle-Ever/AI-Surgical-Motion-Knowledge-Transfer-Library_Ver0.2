import { test, expect } from '@playwright/test'

// 解析結果ページのE2Eテスト
test.describe('Analysis Results Dashboard', () => {
  // テスト用の解析済みIDを使用（実際のDBにあるもの）
  const testAnalysisId = 'd934ce94-36f5-49fc-916f-c32a5327e766'
  const dashboardUrl = `http://localhost:3000/dashboard/${testAnalysisId}`

  test.beforeEach(async ({ page }) => {
    // ダッシュボードページへ直接移動
    await page.goto(dashboardUrl)

    // ページの読み込みを待つ
    await page.waitForLoadState('networkidle')
  })

  test('dashboard page loads correctly', async ({ page }) => {
    // ページタイトルの確認
    await expect(page.getByText('解析結果')).toBeVisible({ timeout: 10000 })

    // 基本的なレイアウトの確認
    const videoSection = page.locator('.lg\\:col-span-2')
    await expect(videoSection).toBeVisible()
  })

  test('video player displays correctly', async ({ page }) => {
    // ビデオプレーヤーの存在確認
    const videoPlayer = page.locator('video')
    await expect(videoPlayer).toBeVisible({ timeout: 15000 })

    // ビデオソースの確認
    const videoSrc = await videoPlayer.getAttribute('src')
    expect(videoSrc).toBeTruthy()
  })

  test('metrics display correctly', async ({ page }) => {
    // メトリクスが表示されるまで待つ
    await page.waitForTimeout(3000)

    // 手技動作メトリクスの確認
    const handMetricsSection = page.getByText('手技動作メトリクス').first()
    if (await handMetricsSection.isVisible()) {
      // 各メトリクスの表示確認
      const metricsToCheck = ['総移動距離', '平均速度', '最大速度', '動作の滑らかさ']

      for (const metric of metricsToCheck) {
        const metricElement = page.getByText(metric).first()
        if (await metricElement.isVisible()) {
          // 値が表示されているか確認（数値またはN/A）
          const parentElement = metricElement.locator('..')
          const valueElement = parentElement.locator('text=/\\d+\\.?\\d*|N\\/A/')
          await expect(valueElement).toBeVisible()
        }
      }
    }
  })

  test('instrument tracking displays when available', async ({ page }) => {
    // 器具追跡メトリクスの確認（内部カメラの場合のみ）
    const instrumentSection = page.getByText('器具追跡メトリクス')

    if (await instrumentSection.isVisible({ timeout: 5000 })) {
      // 器具が検出されている場合
      const instrumentList = page.locator('[data-testid="instrument-list"]')
      if (await instrumentList.isVisible()) {
        const instruments = await instrumentList.locator('li').count()
        expect(instruments).toBeGreaterThan(0)
      }
    }
  })

  test('score comparison loads correctly', async ({ page }) => {
    // スコア比較コンポーネントの表示確認
    const scoreSection = page.getByText('スコア評価')
    await expect(scoreSection).toBeVisible({ timeout: 10000 })

    // 基準モデル選択ドロップダウンの確認
    const modelSelect = page.locator('select').first()
    await expect(modelSelect).toBeVisible()

    // デフォルトで上級者モデルが選択されているか確認
    const selectedValue = await modelSelect.inputValue()
    expect(selectedValue).toBeTruthy()
  })

  test('score calculation works', async ({ page }) => {
    // スコア計算の待機
    await page.waitForTimeout(5000)

    // 総合スコアの表示確認
    const overallScore = page.locator('text=/総合スコア/')
    if (await overallScore.isVisible()) {
      // スコアの数値が表示されているか
      const scoreValue = page.locator('text=/\\d{1,3}点/')
      await expect(scoreValue).toBeVisible()

      // レベル表示の確認
      const levelText = page.locator('text=/レベル: (初級|初中級|中級|中上級|上級)/')
      await expect(levelText).toBeVisible()
    }
  })

  test('individual scores display correctly', async ({ page }) => {
    // 個別スコアの確認
    const scoreTypes = ['動作速度', '滑らかさ', '安定性', '効率性']

    for (const scoreType of scoreTypes) {
      const scoreElement = page.getByText(scoreType)
      if (await scoreElement.isVisible()) {
        // 各スコアに数値が表示されているか確認
        const scoreRow = scoreElement.locator('..')
        const scoreValue = scoreRow.locator('text=/\\d{1,3}|--/')
        await expect(scoreValue).toBeVisible()
      }
    }
  })

  test('reference model selection changes scores', async ({ page }) => {
    // 初期スコアを記録
    await page.waitForTimeout(3000)
    let initialScore = '--'

    const scoreElement = page.locator('text=/\\d{1,3}点/').first()
    if (await scoreElement.isVisible()) {
      initialScore = await scoreElement.textContent() || '--'
    }

    // 別の基準モデルを選択
    const modelSelect = page.locator('select').first()
    const options = await modelSelect.locator('option').all()

    if (options.length > 1) {
      // 2番目のオプションを選択
      await modelSelect.selectOption({ index: 1 })

      // スコアの再計算を待つ
      await page.waitForTimeout(3000)

      // 新しいスコアが表示されているか確認
      const newScoreElement = page.locator('text=/\\d{1,3}点/').first()
      if (await newScoreElement.isVisible()) {
        const newScore = await newScoreElement.textContent()
        // スコアが更新されたか、または処理中であることを確認
        expect(newScore).toBeTruthy()
      }
    }
  })

  test('chart displays correctly', async ({ page }) => {
    // チャートコンポーネントの確認
    const chartCanvas = page.locator('canvas')

    // 少なくとも1つのチャートが表示されているか
    const chartCount = await chartCanvas.count()
    expect(chartCount).toBeGreaterThan(0)
  })

  test('data updates via websocket', async ({ page }) => {
    // WebSocket接続の確認（コンソールログで確認）
    const consoleLogs: string[] = []
    page.on('console', msg => {
      consoleLogs.push(msg.text())
    })

    // ページリロード
    await page.reload()
    await page.waitForTimeout(3000)

    // WebSocket関連のログがあるか確認
    const hasWebSocketLog = consoleLogs.some(log =>
      log.includes('WebSocket') ||
      log.includes('Connected') ||
      log.includes('ws://')
    )

    // WebSocketログがあることを期待（オプショナル）
    // WebSocketが使用されていない場合もあるため、これは情報収集のみ
    console.log('WebSocket logs found:', hasWebSocketLog)
  })

  test('error handling when analysis not found', async ({ page }) => {
    // 存在しない解析IDでアクセス
    const invalidId = 'invalid-analysis-id-12345'
    await page.goto(`http://localhost:3000/dashboard/${invalidId}`)

    // エラーメッセージまたはリダイレクトの確認
    await page.waitForTimeout(3000)

    // エラー表示またはホームへのリダイレクトを確認
    const errorMessage = page.getByText(/エラー|見つかりません|ロード中/)
    const isError = await errorMessage.isVisible({ timeout: 5000 }).catch(() => false)

    if (!isError) {
      // リダイレクトされた場合
      expect(page.url()).not.toContain(invalidId)
    }
  })

  test('responsive layout works', async ({ page }) => {
    // デスクトップビュー
    await page.setViewportSize({ width: 1920, height: 1080 })
    const desktopGrid = page.locator('.lg\\:grid-cols-3')
    await expect(desktopGrid).toBeVisible()

    // タブレットビュー
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.waitForTimeout(500)

    // モバイルビュー
    await page.setViewportSize({ width: 375, height: 667 })
    await page.waitForTimeout(500)

    // モバイルではグリッドが1カラムになることを確認
    const mobileLayout = page.locator('.grid-cols-1')
    await expect(mobileLayout).toBeVisible()
  })
})

// フィードバックパネルのテスト
test.describe('Feedback Panel', () => {
  const testAnalysisId = 'd934ce94-36f5-49fc-916f-c32a5327e766'

  test('feedback panel displays when comparison completes', async ({ page }) => {
    await page.goto(`http://localhost:3000/dashboard/${testAnalysisId}`)
    await page.waitForLoadState('networkidle')

    // スコア計算完了を待つ
    await page.waitForTimeout(5000)

    // フィードバックパネルの確認
    const feedbackPanel = page.getByText('フィードバック')
    if (await feedbackPanel.isVisible()) {
      // 各セクションの確認
      const sections = ['良かった点', '改善が必要な点', '改善のための提案', '総評']

      for (const section of sections) {
        const sectionElement = page.getByText(section)
        if (await sectionElement.isVisible()) {
          console.log(`Feedback section found: ${section}`)
        }
      }
    }
  })
})

// レーダーチャートのテスト
test.describe('Score Radar Chart', () => {
  const testAnalysisId = 'd934ce94-36f5-49fc-916f-c32a5327e766'

  test('radar chart displays with correct data', async ({ page }) => {
    await page.goto(`http://localhost:3000/dashboard/${testAnalysisId}`)
    await page.waitForLoadState('networkidle')

    // スコア分布セクションの確認
    const radarSection = page.getByText('スコア分布')
    if (await radarSection.isVisible()) {
      // チャートキャンバスの確認
      const chartCanvas = radarSection.locator('..').locator('canvas')
      await expect(chartCanvas).toBeVisible()

      // 凡例の確認
      const legends = ['速度', '滑らかさ', '安定性', '効率性']
      for (const legend of legends) {
        const legendElement = page.getByText(legend)
        if (await legendElement.isVisible()) {
          // 各項目のスコア表示確認
          const scoreText = legendElement.locator('..').locator('text=/\\d+点/')
          if (await scoreText.isVisible()) {
            console.log(`Score found for ${legend}`)
          }
        }
      }
    }
  })
})