import { getConfig } from '@edx/frontend-platform';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import {
  deleteApi,
  fetchApi,
  getAdminApiUrl,
  getIntegrationApiUrl,
  normalizePageResponse,
  patchApi,
  postApi,
  putApi,
} from './api';
import {
  isMockMode, mockFetch, mockPost, mockPut, mockDelete,
} from './mockApi';

jest.mock('@edx/frontend-platform', () => ({ getConfig: jest.fn() }));
jest.mock('@edx/frontend-platform/auth', () => ({ getAuthenticatedHttpClient: jest.fn() }));
jest.mock('./mockApi', () => ({
  ...jest.requireActual('./mockApi'),
  mockFetch: jest.fn(),
  mockPost: jest.fn(),
  mockPut: jest.fn(),
  mockDelete: jest.fn(),
}));

const url = 'https://sis.example.com/api/v1/etudiants/';
const payload = { matricule: 'TEST-001' };
const options = { timeout: 1000 };
const requests = [
  ['get', fetchApi, mockFetch, [url, options], [url]],
  ['post', postApi, mockPost, [url, payload, options], [url, payload]],
  ['put', putApi, mockPut, [url, payload, options], [url, payload]],
  ['patch', patchApi, mockPut, [url, payload, options], [url, payload]],
  ['delete', deleteApi, mockDelete, [url, options], [url]],
];

beforeEach(() => {
  jest.clearAllMocks();
  getConfig.mockReturnValue({});
});

describe('explicit mock mode', () => {
  it.each([undefined, false, 'false', '', 'TRUE', '1', 1, null])(
    'uses real APIs for flag %p',
    (value) => {
      getConfig.mockReturnValue({ USE_MOCK_API: value });
      expect(isMockMode()).toBe(false);
    },
  );

  it.each([true, 'true'])('enables the demo only for %p', (value) => {
    getConfig.mockReturnValue({ USE_MOCK_API: value });
    expect(isMockMode()).toBe(true);
  });

  describe('SIS administration API configuration', () => {
    it('uses the dedicated administration API when configured', () => {
      getConfig.mockReturnValue({
        SIS_ADMIN_API_URL: 'https://sis.example.com/api/v1',
        LMS_BASE_URL: 'https://lms.example.com',
      });

      expect(getAdminApiUrl()).toBe('https://sis.example.com/api/v1');
      expect(getIntegrationApiUrl()).toBe('https://sis.example.com/api/v1/integration');
    });

    it('falls back to the LMS administration API', () => {
      getConfig.mockReturnValue({ LMS_BASE_URL: 'https://lms.example.com' });

      expect(getAdminApiUrl()).toBe('https://lms.example.com/api/sis/admin');
      expect(getIntegrationApiUrl()).toBe('https://lms.example.com/api/sis/admin/integration');
    });
  });

  describe('paginated SIS responses', () => {
    it('preserves pagination metadata', () => {
      const page = {
        count: 75,
        next: 'https://sis.example.com/api/v1/integration/outbox/?page=2',
        previous: null,
        results: [{ id: 1 }],
      };

      expect(normalizePageResponse(page)).toEqual(page);
    });

    it('normalizes an unpaginated response', () => {
      expect(normalizePageResponse([{ id: 1 }])).toEqual({
        count: 1,
        next: null,
        previous: null,
        results: [{ id: 1 }],
      });
    });
  });

  it('reads configuration after module import, not just at import time', () => {
    expect(isMockMode()).toBe(false);
    getConfig.mockReturnValue({ USE_MOCK_API: 'true' });
    expect(isMockMode()).toBe(true);
    getConfig.mockReturnValue({ USE_MOCK_API: 'false' });
    expect(isMockMode()).toBe(false);
  });
});

describe.each(requests)('%s API requests', (method, request, mockRequest, args, mockArgs) => {
  it.each([undefined, false, 'false'])('uses the authenticated client when flag is %p', async (flag) => {
    getConfig.mockReturnValue({ USE_MOCK_API: flag });
    const data = { id: 12 };
    const client = { [method]: jest.fn().mockResolvedValue({ data }) };
    getAuthenticatedHttpClient.mockReturnValue(client);

    await expect(request(...args)).resolves.toEqual(data);
    expect(client[method]).toHaveBeenCalledWith(...args);
    expect(mockRequest).not.toHaveBeenCalled();
  });

  it.each([true, 'true'])('uses only simulated data when flag is %p', async (flag) => {
    getConfig.mockReturnValue({ USE_MOCK_API: flag });
    mockRequest.mockResolvedValue({ demo: true });

    await expect(request(...args)).resolves.toEqual({ demo: true });
    expect(mockRequest).toHaveBeenCalledWith(...mockArgs);
    expect(getAuthenticatedHttpClient).not.toHaveBeenCalled();
  });

  it.each([401, 403, 500])('does not disguise HTTP %s as demo success', async (status) => {
    const error = Object.assign(new Error('API request failed'), { response: { status } });
    getAuthenticatedHttpClient.mockReturnValue({ [method]: jest.fn().mockRejectedValue(error) });

    await expect(request(...args)).rejects.toBe(error);
    expect(mockRequest).not.toHaveBeenCalled();
  });
});
