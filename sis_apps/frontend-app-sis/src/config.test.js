const originalEnv = process.env;

beforeEach(() => {
  jest.resetModules();
  process.env = { ...originalEnv };
});

afterEach(() => {
  process.env = originalEnv;
});

it('defaults to live APIs when the mock flag is missing', () => {
  delete process.env.USE_MOCK_API;
  const config = jest.requireActual('../env.config').default;
  expect(config.USE_MOCK_API).toBe(false);
});

it.each(['true', 'false', 'TRUE', '1'])('loads the explicit mock flag %s', (flag) => {
  process.env.USE_MOCK_API = flag;
  const config = jest.requireActual('../env.config').default;
  expect(config.USE_MOCK_API).toBe(flag === 'true');
});

it('honors deployment URLs and derives login URLs from the configured LMS', () => {
  process.env.BASE_URL = 'https://sis.example.com';
  process.env.PUBLIC_PATH = '/sis/';
  process.env.LMS_BASE_URL = 'https://lms.example.com';
  process.env.SIS_SUPERIEUR_API_URL = 'https://university.example.com/api/v1';
  process.env.SIS_SECONDAIRE_API_URL = 'https://school.example.com/api/v1';
  process.env.SIS_ADMIN_API_URL = 'https://school.example.com/api/v1';
  delete process.env.LOGIN_URL;
  delete process.env.LOGOUT_URL;
  delete process.env.REFRESH_ACCESS_TOKEN_ENDPOINT;

  const config = jest.requireActual('../env.config').default;
  expect(config).toMatchObject({
    BASE_URL: 'https://sis.example.com',
    PUBLIC_PATH: '/sis/',
    LMS_BASE_URL: 'https://lms.example.com',
    LOGIN_URL: 'https://lms.example.com/login',
    LOGOUT_URL: 'https://lms.example.com/logout',
    REFRESH_ACCESS_TOKEN_ENDPOINT: 'https://lms.example.com/login_refresh',
    SIS_SUPERIEUR_API_URL: 'https://university.example.com/api/v1',
    SIS_SECONDAIRE_API_URL: 'https://school.example.com/api/v1',
    SIS_ADMIN_API_URL: 'https://school.example.com/api/v1',
  });
});

it('preserves explicit authentication endpoint overrides', () => {
  process.env.LOGIN_URL = 'https://lms.example.com/custom-login';
  process.env.LOGOUT_URL = 'https://lms.example.com/custom-logout';
  process.env.REFRESH_ACCESS_TOKEN_ENDPOINT = 'https://lms.example.com/custom-refresh';

  const config = jest.requireActual('../env.config').default;
  expect(config.LOGIN_URL).toBe(process.env.LOGIN_URL);
  expect(config.LOGOUT_URL).toBe(process.env.LOGOUT_URL);
  expect(config.REFRESH_ACCESS_TOKEN_ENDPOINT).toBe(process.env.REFRESH_ACCESS_TOKEN_ENDPOINT);
});
