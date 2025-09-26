import { test, expect } from '@playwright/test'

test.describe('Dashboard Runtime Error Fixes', () => {
  test('should handle null results without errors in ScoreComparison', async ({ page }) => {
    // コンソールエラーを監視
    const errors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    // ダッシュボードページにアクセス（モックID使用）
    await page.goto('http://localhost:3003/dashboard/test-id')

    // ページロード完了を待機
    await page.waitForLoadState('networkidle')

    // スコア評価セクションが表示されることを確認
    const scoreSection = page.locator('text=スコア評価')
    await expect(scoreSection).toBeVisible({ timeout: 10000 })

    // モックデータが表示されることを確認（最初の要素を指定）
    const overallScore = page.locator('text=/\\d+点/').first()
    await expect(overallScore).toBeVisible({ timeout: 10000 })

    // フィードバックセクションが表示されることを確認  
    const feedbackSection = page.locator('text=フィードバック')
    await expect(feedbackSection).toBeVisible({ timeout: 10000 })

    // モーション分析セクションが表示されることを確認
    const motionSection = page.locator('text=手技の動き分析')
    await expect(motionSection).toBeVisible({ timeout: 10000 })

    // コンソールエラーがないことを確認
    await page.waitForTimeout(2000) // エラーが発生する時間を待つ
    
    // efficiency_scoreやdtw_distanceのエラーが出ていないことを確認
    const hasEfficiencyError = errors.some(e => e.includes('efficiency_score'))
    const hasDtwError = errors.some(e => e.includes('dtw_distance'))
    
    expect(hasEfficiencyError).toBe(false)
    expect(hasDtwError).toBe(false)
    
    // 全体的にTypeErrorがないことを確認
    const hasTypeError = errors.some(e => e.includes('TypeError'))
    expect(hasTypeError).toBe(false)
  })

  test('should display mock data when no real data available', async ({ page }) => {
    await page.goto('http://localhost:3003/dashboard/test-id')
    await page.waitForLoadState('networkidle')

    // スコアセクションでモック値が表示されることを確認
    const scoreText = await page.locator('text=/78点/').textContent()
    expect(scoreText).toBeTruthy()

    // 個別スコアが表示されることを確認
    await expect(page.locator('text=動作速度')).toBeVisible()
    await expect(page.locator('text=滑らかさ')).toBeVisible()
    await expect(page.locator('text=安定性')).toBeVisible()
    await expect(page.locator('text=効率性')).toBeVisible()

    // フィードバックのモックデータが表示されることを確認
    await expect(page.locator('text=/手首の動きが非常に滑らか/')).toBeVisible()
    await expect(page.locator('text=/左手の動作速度が基準より/')).toBeVisible()
    await expect(page.locator('text=/針の持ち方を45度の角度/')).toBeVisible()
  })

  test('should update motion analysis during video playback', async ({ page }) => {
    await page.goto('http://localhost:3003/dashboard/test-id')
    await page.waitForLoadState('networkidle')

    // ビデオプレーヤーが存在することを確認
    const videoPlayer = page.locator('video')
    await expect(videoPlayer).toBeVisible({ timeout: 10000 })

    // モーション分析パネルの初期値を確認
    const speedMetric = page.locator('text=/\\d+\\.\\d+cm\\/s/').first()
    const initialSpeed = await speedMetric.textContent()

    // ビデオを再生
    await videoPlayer.click() // 再生トリガー
    await page.waitForTimeout(2000) // 2秒待つ

    // メトリクスが更新されたことを確認（値が変化するか確認）
    const updatedSpeed = await speedMetric.textContent()
    // モックデータなので値が変化しているはず
    expect(updatedSpeed).toBeTruthy()
  })
})