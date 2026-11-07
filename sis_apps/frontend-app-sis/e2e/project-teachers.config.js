const path = require('path');
const { defineConfig } = require('@playwright/test');
const projects = require('./projects.config');

module.exports = defineConfig({
  ...projects,
  testMatch: 'project-teachers.e2e.js',
  outputDir: path.join(__dirname, '../test-results/project-teachers'),
});
