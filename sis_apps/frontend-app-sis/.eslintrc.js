const { createConfig } = require('@openedx/frontend-build');

const config = createConfig('eslint');
module.exports = {
  ...config,
  ignorePatterns: [...(config.ignorePatterns || []), 'dist/', 'coverage/', 'test-results/', 'playwright-report/'],
  overrides: [
    ...(config.overrides || []),
    {
      files: ['e2e/**/*.js', 'playwright.config.js', '.eslintrc.js'],
      env: { node: true },
      rules: { 'import/no-extraneous-dependencies': ['error', { devDependencies: true }] },
    },
  ],
};
