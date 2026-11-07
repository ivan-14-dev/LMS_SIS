const { test, expect } = require('@playwright/test');
const { loadGradeFixture } = require('./lms-grade-review-fixture');
const { authenticatedApi, respectApiRateLimit } = require('./api');

const mode = process.env.SIS_E2E_MODE || 'dual';
if (!['dual', 'secondaire', 'superieur'].includes(mode)) { throw new Error('Invalid SIS_E2E_MODE.'); }
const variants = mode === 'dual' ? ['secondaire', 'superieur'] : [mode];

async function login(page, variant, username, password) {
  await respectApiRateLimit(page);
  await page.goto(`/${variant}`);
  await page.getByRole('textbox', { name: 'Identifiant', exact: true }).fill(username);
  await page.getByLabel(/^Mot de passe/).fill(password);
  await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
  await expect(page.locator('.sis-layout')).toBeVisible();
}

async function selectBatch(page, usernames) {
  const input = page.getByRole('combobox', { name: 'Comptes du lot' });
  // Each selection updates the same autocomplete; concurrent actions would race.
  /* eslint-disable no-await-in-loop */
  for (const username of usernames) {
    await input.fill(username);
    await page.getByRole('option').filter({ hasText: `(${username})` }).click();
  }
  /* eslint-enable no-await-in-loop */
  await input.press('Escape');
}

async function saveGroup(page, name) {
  await page.getByRole('textbox', { name: 'Nom du groupe' }).fill(name);
  const response = page.waitForResponse(item => (
    item.request().method() === 'POST' && new URL(item.url()).pathname === '/api/v1/utilisateurs/groupes/'
  ));
  await page.getByRole('button', { name: 'Enregistrer le groupe', exact: true }).click();
  const result = await response;
  expect(result.status(), await result.text()).toBe(201);
  await expect(page.getByText('Groupe enregistré.', { exact: true })).toBeVisible();
  return result.json();
}

async function postBatch(page, apiOrigin, groupId, ids) {
  const csrf = await page.request.get(`${apiOrigin}/csrf/api/v1/token`);
  expect(csrf.status()).toBe(200);
  return page.request.post(`${apiOrigin}/api/v1/utilisateurs/groupes/${groupId}/assign_many/`, {
    headers: {
      'X-CSRFToken': (await csrf.json()).csrfToken,
      Origin: process.env.SIS_E2E_URL,
    },
    data: { user_ids: ids },
  });
}

async function setGroupActive(page, group, active) {
  const label = `${group.name}${active ? ' (désactivé)' : ''}`;
  await page.getByRole('button', { name: label, exact: true }).click();
  await page.getByRole('checkbox', { name: 'Groupe actif', exact: true }).setChecked(active);
  const response = page.waitForResponse(item => (
    item.request().method() === 'PATCH'
    && new URL(item.url()).pathname === `/api/v1/utilisateurs/groupes/${group.id}/`
  ));
  await page.getByRole('button', { name: 'Enregistrer le groupe', exact: true }).click();
  const result = await response;
  expect(result.status(), await result.text()).toBe(200);
  expect((await result.json()).actif).toBe(active);
  await expect(page.getByText('Groupe enregistré.', { exact: true })).toBeVisible();
}

for (const variant of variants) {
  test(`${variant}: real group audit, duplication, atomic batches and learner denial`, async ({
    page, browser,
  }) => {
    // Disposable grade fixture extended with two account IDs/usernames and an unrelated group.
    // Both the staff and the learner use the configured synthetic fixture password.
    const {
      fixture, credentials, apiOrigin,
    } = loadGradeFixture(variant);
    expect(fixture.groupUserIds).toHaveLength(2);
    expect(fixture.groupUserNames).toHaveLength(2);
    expect(Number.isInteger(fixture.protectedGroupId)).toBe(true);
    const name = `Browser permissions ${variant} ${Date.now()}`;
    await login(page, variant, credentials.username, credentials.password);
    await page.goto(`/admin/utilisateurs?sis=${variant}`);
    await page.getByRole('tab', { name: 'Groupes et permissions', exact: true }).click();
    await page.getByRole('button', { name: 'Créer un groupe', exact: true }).click();
    await page.getByRole('checkbox', { name: /\(view_utilisateur\)$/ }).check();
    const source = await saveGroup(page, name);
    const api = authenticatedApi(page, variant);
    const accountGroups = async () => Promise.all(fixture.groupUserIds.map(async id => (
      (await api(`utilisateurs/comptes/${id}/`)).groups.slice().sort((a, b) => a - b)
    )));
    const before = await accountGroups();
    expect(before.every(groups => groups.includes(fixture.protectedGroupId))).toBe(true);
    await page.getByRole('button', { name, exact: true }).click();
    await selectBatch(page, fixture.groupUserNames);
    await page.getByRole('button', { name: 'Ajouter la sélection au groupe', exact: true }).click();
    await expect(page.getByText('Affectation en lot enregistrée.', { exact: true })).toBeVisible();
    expect(await accountGroups()).toEqual(before.map(groups => [...groups, source.id].sort((a, b) => a - b)));

    await page.getByRole('button', { name: 'Dupliquer le groupe', exact: true }).click();
    await expect(page.getByRole('checkbox', { name: /\(view_utilisateur\)$/ })).toBeChecked();
    const copy = await saveGroup(page, `${name} copy`);
    expect(copy.permissions).toEqual(source.permissions);
    expect(await accountGroups()).toEqual(before.map(groups => [...groups, source.id].sort((a, b) => a - b)));
    const invalid = await postBatch(page, apiOrigin, copy.id, [fixture.groupUserIds[0], 2147483647]);
    expect(invalid.status(), await invalid.text()).toBe(404);
    expect(await accountGroups()).toEqual(before.map(groups => [...groups, source.id].sort((a, b) => a - b)));

    await page.getByRole('button', { name, exact: true }).click();
    await selectBatch(page, fixture.groupUserNames);
    await page.getByRole('button', { name: 'Retirer la sélection du groupe', exact: true }).click();
    await expect(page.getByText('Affectation en lot enregistrée.', { exact: true })).toBeVisible();
    expect(await accountGroups()).toEqual(before);
    const history = page.getByRole('region', { name: 'Historique des habilitations' });
    await expect(history.getByText('Page 1 · 3 événements', { exact: true })).toBeVisible();
    const creation = history.locator('.MuiPaper-root').filter({
      has: page.getByRole('heading', { name: 'Création de groupe', exact: true }),
    });
    await creation.getByText('Voir les changements', { exact: true }).click();
    await expect(creation.getByText('Avant : Groupe absent', { exact: true })).toBeVisible();
    await expect(creation.getByText(`Après : ${name} — utilisateurs.view_utilisateur`, { exact: true })).toBeVisible();
    const auditPath = `core/workflow-events/?app_label=auth&model=group&object_id=${source.id}`;
    const audit = await api(auditPath);
    expect(audit.count).toBe(3);
    expect(audit.results.map(event => event.action)).toEqual(['unassign_many', 'assign_many', 'group_created']);
    expect(audit.results.every(event => event.object_id === String(source.id) && event.actor_nom)).toBe(true);
    expect(audit.results[0].metadata.removed_user_ids).toEqual(fixture.groupUserIds.slice().sort((a, b) => a - b));
    expect(audit.results[1].metadata.added_user_ids).toEqual(fixture.groupUserIds.slice().sort((a, b) => a - b));

    const context = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    try {
      const learnerPage = await context.newPage();
      await login(learnerPage, variant, fixture.learnerUsername, credentials.password);
      const denied = await postBatch(learnerPage, apiOrigin, copy.id, fixture.groupUserIds);
      expect(denied.status(), await denied.text()).toBe(403);
      const auditDenied = await learnerPage.request.get(`${apiOrigin}/api/v1/${auditPath}`);
      expect(auditDenied.status(), await auditDenied.text()).toBe(403);
      expect(await auditDenied.text()).not.toContain(name);
      expect(await accountGroups()).toEqual(before);
    } finally {
      await context.close();
    }
  });

  test(`${variant}: group deactivation revokes an existing learner session without removing memberships`, async ({
    page, browser,
  }) => {
    const { fixture, credentials, apiOrigin } = loadGradeFixture(variant);
    await login(page, variant, credentials.username, credentials.password);
    await page.goto(`/admin/utilisateurs?sis=${variant}`);
    await page.getByRole('tab', { name: 'Groupes et permissions', exact: true }).click();
    await page.getByRole('button', { name: 'Créer un groupe', exact: true }).click();
    await page.getByRole('checkbox', { name: /\(view_utilisateur\)$/ }).check();
    const group = await saveGroup(page, `Reversible group ${variant} ${Date.now()}`);
    expect(group.actif).toBe(true);
    const api = authenticatedApi(page, variant);
    const context = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    try {
      const learnerPage = await context.newPage();
      await login(learnerPage, variant, fixture.learnerUsername, credentials.password);
      const capabilities = async () => {
        const result = await learnerPage.request.get(`${apiOrigin}/api/v1/utilisateurs/comptes/capabilities/`);
        expect(result.status()).toBe(200);
        return result.json();
      };
      expect((await capabilities()).permissions).not.toContain('utilisateurs.view_utilisateur');
      await page.getByRole('button', { name: group.name, exact: true }).click();
      await selectBatch(page, fixture.groupUserNames);
      await page.getByRole('button', { name: 'Ajouter la sélection au groupe', exact: true }).click();
      await expect(page.getByText('Affectation en lot enregistrée.', { exact: true })).toBeVisible();
      const memberGroups = (await api(`utilisateurs/comptes/${fixture.groupUserIds[0]}/`)).groups;
      expect(memberGroups).toContain(group.id);
      const peerUrl = `${apiOrigin}/api/v1/utilisateurs/comptes/${fixture.groupUserIds[1]}/`;
      expect((await learnerPage.request.get(peerUrl)).status()).toBe(200);
      const activeCapabilities = await capabilities();
      expect(activeCapabilities.permissions).toContain('utilisateurs.view_utilisateur');
      expect(activeCapabilities.groups).toContain(group.name);

      await setGroupActive(page, group, false);
      expect((await learnerPage.request.get(peerUrl)).status()).toBe(404);
      const disabledCapabilities = await capabilities();
      expect(disabledCapabilities.permissions).not.toContain('utilisateurs.view_utilisateur');
      expect(disabledCapabilities.groups).not.toContain(group.name);
      expect((await api(`utilisateurs/comptes/${fixture.groupUserIds[0]}/`)).groups).toEqual(memberGroups);
      const disabled = await api(`utilisateurs/groupes/${group.id}/`);
      expect(disabled.actif).toBe(false);
      expect(disabled.permissions).toEqual(group.permissions);

      await setGroupActive(page, group, true);
      expect((await learnerPage.request.get(peerUrl)).status()).toBe(200);
      const restoredCapabilities = await capabilities();
      expect(restoredCapabilities.permissions).toContain('utilisateurs.view_utilisateur');
      expect(restoredCapabilities.groups).toContain(group.name);
      expect((await api(`utilisateurs/comptes/${fixture.groupUserIds[0]}/`)).groups).toEqual(memberGroups);
    } finally {
      try {
        await api(`utilisateurs/groupes/${group.id}/unassign_many/`, 'POST', { user_ids: fixture.groupUserIds });
      } finally {
        await context.close();
      }
    }
  });
}
