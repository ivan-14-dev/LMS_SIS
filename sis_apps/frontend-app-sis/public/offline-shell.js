const ASSET_NAME = /^(?:[a-zA-Z0-9_-]+\.)?[a-f0-9]{16,}\.(js|css|woff2?|ttf|svg|eot)$/;
const TYPES = {
  js: /(?:javascript|ecmascript)/i,
  css: /^text\/css/i,
  woff: /(?:font\/woff|application\/font-woff)/i,
  woff2: /(?:font\/woff2|application\/font-woff2)/i,
  ttf: /(?:font\/ttf|application\/x-font-ttf)/i,
  svg: /^image\/svg\+xml/i,
  eot: /(?:application\/vnd\.ms-fontobject)/i,
};
const scope = new URL(globalThis.registration.scope);
const CACHE_NAME = `sis-public-shell-v1:${scope.pathname}`;

const assetType = (request) => {
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== scope.origin || url.search || url.hash
    || !url.pathname.startsWith(scope.pathname)) { return null; }
  const file = url.pathname.slice(scope.pathname.length);
  if (file.includes('/')) { return null; }
  const match = ASSET_NAME.exec(file);
  return match && match[1];
};

const prime = async (url) => {
  const request = new Request(url, { credentials: 'omit', mode: 'same-origin' });
  const type = assetType(request);
  if (!type) { return; }
  const response = await fetch(request);
  if (!response.ok || response.redirected || response.type !== 'basic'
    || !TYPES[type].test(response.headers.get('Content-Type') || '')
    || /(?:private|no-store|no-cache|max-age=0(?:\D|$))/i.test(response.headers.get('Cache-Control') || '')
    || response.headers.has('Set-Cookie') || (response.headers.has('Vary')
      && /(?:cookie|authorization)/i.test(response.headers.get('Vary') || ''))) { return; }
  const cache = await caches.open(CACHE_NAME);
  await cache.put(request, response);
};

const offlinePage = () => new Response(
  '<!doctype html><html lang="fr"><meta charset="utf-8"><title>SIS — Hors connexion</title>'
    + '<main><h1>Connexion indisponible</h1><p>Le SIS nécessite une connexion et une authentification.'
    + ' Aucune donnée privée n’est disponible hors connexion et aucun formulaire ne peut être envoyé.'
    + ' Rétablissez la connexion, puis rechargez la page.</p></main></html>',
  { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Content-Security-Policy': "default-src 'none'" } },
);

const isAppNavigation = (request) => {
  if (request.mode !== 'navigate' || request.method !== 'GET') { return false; }
  const url = new URL(request.url);
  if (url.origin !== scope.origin || !url.pathname.startsWith(scope.pathname)) { return false; }
  const path = url.pathname.slice(scope.pathname.length);
  return path === '' || /^(?:secondaire|superieur|forgot-password|reset-password)(?:\/|$)/.test(path);
};

globalThis.addEventListener('install', event => event.waitUntil(globalThis.skipWaiting()));
globalThis.addEventListener('activate', event => event.waitUntil(globalThis.clients.claim()));
globalThis.addEventListener('message', (event) => {
  if (event.data?.type === 'SIS_OFFLINE_SHELL_DISABLE') {
    event.waitUntil((async () => {
      await caches.delete(CACHE_NAME);
      await globalThis.registration.unregister();
    })());
  } else if (event.data?.type === 'SIS_OFFLINE_SHELL_ASSETS' && Array.isArray(event.data.assets)) {
    event.waitUntil(Promise.allSettled(event.data.assets.slice(0, 30).map(prime)));
  }
});
globalThis.addEventListener('fetch', (event) => {
  if (assetType(event.request)) {
    event.respondWith((async () => {
      try {
        const response = await fetch(event.request);
        event.waitUntil(prime(event.request.url).catch(() => {}));
        return response;
      } catch (error) {
        const cached = await (await caches.open(CACHE_NAME)).match(event.request.url);
        if (cached) { return cached; }
        throw error;
      }
    })());
  } else if (isAppNavigation(event.request)) {
    event.respondWith(fetch(event.request).catch(() => offlinePage()));
  }
});
