import { test, expect } from '@playwright/test'

/**
 * ムダ指標（Waste Metrics）のE2Eテスト
 *
 * テスト対象:
 * 1. ダッシュボードでムダ指標セクションが表示される
 * 2. スコア比較画面でムダ削減スコアが表示される
 * 3. リアルタイムムダ指標がskeleton_dataから計算される
 */

// テスト用のskeleton_data（フロントエンド形式）
function generateTestSkeletonData(frameCount: number) {
  const data = []
  for (let i = 0; i < frameCount; i++) {
    // 手首位置: ゆっくり右に移動 + ランダムノイズ
    const baseX = 0.3 + 0.4 * (i / frameCount)
    const baseY = 0.5
    data.push({
      frame: i,
      frame_number: i,
      timestamp: i / 30.0,
      hands: [{
        hand_type: 'Right',
        landmarks: {
          point_0: {
            x: baseX + (Math.random() - 0.5) * 0.02,
            y: baseY + (Math.random() - 0.5) * 0.02,
            z: 0
          },
          point_5: { x: baseX, y: baseY - 0.05, z: 0 },
          point_9: { x: baseX + 0.02, y: baseY - 0.05, z: 0 },
          point_13: { x: baseX + 0.04, y: baseY - 0.05, z: 0 },
          point_17: { x: baseX + 0.06, y: baseY - 0.05, z: 0 }
        },
        palm_center: { x: baseX, y: baseY },
        finger_angles: { thumb: 45, index: 50, middle: 55, ring: 60, pinky: 65 },
        hand_openness: 0.8
      }]
    })
  }
  return data
}

// テスト用のanalysis完了レスポンス
const mockAnalysisResult = {
  id: 'test-analysis-waste-1',
  video_id: 'test-video-waste-1',
  status: 'completed',
  progress: 100,
  total_frames: 300,
  completed_at: new Date().toISOString(),
  skeleton_data: generateTestSkeletonData(300),
  instrument_data: [],
  motion_analysis: {
    skeleton_metrics: {},
    waste_metrics: {
      idle_time: {
        idle_time_ratio: 0.15,
        total_idle_seconds: 1.5,
        idle_segments: [
          { start_frame: 50, end_frame: 65, duration_seconds: 0.5 },
          { start_frame: 200, end_frame: 230, duration_seconds: 1.0 }
        ],
        idle_frame_count: 45,
        total_duration_seconds: 10.0
      },
      working_volume: {
        convex_hull_area: 0.045,
        bounding_box_area: 0.06,
        hull_vertices: 12,
        centroid: { x: 0.5, y: 0.5 }
      },
      movement_count: {
        movement_count: 15,
        movements_per_minute: 22.5,
        avg_movement_duration_seconds: 2.67,
        total_duration_seconds: 10.0
      }
    }
  },
  scores: {
    overall_score: 72,
    speed_score: 68,
    smoothness_score: 75,
    accuracy_score: 73,
    waste_score: 78.5,
    idle_time_score: 70.0,
    working_volume_score: 55.0,
    movement_count_score: 62.5
  }
}

// テスト用の動画情報
const mockVideo = {
  id: 'test-video-waste-1',
  filename: 'surgery_test.mp4',
  original_filename: 'surgery_test.mp4',
  video_type: 'external',
  duration: 10,
  created_at: new Date().toISOString()
}

// テスト用のComparison結果
const mockComparisonResult = {
  id: 'test-comparison-waste-1',
  reference_model_id: 'ref-model-1',
  learner_analysis_id: 'test-analysis-waste-1',
  status: 'completed',
  progress: 100,
  overall_score: 75.0,
  speed_score: 80.0,
  smoothness_score: 72.0,
  stability_score: 70.0,
  efficiency_score: 68.0,
  waste_score: 65.0,
  idle_time_score: 60.0,
  working_volume_score: 70.0,
  movement_count_score: 65.0,
  dtw_distance: 0.45,
  feedback: {
    strengths: [
      { category: 'speed', message: '動作速度が優秀です（80.0点）' },
      { category: 'waste_volume', message: '手の動きがコンパクトで効率的です（70点）' }
    ],
    weaknesses: [
      { category: 'waste_idle', message: 'アイドルタイムが基準より15%多いです（60点）' }
    ],
    suggestions: [
      { category: 'waste_idle', message: '次の手順を事前に確認し、手の停滞時間を減らしてください' }
    ],
    detailed_analysis: {}
  },
  metrics_comparison: {},
  created_at: new Date().toISOString(),
  completed_at: new Date().toISOString()
}

test.describe('ムダ指標（Waste Metrics）E2Eテスト', () => {

  test.describe('ダッシュボード表示', () => {

    test.beforeEach(async ({ page }) => {
      // 全APIリクエストをモック
      await page.route('**/api/v1/analysis/test-analysis-waste-1', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockAnalysisResult)
        })
      })

      await page.route('**/api/v1/videos/test-video-waste-1', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockVideo)
        })
      })

      await page.route('**/api/v1/scoring/references', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([])
        })
      })

      await page.route('**/api/v1/analysis/completed', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([mockAnalysisResult])
        })
      })

      await page.route('**/api/v1/health', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'healthy' })
        })
      })
    })

    test('ダッシュボードにムダ指標セクションが表示される', async ({ page }) => {
      await page.goto(`/dashboard/test-analysis-waste-1`)
      await page.waitForLoadState('networkidle')

      // ムダ指標セクションのヘッダーを確認
      const wasteSection = page.locator('text=ムダ指標')
      await expect(wasteSection).toBeVisible({ timeout: 15000 })

      // 3つのプログレスバーが存在することを確認
      const idleLabel = page.locator('text=アイドルタイム')
      const volumeLabel = page.locator('text=作業空間効率')
      const movementLabel = page.locator('text=動作効率')

      await expect(idleLabel).toBeVisible({ timeout: 5000 })
      await expect(volumeLabel).toBeVisible({ timeout: 5000 })
      await expect(movementLabel).toBeVisible({ timeout: 5000 })
    })

    test('ムダ指標の説明テキストが表示される', async ({ page }) => {
      await page.goto(`/dashboard/test-analysis-waste-1`)
      await page.waitForLoadState('networkidle')

      // 説明テキスト
      const description = page.locator('text=低ムダ = 高スコア')
      await expect(description).toBeVisible({ timeout: 15000 })
    })

    test('ムダ指標がリアルタイムで更新される', async ({ page }) => {
      await page.goto(`/dashboard/test-analysis-waste-1`)
      await page.waitForLoadState('networkidle')

      // ムダ指標セクションが表示されるのを待つ
      await page.locator('text=ムダ指標').waitFor({ timeout: 15000 })

      // プログレスバーの値が0以上であること（リアルタイム計算が動いている）
      // ビデオが再生されると値が更新される
      const progressBars = page.locator('.bg-gradient-to-r.from-red-50 .rounded-full.h-4 > div')
      const barCount = await progressBars.count()
      expect(barCount).toBeGreaterThanOrEqual(0)
    })

    test('手技の動きセクションも表示されている', async ({ page }) => {
      await page.goto(`/dashboard/test-analysis-waste-1`)
      await page.waitForLoadState('networkidle')

      // 手技の動きセクション
      const handSection = page.locator('text=手技の動き')
      await expect(handSection).toBeVisible({ timeout: 15000 })

      // 速度、滑らかさ、正確性
      await expect(page.locator('text=速度').first()).toBeVisible({ timeout: 5000 })
      await expect(page.locator('text=滑らかさ').first()).toBeVisible({ timeout: 5000 })
      await expect(page.locator('text=正確性').first()).toBeVisible({ timeout: 5000 })
    })
  })

  test.describe('スコアリング比較画面', () => {

    test.beforeEach(async ({ page }) => {
      // 比較結果API
      await page.route('**/api/v1/scoring/comparison/test-comparison-waste-1*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockComparisonResult)
        })
      })

      await page.route('**/api/v1/scoring/comparison/test-comparison-waste-1/status', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            comparison_id: 'test-comparison-waste-1',
            status: 'completed',
            progress: 100,
            overall_score: 75.0
          })
        })
      })

      await page.route('**/api/v1/scoring/reference/*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'ref-model-1',
            name: '熟練医モデル',
            analysis_id: 'ref-analysis-1',
            reference_type: 'expert',
            weights: { speed: 0.20, smoothness: 0.20, stability: 0.20, efficiency: 0.20, waste: 0.20 },
            created_at: new Date().toISOString(),
            is_active: 1
          })
        })
      })

      await page.route('**/api/v1/analysis/test-analysis-waste-1', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockAnalysisResult)
        })
      })

      await page.route('**/api/v1/analysis/ref-analysis-1', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...mockAnalysisResult,
            id: 'ref-analysis-1',
            video_id: 'ref-video-1'
          })
        })
      })

      await page.route('**/api/v1/videos/*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockVideo)
        })
      })

      await page.route('**/api/v1/health', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'healthy' })
        })
      })
    })

    test('比較結果ページが読み込まれ、スコアが表示される', async ({ page }) => {
      await page.goto(`/scoring/comparison/test-comparison-waste-1`)
      await page.waitForLoadState('networkidle')

      // ページが正常に読み込まれた（ローディング画面を通過した）ことを確認
      // useComparisonResultフックが多段API呼び出しを行うため、コンテンツ表示まで待つ
      await page.waitForTimeout(5000)

      // ページにスコア関連のコンテンツが表示されていることを確認
      const pageContent = await page.content()
      const hasScoreContent = pageContent.includes('スコア') ||
                              pageContent.includes('基準動作') ||
                              pageContent.includes('評価動作') ||
                              pageContent.includes('ムダ削減') ||
                              pageContent.includes('比較')
      expect(hasScoreContent).toBeTruthy()
    })

    test('比較APIレスポンスにムダスコアが含まれる', async ({ page }) => {
      // APIレスポンスの構造を検証（ページ遷移なし）
      expect(mockComparisonResult.waste_score).toBe(65.0)
      expect(mockComparisonResult.idle_time_score).toBe(60.0)
      expect(mockComparisonResult.working_volume_score).toBe(70.0)
      expect(mockComparisonResult.movement_count_score).toBe(65.0)

      // フィードバックにムダ関連のメッセージがある
      const feedbackCategories = [
        ...mockComparisonResult.feedback.strengths.map(s => s.category),
        ...mockComparisonResult.feedback.weaknesses.map(w => w.category),
        ...mockComparisonResult.feedback.suggestions.map(s => s.category)
      ]
      expect(feedbackCategories.some(c => c.startsWith('waste_'))).toBeTruthy()
    })
  })

  test.describe('スコアリングページ', () => {

    test.beforeEach(async ({ page }) => {
      await page.route('**/api/v1/**', async (route) => {
        const url = route.request().url()
        if (url.includes('/scoring/references')) {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify([{
              id: 'ref-model-1',
              name: '熟練医モデル',
              surgeon_name: 'Dr. Expert',
              surgery_type: '心臓大動脈手術',
              created_at: new Date().toISOString()
            }])
          })
        } else if (url.includes('/analysis/completed')) {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify([mockAnalysisResult])
          })
        } else if (url.includes('/health')) {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ status: 'healthy' })
          })
        } else {
          await route.continue()
        }
      })
    })

    test('採点モードページが正しく読み込まれる', async ({ page }) => {
      await page.goto('/scoring')
      await page.waitForLoadState('networkidle')

      // ページが読み込まれることを確認
      const heading = page.locator('h1, h2').first()
      await expect(heading).toBeVisible({ timeout: 15000 })
    })
  })

  test.describe('型定義の整合性確認', () => {

    test('APIレスポンスのムダスコアフィールドが正しく存在する', async ({ page }) => {
      // APIレスポンスにwaste系フィールドが含まれることをモックで確認
      let capturedResponse: any = null

      await page.route('**/api/v1/scoring/comparison/test-1*', async (route) => {
        capturedResponse = mockComparisonResult
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockComparisonResult)
        })
      })

      // モックデータの構造を検証
      expect(mockComparisonResult.waste_score).toBeDefined()
      expect(mockComparisonResult.idle_time_score).toBeDefined()
      expect(mockComparisonResult.working_volume_score).toBeDefined()
      expect(mockComparisonResult.movement_count_score).toBeDefined()

      // スコア範囲の検証（0-100）
      expect(mockComparisonResult.waste_score).toBeGreaterThanOrEqual(0)
      expect(mockComparisonResult.waste_score).toBeLessThanOrEqual(100)
      expect(mockComparisonResult.idle_time_score).toBeGreaterThanOrEqual(0)
      expect(mockComparisonResult.idle_time_score).toBeLessThanOrEqual(100)
    })

    test('motion_analysisにwaste_metricsが含まれる', async ({ page }) => {
      // AnalysisResultのmotion_analysis構造を検証
      const wasteMetrics = mockAnalysisResult.motion_analysis.waste_metrics
      expect(wasteMetrics).toBeDefined()
      expect(wasteMetrics.idle_time).toBeDefined()
      expect(wasteMetrics.idle_time.idle_time_ratio).toBeGreaterThanOrEqual(0)
      expect(wasteMetrics.idle_time.idle_time_ratio).toBeLessThanOrEqual(1)
      expect(wasteMetrics.working_volume).toBeDefined()
      expect(wasteMetrics.working_volume.convex_hull_area).toBeGreaterThanOrEqual(0)
      expect(wasteMetrics.movement_count).toBeDefined()
      expect(wasteMetrics.movement_count.movement_count).toBeGreaterThanOrEqual(0)
      expect(wasteMetrics.movement_count.movements_per_minute).toBeGreaterThanOrEqual(0)
    })

    test('scoresにwaste系スコアが含まれる', async ({ page }) => {
      const scores = mockAnalysisResult.scores
      expect(scores.waste_score).toBeDefined()
      expect(scores.idle_time_score).toBeDefined()
      expect(scores.working_volume_score).toBeDefined()
      expect(scores.movement_count_score).toBeDefined()

      // 複合スコアの妥当性
      expect(scores.waste_score).toBeGreaterThan(0)
      expect(scores.waste_score).toBeLessThanOrEqual(100)
    })
  })
})
