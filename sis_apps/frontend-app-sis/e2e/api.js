const { expect } = require('@playwright/test');

function authenticatedApi(page, variant) {
  const origin = new URL(process.env.SIS_E2E_URL);
  origin.hostname = `${variant}.validation.localhost`;
  return async (path, method = 'GET', data = undefined) => {
    const result = await page.evaluate(async (request) => {
      const headers = { 'Content-Type': 'application/json' };
      if (request.method !== 'GET') {
        const csrf = await fetch(`${request.origin}/csrf/api/v1/token`, { credentials: 'include' });
        if (!csrf.ok) { throw new Error(`CSRF failed: ${csrf.status}`); }
        headers['X-CSRFToken'] = (await csrf.json()).csrfToken;
      }
      const response = await fetch(`${request.origin}/api/v1/${request.path}`, {
        method: request.method,
        credentials: 'include',
        headers,
        body: request.data === undefined ? undefined : JSON.stringify(request.data),
      });
      return { status: response.status, body: await response.text() };
    }, {
      origin: origin.origin, path, method, data,
    });
    expect(result.status, result.body).toBeGreaterThanOrEqual(200);
    expect(result.status, result.body).toBeLessThan(300);
    return JSON.parse(result.body);
  };
}

async function respectApiRateLimit(page) {
  let nextRequest = 0;
  await page.route('**/api/v1/**', async (route) => {
    const scheduled = Math.max(Date.now(), nextRequest);
    nextRequest = scheduled + 700;
    await new Promise(resolve => { setTimeout(resolve, Math.max(0, scheduled - Date.now())); });
    await route.continue();
  });
}

module.exports = { authenticatedApi, respectApiRateLimit };
