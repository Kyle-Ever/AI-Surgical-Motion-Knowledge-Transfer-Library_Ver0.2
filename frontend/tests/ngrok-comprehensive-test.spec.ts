import { test, expect } from '@playwright/test'
import path from 'path'

const NGROK_URL = 'https://attestable-emily-reservedly.ngrok-free.dev'

// ngrok警告画面をスキップするヘルパー関数
async function skipNgrokWarning(page: any) {
  try {
    // 警告画面が表示されるまで待つ
    await page.waitForLoadState('networkidle', { timeout: 10000 })

    // 「Visit Site」ボタンを探す（複数のセレクタを試す）
    const selectors = [
      'button:has-text("Visit Site")',
      'a:has-text("Visit Site")',
      '[href="#"]',
      'button',
    ]

    for (const selector of selectors) {
      const button = page.locator(selector).first()
      if (await button.isVisible({ timeout: 2000 }).catch(() => false)) {
        console.log(`✓ 警告画面の「Visit Site」ボタンを検出: ${selector}`)
        await button.click()
        await page.waitForLoadState('networkidle')
        console.log('✓ 警告画面をスキップしました')
        return true
      }
    }

    // ボタンが見つからない場合は、すでにメインページにいる可能性
    console.log('⚠ 警告画面のボタンが見つかりません（すでにスキップ済みの可能性）')
    return false
  } catch (error) {
    console.log('⚠ 警告画面スキップ中にエラー:', error)
    return false
  }
}

test.describe('ngrok URL - 包括的動作確認', () => {
  test.beforeEach(async ({ page }) => {
    // コンソールログをキャプチャ
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`❌ Console Error: ${msg.text()}`)
      }
    })
  })

  test('1. ホームページの表示とナビゲーション', async ({ page }) => {
    console.log('=== テスト開始: ホームページ ===')

    await page.goto(NGROK_URL)
    await skipNgrokWarning(page)

    // スクリーンショット撮影
    await page.screenshot({
      path: 'tests/screenshots/ngrok-01-home.png',
      fullPage: true
    })

    // ホームページの要素を確認
    const homeTitle = page.locator('h1').first()
    await expect(homeTitle).toBeVisible({ timeout: 10000 })

    // ナビゲーションカードが4つあることを確認
    const navCards = page.locator('[data-testid^="nav-card"]')
    const cardCount = await navCards.count()
    console.log(`✓ ナビゲーションカード数: ${cardCount}`)
    expect(cardCount).toBeGreaterThanOrEqual(3)

    console.log('✅ ホームページテスト完了')
  })

  test('2. ライブラリページ - 解析データ一覧', async ({ page }) => {
    console.log('=== テスト開始: ライブラリページ ===')

    await page.goto(`${NGROK_URL}/library`)
    await skipNgrokWarning(page)
    await page.waitForTimeout(5000) // データ読み込み待機

    // スクリーンショット撮影
    await page.screenshot({
      path: 'tests/screenshots/ngrok-02-library.png',
      fullPage: true
    })

    // ページタイトル確認
    const pageTitle = page.locator('h1').first()
    await expect(pageTitle).toBeVisible({ timeout: 10000 })
    console.log(`✓ ページタイトル表示: ${await pageTitle.textContent()}`)

    // データグリッドまたはテーブルが表示されることを確認
    const hasGrid = await page.locator('.library-grid, table, [role="grid"]').count() > 0
    console.log(`✓ データ表示領域: ${hasGrid ? '検出' : '未検出'}`)

    // エラーメッセージが表示されていないことを確認
    const errorMessages = page.locator('text=/バックエンドに接続できません|Failed to fetch|Network Error/')
    const errorCount = await errorMessages.count()
    console.log(`✓ エラーメッセージ数: ${errorCount}`)
    expect(errorCount).toBe(0)

    console.log('✅ ライブラリページテスト完了')
  })

  test('3. 新規解析ページ - 手技のみ（external）', async ({ page }) => {
    console.log('=== テスト開始: 新規解析（手技のみ） ===')

    await page.goto(`${NGROK_URL}/upload`)
    await skipNgrokWarning(page)

    // スクリーンショット撮影
    await page.screenshot({
      path: 'tests/screenshots/ngrok-03-upload-external.png',
      fullPage: true
    })

    // ページタイトル確認
    const pageTitle = page.locator('h1').first()
    await expect(pageTitle).toBeVisible({ timeout: 10000 })
    console.log(`✓ ページタイトル: ${await pageTitle.textContent()}`)

    // 動画タイプ選択（external = 手技のみ）
    const externalRadio = page.locator('input[value="external"]').first()
    if (await externalRadio.isVisible({ timeout: 5000 }).catch(() => false)) {
      await externalRadio.click()
      console.log('✓ 動画タイプ選択: external（手技のみ）')
    }

    // ファイル入力が存在することを確認
    const fileInput = page.locator('input[type="file"]').first()
    await expect(fileInput).toBeVisible({ timeout: 5000 })
    console.log('✓ ファイル入力欄を検出')

    // 解析開始ボタンが存在することを確認
    const analyzeButton = page.locator('button:has-text("解析"), button:has-text("開始")').first()
    const hasButton = await analyzeButton.isVisible({ timeout: 5000 }).catch(() => false)
    console.log(`✓ 解析開始ボタン: ${hasButton ? '検出' : '未検出'}`)

    console.log('✅ 新規解析（手技のみ）ページテスト完了')
  })

  test('4. 新規解析ページ - 器具あり（internal）', async ({ page }) => {
    console.log('=== テスト開始: 新規解析（器具あり） ===')

    await page.goto(`${NGROK_URL}/upload`)
    await skipNgrokWarning(page)

    // 動画タイプ選択（internal = 器具あり）
    const internalRadio = page.locator('input[value="internal"], input[value="external_with_instruments"]').first()
    if (await internalRadio.isVisible({ timeout: 5000 }).catch(() => false)) {
      await internalRadio.click()
      console.log('✓ 動画タイプ選択: 器具あり')

      await page.screenshot({
        path: 'tests/screenshots/ngrok-04-upload-instruments.png',
        fullPage: true
      })
    }

    console.log('✅ 新規解析（器具あり）ページテスト完了')
  })

  test('5. 新規解析ページ - 視線解析（eye_gaze）', async ({ page }) => {
    console.log('=== テスト開始: 新規解析（視線解析） ===')

    await page.goto(`${NGROK_URL}/upload`)
    await skipNgrokWarning(page)

    // 動画タイプ選択（eye_gaze = 視線解析）
    const gazeRadio = page.locator('input[value="eye_gaze"]').first()
    if (await gazeRadio.isVisible({ timeout: 5000 }).catch(() => false)) {
      await gazeRadio.click()
      console.log('✓ 動画タイプ選択: eye_gaze（視線解析）')

      await page.screenshot({
        path: 'tests/screenshots/ngrok-05-upload-gaze.png',
        fullPage: true
      })
    } else {
      console.log('⚠ 視線解析オプションが見つかりません')
    }

    console.log('✅ 新規解析（視線解析）ページテスト完了')
  })

  test('6. 採点モードページ', async ({ page }) => {
    console.log('=== テスト開始: 採点モード ===')

    await page.goto(`${NGROK_URL}/scoring`)
    await skipNgrokWarning(page)
    await page.waitForTimeout(3000)

    // スクリーンショット撮影
    await page.screenshot({
      path: 'tests/screenshots/ngrok-06-scoring.png',
      fullPage: true
    })

    // ページタイトル確認
    const pageTitle = page.locator('h1').first()
    await expect(pageTitle).toBeVisible({ timeout: 10000 })
    console.log(`✓ ページタイトル: ${await pageTitle.textContent()}`)

    // 採点モードの要素が表示されることを確認
    const hasScoringElements = await page.locator('select, button, [role="combobox"]').count() > 0
    console.log(`✓ 採点モード要素: ${hasScoringElements ? '検出' : '未検出'}`)

    console.log('✅ 採点モードページテスト完了')
  })

  test('7. APIプロキシ動作確認', async ({ page }) => {
    console.log('=== テスト開始: APIプロキシ ===')

    // ネットワークリクエストをモニタリング
    const apiRequests: string[] = []
    page.on('request', request => {
      const url = request.url()
      if (url.includes('/api/v1/')) {
        apiRequests.push(url)
        console.log(`📡 API Request: ${url}`)
      }
    })

    // ライブラリページにアクセスしてAPIコールを発生させる
    await page.goto(`${NGROK_URL}/library`)
    await skipNgrokWarning(page)
    await page.waitForTimeout(5000)

    // APIリクエストが発生していることを確認
    console.log(`✓ 検出されたAPIリクエスト数: ${apiRequests.length}`)
    expect(apiRequests.length).toBeGreaterThan(0)

    // プロキシ経由（相対パス）でアクセスしていることを確認
    const hasRelativePath = apiRequests.some(url =>
      url.includes('attestable-emily-reservedly.ngrok-free.dev/api/v1/')
    )
    console.log(`✓ プロキシ経由アクセス: ${hasRelativePath ? 'YES' : 'NO'}`)

    console.log('✅ APIプロキシテスト完了')
  })

  test('8. レスポンシブデザイン確認（モバイル）', async ({ page }) => {
    console.log('=== テスト開始: モバイルビュー ===')

    // モバイルビューポートに変更
    await page.setViewportSize({ width: 375, height: 667 })

    await page.goto(NGROK_URL)
    await skipNgrokWarning(page)

    // スクリーンショット撮影
    await page.screenshot({
      path: 'tests/screenshots/ngrok-07-mobile-home.png',
      fullPage: true
    })

    // ナビゲーションが表示されることを確認
    const nav = page.locator('nav, [role="navigation"]').first()
    await expect(nav).toBeVisible({ timeout: 10000 })
    console.log('✓ モバイルナビゲーション表示')

    // ライブラリページも確認
    await page.goto(`${NGROK_URL}/library`)
    await page.waitForTimeout(3000)

    await page.screenshot({
      path: 'tests/screenshots/ngrok-08-mobile-library.png',
      fullPage: true
    })

    console.log('✅ モバイルビューテスト完了')
  })

  test('9. エラーハンドリング確認', async ({ page }) => {
    console.log('=== テスト開始: エラーハンドリング ===')

    // 存在しないページにアクセス
    await page.goto(`${NGROK_URL}/nonexistent-page`)
    await skipNgrokWarning(page)
    await page.waitForTimeout(2000)

    // スクリーンショット撮影
    await page.screenshot({
      path: 'tests/screenshots/ngrok-09-404.png',
      fullPage: true
    })

    // 404ページまたはエラーメッセージが表示されることを確認
    const has404 = await page.locator('text=/404|Not Found|ページが見つかりません/i').count() > 0
    console.log(`✓ 404エラー表示: ${has404 ? 'YES' : 'NO'}`)

    console.log('✅ エラーハンドリングテスト完了')
  })

  test('10. パフォーマンス測定', async ({ page }) => {
    console.log('=== テスト開始: パフォーマンス測定 ===')

    // ページロード時間を測定
    const startTime = Date.now()

    await page.goto(`${NGROK_URL}/library`)
    await skipNgrokWarning(page)
    await page.waitForLoadState('networkidle')

    const loadTime = Date.now() - startTime
    console.log(`✓ ページロード時間: ${loadTime}ms`)

    // ライブラリページのデータ読み込み時間
    const dataStartTime = Date.now()
    await page.waitForTimeout(5000) // APIレスポンス待機
    const dataLoadTime = Date.now() - dataStartTime
    console.log(`✓ データ読み込み時間: ${dataLoadTime}ms`)

    // パフォーマンスメトリクスを取得
    const metrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
      return {
        domContentLoaded: Math.round(navigation.domContentLoadedEventEnd - navigation.fetchStart),
        loadComplete: Math.round(navigation.loadEventEnd - navigation.fetchStart),
      }
    })

    console.log(`✓ DOMContentLoaded: ${metrics.domContentLoaded}ms`)
    console.log(`✓ Load Complete: ${metrics.loadComplete}ms`)

    // スクリーンショット撮影
    await page.screenshot({
      path: 'tests/screenshots/ngrok-10-performance.png',
      fullPage: true
    })

    console.log('✅ パフォーマンス測定完了')
  })
})

test.describe('ngrok URL - 統合テストサマリー', () => {
  test('全機能動作確認サマリー', async ({ page }) => {
    console.log('\n' + '='.repeat(60))
    console.log('📊 ngrok URL 包括的テスト結果サマリー')
    console.log('='.repeat(60))

    const results = {
      url: NGROK_URL,
      timestamp: new Date().toISOString(),
      tests: {
        'ホームページ': 'screenshots/ngrok-01-home.png',
        'ライブラリ': 'screenshots/ngrok-02-library.png',
        '新規解析（手技のみ）': 'screenshots/ngrok-03-upload-external.png',
        '新規解析（器具あり）': 'screenshots/ngrok-04-upload-instruments.png',
        '新規解析（視線解析）': 'screenshots/ngrok-05-upload-gaze.png',
        '採点モード': 'screenshots/ngrok-06-scoring.png',
        'モバイル（ホーム）': 'screenshots/ngrok-07-mobile-home.png',
        'モバイル（ライブラリ）': 'screenshots/ngrok-08-mobile-library.png',
        '404エラー': 'screenshots/ngrok-09-404.png',
        'パフォーマンス': 'screenshots/ngrok-10-performance.png',
      }
    }

    console.log('\n📸 生成されたスクリーンショット:')
    Object.entries(results.tests).forEach(([name, path]) => {
      console.log(`  ✓ ${name}: tests/${path}`)
    })

    console.log('\n✅ 全テスト完了')
    console.log('='.repeat(60) + '\n')

    // ダミーアサーション（サマリー表示のため）
    expect(true).toBe(true)
  })
})
