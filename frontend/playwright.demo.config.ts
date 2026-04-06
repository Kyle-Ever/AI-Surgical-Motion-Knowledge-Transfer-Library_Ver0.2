import { defineConfig } from '@playwright/test'

/**
 * デモ動画録画用の Playwright 設定
 * 使用方法: npx playwright test --config=playwright.demo.config.ts
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'list',
  timeout: 600_000, // 10分
  use: {
    baseURL: 'http://localhost:3000',
    video: 'on',
    viewport: { width: 1400, height: 900 },
    launchOptions: {
      slowMo: 100, // ゆっくりとした操作でデモ感を出す
    },
  },
  projects: [
    {
      name: 'demo',
      use: {
        browserName: 'chromium',
        viewport: { width: 1400, height: 900 },
      },
    },
  ],
})
