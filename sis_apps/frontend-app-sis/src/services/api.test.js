import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getConfig } from '@edx/frontend-platform';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import axios from 'axios';
import {
  deleteApi,
  fetchApi,
  fetchCollection,
  getAdminApiUrl,
  getCurrentEstablishmentUrl,
  getIntegrationApiUrl,
  normalizePageResponse,
  patchApi,
  postApi,
  putApi,
  requestIntegrationUserSynchronization,
  useIntegrationUserCandidates,
} from './api';
import { localHttpClient } from './localSession';
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

describe('complete collection requests', () => {
  it('loads later pages instead of truncating at the server page size', async () => {
    const get = jest.fn()
      .mockResolvedValueOnce({ data: { count: 51, results: [{ id: 1 }], next: `${url}?page=2` } })
      .mockResolvedValueOnce({ data: { count: 51, results: [{ id: 51 }], next: null } });
    getAuthenticatedHttpClient.mockReturnValue({ get });
    expect(await fetchCollection(url)).toEqual([{ id: 1 }, { id: 51 }]);
    expect(get).toHaveBeenLastCalledWith(`${url}?page=2`, {});
  });

  it.each(['https://outside.example/collect', url])('rejects unsafe or cyclic pagination to %s', async (next) => {
    const get = jest.fn().mockResolvedValue({ data: { count: 2, results: [{ id: 1 }], next } });
    getAuthenticatedHttpClient.mockReturnValue({ get });
    await expect(fetchCollection(url)).rejects.toThrow('pagination invalide');
    expect(get).toHaveBeenCalledTimes(1);
  });

  it('does not return a successful partial export when a later page fails', async () => {
    const get = jest.fn()
      .mockResolvedValueOnce({ data: { count: 2, results: [{ id: 1 }], next: `${url}?page=2` } })
      .mockRejectedValueOnce(new Error('Server unavailable'));
    getAuthenticatedHttpClient.mockReturnValue({ get });
    await expect(fetchCollection(url)).rejects.toThrow('Server unavailable');
  });
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
      expect(getCurrentEstablishmentUrl()).toBe(
        'https://sis.example.com/api/v1/etablissement/current/',
      );
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

describe('individual LMS identity synchronization', () => {
  const receipt = { status: 'ok', username_edx: 'sis_owned_identity', user_id_edx: 83 };
  const integrationUrl = 'https://secondaire.example/api/v1/integration';
  const synchronize = () => requestIntegrationUserSynchronization(integrationUrl, 41, receipt.username_edx);

  it.each(['secondaire', 'superieur'])('posts only an empty object through the authenticated client for %s', async (variant) => {
    const post = jest.fn().mockResolvedValue({ status: 200, data: receipt });
    getAuthenticatedHttpClient.mockReturnValue({ post });
    const scopedUrl = `https://${variant}.example/api/v1/integration`;
    await expect(requestIntegrationUserSynchronization(scopedUrl, 41, receipt.username_edx)).resolves.toEqual(receipt);
    expect(post.mock.calls).toEqual([[`${scopedUrl}/sync/user/41/`, {}]]);
    expect(mockPost).not.toHaveBeenCalled();
  });

  describe('first-association candidate pages', () => {
    const candidateEndpoint = 'https://sis.example.com/api/v1/integration';
    const candidate = {
      user_sis: 41,
      user_sis_username: 'alice',
      user_sis_name: 'Alice Martin',
      username_edx: 'sis_canonical_opaque',
      user_id_edx: null,
      actif: true,
    };
    const response = {
      count: 51, next: 'https://untrusted.example/unused', previous: '?page=1', results: [candidate],
    };
    const renderCandidates = (enabled = false) => {
      const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
      const wrapper = ({ children }) => React.createElement(QueryClientProvider, { client }, children);
      return {
        client,
        ...renderHook(({ active }) => useIntegrationUserCandidates(2, active), {
          wrapper, initialProps: { active: enabled },
        }),
      };
    };

    beforeEach(() => {
      window.history.replaceState({}, '', '/admin/integration-lms');
      getConfig.mockReturnValue({ SIS_ADMIN_API_URL: 'https://sis.example.com/api/v1' });
    });

    it('fetches only the explicitly enabled page without inventing a mapping ID or following next', async () => {
      const get = jest.fn().mockResolvedValue({ data: response });
      const post = jest.fn();
      getAuthenticatedHttpClient.mockReturnValue({ get, post });
      const view = renderCandidates();
      expect(get).not.toHaveBeenCalled();
      view.rerender({ active: true });
      await waitFor(() => expect(view.result.current.isSuccess).toBe(true));
      expect(view.result.current.data).toEqual(response);
      expect(view.result.current.data.results[0]).not.toHaveProperty('id');
      expect(get.mock.calls).toEqual([[
        `${candidateEndpoint}/mappings/users/candidates/?page=2`, { signal: expect.any(AbortSignal) },
      ]]);
      expect(post).not.toHaveBeenCalled();
    });

    it.each([403, 404, 503])('preserves HTTP %s errors instead of an empty candidate list', async (status) => {
      const error = { response: { status, data: { detail: 'Lecture refusée ou indisponible.' } } };
      getAuthenticatedHttpClient.mockReturnValue({ get: jest.fn().mockRejectedValue(error) });
      const view = renderCandidates(true);
      await waitFor(() => expect(view.result.current.isError).toBe(true));
      expect(view.result.current.error).toBe(error);
      expect(view.result.current.data).toBeUndefined();
    });

    it('invalidates every candidate and mapping page of only its own SIS without preloading disabled lists', async () => {
      const get = jest.fn();
      getAuthenticatedHttpClient.mockReturnValue({ get });
      const view = renderCandidates();
      const ownKeys = ['user-candidates', 'user-mappings'].flatMap(resource => [1, 2, 3]
        .map(pageNumber => ['integration', resource, pageNumber, candidateEndpoint]));
      const otherKeys = ownKeys.map(key => [...key.slice(0, 3), 'https://other.example/api/v1/integration']);
      [...ownKeys, ...otherKeys].forEach(key => view.client.setQueryData(key, response));
      await act(async () => view.result.current.invalidatePages());
      ownKeys.forEach(key => expect(view.client.getQueryState(key).isInvalidated).toBe(true));
      otherKeys.forEach(key => expect(view.client.getQueryState(key).isInvalidated).toBe(false));
      expect(get).not.toHaveBeenCalled();
    });
  });

  it('uses the actual local-session cookie and CSRF interceptor instead of the edX client', async () => {
    getConfig.mockReturnValue({ SIS_AUTH_MODE: 'local' });
    const csrf = jest.spyOn(axios, 'get').mockResolvedValue({ data: { csrfToken: 'test-csrf-token' } });
    const originalAdapter = localHttpClient.defaults.adapter;
    const adapter = jest.fn(async config => ({
      config, headers: {}, status: 200, statusText: 'OK', data: receipt,
    }));
    localHttpClient.defaults.adapter = adapter;
    try {
      await expect(synchronize()).resolves.toEqual(receipt);
      expect(csrf).toHaveBeenCalledWith('https://secondaire.example/csrf/api/v1/token', { withCredentials: true });
      expect(adapter).toHaveBeenCalledTimes(1);
      const [request] = adapter.mock.calls[0];
      expect(request).toMatchObject({
        url: `${integrationUrl}/sync/user/41/`, method: 'post', withCredentials: true, data: '{}',
      });
      expect(request.headers.get('X-CSRFToken')).toBe('test-csrf-token');
      expect(getAuthenticatedHttpClient).not.toHaveBeenCalled();
    } finally {
      localHttpClient.defaults.adapter = originalAdapter;
      csrf.mockRestore();
    }
  });

  it.each([
    null,
    { status: 201, data: receipt },
    { status: 200, data: null },
    { status: 200, data: { ...receipt, status: 'queued' } },
    { status: 200, data: { ...receipt, username_edx: 'another_identity' } },
    ...[undefined, null, 0, -1, 1.5, '83', true, Number.MAX_SAFE_INTEGER + 1]
      .map(userId => ({ status: 200, data: { ...receipt, user_id_edx: userId } })),
  ])('rejects an unconfirmed response %p', async (response) => {
    getAuthenticatedHttpClient.mockReturnValue({ post: jest.fn().mockResolvedValue(response) });
    await expect(synchronize()).rejects.toThrow('n’a pas confirmé l’identité LMS');
    expect(mockPost).not.toHaveBeenCalled();
  });

  it.each([
    [0, receipt.username_edx],
    ['41', receipt.username_edx],
    [41, ''],
    [41, null],
  ])('refuses an invalid selected identity %p / %p before sending', async (userSis, username) => {
    await expect(requestIntegrationUserSynchronization(integrationUrl, userSis, username)).rejects.toThrow('identité SIS–LMS');
    expect(getAuthenticatedHttpClient).not.toHaveBeenCalled();
  });

  it('does not simulate synchronization in demo mode', async () => {
    getConfig.mockReturnValue({ USE_MOCK_API: true });
    await expect(synchronize()).rejects.toThrow('mode démonstration');
    expect(getAuthenticatedHttpClient).not.toHaveBeenCalled();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('requires the same native ID when one is already recorded on the selected mapping', async () => {
    const post = jest.fn().mockResolvedValue({ status: 200, data: receipt });
    getAuthenticatedHttpClient.mockReturnValue({ post });
    await expect(requestIntegrationUserSynchronization(integrationUrl, 41, receipt.username_edx, 84))
      .rejects.toThrow('n’a pas confirmé l’identité LMS');
    await expect(requestIntegrationUserSynchronization(integrationUrl, 41, receipt.username_edx, 83))
      .resolves.toEqual(receipt);
    expect(post.mock.calls).toEqual(Array(2).fill([`${integrationUrl}/sync/user/41/`, {}]));
  });

  it.each([undefined, 403, 500])('preserves a transport or HTTP %s failure for deliberate same-identity retry', async (status) => {
    const error = Object.assign(new Error('Réponse perdue'), status ? { response: { status } } : {});
    const post = jest.fn().mockRejectedValueOnce(error).mockResolvedValueOnce({ status: 200, data: receipt });
    getAuthenticatedHttpClient.mockReturnValue({ post });
    await expect(synchronize()).rejects.toBe(error);
    expect(post).toHaveBeenCalledTimes(1);
    await expect(synchronize()).resolves.toEqual(receipt);
    expect(post.mock.calls).toEqual([
      [`${integrationUrl}/sync/user/41/`, {}],
      [`${integrationUrl}/sync/user/41/`, {}],
    ]);
    expect(mockPost).not.toHaveBeenCalled();
  });
});
