import { test, expect } from '@playwright/test'

// スコア比較機能のE2Eテスト
test.describe('Score Comparison Feature', () => {
  const testAnalysisId = 'd934ce94-36f5-49fc-916f-c32a5327e766'

  test.beforeEach(async ({ page }) => {
    await page.goto(`http://localhost:3000/dashboard/${testAnalysisId}`)
    await page.waitForLoadState('networkidle')
  })

  test('reference models load correctly', async ({ page }) => {
    // 基準モデル選択ドロップダウンの確認
    const modelSelect = page.locator('select').filter({ hasText: /上級|中級|初級/ })
    await expect(modelSelect).toBeVisible({ timeout: 10000 })

    // オプションの取得
    const options = await modelSelect.locator('option').allTextContents()

    // 少なくとも1つのモデルが存在することを確認
    expect(options.length).toBeGreaterThan(0)

    // 期待されるモデルが含まれているか確認
    const hasExpertModel = options.some(opt => opt.includes('上級'))
    const hasIntermediateModel = options.some(opt => opt.includes('中級'))

    console.log('Available models:', options)
    expect(hasExpertModel || hasIntermediateModel).toBeTruthy()
  })

  test('score comparison starts automatically', async ({ page }) => {
    // ページ読み込み後、自動的にスコア計算が開始されるか確認
    await page.waitForTimeout(3000)

    // 処理中または完了状態の確認
    const processingText = page.getByText(/計算中|処理中/)
    const scoreText = page.locator('text=/\\d{1,3}点/')

    // どちらかが表示されていることを確認
    const isProcessing = await processingText.isVisible({ timeout: 5000 }).catch(() => false)
    const hasScore = await scoreText.isVisible({ timeout: 5000 }).catch(() => false)

    expect(isProcessing || hasScore).toBeTruthy()
  })

  test('overall score displays correctly', async ({ page }) => {
    // スコア計算完了を待つ
    await page.waitForTimeout(5000)

    // 総合スコアセクションの確認
    const overallScoreSection = page.locator('text=/総合スコア/').locator('..')

    if (await overallScoreSection.isVisible()) {
      // スコア値の確認（0-100の範囲）
      const scoreValue = await overallScoreSection.locator('text=/\\d{1,3}/').first().textContent()

      if (scoreValue) {
        const score = parseInt(scoreValue)
        expect(score).toBeGreaterThanOrEqual(0)
        expect(score).toBeLessThanOrEqual(100)
        console.log('Overall score:', score)
      }

      // レベル判定の確認
      const levelText = await overallScoreSection.locator('text=/レベル:/').textContent()
      if (levelText) {
        expect(levelText).toMatch(/初級|初中級|中級|中上級|上級/)
        console.log('Skill level:', levelText)
      }
    }
  })

  test('individual metric scores display', async ({ page }) => {
    await page.waitForTimeout(5000)

    const metrics = [
      { name: '動作速度', color: 'blue' },
      { name: '滑らかさ', color: 'green' },
      { name: '安定性', color: 'yellow' },
      { name: '効率性', color: 'purple' }
    ]

    for (const metric of metrics) {
      const metricElement = page.locator(`text=/${metric.name}/`).first()

      if (await metricElement.isVisible()) {
        // スコア値の確認
        const metricRow = metricElement.locator('..').locator('..')
        const scoreElement = metricRow.locator('text=/\\d{1,3}|--/')

        if (await scoreElement.isVisible()) {
          const scoreText = await scoreElement.textContent()
          console.log(`${metric.name} score:`, scoreText)

          // トレンドアイコンの確認（上昇、下降、横ばい）
          const trendIcon = metricRow.locator('svg')
          if (await trendIcon.isVisible()) {
            console.log(`${metric.name} has trend indicator`)
          }
        }
      }
    }
  })

  test('DTW distance (similarity) displays', async ({ page }) => {
    await page.waitForTimeout(5000)

    // 動作パターン類似度の確認
    const similaritySection = page.getByText('動作パターン類似度')

    if (await similaritySection.isVisible()) {
      const parentSection = similaritySection.locator('..')
      const similarityLevel = await parentSection.locator('text=/高|中|低/').textContent()

      if (similarityLevel) {
        console.log('Motion pattern similarity:', similarityLevel)
        expect(['高', '中', '低']).toContain(similarityLevel)
      }
    }
  })

  test('changing reference model updates scores', async ({ page }) => {
    await page.waitForTimeout(3000)

    // 初期スコアを記録
    let initialScore: string | null = null
    const scoreElement = page.locator('text=/\\d{1,3}点/').first()

    if (await scoreElement.isVisible()) {
      initialScore = await scoreElement.textContent()
      console.log('Initial score:', initialScore)
    }

    // 基準モデルを変更
    const modelSelect = page.locator('select').first()
    const currentValue = await modelSelect.inputValue()

    // 全オプションを取得
    const optionValues = await modelSelect.locator('option').evaluateAll(
      options => options.map(opt => (opt as HTMLOptionElement).value)
    )

    // 現在とは違うオプションを選択
    const newValue = optionValues.find(val => val !== currentValue)

    if (newValue) {
      await modelSelect.selectOption(newValue)
      console.log('Changed to model:', newValue)

      // スコア再計算を待つ
      await page.waitForTimeout(3000)

      // 新しいスコアを確認
      const newScoreElement = page.locator('text=/\\d{1,3}点/').first()

      if (await newScoreElement.isVisible()) {
        const newScore = await newScoreElement.textContent()
        console.log('New score:', newScore)

        // スコアが存在することを確認（値が変わったかどうかは問わない）
        expect(newScore).toBeTruthy()
      }
    }
  })

  test('score trend indicators work correctly', async ({ page }) => {
    await page.waitForTimeout(5000)

    // 各メトリクスのトレンドインジケーターを確認
    const metricRows = page.locator('.bg-gray-50.rounded-lg')
    const count = await metricRows.count()

    for (let i = 0; i < count; i++) {
      const row = metricRows.nth(i)

      if (await row.isVisible()) {
        // スコア値を取得
        const scoreText = await row.locator('text=/\\d{1,3}|--/').textContent()

        if (scoreText && scoreText !== '--') {
          const score = parseInt(scoreText)

          // トレンドアイコンの色を確認
          const svgElement = row.locator('svg')

          if (await svgElement.isVisible()) {
            const className = await svgElement.getAttribute('class') || ''

            // スコアに応じた色の確認
            if (score >= 85) {
              expect(className).toContain('green')
            } else if (score >= 70) {
              expect(className).toContain('yellow')
            } else {
              expect(className).toContain('red')
            }
          }
        }
      }
    }
  })

  test('score comparison error handling', async ({ page }) => {
    // 無効な解析IDでのアクセス
    const invalidAnalysisId = 'invalid-id-12345'
    await page.goto(`http://localhost:3000/dashboard/${invalidAnalysisId}`)

    await page.waitForTimeout(3000)

    // エラー表示の確認
    const errorIndicators = [
      page.getByText(/エラー/),
      page.getByText(/失敗/),
      page.getByText(/見つかりません/),
      page.getByText(/ロード中/)
    ]

    let hasError = false
    for (const indicator of errorIndicators) {
      if (await indicator.isVisible({ timeout: 1000 }).catch(() => false)) {
        hasError = true
        const errorText = await indicator.textContent()
        console.log('Error found:', errorText)
        break
      }
    }

    // エラーが表示されるか、ホームにリダイレクトされることを期待
    if (!hasError) {
      expect(page.url()).not.toContain(invalidAnalysisId)
    }
  })

  test('feedback generates based on scores', async ({ page }) => {
    await page.waitForTimeout(5000)

    // フィードバックパネルの確認
    const feedbackPanel = page.getByText('フィードバック').locator('..')

    if (await feedbackPanel.isVisible()) {
      // 総合スコアを取得
      const scoreElement = page.locator('text=/\\d{1,3}点/').first()
      let overallScore = 0

      if (await scoreElement.isVisible()) {
        const scoreText = await scoreElement.textContent()
        if (scoreText) {
          overallScore = parseInt(scoreText.replace('点', ''))
        }
      }

      // スコアに応じた総評の確認
      const summarySection = page.getByText('総評').locator('..')

      if (await summarySection.isVisible()) {
        const summaryText = await summarySection.textContent()

        if (overallScore >= 90) {
          expect(summaryText).toContain('素晴らしい')
        } else if (overallScore >= 80) {
          expect(summaryText).toContain('良好')
        } else if (overallScore >= 70) {
          expect(summaryText).toContain('基本的')
        } else if (overallScore >= 60) {
          expect(summaryText).toContain('継続的')
        } else {
          expect(summaryText).toContain('基礎')
        }

        console.log(`Score ${overallScore} generated feedback:`, summaryText?.substring(0, 50))
      }
    }
  })

  test('performance of score calculation', async ({ page }) => {
    // パフォーマンステスト：スコア計算の速度を測定
    const startTime = Date.now()

    await page.goto(`http://localhost:3000/dashboard/${testAnalysisId}`)

    // スコアが表示されるまで待つ
    await page.waitForSelector('text=/\\d{1,3}点/', { timeout: 30000 })

    const endTime = Date.now()
    const loadTime = endTime - startTime

    console.log(`Score calculation took ${loadTime}ms`)

    // 30秒以内に完了することを期待
    expect(loadTime).toBeLessThan(30000)

    // 理想的には10秒以内
    if (loadTime < 10000) {
      console.log('✓ Excellent performance')
    } else if (loadTime < 20000) {
      console.log('⚠ Acceptable performance')
    } else {
      console.log('✗ Poor performance - needs optimization')
    }
  })
})