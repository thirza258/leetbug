import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', timeout: 120_000, expect: { timeout: 15_000 },
  fullyParallel: false, workers: 1, retries: 0,
  use: { baseURL: process.env.BASE_URL || 'http://localhost:8080',
    headless: true, viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  reporter: [['list'], ['html', { open: 'never' }]],
});

