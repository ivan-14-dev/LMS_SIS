module.exports = {
    globals: {
        gettext: (t) => t,
    },
    modulePaths: [
        'common/static/common/js/components',
    ],
    setupFilesAfterEnv: ['<rootDir>/setupTests.js'],
    testMatch: [
        '/**/*.test.jsx',
        'common/static/common/js/components/**/?(*.)+(spec|test).js?(x)',
    ],
    testPathIgnorePatterns: [
        '/node_modules/',
        '/sis_apps/frontend-app-sis/',
    ],
    testEnvironment: 'jsdom',
    transform: {
        '^.+\\.jsx$': 'babel-jest',
        '^.+\\.js$': 'babel-jest',
    },
};
