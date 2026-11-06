import { disableOfflineShell, registerOfflineShell } from './offlineShellRegistration';

jest.mock('./offlineShellWorkerUrl', () => 'http://localhost/5a1b2c3d4e5f67890123456789012345.js');

const originalServiceWorker = navigator.serviceWorker;
const originalProtocol = window.location.protocol;

afterEach(() => {
  document.querySelector('meta[name="sis-offline-shell"]')?.remove();
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: originalServiceWorker });
});

const serviceWorker = (active) => {
  const worker = {
    controller: { postMessage: jest.fn() },
    register: jest.fn().mockResolvedValue({ active }),
    ready: Promise.resolve({ active }),
  };
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: worker });
  return worker;
};

it('does not register unless explicitly enabled, even when supported', async () => {
  const worker = serviceWorker({ postMessage: jest.fn() });
  await registerOfflineShell();
  expect(worker.register).not.toHaveBeenCalled();

  disableOfflineShell();
  expect(worker.controller.postMessage).toHaveBeenCalledWith({ type: 'SIS_OFFLINE_SHELL_DISABLE' });
});

it('registers on localhost and primes only via the worker', async () => {
  const active = { postMessage: jest.fn() };
  const worker = serviceWorker(active);
  const meta = document.createElement('meta');
  meta.name = 'sis-offline-shell';
  meta.content = 'enabled';
  document.head.append(meta);
  const script = document.createElement('script');
  script.src = '/app.5a1b2c3d4e5f67890123456789012345.js';
  document.body.append(script);
  try {
    expect(originalProtocol).toBe('http:');
    await registerOfflineShell();
    expect(worker.register).toHaveBeenCalledWith(
      'http://localhost/5a1b2c3d4e5f67890123456789012345.js',
      { scope: '/' },
    );
    expect(active.postMessage).toHaveBeenCalledWith({
      type: 'SIS_OFFLINE_SHELL_ASSETS',
      assets: expect.arrayContaining([script.src]),
    });
    disableOfflineShell();
    expect(worker.controller.postMessage).not.toHaveBeenCalled();
  } finally {
    script.remove();
  }
});
