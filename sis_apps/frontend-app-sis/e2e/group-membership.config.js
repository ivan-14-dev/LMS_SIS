const path = require('path');
const { defineConfig } = require('@playwright/test');
const base = require('./lms-grade-review.config');

module.exports = defineConfig({
  ...base,
  testMatch: 'group-membership.e2e.js',
  projects: [{ name: 'group-membership' }],
  outputDir: path.join(__dirname, '../test-results/group-membership'),
});
