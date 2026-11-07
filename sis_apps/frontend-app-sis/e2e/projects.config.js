const path = require('path');
const { defineConfig } = require('@playwright/test');
const base = require('../playwright.config');

module.exports = defineConfig({
  ...base,
  testDir: __dirname,
  testMatch: ['projects.e2e.js', 'project-courses.e2e.js'],
  projects: [{ name: 'learning-projects' }],
  outputDir: path.join(__dirname, '../test-results/projects'),
  timeout: 300000,
  retries: 0,
  workers: 1,
  use: { ...base.use, actionTimeout: 20000 },
});
