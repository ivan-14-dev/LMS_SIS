const path = require('path');
const { defineConfig } = require('@playwright/test');
const base = require('./lms-grade-review.config');

module.exports = defineConfig({
  ...base,
  testMatch: 'academic-search.e2e.js',
  projects: [{ name: 'academic-search' }],
  outputDir: path.join(__dirname, '../test-results/academic-search'),
});
