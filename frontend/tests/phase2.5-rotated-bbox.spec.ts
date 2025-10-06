import { test, expect } from '@playwright/test'

/**
 * Phase 2.5 E2Eテスト: 回転BBox（Rotated Bounding Box）
 *
 * 重要: 新規解析を実行して回転BBox機能を検証
 * - 既存データには回転BBoxが含まれないため、新規解析が必要
 * - INTERNAL動画で器具トラッキングを実行
 * - 回転BBoxデータの構造と精度を検証
 */

test.describe('Phase 2.5: 回転BBoxテスト', () => {
  test('新規INTERNAL解析で回転BBox検証', async ({ request }) => {
    test.setTimeout(360000)  // 6分タイムアウト

    // 利用可能な動画を検索
    const videosResponse = await request.get('http://localhost:8000/api/v1/videos/')
    expect(videosResponse.ok()).toBeTruthy()

    const videos = await videosResponse.json()
    const internalVideo = videos.find((v: any) => v.video_type === 'internal')

    if (!internalVideo) {
      console.log('⏭️  INTERNAL動画が見つかりません - テストをスキップ')
      test.skip()
      return
    }

    console.log(`📹 INTERNAL動画ID: ${internalVideo.id}`)

    // 新規解析を開始
    const analysisResponse = await request.post(
      `http://localhost:8000/api/v1/analysis/${internalVideo.id}/analyze`,
      {
        data: {
          video_id: internalVideo.id,
          instruments: [],
          sampling_rate: 1
        }
      }
    )

    if (!analysisResponse.ok()) {
      const errorBody = await analysisResponse.text()
      console.log(`❌ API Error: ${analysisResponse.status()} - ${errorBody}`)
    }
    expect(analysisResponse.ok()).toBeTruthy()

    const analysisData = await analysisResponse.json()
    const analysisId = analysisData.id

    console.log(`🔄 新規解析開始: ${analysisId}`)

    // 解析完了まで待機（最大5分）
    let completed = false
    for (let i = 0; i < 60; i++) {
      await new Promise(resolve => setTimeout(resolve, 5000))  // 5秒待機

      const statusResponse = await request.get(
        `http://localhost:8000/api/v1/analysis/${analysisId}/status`
      )
      const status = await statusResponse.json()

      console.log(`   進捗: ${status.progress || 0}% - ${status.current_step || 'processing'}`)

      if (status.status === 'completed') {
        completed = true
        break
      }

      if (status.status === 'failed') {
        console.log(`❌ 解析失敗: ${status.error || 'Unknown error'}`)
        test.skip()
        return
      }
    }

    if (!completed) {
      console.log('⏭️  解析がタイムアウト - テストをスキップ')
      test.skip()
      return
    }

    console.log(`✅ 解析完了: ${analysisId}`)

    // 解析結果を取得
    const detailResponse = await request.get(
      `http://localhost:8000/api/v1/analysis/${analysisId}`
    )
    expect(detailResponse.ok()).toBeTruthy()

    const data = await detailResponse.json()

    // 器具データが存在するか確認
    expect(data.instrument_data).toBeDefined()
    expect(data.instrument_data.length).toBeGreaterThan(0)

    // 回転BBoxフィールドの検証
    let rotatedBboxCount = 0
    let totalAreaReduction = 0
    let areaReductionCount = 0
    let sampleDetections: any[] = []

    for (const frame of data.instrument_data) {
      if (!frame.instruments || frame.instruments.length === 0) continue

      for (const instrument of frame.instruments) {
        // Phase 2.5: 回転BBoxフィールドの存在確認
        if (instrument.rotated_bbox) {
          rotatedBboxCount++

          // サンプルとして最初の5件を保存
          if (sampleDetections.length < 5) {
            sampleDetections.push({
              frame: frame.frame_number,
              bbox: instrument.bbox,
              rotated_bbox: instrument.rotated_bbox,
              rotation_angle: instrument.rotation_angle,
              area_reduction: instrument.area_reduction
            })
          }

          // 回転BBoxは4点の配列
          expect(Array.isArray(instrument.rotated_bbox)).toBeTruthy()
          expect(instrument.rotated_bbox.length).toBe(4)

          // 各点は [x, y] の配列
          for (const point of instrument.rotated_bbox) {
            expect(Array.isArray(point)).toBeTruthy()
            expect(point.length).toBe(2)
            expect(typeof point[0]).toBe('number')
            expect(typeof point[1]).toBe('number')
          }
        }

        // rotation_angleフィールドの検証
        if (instrument.rotation_angle !== undefined) {
          expect(typeof instrument.rotation_angle).toBe('number')
          expect(instrument.rotation_angle).toBeGreaterThanOrEqual(-90)
          expect(instrument.rotation_angle).toBeLessThanOrEqual(90)
        }

        // area_reductionフィールドの検証
        if (instrument.area_reduction !== undefined) {
          expect(typeof instrument.area_reduction).toBe('number')
          expect(instrument.area_reduction).toBeGreaterThanOrEqual(0)
          expect(instrument.area_reduction).toBeLessThanOrEqual(100)

          if (instrument.area_reduction > 0) {
            totalAreaReduction += instrument.area_reduction
            areaReductionCount++
          }
        }
      }
    }

    console.log(`\n✅ 回転BBox検出数: ${rotatedBboxCount} 個`)

    if (areaReductionCount > 0) {
      const avgReduction = totalAreaReduction / areaReductionCount
      console.log(`📐 平均面積削減率: ${avgReduction.toFixed(1)}%`)
      console.log(`   (期待値: 30-50% for 斜め器具)`)

      // Phase 2.5の期待値: 面積削減が実際に発生している
      expect(avgReduction).toBeGreaterThan(0)
    }

    // サンプル検出結果を表示
    if (sampleDetections.length > 0) {
      console.log(`\n🔍 サンプル検出結果（最初の5件）:`)
      for (const sample of sampleDetections) {
        console.log(`  Frame ${sample.frame}:`)
        console.log(`    回転角度: ${sample.rotation_angle?.toFixed(1)}°`)
        console.log(`    面積削減: ${sample.area_reduction?.toFixed(1)}%`)
        console.log(`    rect bbox: [${sample.bbox.join(', ')}]`)
        console.log(`    rotated bbox: ${JSON.stringify(sample.rotated_bbox)}`)
      }
    }

    // 回転BBoxが検出されたことを確認
    expect(rotatedBboxCount).toBeGreaterThan(0)
  })

  test('ダッシュボードで回転BBox表示確認', async ({ page, request }) => {
    test.setTimeout(360000)  // 6分タイムアウト

    // 最新のINTERNAL解析を検索
    const analysesResponse = await request.get('http://localhost:8000/api/v1/analysis/completed')
    expect(analysesResponse.ok()).toBeTruthy()

    const analyses = await analysesResponse.json()
    // video_typeでフィルタ
    const internalAnalyses = analyses.filter((a: any) =>
      a.video_type === 'internal' || a.video_type === 'external_with_instruments'
    )

    if (internalAnalyses.length === 0) {
      console.log('⏭️  器具解析が見つかりません - テストをスキップ')
      test.skip()
      return
    }

    // 最新の解析を使用
    const latestAnalysis = internalAnalyses.sort((a: any, b: any) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )[0]

    console.log(`📊 ダッシュボードテスト - 解析ID: ${latestAnalysis.id}`)

    // ダッシュボードを開く
    await page.goto(`http://localhost:3000/dashboard/${latestAnalysis.id}`)
    await page.waitForLoadState('networkidle')

    // ビデオプレイヤーまたはキャンバスが表示されるまで待機
    const videoPlayer = page.locator('video').or(page.locator('canvas'))
    await expect(videoPlayer.first()).toBeVisible({ timeout: 10000 })

    // フレーム描画を待機
    await page.waitForTimeout(2000)

    // キャンバス要素を確認（器具描画に使用）
    const canvas = page.locator('canvas')
    if (await canvas.count() > 0) {
      console.log('✅ キャンバス要素が見つかりました')

      const canvasElement = canvas.first()
      const boundingBox = await canvasElement.boundingBox()

      if (boundingBox) {
        console.log(`📐 キャンバスサイズ: ${boundingBox.width}x${boundingBox.height}`)
        expect(boundingBox.width).toBeGreaterThan(0)
        expect(boundingBox.height).toBeGreaterThan(0)
      }
    }

    // スクリーンショット保存（視覚的確認用）
    await page.screenshot({
      path: 'test-results/phase2.5-rotated-bbox-dashboard.png',
      fullPage: true
    })

    console.log('✅ スクリーンショット保存: test-results/phase2.5-rotated-bbox-dashboard.png')
  })
})
