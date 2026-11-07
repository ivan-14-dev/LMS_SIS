const path = require('path');
const { defineConfig } = require('@playwright/test');
const projects = require('./projects.config');

module.exports = defineConfig({
  ...projects,
  testMatch: 'project-competencies.e2e.js',
  outputDir: path.join(__dirname, '../test-results/project-competencies'),
});
