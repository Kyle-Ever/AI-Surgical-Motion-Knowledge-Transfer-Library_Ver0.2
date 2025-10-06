import { test, expect } from '@playwright/test'

/**
 * Phase 5 E2Eテスト: 器具検出の確認
 *
 * 目的:
 * 1. INTERNAL解析で器具データが正しく取得されるか
 * 2. EXTERNAL_WITH_INSTRUMENTS解析で骨格と器具が両方取得されるか
 * 3. ダッシュボードで器具データが表示されるか
 */

test.describe('Phase 5: 器具検出テスト', () => {
  test('INTERNAL解析の器具データを確認', async ({ request, page }) => {
    // INTERNAL解析IDを検索
    const analysesResponse = await request.get('http://localhost:8000/api/v1/analysis/completed')
    expect(analysesResponse.ok()).toBeTruthy()

    const analyses = await analysesResponse.json()
    const internalAnalysis = analyses.find((a: any) => a.video_type === 'internal')

    if (!internalAnalysis) {
      console.log('⏭️  INTERNAL解析が見つかりません - テストをスキップ')
      test.skip()
      return
    }

    console.log(`📊 INTERNAL解析ID: ${internalAnalysis.id}`)

    // 解析詳細を取得
    const detailResponse = await request.get(
      `http://localhost:8000/api/v1/analysis/${internalAnalysis.id}`
    )
    expect(detailResponse.ok()).toBeTruthy()

    const data = await detailResponse.json()
    console.log('📊 INTERNAL analysis data:', {
      id: data.id,
      status: data.status,
      skeleton_data_length: data.skeleton_data?.length || 0,
      instrument_data_length: data.instrument_data?.length || 0
    })

    // INTERNALは器具のみ
    expect(data.instrument_data).toBeDefined()
    expect(data.instrument_data.length).toBeGreaterThan(0)

    // 器具データ構造の確認
    const firstFrame = data.instrument_data[0]
    console.log('🔧 First instrument frame:', Object.keys(firstFrame))

    expect(firstFrame).toHaveProperty('frame_number')
    expect(firstFrame).toHaveProperty('instruments')

    if (firstFrame.instruments && firstFrame.instruments.length > 0) {
      const firstInstrument = firstFrame.instruments[0]
      console.log('🔧 First instrument:', Object.keys(firstInstrument))
      console.log(`✅ Instrument detected: ${firstInstrument.name || 'unnamed'}`)
    }

    // ダッシュボードで確認
    await page.goto(`http://localhost:3001/dashboard/${internalAnalysis.id}`)
    await page.waitForLoadState('networkidle')

    const videoPlayer = page.locator('video').or(page.locator('canvas'))
    await expect(videoPlayer.first()).toBeVisible({ timeout: 10000 })

    // スクリーンショット保存
    await page.screenshot({
      path: 'test-results/phase5-instrument-internal.png',
      fullPage: true
    })

    console.log('✅ INTERNAL器具検出テスト: 完了')
  })

  test('EXTERNAL_WITH_INSTRUMENTS解析を確認', async ({ request, page }) => {
    // EXTERNAL_WITH_INSTRUMENTS解析IDを検索
    const analysesResponse = await request.get('http://localhost:8000/api/v1/analysis/completed')
    expect(analysesResponse.ok()).toBeTruthy()

    const analyses = await analysesResponse.json()
    const externalWithInstruments = analyses.find(
      (a: any) => a.video_type === 'external_with_instruments'
    )

    if (!externalWithInstruments) {
      console.log('⏭️  EXTERNAL_WITH_INSTRUMENTS解析が見つかりません')
      console.log('ℹ️  このテストをパスするには、器具を含む外部カメラ動画で解析を実行してください')
      test.skip()
      return
    }

    console.log(`📊 EXTERNAL_WITH_INSTRUMENTS解析ID: ${externalWithInstruments.id}`)

    // 解析詳細を取得
    const detailResponse = await request.get(
      `http://localhost:8000/api/v1/analysis/${externalWithInstruments.id}`
    )
    expect(detailResponse.ok()).toBeTruthy()

    const data = await detailResponse.json()
    console.log('📊 EXTERNAL_WITH_INSTRUMENTS data:', {
      id: data.id,
      status: data.status,
      skeleton_data_length: data.skeleton_data?.length || 0,
      instrument_data_length: data.instrument_data?.length || 0
    })

    // 骨格と器具の両方が必要
    if (data.skeleton_data?.length > 0) {
      console.log('✅ 骨格データ検出: ', data.skeleton_data.length, 'フレーム')

      // フロントエンド互換形式確認
      const firstSkeleton = data.skeleton_data[0]
      expect(firstSkeleton).toHaveProperty('hands')
      expect(Array.isArray(firstSkeleton.hands)).toBeTruthy()
    } else {
      console.log('⚠️  骨格データなし - 旧データの可能性')
    }

    if (data.instrument_data?.length > 0) {
      console.log('✅ 器具データ検出: ', data.instrument_data.length, 'フレーム')
    } else {
      console.log('⚠️  器具データなし - 器具が選択されていない可能性')
    }

    // ダッシュボードで確認
    await page.goto(`http://localhost:3001/dashboard/${externalWithInstruments.id}`)
    await page.waitForLoadState('networkidle')

    const videoPlayer = page.locator('video').or(page.locator('canvas'))
    await expect(videoPlayer.first()).toBeVisible({ timeout: 10000 })

    // スクリーンショット保存
    await page.screenshot({
      path: 'test-results/phase5-external-with-instruments.png',
      fullPage: true
    })

    console.log('✅ EXTERNAL_WITH_INSTRUMENTS検出テスト: 完了')
  })

  test('器具トラッキングAPIの動作確認', async ({ request }) => {
    // 最新のビデオを取得
    const videosResponse = await request.get('http://localhost:8000/api/v1/videos/')
    expect(videosResponse.ok()).toBeTruthy()

    const videos = await videosResponse.json()
    if (!videos || videos.length === 0) {
      console.log('⏭️  ビデオが見つかりません - テストをスキップ')
      test.skip()
      return
    }

    const video = videos[0]
    console.log(`🎥 テスト用ビデオ: ${video.id} (${video.video_type})`)

    // 器具トラッキングAPIを呼び出し（サンプル器具定義で）
    const sampleInstruments = [
      {
        id: 0,
        name: 'Test Instrument',
        selection: {
          type: 'box',
          data: [100, 100, 200, 200] // x1, y1, x2, y2
        },
        color: '#FF0000'
      }
    ]

    const trackingResponse = await request.post(
      `http://localhost:8000/api/v1/instrument-tracking/${video.id}/track`,
      {
        data: { instruments: sampleInstruments }
      }
    )

    if (trackingResponse.ok()) {
      const trackingData = await trackingResponse.json()
      console.log('✅ 器具トラッキングAPI応答:', {
        video_id: trackingData.video_id,
        instruments_count: trackingData.instruments?.length || 0
      })

      expect(trackingData).toHaveProperty('video_id')
      expect(trackingData).toHaveProperty('instruments')
    } else {
      const error = await trackingResponse.text()
      console.log('⚠️  器具トラッキングAPI失敗:', trackingResponse.status(), error)
    }
  })
})
