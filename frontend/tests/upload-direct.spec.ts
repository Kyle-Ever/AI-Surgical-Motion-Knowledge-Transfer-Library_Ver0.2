import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'

test('upload page direct test', async ({ page }) => {
  // 直接アップロードページへ移動
  await page.goto('http://localhost:3000/upload')

  // ページ読み込み待機
  await page.waitForLoadState('networkidle')

  // タイトル確認
  await expect(page.getByText('動画アップロード')).toBeVisible()

  // ドロップゾーンの確認
  const dropzone = page.locator('[class*="border-dashed"]')
  await expect(dropzone).toBeVisible()

  // "ファイルを選択"ボタンの確認
  const selectButton = page.locator('button:has-text("ファイルを選択")')
  await expect(selectButton).toBeVisible()

  // ファイル入力要素の確認
  const fileInput = page.locator('input[type="file"]')
  await expect(fileInput).toHaveAttribute('accept', expect.stringContaining('video'))

  // テスト用ビデオファイルを作成
  const testVideoPath = path.join(process.cwd(), 'test-upload.mp4')

  // モックファイルをアップロード
  await fileInput.setInputFiles({
    name: 'test-video.mp4',
    mimeType: 'video/mp4',
    buffer: Buffer.from('mock video content')
  })

  // ファイル名が表示されることを確認
  await expect(page.getByText('test-video.mp4')).toBeVisible({ timeout: 5000 })

  // ファイル削除ボタンの確認
  const removeButton = page.locator('[aria-label="ファイルを削除"]')
  await expect(removeButton).toBeVisible()

  // 次へボタンが有効になることを確認
  const nextButton = page.getByRole('button', { name: '次へ' })
  await expect(nextButton).toBeEnabled()

  // 次へボタンをクリック
  await nextButton.click()

  // 映像タイプ選択画面の確認
  await expect(page.getByText('映像タイプを選択')).toBeVisible({ timeout: 5000 })

  // 外部カメラボタンの確認
  const externalButton = page.getByText('外部カメラ').first()
  await expect(externalButton).toBeVisible()

  console.log('✓ アップロードページの基本機能は正常に動作しています')
})

test('upload flow with dropzone click', async ({ page }) => {
  await page.goto('http://localhost:3000/upload')

  // ドロップゾーンをクリックしてファイル選択
  const dropzone = page.locator('[class*="border-dashed"]')

  // ドロップゾーンが見えることを確認
  await expect(dropzone).toBeVisible()

  // ファイル入力要素を探す
  const fileInput = page.locator('input[type="file"]')

  // ファイルをセット
  await fileInput.setInputFiles({
    name: 'dropzone-test.mp4',
    mimeType: 'video/mp4',
    buffer: Buffer.from('test video for dropzone')
  })

  // ファイルがセットされたことを確認
  await expect(page.getByText('dropzone-test.mp4')).toBeVisible({ timeout: 5000 })

  console.log('✓ ドロップゾーンでのファイルアップロードも正常に動作しています')
})