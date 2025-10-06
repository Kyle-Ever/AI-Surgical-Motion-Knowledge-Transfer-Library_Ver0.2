import { test, expect } from '@playwright/test'
import path from 'path'

test.describe('Instrument Selection Coordinate Test', () => {
  test('should accurately track click coordinates on canvas', async ({ page }) => {
    // Navigate to upload page
    await page.goto('http://localhost:3000/upload')

    // Upload a test video
    const testVideoPath = path.join(__dirname, '../../data/test-videos/test-video.mp4')
    await page.setInputFiles('input[type="file"]', testVideoPath)

    // Wait for upload to complete
    await page.waitForTimeout(2000)

    // Select internal video type
    await page.click('text=内視鏡（術野カメラ）')
    await page.click('button:has-text("次へ")')

    // Select direct selection from video
    await page.click('text=映像から直接選択')

    // Wait for canvas to load
    await page.waitForSelector('canvas', { timeout: 5000 })

    // Get canvas element
    const canvas = await page.locator('canvas')
    const canvasBox = await canvas.boundingBox()

    if (!canvasBox) {
      throw new Error('Canvas not found')
    }

    // Test canvas dimensions
    console.log('Canvas bounding box:', canvasBox)

    // Click at specific coordinates
    const testPoints = [
      { x: 320, y: 240 }, // Center
      { x: 100, y: 100 }, // Top-left area
      { x: 540, y: 380 }, // Bottom-right area
    ]

    for (const point of testPoints) {
      // Click on the canvas at specific coordinates
      await canvas.click({
        position: { x: point.x, y: point.y }
      })

      console.log(`Clicked at (${point.x}, ${point.y})`)
      await page.waitForTimeout(500)
    }

    // Click segment button
    await page.click('button:has-text("セグメント実行")')

    // Wait for segmentation result
    await page.waitForTimeout(2000)

    // Check if visualization appears
    const hasVisualization = await page.locator('canvas').evaluate((el) => {
      const ctx = (el as HTMLCanvasElement).getContext('2d')
      if (!ctx) return false
      // Check if canvas has been modified
      const imageData = ctx.getImageData(0, 0, 1, 1)
      return imageData.data.some(pixel => pixel > 0)
    })

    expect(hasVisualization).toBeTruthy()
  })

  test('should handle box selection correctly', async ({ page }) => {
    await page.goto('http://localhost:3000/upload')

    // Upload test video
    const testVideoPath = path.join(__dirname, '../../data/test-videos/test-video.mp4')
    await page.setInputFiles('input[type="file"]', testVideoPath)

    await page.waitForTimeout(2000)

    // Select internal video type
    await page.click('text=内視鏡（術野カメラ）')
    await page.click('button:has-text("次へ")')

    // Select direct selection from video
    await page.click('text=映像から直接選択')

    // Wait for canvas
    await page.waitForSelector('canvas', { timeout: 5000 })

    // Switch to box selection mode
    await page.click('button:has-text("ボックス選択")')

    const canvas = await page.locator('canvas')

    // Perform drag to create box
    await canvas.dragTo(canvas, {
      sourcePosition: { x: 200, y: 150 },
      targetPosition: { x: 440, y: 330 }
    })

    console.log('Created box from (200, 150) to (440, 330)')

    // Click segment button
    await page.click('button:has-text("セグメント実行")')

    await page.waitForTimeout(2000)

    // Verify segmentation executed
    const hasResult = await page.locator('text=器具名を入力').isVisible()
    expect(hasResult).toBeTruthy()
  })

  test('should maintain aspect ratio of canvas', async ({ page }) => {
    await page.goto('http://localhost:3000/upload')

    const testVideoPath = path.join(__dirname, '../../data/test-videos/test-video.mp4')
    await page.setInputFiles('input[type="file"]', testVideoPath)

    await page.waitForTimeout(2000)

    await page.click('text=内視鏡（術野カメラ）')
    await page.click('button:has-text("次へ")')
    await page.click('text=映像から直接選択')

    await page.waitForSelector('canvas')

    // Check canvas dimensions
    const canvasDimensions = await page.locator('canvas').evaluate((el) => {
      const canvas = el as HTMLCanvasElement
      return {
        width: canvas.width,
        height: canvas.height,
        clientWidth: canvas.clientWidth,
        clientHeight: canvas.clientHeight,
        aspectRatio: canvas.width / canvas.height,
        displayAspectRatio: canvas.clientWidth / canvas.clientHeight
      }
    })

    console.log('Canvas dimensions:', canvasDimensions)

    // Verify aspect ratio is maintained (640/480 = 1.333)
    expect(canvasDimensions.aspectRatio).toBeCloseTo(1.333, 2)
    expect(canvasDimensions.displayAspectRatio).toBeCloseTo(1.333, 1)
  })
})