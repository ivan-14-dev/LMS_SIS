const fs = require('fs');
const { expect } = require('@playwright/test');
const { respectApiRateLimit } = require('./api');

const mode = process.env.SIS_E2E_MODE || 'dual';
if (!['dual', 'secondaire', 'superieur'].includes(mode)) { throw new Error('Invalid SIS_E2E_MODE.'); }
const variants = mode === 'dual' ? ['secondaire', 'superieur'] : [mode];

function loadFixture(variant) {
  if (process.env.SIS_PROJECTS_E2E_ISOLATED !== '1'
      || !process.env.SIS_PROJECTS_E2E_FIXTURE || !process.env.SIS_E2E_CREDENTIALS || !process.env.SIS_E2E_URL) {
    throw new Error('Projects require SIS_PROJECTS_E2E_ISOLATED=1 and explicit fixture, credentials and URL.');
  }
  const origin = new URL(process.env.SIS_E2E_URL);
  if (!['http:', 'https:'].includes(origin.protocol) || origin.hostname !== 'validation.localhost'
      || Number(origin.port) <= 1024) {
    throw new Error('Projects may mutate only a disposable validation.localhost stack on an explicit port above 1024.');
  }
  const config = JSON.parse(fs.readFileSync(process.env.SIS_PROJECTS_E2E_FIXTURE, 'utf8'));
  const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
  const fixture = config.variants?.[variant];
  if (config.isolated !== true || config.kind !== 'projects' || new URL(config.baseUrl).origin !== origin.origin
      || !Array.isArray(fixture?.learnerUserIds) || fixture.learnerUserIds.length !== 2
      || !fixture.learnerUserIds.every(id => Number.isInteger(id) && id > 0)
      || new Set(fixture.learnerUserIds).size !== 2
      || !Array.isArray(fixture.learnerUsernames) || fixture.learnerUsernames.length !== 2
      || !fixture.learnerUsernames.every(name => typeof name === 'string' && name.trim())
      || !credentials.username || !credentials.password) {
    throw new Error('Invalid isolated project fixture or synthetic credentials.');
  }
  origin.hostname = `${variant}.validation.localhost`;
  return { fixture, credentials, apiOrigin: origin.origin };
}

async function login(page, variant, username, password) {
  await respectApiRateLimit(page);
  await page.goto(`/${variant}`);
  await page.getByRole('textbox', { name: 'Identifiant', exact: true }).fill(username);
  await page.getByLabel(/^Mot de passe/).fill(password);
  const [response] = await Promise.all([
    page.waitForResponse(item => (
      item.request().method() === 'POST' && new URL(item.url()).pathname === '/api/v1/auth/session/'
    )),
    page.getByRole('button', { name: 'Se connecter', exact: true }).click(),
  ]);
  expect(response.status()).toBe(200);
  await expect(page.locator('.sis-layout')).toBeVisible();
}

async function choose(page, label, query, name) {
  const field = page.getByRole('combobox', { name: label });
  await field.fill(query);
  await page.getByRole('option', { name, exact: true }).click();
}

async function submit(page, endpoint, status = 201, label = 'Enregistrer') {
  const [result] = await Promise.all([
    page.waitForResponse(item => (
      item.request().method() === 'POST' && new URL(item.url()).pathname === `/api/v1/${endpoint}`
    )),
    page.getByRole('dialog').getByRole('button', { name: label, exact: true }).click(),
  ]);
  expect(result.status(), await result.text()).toBe(status);
  await expect(page.getByRole('dialog')).not.toBeVisible();
  return result.json();
}

async function command(page, origin, path, method, data, status) {
  const csrf = await page.request.get(`${origin}/csrf/api/v1/token`);
  expect(csrf.status()).toBe(200);
  const response = await page.request.fetch(`${origin}${path}`, {
    method, data, headers: { 'X-CSRFToken': (await csrf.json()).csrfToken },
  });
  expect(response.status(), await response.text()).toBe(status);
  return status === 204 ? null : response.json();
}

module.exports = {
  variants, loadFixture, login, choose, submit, command,
};
