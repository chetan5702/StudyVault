import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  workers: 1,
  globalSetup: './tests/global-setup.ts',
  use: { baseURL: 'http://127.0.0.1:5174', channel: 'msedge', headless: true, trace: 'retain-on-failure' },
})
