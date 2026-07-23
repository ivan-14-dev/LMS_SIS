const { createConfig } = require('@openedx/frontend-build');

module.exports = createConfig('jest', {
  setupFilesAfterEnv: [
    '<rootDir>/src/setupTests.js',
  ],
  moduleNameMapper: {
    '\\.scss$': 'identity-obj-proxy',
  },
  collectCoverageFrom: [
    'src/**/*.{js,jsx}',
    '!src/**/*.test.{js,jsx}',
    '!src/index.jsx',
    '!src/setupTests.js',
  ],
});
