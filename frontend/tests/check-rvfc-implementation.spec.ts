/**
 * 指定されたページでRVFC実装が反映されているか確認するテスト
 */

import { test, expect } from '@playwright/test'

test('Check if RVFC implementation is loaded', async ({ page, browserName }) => {
  const ANALYSIS_ID = '182aae42-f5d8-4ca6-a261-de88d863a95f'
  const url = `http://localhost:3000/dashboard/${ANALYSIS_ID}`

  console.log('\n========================================')
  console.log(`Testing URL: ${url}`)
  console.log(`Browser: ${browserName}`)
  console.log('========================================\n')

  // コンソールログを収集
  const logs: string[] = []
  page.on('console', (msg) => {
    const text = msg.text()
    logs.push(text)

    // RVFC/RAFログを表示
    if (text.includes('requestVideoFrameCallback') || text.includes('requestAnimationFrame') || text.includes('Using')) {
      console.log(`✨ [Browser Log] ${text}`)
    }
  })

  // ページエラーを収集
  page.on('pageerror', (error) => {
    console.log(`❌ [Page Error] ${error.message}`)
  })

  // ページにアクセス
  console.log('📄 Loading page...')
  await page.goto(url, {
    waitUntil: 'domcontentloaded',
    timeout: 30000
  })

  // 少し待機してコンソールログを確認
  await page.waitForTimeout(3000)

  // VideoPlayerコンポーネントのソースコードを確認
  console.log('\n🔍 Checking VideoPlayer source code in browser...')

  const hasRVFCCode = await page.evaluate(() => {
    // ページ内のscriptタグからVideoPlayerのコードを探す
    const scripts = Array.from(document.querySelectorAll('script'))
    let foundRVFC = false
    let foundScheduleNextFrame = false

    for (const script of scripts) {
      const content = script.textContent || ''
      if (content.includes('requestVideoFrameCallback')) {
        foundRVFC = true
      }
      if (content.includes('scheduleNextFrame')) {
        foundScheduleNextFrame = true
      }
    }

    return { foundRVFC, foundScheduleNextFrame }
  })

  console.log(`   - requestVideoFrameCallback found: ${hasRVFCCode.foundRVFC ? '✅' : '❌'}`)
  console.log(`   - scheduleNextFrame found: ${hasRVFCCode.foundScheduleNextFrame ? '✅' : '❌'}`)

  // 動画要素の存在確認
  console.log('\n🎥 Checking video player...')
  const videoExists = await page.locator('video').count()
  console.log(`   - Video element found: ${videoExists > 0 ? '✅' : '❌'} (count: ${videoExists})`)

  // 再生ボタンをクリックしてRVFCログを確認
  if (videoExists > 0) {
    console.log('\n▶️  Attempting to play video to trigger RVFC logs...')

    try {
      const playButton = page.getByRole('button', { name: /再生|Play/i })
      const playButtonExists = await playButton.count()

      if (playButtonExists > 0) {
        await playButton.click({ timeout: 5000 })
        console.log('   - Play button clicked ✅')

        // RVFC/RAFログが出るまで待機
        await page.waitForTimeout(2000)
      } else {
        console.log('   - Play button not found ⚠️')
      }
    } catch (error) {
      console.log(`   - Could not click play button: ${error}`)
    }
  }

  // 収集したログを分析
  console.log('\n📊 Console Log Analysis:')
  console.log(`   - Total logs captured: ${logs.length}`)

  const rvfcLog = logs.find(log => log.includes('Using requestVideoFrameCallback'))
  const rafLog = logs.find(log => log.includes('Using requestAnimationFrame') && log.includes('fallback'))

  if (rvfcLog) {
    console.log('\n✅ RVFC IS ACTIVE (Chrome/Edge/Safari)')
    console.log(`   "${rvfcLog}"`)
  } else if (rafLog) {
    console.log('\n⚠️  RAF FALLBACK IS ACTIVE (Firefox)')
    console.log(`   "${rafLog}"`)
  } else {
    console.log('\n❓ No RVFC/RAF log found yet')
    console.log('   (Logs may appear after video playback starts)')
  }

  // 結果サマリー
  console.log('\n========================================')
  console.log('Test Summary:')
  console.log(`  Browser: ${browserName}`)
  console.log(`  RVFC Code Present: ${hasRVFCCode.foundRVFC ? 'YES ✅' : 'NO ❌'}`)
  console.log(`  scheduleNextFrame Present: ${hasRVFCCode.foundScheduleNextFrame ? 'YES ✅' : 'NO ❌'}`)
  console.log(`  Video Element: ${videoExists > 0 ? 'YES ✅' : 'NO ❌'}`)
  console.log(`  RVFC/RAF Log: ${rvfcLog || rafLog ? 'DETECTED ✅' : 'NOT YET ⏳'}`)
  console.log('========================================\n')

  // アサーション
  expect(hasRVFCCode.foundRVFC || hasRVFCCode.foundScheduleNextFrame).toBeTruthy()
})
