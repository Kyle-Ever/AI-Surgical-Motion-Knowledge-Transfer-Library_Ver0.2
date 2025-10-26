/**
 * RVFC実装の手動確認用テスト
 * ブラウザを開いてコンソールログを確認します
 */

import { test } from '@playwright/test'

test('RVFC実装の手動確認', async ({ page }) => {
  const ANALYSIS_ID = 'fff74a77-620a-4d82-9c9c-ed57c31dee06'

  // コンソールログをキャプチャ
  page.on('console', (msg) => {
    const text = msg.text()
    console.log(`[Browser Console] ${text}`)

    // RVFC/RAFログを強調表示
    if (text.includes('requestVideoFrameCallback') || text.includes('requestAnimationFrame')) {
      console.log('🎯 ========================================')
      console.log(`🎯 ${text}`)
      console.log('🎯 ========================================')
    }
  })

  console.log('\n=== RVFC Implementation Test ===\n')
  console.log(`Opening: http://localhost:3000/dashboard/${ANALYSIS_ID}`)
  console.log('\n手動確認項目:')
  console.log('1. コンソールログに "Using requestVideoFrameCallback (RVFC)" が表示される（Chrome/Edge）')
  console.log('2. または "Using requestAnimationFrame (RAF)" が表示される（Firefox）')
  console.log('3. 動画再生時にオーバーレイが遅延なく同期している')
  console.log('4. 一時停止・シーク操作が正常に動作する')
  console.log('\nブラウザを開いたままにします（Ctrl+Cで終了）...\n')

  await page.goto(`http://localhost:3000/dashboard/${ANALYSIS_ID}`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000
  })

  // ページを開いたまま待機（5分間）
  await page.waitForTimeout(300000)
})
