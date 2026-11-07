const fs = require('fs');
const { createHash } = require('crypto');
const { test, expect } = require('@playwright/test');
const { authenticatedApi } = require('./api');
const {
  variants, loadFixture, login, choose, submit, samplePdf,
} = require('./project-helpers');

for (const variant of variants) {
  test(`${variant}: private collective project, contributions, revocation and module restoration`, async ({
    page, browser,
  }, testInfo) => {
    const { fixture, credentials, apiOrigin } = loadFixture(variant);
    await login(page, variant, credentials.username, credentials.password);
    const api = authenticatedApi(page, variant);
    const modulesPath = 'etablissement/current/modules/';
    const originalModules = await api(modulesPath);
    const setEnabled = async enabled => {
      const current = await api(modulesPath);
      if (current.enabled['sis.projects'] !== enabled) {
        await api(modulesPath, 'PATCH', {
          revision: current.revision, enabled: { 'sis.projects': enabled }, reason: 'Isolated project acceptance',
        });
      }
    };
    const context = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    const otherContext = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    try {
      await setEnabled(true);
      const nonce = Date.now();
      const extraUsername = `project-extra-${nonce}`;
      await api('utilisateurs/comptes/', 'POST', {
        username: extraUsername,
        first_name: 'Projet',
        last_name: `Partenaire ${nonce}`,
        role: variant === 'secondaire' ? 'eleve' : 'etudiant',
        password: credentials.password,
        password_confirm: credentials.password,
      });
      const extraAccounts = await api(`utilisateurs/comptes/?search=${extraUsername}`);
      const extra = extraAccounts.results.find(user => user.username === extraUsername);
      expect(extra).toBeDefined();
      const ownerCandidates = await api(`core/projets/candidats/?type=responsable&q=${encodeURIComponent(credentials.username)}`);
      expect(ownerCandidates.results).toHaveLength(1);
      const owner = ownerCandidates.results[0];
      await page.goto(`/${variant}/projets`);
      await page.getByRole('button', { name: 'Nouveau projet', exact: true }).click();
      const title = `Projet collectif ${variant} ${nonce}`;
      await page.getByLabel('Titre du projet').fill(title);
      await page.getByLabel('Description', { exact: true }).fill('Dossier pédagogique privé de qualification.');
      await choose(page, 'Responsable', credentials.username, owner.nom);
      const project = await submit(page, 'core/projets/');
      const projectPath = `core/projets/${project.id}/`;
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();

      await page.getByRole('button', { name: 'Nouveau jalon', exact: true }).click();
      await page.getByLabel('Titre du jalon').fill('Rapport collectif');
      await page.getByLabel(/^Ordre/).fill('1');
      await page.getByLabel('Échéance (heure locale)').fill('2020-01-01T12:00');
      await page.getByLabel(/^Barème/).fill('20');
      const { jalon } = await submit(page, `${projectPath}jalons/`);
      const members = await Promise.all(fixture.learnerUsernames.map(async (username, index) => {
        const result = await api(`core/projets/candidats/?type=membre&projet=${project.id}&q=${encodeURIComponent(username)}`);
        const member = result.results.find(user => user.id === fixture.learnerUserIds[index]);
        expect(member).toBeDefined();
        return { ...member, username };
      }));
      await page.getByRole('button', { name: 'Nouvelle équipe', exact: true }).click();
      await page.getByLabel('Nom de l’équipe').fill('Équipe A');
      await choose(page, 'Membres actifs', members[0].username, members[0].nom);
      await choose(page, 'Membres actifs', extraUsername, extra.full_name);
      const { equipe } = await submit(page, `${projectPath}equipes/`);
      await page.getByRole('button', { name: 'Nouvelle équipe', exact: true }).click();
      await page.getByLabel('Nom de l’équipe').fill('Équipe B');
      await choose(page, 'Membres actifs', members[1].username, members[1].nom);
      await submit(page, `${projectPath}equipes/`);
      const teamPath = `${projectPath}equipes/${equipe.id}/`;
      const learnerPage = await context.newPage();
      const otherPage = await otherContext.newPage();
      await login(learnerPage, variant, members[0].username, credentials.password);
      await login(otherPage, variant, members[1].username, credentials.password);
      await learnerPage.goto(`/${variant}/projets?projet=${project.id}`);
      await expect(learnerPage.getByRole('heading', { name: title, exact: true })).toBeVisible();
      await expect(learnerPage.getByRole('button', { name: 'Nouvelle équipe', exact: true })).toHaveCount(0);
      await expect(learnerPage.getByRole('button', { name: 'Nouveau brouillon d’évaluation', exact: true })).toHaveCount(0);
      const pdf = samplePdf();
      const filename = `rapport-${variant}.pdf`;
      await learnerPage.getByRole('button', { name: 'Déposer un PDF', exact: true }).click();
      await learnerPage.getByLabel('Fichier PDF').setInputFiles({ name: filename, mimeType: 'application/pdf', buffer: pdf });
      await learnerPage.getByLabel('Commentaire du dépôt').fill('Remise réelle du groupe.');
      const { livrable } = await submit(learnerPage, `${teamPath}livrables/`);
      expect(livrable.jalon).toBe(jalon.id);
      expect(livrable.sha256).toBe(createHash('sha256').update(pdf).digest('hex'));
      await expect(learnerPage.getByText('En retard', { exact: true })).toBeVisible();
      const downloadEvent = learnerPage.waitForEvent('download');
      await learnerPage.getByRole('button', { name: `Télécharger ${filename} (révision 1)`, exact: true }).click();
      const downloaded = await downloadEvent;
      expect(fs.readFileSync(await downloaded.path())).toEqual(pdf);
      const fileUrl = `${apiOrigin}/api/v1/${teamPath}livrables/${livrable.id}/telecharger/`;
      expect((await otherPage.request.get(fileUrl)).status()).toBe(404);
      await otherPage.goto(`/${variant}/projets?projet=${project.id}`);
      await expect(otherPage.getByRole('heading', { name: title, exact: true })).toBeVisible();
      await expect(otherPage.getByText(filename, { exact: false })).toHaveCount(0);
      await expect(otherPage.getByLabel('Équipe').locator('option')).toHaveText(['Équipe B']);

      await page.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      await page.getByLabel('Équipe', { exact: true }).selectOption(equipe.id);
      await page.getByRole('button', { name: 'Nouveau brouillon d’évaluation', exact: true }).click();
      await page.getByLabel(/^Note du groupe/).fill('16');
      await page.getByLabel('Commentaire du groupe').fill('Évaluation collective explicite.');
      await page.getByLabel(`Note de ${members[0].nom}`).fill('17');
      await page.getByLabel(`Contribution de ${members[0].nom}`).fill('Analyse personnelle publiée.');
      await page.getByLabel(`Note de ${extra.full_name}`).fill('15');
      await page.getByLabel(`Contribution de ${extra.full_name}`).fill('Commentaire confidentiel du partenaire.');
      const { evaluation } = await submit(page, `${teamPath}evaluations/`);
      expect(evaluation.statut).toBe('brouillon');
      await learnerPage.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      await expect(learnerPage.getByText('Aucune évaluation accessible pour ce jalon.', { exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Publier cette évaluation', exact: true }).click();
      const published = await submit(page, `${teamPath}evaluations/${evaluation.id}/publier/`, 200, 'Confirmer la publication');
      expect(published.evaluation.statut).toBe('publiee');
      await learnerPage.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      await expect(learnerPage.getByText('Note du groupe : 16.00 / 20.00', { exact: true })).toBeVisible();
      await expect(learnerPage.getByText('Analyse personnelle publiée.', { exact: true })).toBeVisible();
      await expect(learnerPage.getByText('Commentaire confidentiel du partenaire.', { exact: true })).toHaveCount(0);
      expect((await otherPage.request.get(`${apiOrigin}/api/v1/${teamPath}evaluations/`)).status()).toBe(404);

      await page.getByRole('button', { name: 'Remplacer les membres actifs', exact: true }).click();
      await page.getByRole('dialog').getByRole('button', { name: members[0].nom, exact: true }).press('Delete');
      await submit(page, `${teamPath}membres/`, 200);
      expect((await learnerPage.request.get(fileUrl)).status()).toBe(404);
      await learnerPage.reload();
      await expect(learnerPage.getByText(/Accès aux projets refusé/)).toBeVisible();
      await expect(learnerPage.getByText('Dossier pédagogique privé de qualification.', { exact: true })).toHaveCount(0);
      await page.getByRole('button', { name: 'Remplacer les membres actifs', exact: true }).click();
      await choose(page, 'Membres actifs', members[0].username, members[0].nom);
      await submit(page, `${teamPath}membres/`, 200);
      await learnerPage.goto(`/${variant}/projets?projet=${project.id}`);
      await expect(learnerPage.getByRole('heading', { name: title, exact: true })).toBeVisible();

      await setEnabled(false);
      expect((await learnerPage.request.get(fileUrl)).status()).toBe(403);
      expect((await page.request.get(`${apiOrigin}/api/v1/core/projets/capacites/`)).status()).toBe(403);
      await learnerPage.reload();
      await expect(learnerPage.getByText(/module Projets pédagogiques est désactivé/)).toBeVisible();
      await expect(learnerPage.getByText('Dossier pédagogique privé de qualification.', { exact: true })).toHaveCount(0);
      await setEnabled(true);
      await learnerPage.reload();
      await expect(learnerPage.getByRole('heading', { name: title, exact: true })).toBeVisible();
      const restored = await learnerPage.request.get(fileUrl);
      expect(restored.status()).toBe(200);
      expect(await restored.body()).toEqual(pdf);
      await expect(learnerPage.getByText('Analyse personnelle publiée.', { exact: true })).toBeVisible();
      fs.writeFileSync(testInfo.outputPath('project-receipt.json'), JSON.stringify({
        isolated: true,
        variant,
        projectId: project.id,
        teamId: equipe.id,
        milestoneId: jalon.id,
        deliveryId: livrable.id,
        evaluationId: evaluation.id,
        sha256: livrable.sha256,
        learnerUserId: members[0].id,
        extraUserId: extra.id,
      }, null, 2));
    } finally {
      try {
        await setEnabled(originalModules.enabled['sis.projects'] === true);
      } finally {
        await Promise.all([context.close(), otherContext.close()]);
      }
    }
  });
}
