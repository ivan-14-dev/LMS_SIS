const asset = 'http://localhost/app.5a1b2c3d4e5f67890123456789012345.js';
const originalRegistration = globalThis.registration;
const originalCaches = global.caches;
const originalFetch = global.fetch;
const originalRequest = global.Request;
const originalResponse = global.Response;

let handlers;
let store;
let response;

const request = (url, options = {}) => ({
  url, method: 'GET', mode: 'cors', credentials: 'include', ...options,
});
const eventFor = req => ({
  request: req,
  waitUntil: jest.fn(),
  respondWith: jest.fn(),
});

beforeEach(() => {
  jest.resetModules();
  handlers = {};
  store = new Map();
  jest.spyOn(globalThis, 'addEventListener').mockImplementation((name, handler) => { handlers[name] = handler; });
  Object.defineProperty(globalThis, 'registration', {
    configurable: true,
    value: { scope: 'http://localhost/', unregister: jest.fn().mockResolvedValue(true) },
  });
  global.Request = function MockRequest(url, options) {
    Object.assign(this, request(url, options));
  };
  global.Response = function MockResponse(body, options) {
    this.body = body;
    this.headers = options.headers;
  };
  global.caches = {
    open: jest.fn().mockResolvedValue({
      put: jest.fn(async (req, res) => { store.set(req.url, res); }),
      match: jest.fn(async url => store.get(url)),
    }),
    delete: jest.fn().mockResolvedValue(true),
  };
  response = {
    ok: true,
    redirected: false,
    type: 'basic',
    headers: new Map([['Content-Type', 'text/javascript']]),
  };
  global.fetch = jest.fn().mockResolvedValue(response);
  // eslint-disable-next-line global-require
  require('./offline-shell');
});

afterEach(() => {
  globalThis.addEventListener.mockRestore();
  Object.defineProperty(globalThis, 'registration', { configurable: true, value: originalRegistration });
  global.caches = originalCaches;
  global.fetch = originalFetch;
  global.Request = originalRequest;
  global.Response = originalResponse;
});

it('primes only anonymous versioned static assets and serves them after a network failure', async () => {
  const msg = {
    data: {
      type: 'SIS_OFFLINE_SHELL_ASSETS',
      assets: [
        asset, 'http://localhost/api/v1/users/me', 'https://other.example/app.5a1b2c3d4e5f67890123456789012345.js',
      ],
    },
    waitUntil: jest.fn(),
  };
  handlers.message(msg);
  await msg.waitUntil.mock.calls[0][0];
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(global.fetch.mock.calls[0][0].credentials).toBe('omit');
  expect(store.get(asset)).toBe(response);

  global.fetch.mockRejectedValue(new Error('offline'));
  const event = eventFor(request(asset));
  handlers.fetch(event);
  await expect(event.respondWith.mock.calls[0][0]).resolves.toBe(response);
});

it('never intercepts private API requests, credentials, or non-GET traffic', () => {
  [
    request('http://localhost/api/v1/users/me'),
    request('http://localhost/auth/session'),
    request(asset, { method: 'POST' }),
    request('http://localhost/app.5a1b2c3d4e5f67890123456789012345.js?token=secret'),
    request('https://other.example/app.5a1b2c3d4e5f67890123456789012345.js'),
  ].forEach((req) => {
    const event = eventFor(req);
    handlers.fetch(event);
    expect(event.respondWith).not.toHaveBeenCalled();
  });
  expect(global.caches.open).not.toHaveBeenCalled();
});

it('rejects private, varied or mislabeled responses even for asset-looking URLs', async () => {
  const variedHeaders = [
    new Map([['Content-Type', 'application/json']]),
    new Map([['Content-Type', 'text/javascript'], ['Cache-Control', 'private']]),
    new Map([['Content-Type', 'text/javascript'], ['Cache-Control', 'no-cache']]),
    new Map([['Content-Type', 'text/javascript'], ['Vary', 'Cookie']]),
  ];
  await Promise.all(variedHeaders.map(async (headers) => {
    global.fetch.mockResolvedValueOnce({ ...response, headers });
    const event = { data: { type: 'SIS_OFFLINE_SHELL_ASSETS', assets: [asset] }, waitUntil: jest.fn() };
    handlers.message(event);
    await event.waitUntil.mock.calls[0][0];
  }));
  expect(store.size).toBe(0);
});

it('shows only an inert notice for an offline app navigation, not an API navigation', async () => {
  global.fetch.mockRejectedValue(new Error('offline'));
  const nav = eventFor(request('http://localhost/secondaire', { mode: 'navigate' }));
  handlers.fetch(nav);
  const page = await nav.respondWith.mock.calls[0][0];
  expect(page.body).toContain('aucun formulaire ne peut être envoyé');
  expect(page.body).not.toMatch(/<form|<script/i);
  const api = eventFor(request('http://localhost/api/v1/users/me', { mode: 'navigate' }));
  handlers.fetch(api);
  expect(api.respondWith).not.toHaveBeenCalled();
});

it('deletes only its own cache and unregisters when disabled', async () => {
  const event = { data: { type: 'SIS_OFFLINE_SHELL_DISABLE' }, waitUntil: jest.fn() };
  handlers.message(event);
  await event.waitUntil.mock.calls[0][0];
  expect(global.caches.delete).toHaveBeenCalledWith('sis-public-shell-v1:/');
  expect(globalThis.registration.unregister).toHaveBeenCalledTimes(1);
});
