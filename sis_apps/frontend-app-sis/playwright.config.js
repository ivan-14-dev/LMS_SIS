const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.js',
  timeout: 120000,
  workers: 1,
  use: {
    baseURL: process.env.SIS_E2E_URL,
    headless: true,
    trace: 'retain-on-failure',
  },
});
