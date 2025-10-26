import { test, expect } from '@playwright/test'

test.describe('視線解析ダッシュボード分岐検証', () => {
  test('視線解析データでGazeDashboardClientが表示される', async ({ page }) => {
    // 視線解析のanalysis ID
    const gazeAnalysisId = 'ec54d15e-57b2-420b-8502-7cce2795d6a4'

    // コンソールログをキャプチャ
    const logs: string[] = []
    page.on('console', msg => {
      logs.push(msg.text())
    })

    // ダッシュボードページに移動
    await page.goto(`http://localhost:3000/dashboard/${gazeAnalysisId}`)

    // ページが読み込まれるまで待機
    await page.waitForLoadState('networkidle')

    // DashboardClientのログを確認
    const detectedLog = logs.find(log => log.includes('Detected eye_gaze analysis'))
    console.log('✅ 検出ログ:', detectedLog || '見つかりません')

    // 視線解析データの取得ログを確認
    const analysisDataLog = logs.find(log => log.includes('Analysis data received') && log.includes('eye_gaze'))
    console.log('✅ 解析データログ:', analysisDataLog || '見つかりません')

    // GazeDashboardClientが表示されているか確認
    // 視線解析ダッシュボード特有の要素を確認
    const gazeTitle = await page.locator('h1:has-text("視線解析ダッシュボード")').count()
    const gazeElements = await page.locator('text=ゲーズプロット').count()
    const heatmapElements = await page.locator('text=ヒートマップ').count()

    console.log('視線解析ダッシュボードタイトル:', gazeTitle)
    console.log('ゲーズプロット要素:', gazeElements)
    console.log('ヒートマップ要素:', heatmapElements)

    // いずれかの視線解析特有要素が存在することを確認
    const isGazeDashboard = gazeTitle > 0 || gazeElements > 0 || heatmapElements > 0

    if (!isGazeDashboard) {
      // 旧ダッシュボードが表示されている場合
      console.log('❌ エラー: 旧ダッシュボードが表示されています')

      // ページのHTML構造を確認
      const bodyText = await page.locator('body').textContent()
      console.log('表示されているテキスト:', bodyText?.substring(0, 500))

      // コンソールログを全て出力
      console.log('=== 全コンソールログ ===')
      logs.forEach(log => console.log(log))
    }

    expect(isGazeDashboard).toBe(true)
  })

  test('手技解析データで既存のDashboardClientが表示される', async ({ page }) => {
    // 手技解析のanalysis ID（適当なIDを使用）
    // ライブラリから最初の手技解析データを取得
    await page.goto('http://localhost:3000/library')
    await page.waitForLoadState('networkidle')

    // 視線解析以外のデータを探す
    const items = await page.locator('[class*="border-b"][class*="hover:bg-gray-50"]').all()

    let handAnalysisId: string | null = null

    for (const item of items) {
      const categoryBadge = await item.locator('span[class*="rounded-full"]').textContent()

      // 視線解析以外のカテゴリを探す
      if (categoryBadge && !categoryBadge.includes('視線解析')) {
        // このアイテムのIDを取得するためにクリック時のURLを確認
        const onClick = await item.getAttribute('onclick')
        if (onClick) {
          const match = onClick.match(/dashboard\/([a-f0-9-]+)/)
          if (match) {
            handAnalysisId = match[1]
            break
          }
        }
      }
    }

    if (!handAnalysisId) {
      console.log('⚠️ 手技解析データが見つかりません。テストをスキップします。')
      return
    }

    console.log('手技解析ID:', handAnalysisId)

    // ダッシュボードページに移動
    await page.goto(`http://localhost:3000/dashboard/${handAnalysisId}`)
    await page.waitForLoadState('networkidle')

    // 既存のダッシュボードが表示されているか確認
    const dashboardTitle = await page.locator('h1:has-text("解析結果")').count()
    const videoPlayer = await page.locator('video').count()

    console.log('解析結果タイトル:', dashboardTitle)
    console.log('ビデオプレイヤー:', videoPlayer)

    expect(dashboardTitle).toBeGreaterThan(0)
  })
})
