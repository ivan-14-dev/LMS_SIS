/**
 * Environment configuration for SIS MFE
 * This file is loaded by @openedx/frontend-build during webpack compilation
 */

const config = {
  // Core MFE settings
  BASE_URL: 'http://localhost:8080',
  LMS_BASE_URL: 'http://localhost:18000',
  STUDIO_BASE_URL: 'http://localhost:18010',
  LOGIN_URL: 'http://localhost:18000/login',
  LOGOUT_URL: 'http://localhost:18000/logout',
  REFRESH_ACCESS_TOKEN_ENDPOINT: 'http://localhost:18000/login_refresh',
  ACCESS_TOKEN_COOKIE_NAME: 'edx-jwt-cookie-header-payload',
  USER_INFO_COOKIE_NAME: 'edx-user-info',
  CSRF_TOKEN_API_PATH: '/csrf/api/v1/token',
  
  // Site configuration
  SITE_NAME: 'SIS - Système d\'Information Scolaire',
  LOGO_URL: 'https://edx-cdn.org/v3/default/logo.svg',
  LOGO_TRADEMARK_URL: 'https://edx-cdn.org/v3/default/logo-trademark.svg',
  LOGO_WHITE_URL: 'https://edx-cdn.org/v3/default/logo-white.svg',
  FAVICON_URL: 'https://edx-cdn.org/v3/default/favicon.ico',
  
  // Marketing and support
  MARKETING_SITE_BASE_URL: 'http://localhost:8080',
  SUPPORT_URL: 'http://localhost:8080/support',
  SUPPORT_EMAIL: 'support@example.com',
  TERMS_OF_SERVICE_URL: 'http://localhost:8080/tos',
  PRIVACY_POLICY_URL: 'http://localhost:8080/privacy',
  CONTACT_URL: 'http://localhost:8080/contact',
  
  // Optional features
  ENABLE_ACCESSIBILITY_PAGE: false,
  ORDER_HISTORY_URL: 'http://localhost:8080/orders',
  
  // SIS specific configuration
  SIS_API_BASE_URL: 'http://localhost:8001/api/v1',
  SIS_SUPERIEUR_API_URL: 'http://localhost:8002/api/v1',
  SIS_SECONDAIRE_API_URL: 'http://localhost:8001/api/v1',
  STANDALONE_MODE: true,
};

export default config;
