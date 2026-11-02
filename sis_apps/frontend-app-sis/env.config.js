/**
 * Environment configuration for SIS MFE
 * This file is loaded by @openedx/frontend-build during webpack compilation
 */

const config = {
  // Core MFE settings
  BASE_URL: process.env.BASE_URL || 'http://localhost:8080',
  PUBLIC_PATH: process.env.PUBLIC_PATH || '/',
  LMS_BASE_URL: process.env.LMS_BASE_URL || 'http://localhost:18000',
  STUDIO_BASE_URL: process.env.STUDIO_BASE_URL || 'http://localhost:18010',
  LOGIN_URL: process.env.LOGIN_URL || `${process.env.LMS_BASE_URL || 'http://localhost:18000'}/login`,
  LOGOUT_URL: process.env.LOGOUT_URL || `${process.env.LMS_BASE_URL || 'http://localhost:18000'}/logout`,
  REFRESH_ACCESS_TOKEN_ENDPOINT: process.env.REFRESH_ACCESS_TOKEN_ENDPOINT
    || `${process.env.LMS_BASE_URL || 'http://localhost:18000'}/login_refresh`,
  ACCESS_TOKEN_COOKIE_NAME: process.env.ACCESS_TOKEN_COOKIE_NAME || 'edx-jwt-cookie-header-payload',
  USER_INFO_COOKIE_NAME: process.env.USER_INFO_COOKIE_NAME || 'edx-user-info',
  CSRF_TOKEN_API_PATH: process.env.CSRF_TOKEN_API_PATH || '/csrf/api/v1/token',

  // Site configuration
  SITE_NAME: process.env.SITE_NAME || 'SIS - Système d\'Information Scolaire',
  LOGO_URL: process.env.LOGO_URL || 'https://edx-cdn.org/v3/default/logo.svg',
  LOGO_TRADEMARK_URL: 'https://edx-cdn.org/v3/default/logo-trademark.svg',
  LOGO_WHITE_URL: 'https://edx-cdn.org/v3/default/logo-white.svg',
  FAVICON_URL: 'https://edx-cdn.org/v3/default/favicon.ico',

  // Marketing and support
  MARKETING_SITE_BASE_URL: 'http://localhost:8080',
  SUPPORT_URL: process.env.SUPPORT_URL || '',
  SUPPORT_EMAIL: process.env.SUPPORT_EMAIL || '',
  TERMS_OF_SERVICE_URL: process.env.TERMS_OF_SERVICE_URL || '',
  PRIVACY_POLICY_URL: process.env.PRIVACY_POLICY_URL || '',
  CONTACT_URL: process.env.CONTACT_URL || process.env.SUPPORT_URL || '',

  // Optional features
  ENABLE_ACCESSIBILITY_PAGE: false,
  ORDER_HISTORY_URL: 'http://localhost:8080/orders',

  // SIS specific configuration
  SIS_MODE: process.env.SIS_MODE || 'dual',
  SIS_AUTH_MODE: process.env.SIS_AUTH_MODE || 'lms',
  SIS_API_BASE_URL: process.env.SIS_API_BASE_URL || 'http://localhost:8001/api/v1',
  SIS_SUPERIEUR_API_URL: process.env.SIS_SUPERIEUR_API_URL || 'http://localhost:8002/api/v1',
  SIS_SECONDAIRE_API_URL: process.env.SIS_SECONDAIRE_API_URL || 'http://localhost:8001/api/v1',
  SIS_ADMIN_API_URL: process.env.SIS_ADMIN_API_URL || 'http://localhost:8001/api/v1',
  USE_MOCK_API: process.env.USE_MOCK_API === 'true',
};

export default config;
