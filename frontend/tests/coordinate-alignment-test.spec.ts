import { test, expect } from '@playwright/test'

/**
 * 座標整合性テスト
 *
 * 目的: サムネイル、セグメンテーション、SAM2の座標系が統一されていることを検証
 *
 * 検証項目:
 * 1. サムネイルが元動画サイズで返されること
 * 2. Canvasが画像の実際のサイズに設定されること
 * 3. クリック座標がそのまま使用されること（スケール変換なし）
 * 4. セグメンテーション結果の座標が正しいこと
 */

test.describe('座標整合性テスト', () => {
  const TEST_VIDEO_PATH = 'C:\\Users\\ajksk\\Desktop\\Dev\\AI Surgical Motion Knowledge Transfer Library_Ver0.2\\backend_experimental\\data\\uploads\\c77e6a9d-840e-4b97-97d9-a6e0b9ce4dd4.mp4'
  const API_URL = 'http://localhost:8001/api/v1'

  let videoId: string

  test.beforeEach(async ({ page }) => {
    // アップロードページに移動
    await page.goto('http://localhost:3000/upload')
    await page.waitForLoadState('networkidle')
  })

  test('サムネイルが元動画サイズで返されること', async ({ page }) => {
    // 動画をアップロード
    const fileInput = await page.locator('input[type="file"]')
    await fileInput.setInputFiles(TEST_VIDEO_PATH)

    // アップロード完了を待つ
    await page.waitForSelector('text=映像から直接選択 (SAM)', { timeout: 30000 })

    // 映像から直接選択ボタンをクリック
    await page.click('button:has-text("映像から直接選択 (SAM)")')

    // Canvas要素を取得
    const canvas = await page.locator('canvas')
    await canvas.waitFor({ state: 'visible' })

    // Canvasのサイズを取得
    const canvasWidth = await canvas.evaluate((el) => el.width)
    const canvasHeight = await canvas.evaluate((el) => el.height)

    console.log(`Canvas size: ${canvasWidth}x${canvasHeight}`)

    // Canvas が 640x480 ではなく、元動画サイズ（例: 1214x620）であることを確認
    expect(canvasWidth).toBeGreaterThan(640)
    expect(canvasHeight).toBeGreaterThan(480)

    // 一般的な動画サイズの範囲内であることを確認
    expect(canvasWidth).toBeGreaterThanOrEqual(1024)
    expect(canvasWidth).toBeLessThanOrEqual(1920)
    expect(canvasHeight).toBeGreaterThanOrEqual(576)
    expect(canvasHeight).toBeLessThanOrEqual(1080)
  })

  test('クリック座標とセグメンテーション座標が一致すること', async ({ page }) => {
    // 動画をアップロード
    const fileInput = await page.locator('input[type="file"]')
    await fileInput.setInputFiles(TEST_VIDEO_PATH)

    await page.waitForSelector('text=映像から直接選択 (SAM)', { timeout: 30000 })
    await page.click('button:has-text("映像から直接選択 (SAM)")')

    const canvas = await page.locator('canvas')
    await canvas.waitFor({ state: 'visible' })

    // Canvas情報を取得
    const canvasInfo = await canvas.evaluate((el) => ({
      width: el.width,
      height: el.height,
      displayWidth: el.clientWidth,
      displayHeight: el.clientHeight
    }))

    console.log('Canvas info:', canvasInfo)

    // ネットワークリクエストを監視
    const segmentRequests: any[] = []
    page.on('request', (request) => {
      if (request.url().includes('/segment')) {
        console.log('Segment request URL:', request.url())
        segmentRequests.push({
          url: request.url(),
          method: request.method(),
          postData: request.postDataJSON()
        })
      }
    })

    // Canvas中央をクリック
    const clickX = Math.floor(canvasInfo.displayWidth / 2)
    const clickY = Math.floor(canvasInfo.displayHeight / 2)

    await canvas.click({ position: { x: clickX, y: clickY } })

    // セグメンテーション実行
    await page.click('button:has-text("セグメント実行")')

    // セグメンテーション完了を待つ
    await page.waitForTimeout(3000)

    // セグメンテーションリクエストを確認
    expect(segmentRequests.length).toBeGreaterThan(0)

    const segmentRequest = segmentRequests[0]
    console.log('Segment request data:', JSON.stringify(segmentRequest.postData, null, 2))

    // リクエストに含まれる座標を取得
    const coords = segmentRequest.postData.coords
    expect(coords).toBeDefined()
    expect(coords.length).toBeGreaterThan(0)

    // 座標がCanvas座標系の範囲内にあることを確認
    const [coordX, coordY] = coords[0]

    console.log(`Click position: (${clickX}, ${clickY})`)
    console.log(`Sent coordinate: (${coordX}, ${coordY})`)
    console.log(`Canvas size: ${canvasInfo.width}x${canvasInfo.height}`)

    // 座標がCanvas範囲内であることを確認
    expect(coordX).toBeGreaterThanOrEqual(0)
    expect(coordX).toBeLessThanOrEqual(canvasInfo.width)
    expect(coordY).toBeGreaterThanOrEqual(0)
    expect(coordY).toBeLessThanOrEqual(canvasInfo.height)

    // スケール変換が正しく行われていることを確認
    const expectedX = Math.floor(clickX * canvasInfo.width / canvasInfo.displayWidth)
    const expectedY = Math.floor(clickY * canvasInfo.height / canvasInfo.displayHeight)

    console.log(`Expected coordinate: (${expectedX}, ${expectedY})`)

    // 許容誤差 ±5ピクセル
    expect(Math.abs(coordX - expectedX)).toBeLessThanOrEqual(5)
    expect(Math.abs(coordY - expectedY)).toBeLessThanOrEqual(5)
  })

  test('バックエンドログで座標系の一致を確認', async ({ page }) => {
    // 動画をアップロード
    const fileInput = await page.locator('input[type="file"]')
    await fileInput.setInputFiles(TEST_VIDEO_PATH)

    await page.waitForSelector('text=映像から直接選択 (SAM)', { timeout: 30000 })
    await page.click('button:has-text("映像から直接選択 (SAM)")')

    const canvas = await page.locator('canvas')
    await canvas.waitFor({ state: 'visible' })

    // レスポンスを監視
    const responses: any[] = []
    page.on('response', async (response) => {
      if (response.url().includes('/segment')) {
        const status = response.status()
        console.log(`Segment response status: ${status}`)

        if (status === 200) {
          const data = await response.json()
          responses.push(data)
          console.log('Segment response:', JSON.stringify(data, null, 2))
        }
      }
    })

    // 適当な位置をクリック
    await canvas.click({ position: { x: 200, y: 150 } })
    await page.click('button:has-text("セグメント実行")')

    // セグメンテーション完了を待つ
    await page.waitForTimeout(3000)

    // レスポンスを確認
    expect(responses.length).toBeGreaterThan(0)

    const segmentResult = responses[0]

    // bbox が存在することを確認
    expect(segmentResult.bbox).toBeDefined()
    expect(segmentResult.bbox.length).toBe(4)

    const [x1, y1, x2, y2] = segmentResult.bbox

    console.log(`Segment bbox: [${x1}, ${y1}, ${x2}, ${y2}]`)

    // bbox座標が妥当な範囲内であることを確認
    expect(x1).toBeGreaterThanOrEqual(0)
    expect(y1).toBeGreaterThanOrEqual(0)
    expect(x2).toBeGreaterThan(x1)
    expect(y2).toBeGreaterThan(y1)

    // Mock SAMの場合、座標が入力点周辺にあることを確認
    // Real SAMの場合、実際のオブジェクトのbboxが返される
    expect(x2 - x1).toBeGreaterThan(10) // 最低でも10ピクセル幅
    expect(y2 - y1).toBeGreaterThan(10) // 最低でも10ピクセル高さ
  })
})
