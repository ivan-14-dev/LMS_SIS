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
  test(`${variant}: authorized typed search opens real academic and financial details`, async ({ page }) => {
    // Extend the disposable grade fixture with invoiceId/Number/Prefix (25 matching invoices),
    // documentId/Number for an attestation, bulletinId for a school bulletin and courseMappingId.
    // Learner paths require learnerUsername (same synthetic password) and peerInvoiceId/Number.
    // No records are created by this test.
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

    expect(Number.isInteger(fixture.courseMappingId)).toBe(true);
    dialog = await openSearch(page, 'Cours LMS', fixture.courseId);
    const courseLink = dialog.getByRole('link').filter({ hasText: fixture.courseId });
    await expect(courseLink).toHaveAttribute('href', `/${variant}/cours/${fixture.courseMappingId}`);
    await courseLink.click();
    await expect(page.getByRole('heading', { name: 'Cours LMS', exact: true })).toBeVisible();
    await expect(page.locator('dd').filter({ hasText: fixture.courseId })).toBeVisible();

    dialog = await openSearch(page, 'Évaluations reliées au LMS', fixture.evaluationTitle);
    const evaluationLink = dialog.getByRole('link').filter({ hasText: fixture.evaluationTitle });
    await expect(evaluationLink).toHaveAttribute('href', `/${variant}/evaluations_lms/${fixture.evaluationId}`);
    await evaluationLink.click();
    await expect(page.getByRole('heading', { name: 'Évaluation reliée au LMS', exact: true })).toBeVisible();
    await expect(page.locator('dd').filter({ hasText: fixture.evaluationTitle })).toBeVisible();

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
    } else {
      expect(Number.isInteger(fixture.bulletinId)).toBe(true);
      dialog = await openSearch(page, 'Bulletins', `BUL-${fixture.bulletinId}`);
      const bulletinLink = dialog.getByRole('link').filter({ hasText: `BUL-${fixture.bulletinId}` });
      await expect(bulletinLink).toHaveAttribute('href', `/${variant}/bulletins/${fixture.bulletinId}`);
      await bulletinLink.click();
      await expect(page.getByRole('heading', { name: 'Bulletin', exact: true })).toBeVisible();
      await expect(page.locator('dd').filter({ hasText: fixture.learnerMatricule })).toBeVisible();
      await expect(page.getByText(/La validation administrative n’est pas une signature numérique vérifiable/)).toBeVisible();
    }
  });

  test(`${variant}: learner search excludes administrative types and other learners' invoices`, async ({ page }) => {
    const { fixture, credentials, apiOrigin } = loadGradeFixture(variant);
    expect(typeof fixture.learnerUsername).toBe('string');
    expect(Number.isInteger(fixture.peerInvoiceId)).toBe(true);
    expect(typeof fixture.peerInvoiceNumber).toBe('string');
    // The disposable learner fixture uses the same synthetic password as the staff fixture.
    await respectApiRateLimit(page);
    await page.goto(`/${variant}`);
    await page.getByRole('textbox', { name: 'Identifiant', exact: true }).fill(fixture.learnerUsername);
    await page.getByLabel(/^Mot de passe/).fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.locator('.sis-layout')).toBeVisible();
    let dialog = await openSearch(page, 'Factures', fixture.invoiceNumber);
    const invoiceLink = dialog.getByRole('link').filter({ hasText: fixture.invoiceNumber });
    await expect(invoiceLink).toHaveAttribute('href', `/${variant}/factures/${fixture.invoiceId}`);
    await invoiceLink.click();
    await expect(page.locator('dd').filter({ hasText: fixture.invoiceNumber })).toBeVisible();

    await page.getByRole('button', { name: 'Ouvrir la palette de navigation' }).click();
    await page.getByRole('tab', { name: 'Dossiers', exact: true }).click();
    dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox', { name: 'Type de dossier' }).click();
    await expect(page.getByRole('option', { name: 'Cours LMS', exact: true })).toHaveCount(0);
    await expect(page.getByRole('option', { name: 'Évaluations reliées au LMS', exact: true })).toHaveCount(0);
    await page.getByRole('option', { name: 'Factures', exact: true }).click();
    await dialog.getByRole('textbox', { name: 'Rechercher un dossier' }).fill(fixture.peerInvoiceNumber);
    await dialog.getByRole('button', { name: 'Rechercher les dossiers', exact: true }).click();
    await expect(dialog.getByText('Aucun dossier autorisé ne correspond.', { exact: true })).toBeVisible();

    const rejected = await page.evaluate(async (url) => {
      const response = await fetch(url, { credentials: 'include' });
      return { status: response.status, text: await response.text() };
    }, `${apiOrigin}/api/v1/paiements/factures/${fixture.peerInvoiceId}/`);
    expect(rejected.status, rejected.text).toBe(404);
    expect(rejected.text).not.toContain(fixture.peerInvoiceNumber);
    await dialog.getByRole('button', { name: 'Fermer la palette' }).click();
    await page.goto(`/${variant}/evaluations_lms/${fixture.evaluationId}`);
    await expect(page.getByText('Vous n’avez pas accès à ce type de dossier dans ce contexte.')).toBeVisible();
    await expect(page.locator('dd')).toHaveCount(0);
  });
}
