import { test, expect } from '@playwright/test'
import path from 'path'
import {
  blankIntro,
  initOverlays,
  titleCard,
  sub,
  subPersist,
  hideSub,
  smoothScrollPage,
} from './showcase-helpers'

// テスト動画のパス
const TEST_VIDEO = path.resolve(
  __dirname,
  '..',
  '..',
  'data',
  'uploads',
  '【正式】手技動画.mp4'
)

test('MindMotionAI Demo — 手技動画の解析フロー', async ({ page }) => {
  test.setTimeout(600_000) // 10分

  // ━━━ 1. イントロ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  await blankIntro(page)
  await titleCard(
    page,
    'MindモーションAI',
    '手術手技のモーション解析プラットフォーム',
    5000,
    {
      bg: 'linear-gradient(135deg, #020617, #0f172a, #1e3a5f, #0f172a, #020617)',
      titleColor:
        'background:linear-gradient(135deg,#60a5fa,#38bdf8,#67e8f9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;',
      subtitleColor: 'color:#94a3b8;',
    }
  )

  // ━━━ 2. ホームページ — ダッシュボード ━━━━━━━━━━━━━━
  await titleCard(page, 'Step 1', 'ダッシュボード', 2500)

  await page.goto('/')
  await initOverlays(page)
  await page.waitForTimeout(1500)

  await sub(page, 'ダッシュボードから新規解析を開始します', 3000)
  await page.waitForTimeout(1000)

  // ページ全体を見せる
  await subPersist(page, 'クイックスタートで手順を確認')
  await smoothScrollPage(page, 200, 600)
  await hideSub(page)
  await page.waitForTimeout(800)

  // トップに戻る
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
  await page.waitForTimeout(1000)

  // ━━━ 3. アップロードページへ ━━━━━━━━━━━━━━━━━━━━
  await titleCard(page, 'Step 2', '動画アップロード', 2500)

  await page.goto('/upload')
  await initOverlays(page)
  await page.waitForTimeout(1000)

  await sub(page, '手技動画をアップロードします', 2500)

  // ファイルをアップロード
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles(TEST_VIDEO)
  await page.waitForTimeout(2000)

  await sub(page, '【正式】手技動画.mp4 が選択されました', 2500)

  // メタデータ入力
  await subPersist(page, '手術情報を入力します')
  await page.waitForTimeout(800)

  const surgeryNameInput = page.locator('input[placeholder="例: 腹腔鏡手術"]')
  await surgeryNameInput.click()
  await surgeryNameInput.pressSequentially('縫合手技デモ', { delay: 80 })
  await page.waitForTimeout(500)

  const surgeonInput = page.locator('input[placeholder="例: 山田医師"]')
  await surgeonInput.click()
  await surgeonInput.pressSequentially('デモ医師', { delay: 80 })
  await page.waitForTimeout(1000)
  await hideSub(page)

  // 次へ
  await sub(page, '次のステップへ進みます', 1500)
  await page.getByTestId('next-button').click()
  await page.waitForTimeout(1000)

  // ━━━ 4. 映像タイプ選択 ━━━━━━━━━━━━━━━━━━━━━━━━━
  await titleCard(page, 'Step 3', '映像タイプの選択', 2500)

  await initOverlays(page)
  await sub(page, '手技動画は「外部カメラ（器具なし）」を選択', 3000)

  // 外部カメラ（器具なし）を選択
  const externalBtn = page.getByRole('button', { name: /外部カメラ.*器具なし/ })
  await externalBtn.click()
  await page.waitForTimeout(1500)

  await sub(page, '手の骨格のみを検出対象とします', 2500)

  // 次へ
  await page.getByRole('button', { name: '次へ' }).click()
  await page.waitForTimeout(1000)

  // ━━━ 5. 解析設定確認 & 開始 ━━━━━━━━━━━━━━━━━━━━━
  await titleCard(page, 'Step 4', '解析設定の確認と開始', 2500)

  await initOverlays(page)
  await sub(page, '設定内容を確認し、解析を開始します', 3000)
  await page.waitForTimeout(1500)

  // 解析を開始ボタンをクリック
  await subPersist(page, '解析を開始します...')
  await page.getByRole('button', { name: '解析を開始' }).click()
  await page.waitForTimeout(2000)
  await hideSub(page)

  // ━━━ 6. 解析進捗ページ ━━━━━━━━━━━━━━━━━━━━━━━━━
  await titleCard(page, 'Step 5', 'AI解析の実行', 2500)

  // 解析ページに遷移するのを待つ
  await page.waitForURL(/\/analysis\//, { timeout: 30_000 })
  await initOverlays(page)

  await subPersist(page, 'AIがフレームごとの骨格モーションを抽出中...')

  // 進捗を待つ — 解析完了（ダッシュボードへリダイレクト）まで待機
  // もしくは一定時間後にタイムアウト
  try {
    await page.waitForURL(/\/dashboard\//, { timeout: 300_000 }) // 5分
    await hideSub(page)
  } catch {
    // タイムアウトした場合は手動でダッシュボードに遷移を試みる
    await hideSub(page)
    await sub(page, '解析が進行中です（デモではここまで表示）', 3000)

    // URLからanalysis IDを取得してダッシュボードへ
    const url = page.url()
    const match = url.match(/\/analysis\/([^/]+)/)
    if (match) {
      await page.goto(`/dashboard/${match[1]}`)
    }
  }

  // ━━━ 7. ダッシュボード — 解析結果 ━━━━━━━━━━━━━━━━━
  await titleCard(page, 'Step 6', '解析結果ダッシュボード', 3000)

  await initOverlays(page)
  await page.waitForTimeout(3000) // データ読み込み待ち

  await sub(page, '骨格トラッキング付き動画プレーヤー', 3000)
  await page.waitForTimeout(1500)

  // ページをスクロールして全体を見せる
  await subPersist(page, 'ロスタイムタイムライン & 6指標パネル')
  await smoothScrollPage(page, 200, 800)
  await hideSub(page)
  await page.waitForTimeout(1500)

  // さらにスクロール
  await subPersist(page, 'レーダーチャート & フィードバック')
  await smoothScrollPage(page, 200, 800)
  await hideSub(page)
  await page.waitForTimeout(2000)

  // ━━━ 8. アウトロ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  await titleCard(
    page,
    'MindモーションAI',
    '手術手技の定量評価で、医療教育を変革する',
    5000,
    {
      bg: 'linear-gradient(135deg, #020617, #0f172a, #1e3a5f, #0f172a, #020617)',
      titleColor:
        'background:linear-gradient(135deg,#60a5fa,#38bdf8,#67e8f9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;',
      subtitleColor: 'color:#94a3b8;',
    }
  )
})
