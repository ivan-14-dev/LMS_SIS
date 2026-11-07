const { test, expect } = require('@playwright/test');
const { loadGradeFixture } = require('./lms-grade-review-fixture');
const { respectApiRateLimit } = require('./api');

const mode = process.env.SIS_E2E_MODE || 'dual';
if (!['dual', 'secondaire', 'superieur'].includes(mode)) { throw new Error('Invalid SIS_E2E_MODE.'); }
const variants = mode === 'dual' ? ['secondaire', 'superieur'] : [mode];

async function openSearch(page, type, term) {
  await page.getByRole('button', { name: 'Ouvrir la palette de navigation' }).click();
  await page.getByRole('tab', { name: 'Dossiers', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Type de dossier' }).click();
  await page.getByRole('option', { name: type, exact: true }).click();
  await dialog.getByRole('textbox', { name: 'Rechercher un dossier' }).fill(term);
  await dialog.getByRole('button', { name: 'Rechercher les dossiers', exact: true }).click();
  await expect(dialog.getByRole('list', { name: 'Résultats de la recherche' })).toBeVisible();
  return dialog;
}

for (const variant of variants) {
  test(`${variant}: authorized typed search opens real learner and invoice details`, async ({ page }) => {
    // Extend the disposable grade fixture with invoiceId/Number/Prefix (25 matching invoices),
    // and documentId/Number for a university attestation. No records are created by this test.
    const { fixture, credentials } = loadGradeFixture(variant);
    expect(Number.isInteger(fixture.invoiceId)).toBe(true);
    expect(typeof fixture.invoiceNumber).toBe('string');
    expect(typeof fixture.invoicePrefix).toBe('string');
    await respectApiRateLimit(page);
    await page.goto(`/${variant}`);
    await page.getByRole('textbox', { name: 'Identifiant', exact: true }).fill(credentials.username);
    await page.getByLabel(/^Mot de passe/).fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.locator('.sis-layout')).toBeVisible();

    let dialog = await openSearch(page, variant === 'secondaire' ? 'Élèves' : 'Étudiants', fixture.learnerMatricule);
    await expect(dialog.getByRole('status')).toContainText('1 résultat(s)');
    const learnerLink = dialog.getByRole('link').filter({ hasText: fixture.learnerMatricule });
    await expect(learnerLink).toHaveAttribute('href', `/${variant}/${variant === 'secondaire' ? 'eleves' : 'etudiants'}/${fixture.learnerId}`);
    await learnerLink.click();
    await expect(page.getByText(`Matricule: ${fixture.learnerMatricule}`, { exact: true })).toBeVisible();

    dialog = await openSearch(page, 'Factures', fixture.invoicePrefix);
    await expect(dialog.getByRole('status')).toContainText('25 résultat(s) — page 1');
    await expect(dialog.getByRole('link')).toHaveCount(20);
    await dialog.getByRole('button', { name: 'Résultats suivants' }).click();
    await expect(dialog.getByRole('status')).toContainText('25 résultat(s) — page 2');
    await expect(dialog.getByRole('link')).toHaveCount(5);
    await expect(dialog.getByRole('button', { name: 'Résultats suivants' })).toBeDisabled();
    await dialog.getByRole('textbox', { name: 'Rechercher un dossier' }).fill('x');
    await expect(dialog.getByRole('button', { name: 'Rechercher les dossiers', exact: true })).toBeDisabled();
    await expect(dialog.getByRole('link')).toHaveCount(0);
    await dialog.getByRole('textbox', { name: 'Rechercher un dossier' }).fill(fixture.invoiceNumber);
    await dialog.getByRole('button', { name: 'Rechercher les dossiers', exact: true }).click();
    const invoiceLink = dialog.getByRole('link').filter({ hasText: fixture.invoiceNumber });
    await expect(invoiceLink).toHaveCount(1);
    await expect(invoiceLink).toHaveAttribute('href', `/${variant}/factures/${fixture.invoiceId}`);
    await invoiceLink.click();
    await expect(page.getByRole('heading', { name: 'Facture', exact: true })).toBeVisible();
    await expect(page.locator('dd').filter({ hasText: fixture.invoiceNumber })).toBeVisible();

    if (variant === 'superieur') {
      expect(Number.isInteger(fixture.documentId)).toBe(true);
      expect(typeof fixture.documentNumber).toBe('string');
      dialog = await openSearch(page, 'Attestations', fixture.documentNumber);
      const documentLink = dialog.getByRole('link').filter({ hasText: fixture.documentNumber });
      await expect(documentLink).toHaveAttribute('href', `/${variant}/documents/attestations/${fixture.documentId}`);
      await documentLink.click();
      await expect(page.getByRole('heading', { name: 'Attestation', exact: true })).toBeVisible();
      await expect(page.locator('dd').filter({ hasText: fixture.documentNumber })).toBeVisible();
      await expect(page.getByText(/La validation administrative n’est pas une signature numérique vérifiable/)).toBeVisible();
    }
  });
}
