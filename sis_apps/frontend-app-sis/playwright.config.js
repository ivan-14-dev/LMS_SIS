const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.js',
  timeout: 120000,
  workers: 1,
  projects: [
    { name: 'workspace', testMatch: '**/workspace.e2e.js' },
    { name: 'hierarchy', testMatch: '**/hierarchy.e2e.js', dependencies: ['workspace'] },
    { name: 'design', testMatch: '**/design.e2e.js', dependencies: ['hierarchy'] },
    { name: 'institution', testMatch: '**/institution.e2e.js', dependencies: ['design'] },
  ],
  use: {
    baseURL: process.env.SIS_E2E_URL,
    headless: true,
    trace: 'retain-on-failure',
  },
});
