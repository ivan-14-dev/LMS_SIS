const { test, expect } = require('@playwright/test');
const { authenticatedApi, respectApiRateLimit } = require('./api');
const {
  loadGradeFixture, gradeEvent, deliverGrade, waitForProposal,
} = require('./lms-grade-review-fixture');

const mode = process.env.SIS_E2E_MODE || 'dual';
if (!['dual', 'secondaire', 'superieur'].includes(mode)) { throw new Error('Invalid SIS_E2E_MODE.'); }
const variants = mode === 'dual' ? ['secondaire', 'superieur'] : [mode];

async function evaluationRow(page, variant, fixture) {
  await page.goto(`/${variant}/${variant === 'secondaire' ? 'evaluations' : 'notes'}`);
  await page.getByRole('textbox', { name: 'Rechercher', exact: true }).fill(fixture.evaluationTitle);
  const row = page.getByRole('row').filter({
    has: page.getByRole('cell', { name: fixture.evaluationTitle, exact: true }),
  });
  await expect(row).toHaveCount(1);
  return row;
}

async function openProposals(page, variant, fixture) {
  const row = await evaluationRow(page, variant, fixture);
  await row.getByRole('button', { name: 'Propositions LMS', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: `Propositions LMS — ${fixture.evaluationTitle}` })).toBeVisible();
  return dialog;
}

async function decide(page, dialog, evaluationId, label, expectedStatus) {
  const response = page.waitForResponse(item => (
    item.url().endsWith(`/notes/evaluations/${evaluationId}/examiner_proposition_lms/`)
    && item.request().method() === 'POST'
  ));
  await dialog.getByRole('button', { name: label, exact: true }).click();
  const result = await response;
  expect(result.status(), await result.text()).toBe(expectedStatus);
  return result.json();
}

for (const variant of variants) {
  test(`${variant}: real LMS receipt requires human review and never overwrites an official grade`, async ({ page, request }) => {
    const environment = loadGradeFixture(variant);
    const { fixture, credentials } = environment;
    await respectApiRateLimit(page);
    await page.goto(`/${variant}`);
    await page.getByRole('textbox', { name: 'Identifiant', exact: true }).fill(credentials.username);
    await page.getByLabel(/^Mot de passe/).fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.locator('.sis-layout')).toBeVisible();
    const api = authenticatedApi(page, variant);
    const evaluationUrl = `notes/evaluations/${fixture.evaluationId}/`;
    const evaluation = await api(evaluationUrl);
    expect(evaluation.titre, 'Fixture must identify the disposable evaluation exactly.').toBe(fixture.evaluationTitle);
    expect(Number(evaluation.bareme)).toBe(20);
    expect(evaluation.offre_configuration?.assessment?.mode || 'numeric').toBe('numeric');
    expect(variant === 'secondaire'
      ? ['interrogation', 'ds', 'dm', 'tp', 'oral', 'projet'].includes(evaluation.type)
      : ['cc', 'tp', 'projet'].includes(evaluation.modalite) && !evaluation.anonyme).toBe(true);
    expect(await api(`${evaluationUrl}notes/`), 'Use a fresh evaluation, never a shared official grade.').toEqual([]);
    expect((await api(`${evaluationUrl}propositions_lms/`)).count, 'Recreate the disposable fixture before rerunning.').toBe(0);

    const row = await evaluationRow(page, variant, fixture);
    await row.getByRole('button', { name: 'Saisir les notes', exact: true }).click();
    await expect(page.getByLabel(`Note ${fixture.learnerMatricule}`, { exact: true })).toHaveValue('');
    await page.getByRole('button', { name: 'Annuler', exact: true }).click();

    const rejectedEvent = gradeEvent(fixture, '8');
    await deliverGrade(request, environment, rejectedEvent);
    const rejectedProposal = await waitForProposal(api, fixture.evaluationId, rejectedEvent);
    expect(rejectedProposal.learner_id).toBe(fixture.learnerId);
    expect(rejectedProposal.note_id).toBeNull();
    await deliverGrade(request, environment, rejectedEvent);
    expect(await api(`${evaluationUrl}notes/`)).toEqual([]);
    let dialog = await openProposals(page, variant, fixture);
    await expect(dialog.getByText('En attente de validation', { exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: `Examiner la proposition ${rejectedProposal.id}`, exact: true }).click();
    const reject = dialog.getByRole('button', { name: 'Rejeter la proposition', exact: true });
    await expect(reject).toBeDisabled();
    await dialog.getByLabel('Motif de la décision', { exact: true }).fill('   ');
    await expect(reject).toBeDisabled();
    await dialog.getByLabel('Motif de la décision', { exact: true }).fill('Mauvais essai LMS — recette isolée.');
    const rejection = await decide(page, dialog, fixture.evaluationId, 'Rejeter la proposition', 200);
    expect(rejection).toMatchObject({ id: rejectedProposal.id, review_status: 'rejected', note_id: null });
    await expect(dialog.getByText('Proposition rejetée. Aucune note officielle créée.', { exact: true })).toBeVisible();
    expect(await api(`${evaluationUrl}notes/`)).toEqual([]);
    await dialog.getByRole('button', { name: 'Fermer', exact: true }).click();

    const approvedEvent = gradeEvent(fixture, '14');
    await deliverGrade(request, environment, approvedEvent);
    const approvedProposal = await waitForProposal(api, fixture.evaluationId, approvedEvent);
    expect(await api(`${evaluationUrl}notes/`)).toEqual([]);
    dialog = await openProposals(page, variant, fixture);
    await dialog.getByRole('button', { name: `Examiner la proposition ${approvedProposal.id}`, exact: true }).click();
    const stalePage = await page.context().newPage();
    try {
      await respectApiRateLimit(stalePage);
      const staleDialog = await openProposals(stalePage, variant, fixture);
      await staleDialog.getByRole('button', { name: `Examiner la proposition ${approvedProposal.id}`, exact: true }).click();
      const approved = await decide(page, dialog, fixture.evaluationId, 'Approuver et créer la note', 200);
      expect(approved).toMatchObject({ id: approvedProposal.id, review_status: 'approved' });
      expect(approved.note_id).toBeGreaterThan(0);
      await expect(dialog.getByText(`Proposition approuvée : note officielle n° ${approved.note_id} créée.`)).toBeVisible();
      const official = await api(`${evaluationUrl}notes/`);
      expect(official).toHaveLength(1);
      expect(official[0]).toMatchObject({
        id: approved.note_id, valeur: '14.00', [variant === 'secondaire' ? 'eleve' : 'etudiant']: fixture.learnerId,
      });

      await decide(stalePage, staleDialog, fixture.evaluationId, 'Approuver et créer la note', 409);
      await expect(staleDialog.getByRole('alert').filter({ hasText: 'Conflit :' })).toBeVisible();
      await expect(staleDialog.getByText(/Proposition approuvée :/)).toHaveCount(0);
      await expect(staleDialog.getByRole('button', { name: 'Approuver et créer la note', exact: true })).toBeDisabled();
      expect(await api(`${evaluationUrl}notes/`)).toEqual(official);
      await dialog.getByRole('button', { name: 'Fermer', exact: true }).click();

      if (variant === 'superieur') {
        await page.getByRole('tab', { name: 'Notes enregistrées', exact: true }).click();
        const officialRow = page.getByRole('row').filter({
          has: page.getByRole('cell', { name: fixture.evaluationTitle, exact: true }),
        });
        await expect(officialRow.getByRole('cell', { name: '14.00', exact: true })).toBeVisible();
      } else {
        const officialRow = page.getByRole('row').filter({
          has: page.getByRole('cell', { name: fixture.evaluationTitle, exact: true }),
        });
        await officialRow.getByRole('button', { name: 'Saisir les notes', exact: true }).click();
        await expect(page.getByLabel(`Note ${fixture.learnerMatricule}`, { exact: true })).toHaveValue('14.00');
        await page.getByRole('button', { name: 'Annuler', exact: true }).click();
      }

      const overwriteEvent = gradeEvent(fixture, '19');
      await deliverGrade(request, environment, overwriteEvent);
      const overwriteProposal = await waitForProposal(api, fixture.evaluationId, overwriteEvent);
      expect(await api(`${evaluationUrl}notes/`)).toEqual(official);
      dialog = await openProposals(page, variant, fixture);
      await dialog.getByRole('button', { name: `Examiner la proposition ${overwriteProposal.id}`, exact: true }).click();
      await decide(page, dialog, fixture.evaluationId, 'Approuver et créer la note', 409);
      await expect(dialog.getByRole('alert').filter({ hasText: 'Conflit :' })).toBeVisible();
      await expect(dialog.getByText(/Proposition approuvée :/)).toHaveCount(0);
      expect(await api(`${evaluationUrl}notes/`)).toEqual(official);
      const proposals = await api(`${evaluationUrl}propositions_lms/`);
      expect(proposals.count, 'Replayed webhook must not duplicate the original proposal.').toBe(3);
      expect(proposals.results.filter(item => item.review_status === 'approved')).toHaveLength(1);
      expect(proposals.results.find(item => item.id === rejectedProposal.id)).toMatchObject({
        review_status: 'rejected', review_reason: 'Mauvais essai LMS — recette isolée.',
      });
    } finally {
      await stalePage.close();
    }
  });
}
