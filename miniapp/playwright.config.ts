import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/h5', fullyParallel: false, workers: 1,
  timeout: 30000, expect: { timeout: 7000 },
  reporter: [['list'], ['json', { outputFile: 'test-results/h5-report.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:5186', viewport: { width: 390, height: 844 },
    launchOptions: { channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' },
    screenshot: 'only-on-failure', trace: 'retain-on-failure', video: 'on',
  },
})
