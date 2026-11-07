const path = require('path');
const { defineConfig } = require('@playwright/test');
const base = require('../playwright.config');

module.exports = defineConfig({
  ...base,
  testDir: __dirname,
  testMatch: 'lms-grade-review.e2e.js',
  projects: [{ name: 'lms-grade-review' }],
  outputDir: path.join(__dirname, '../test-results/lms-grade-review'),
  timeout: 180000,
  retries: 0,
  workers: 1,
  use: { ...base.use, actionTimeout: 20000 },
});
