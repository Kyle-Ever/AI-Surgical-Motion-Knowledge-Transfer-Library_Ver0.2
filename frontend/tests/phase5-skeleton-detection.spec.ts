import { test, expect } from '@playwright/test'

/**
 * Phase 5 E2Eテスト: 骨格検出の確認
 *
 * 目的:
 * 1. EXTERNAL_NO_INSTRUMENTS解析で骨格データが正しく取得されるか
 * 2. ダッシュボードで骨格データが表示されるか
 * 3. 新しいフロントエンド互換形式が機能するか
 */

test.describe('Phase 5: 骨格検出テスト', () => {
  test('既存の骨格解析結果を確認', async ({ page }) => {
    // 既知の解析ID（Phase 0で作成されたもの）
    const analysisId = '3493e268-6b94-471b-b21b-fe95f2a6cc59'

    // ダッシュボードに移動
    await page.goto(`http://localhost:3001/dashboard/${analysisId}`)

    // ページが読み込まれるまで待機
    await page.waitForLoadState('networkidle')

    // タイトルを確認
    await expect(page.locator('h1, h2').first()).toBeVisible()

    // 解析結果セクションを確認
    const analysisSection = page.locator('text=解析結果').or(page.locator('text=Analysis Result'))
    await expect(analysisSection).toBeVisible({ timeout: 10000 })

    // 骨格データの存在確認（コンソールログをチェック）
    const consoleMessages: string[] = []
    page.on('console', msg => {
      consoleMessages.push(msg.text())
    })

    // ページをリロードしてコンソールログを取得
    await page.reload()
    await page.waitForLoadState('networkidle')

    // 5秒待機してコンソールログを収集
    await page.waitForTimeout(5000)

    // VideoPlayerのログを確認
    const skeletonLog = consoleMessages.find(msg =>
      msg.includes('skeletonData_length') || msg.includes('skeleton')
    )

    if (skeletonLog) {
      console.log('📊 Skeleton data log found:', skeletonLog)

      // skeletonData_lengthが0より大きいことを確認
      const lengthMatch = skeletonLog.match(/skeletonData_length[:\s]+(\d+)/)
      if (lengthMatch) {
        const length = parseInt(lengthMatch[1])
        console.log(`✅ Skeleton data length: ${length}`)
        expect(length).toBeGreaterThan(0)
      }
    }

    // ビデオプレイヤーの存在確認
    const videoPlayer = page.locator('video').or(page.locator('canvas'))
    await expect(videoPlayer.first()).toBeVisible({ timeout: 10000 })

    // スクリーンショットを保存
    await page.screenshot({
      path: 'test-results/phase5-skeleton-dashboard.png',
      fullPage: true
    })

    console.log('✅ 骨格検出ダッシュボード表示テスト: 完了')
  })

  test('API経由で骨格データ形式を確認', async ({ request }) => {
    const analysisId = '3493e268-6b94-471b-b21b-fe95f2a6cc59'

    // 解析結果APIを呼び出し
    const response = await request.get(`http://localhost:8000/api/v1/analysis/${analysisId}`)
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    console.log('📊 Analysis data received:', {
      id: data.id,
      status: data.status,
      skeleton_data_length: data.skeleton_data?.length || 0,
      instrument_data_length: data.instrument_data?.length || 0
    })

    // 骨格データの存在確認
    expect(data.skeleton_data).toBeDefined()
    expect(data.skeleton_data.length).toBeGreaterThan(0)

    // 新しいフロントエンド互換形式の確認
    const firstFrame = data.skeleton_data[0]
    console.log('🔍 First frame structure:', Object.keys(firstFrame))

    // 期待されるキーの確認
    expect(firstFrame).toHaveProperty('frame')
    expect(firstFrame).toHaveProperty('frame_number')
    expect(firstFrame).toHaveProperty('timestamp')
    expect(firstFrame).toHaveProperty('hands')

    // handsが配列であることを確認
    expect(Array.isArray(firstFrame.hands)).toBeTruthy()

    if (firstFrame.hands.length > 0) {
      const firstHand = firstFrame.hands[0]
      console.log('🖐️  First hand structure:', Object.keys(firstHand))

      // 手のデータ構造確認
      expect(firstHand).toHaveProperty('hand_type')
      expect(firstHand).toHaveProperty('landmarks')

      console.log(`✅ Skeleton data format: Frontend compatible`)
      console.log(`   - Frames: ${data.skeleton_data.length}`)
      console.log(`   - Hands in first frame: ${firstFrame.hands.length}`)
      console.log(`   - Hand type: ${firstHand.hand_type}`)
    } else {
      console.log('⚠️  No hands detected in first frame')
    }
  })

  test('履歴ページから骨格解析を確認', async ({ page }) => {
    // 履歴ページに移動
    await page.goto('http://localhost:3001/history')
    await page.waitForLoadState('networkidle')

    // 完了した解析を検索
    const completedAnalysis = page.locator('text=完了').or(page.locator('text=Completed')).first()
    await expect(completedAnalysis).toBeVisible({ timeout: 10000 })

    // 解析カードをクリック
    const analysisCard = page.locator('[data-testid="analysis-card"]').first()
      .or(page.locator('div').filter({ hasText: /完了|Completed/ }).first())

    if (await analysisCard.isVisible()) {
      await analysisCard.click()

      // ダッシュボードに遷移したことを確認
      await expect(page).toHaveURL(/\/dashboard\/[a-f0-9-]+/)

      // 骨格データの表示を確認
      const videoPlayer = page.locator('video').or(page.locator('canvas'))
      await expect(videoPlayer.first()).toBeVisible({ timeout: 10000 })

      console.log('✅ 履歴ページからの骨格解析確認: 完了')
    }
  })
})
