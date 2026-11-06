import workerUrl from './offlineShellWorkerUrl';

const enabled = () => document.querySelector('meta[name="sis-offline-shell"]')?.content === 'enabled';

export const disableOfflineShell = () => {
  if ('serviceWorker' in navigator && !enabled()) {
    navigator.serviceWorker.controller?.postMessage({ type: 'SIS_OFFLINE_SHELL_DISABLE' });
  }
};

export const registerOfflineShell = async () => {
  if (!enabled() || !('serviceWorker' in navigator) || (window.location.protocol !== 'https:'
    && window.location.hostname !== 'localhost')) { return; }

  const url = new URL(workerUrl, window.location.href);
  if (url.origin !== window.location.origin) { return; }

  try {
    const registration = await navigator.serviceWorker.register(url.href, {
      scope: new URL('.', url).pathname,
    });
    const assets = [...document.querySelectorAll('script[src], link[rel="stylesheet"][href]')]
      .map(element => element.src || element.href);
    const active = registration.active || (await navigator.serviceWorker.ready).active;
    active?.postMessage({ type: 'SIS_OFFLINE_SHELL_ASSETS', assets });
  } catch {
    // Offline support is optional and must never prevent application startup.
  }
};
