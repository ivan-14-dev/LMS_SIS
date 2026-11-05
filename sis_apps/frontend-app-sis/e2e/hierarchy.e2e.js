const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { authenticatedApi, respectApiRateLimit } = require('./api');
const { capturePresentation, captureDialog } = require('./presentation');

const variants = process.env.SIS_E2E_MODE === 'dual'
  ? ['secondaire', 'superieur'] : [process.env.SIS_E2E_MODE || 'secondaire'];

async function select(page, label, option) {
  await page.getByLabel(label, { exact: true }).click();
  await page.getByRole('option', { name: option, exact: true }).click();
}

for (const variant of variants) {
  test(`${variant}: organization, inherited rules, dated publication and audit`, async ({ page }, testInfo) => {
    await respectApiRateLimit(page);
    const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
    await page.goto(`/admin/etablissement?sis=${variant}`);
    await page.getByLabel('Identifiant').fill(credentials.username);
    await page.getByLabel('Mot de passe').fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Configuration établissement', exact: true })).toBeVisible();
    const api = authenticatedApi(page, variant);
    const original = await api('etablissement/current/');
    const offering = original.configuration_schema.institutional_profiles.profiles.find(item => item.code === 'primary').template;
    await api('etablissement/current/', 'PATCH', { configuration_academique: { learning_offerings: [offering] } });
    await page.getByRole('tab', { name: 'Organisation et règles', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Enregistrer la configuration' })).toHaveCount(0);
    await page.getByRole('region', { name: 'Unités d’organisation', exact: true }).getByRole('button', { name: 'Ajouter', exact: true }).click();
    const dialog = page.getByRole('dialog');
    const code = `cfg-${variant}-${Date.now()}`;
    await dialog.getByLabel('Code de l’unité', { exact: false }).fill(code);
    await dialog.getByLabel('Nom de l’unité', { exact: false }).fill('Campus de recette');
    await dialog.getByLabel(/Type d’unité/).click();
    await page.getByRole('option', { name: 'Campus', exact: true }).click();
    await captureDialog(page, `${variant}-unit-form`, testInfo);
    const created = page.waitForResponse(response => response.url().endsWith('/etablissement/unites/')
      && response.request().method() === 'POST');
    await dialog.getByRole('button', { name: 'Enregistrer', exact: true }).click();
    const unitResponse = await created;
    expect(unitResponse.status()).toBe(201);
    const unit = await unitResponse.json();
    await expect(dialog).not.toBeVisible();
    await page.getByRole('button', { name: 'Règles héritées', exact: true }).click();
    await select(page, 'Périmètre des règles', `${code} - Campus de recette`);
    await expect(page.getByText('Configuration actuellement effective.')).toBeVisible();
    await select(page, 'Règle d’offre', 'Choisir une offre institutionnelle');
    await select(page, 'Offre à publier', offering.label);
    await page.getByLabel('Verrouiller cette valeur pour les périmètres inférieurs').check();
    await page.getByLabel('Motif de publication').fill('Règles du campus de recette');
    await page.getByRole('button', { name: 'Simuler les règles', exact: true }).click();
    await expect(page.getByText('Simulation — aucun changement enregistré.')).toBeVisible();
    expect((await api(`etablissement/current/hierarchy/?unit=${unit.id}`)).history).toHaveLength(0);
    await page.getByRole('button', { name: 'Publier les règles', exact: true }).click();
    await expect(page.getByText('Configuration publiée. Les dossiers existants sont conservés.')).toBeVisible();
    await expect(page.getByText(`Offre effective : ${offering.label}`, { exact: true })).toBeVisible();
    await capturePresentation(page, `${variant}-hierarchy`, testInfo);
    await page.setViewportSize({ width: 1440, height: 960 });
    const saved = await api(`etablissement/current/hierarchy/?unit=${unit.id}`);
    expect(saved.effective.locks['learning.offering'].unit).toBe(unit.id);
    expect(saved.history[0].reason).toBe('Règles du campus de recette');
    await select(page, 'Règle d’offre', 'Hériter du périmètre supérieur');
    const date = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000);
    const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    await page.getByLabel('Date d’effet (heure de cet appareil, vide : maintenant)').fill(localDate);
    await page.getByLabel('Motif de publication').fill('Retour futur à l’héritage');
    await page.getByRole('button', { name: 'Simuler les règles', exact: true }).click();
    await expect(page.getByText('Offre effective : Aucune', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Publier les règles', exact: true }).click();
    await expect(page.getByText('Configuration publiée. Les dossiers existants sont conservés.')).toBeVisible();
    await expect(page.getByText(`Offre effective : ${offering.label}`, { exact: true })).toBeVisible();
    await page.getByLabel('Date à consulter (heure de cet appareil)').fill(localDate);
    await page.getByRole('button', { name: 'Consulter les règles à cette date', exact: true }).click();
    await expect(page.getByText('Configuration à la date consultée.')).toBeVisible();
    await expect(page.getByText('Offre effective : Aucune', { exact: true })).toBeVisible();
    await api('etablissement/current/', 'PATCH', {
      configuration_academique: { learning_offerings: original.configuration_academique.learning_offerings || [] },
    });
  });
}
