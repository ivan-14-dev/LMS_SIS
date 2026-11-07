const fs = require('fs');
const { createHash } = require('crypto');
const { test, expect } = require('@playwright/test');
const { authenticatedApi } = require('./api');
const {
  variants, loadFixture, login, choose, submit, command, samplePdf,
} = require('./project-helpers');

async function downloadedBytes(download) {
  const stream = await download.createReadStream();
  const chunks = [];
  return new Promise((resolve, reject) => {
    stream.on('data', chunk => chunks.push(chunk));
    stream.on('end', () => resolve(Buffer.concat(chunks)));
    stream.on('error', reject);
  });
}

for (const variant of variants) {
  test(`${variant}: individual revisions and human publication by a distinct evaluator`, async ({
    page, browser,
  }, testInfo) => {
    const { fixture, credentials, apiOrigin } = loadFixture(variant);
    const { competencyTeacher: manager, individualEvaluator: evaluator } = fixture;
    const [course] = fixture.competencyCourses;
    expect(manager.username).toBe('wave28-teacher');
    expect(manager.is_staff).toBe(false);
    expect(manager.is_superuser).toBe(false);
    expect(manager.permissions).toEqual(expect.arrayContaining([
      'core.gerer_projet_pedagogique', 'integration.view_edxcoursemapping',
    ]));
    expect(manager.permissions).not.toContain('core.evaluer_projet_pedagogique');
    expect(evaluator.username).toBe('wave29-evaluator');
    expect(evaluator.id).not.toBe(manager.id);
    expect(evaluator.is_staff).toBe(false);
    expect(evaluator.is_superuser).toBe(false);
    expect(evaluator.permissions).toEqual(['core.evaluer_projet_pedagogique']);
    expect(fixture.learnerUserIds).toEqual([4, 5]);
    expect(course.id).toBe(4);
    expect(manager.course_id).toBe(course.id);
    const criterion = course.offering.assessment.criteria.find(item => item.code === 'analyse');
    expect(criterion.label).toBe('Wave28 analyse A');

    await login(page, variant, manager.username, credentials.password);
    const api = authenticatedApi(page, variant);
    const contexts = [];
    try {
      const ownerCandidates = await api(`core/projets/candidats/?type=responsable&q=${manager.username}`);
      expect(ownerCandidates.results.map(owner => owner.id)).toEqual([manager.id]);
      const evaluatorCandidates = await api(
        `core/projets/candidats/?type=evaluateur&responsable=${manager.id}&q=${evaluator.username}`,
      );
      expect(evaluatorCandidates.results.map(user => user.id)).toEqual([evaluator.id]);
      await page.goto(`/${variant}/projets`);
      await page.getByRole('button', { name: 'Nouveau projet', exact: true }).click();
      const title = `Projet individuel ${variant} ${Date.now()}`;
      await page.getByLabel('Titre du projet').fill(title);
      await page.getByLabel('Mode du projet', { exact: true }).selectOption('individuel');
      await choose(page, 'Responsable', manager.username, ownerCandidates.results[0].nom);
      await choose(page, 'Évaluateurs', evaluator.username, evaluatorCandidates.results[0].nom);
      await page.getByRole('combobox', { name: 'Cours existant (facultatif)' }).fill(course.name);
      await page.getByRole('listbox').getByRole('option').filter({ hasText: course.name }).click();
      await page.getByRole('button', { name: 'Nouvelle sélection des compétences visées', exact: true }).click();
      await page.getByRole('checkbox', { name: `${criterion.label} (${criterion.code})`, exact: true }).check();
      const project = await submit(page, 'core/projets/');
      expect(project.mode).toBe('individuel');
      expect(project.responsable).toBe(manager.id);
      expect(project.evaluateurs).toEqual([evaluator.id]);
      expect(project.actions).toMatchObject({ can_manage: true, can_evaluate: false });
      expect(project.cours.id).toBe(course.id);
      expect(project.competences).toEqual(course.expected_public_snapshot);
      const projectPath = `core/projets/${project.id}/`;
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible({ timeout: 20000 });
      await page.getByRole('button', { name: 'Nouveau jalon', exact: true }).click();
      await page.getByLabel('Titre du jalon').fill('Analyse individuelle');
      await page.getByLabel(/^Ordre/).fill('1');
      await page.getByLabel('Échéance (heure locale)').fill('2030-01-01T12:00');
      await page.getByLabel(/^Barème/).fill('20');
      const { jalon } = await submit(page, `${projectPath}jalons/`);
      const members = await Promise.all(fixture.learnerUsernames.map(async (username, index) => {
        const candidates = await api(`core/projets/candidats/?type=membre&projet=${project.id}&q=${username}`);
        const member = candidates.results.find(user => user.id === fixture.learnerUserIds[index]);
        expect(member).toBeDefined();
        return { ...member, username };
      }));
      await page.getByRole('button', { name: 'Nouvelle équipe', exact: true }).click();
      await page.getByLabel('Nom de l’équipe').fill('Individuel Alice');
      await choose(page, 'Membres actifs', members[0].username, members[0].nom);
      const { equipe } = await submit(page, `${projectPath}equipes/`);
      expect(equipe.membres.map(member => member.membre)).toEqual([4]);
      const teamPath = `${projectPath}equipes/${equipe.id}/`;
      await page.getByLabel('Équipe', { exact: true }).selectOption(equipe.id);
      const before = await api(projectPath);
      const historyBefore = await api(`${projectPath}historique/`);
      const teamsBefore = await api(`${projectPath}equipes/`);
      await page.getByRole('button', { name: 'Remplacer les membres actifs', exact: true }).click();
      await choose(page, 'Membres actifs', members[1].username, members[1].nom);
      await expect(page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
      // The UI prevents sending two members; exercise the server refusal without bypassing that UI guard.
      const refused = await command(page, apiOrigin, `/api/v1/${teamPath}membres/`, 'POST', {
        version: before.version, membres: [4, 5],
      }, 400);
      expect(refused.membres).toBeTruthy();
      expect(await api(projectPath)).toEqual(before);
      expect(await api(`${projectPath}historique/`)).toEqual(historyBefore);
      expect(await api(`${projectPath}equipes/`)).toEqual(teamsBefore);
      await page.getByRole('dialog').getByRole('button', { name: 'Annuler', exact: true }).click();
      await page.getByRole('button', { name: 'Nouvelle équipe', exact: true }).click();
      await page.getByLabel('Nom de l’équipe').fill('Individuel Bob');
      await choose(page, 'Membres actifs', members[1].username, members[1].nom);
      const otherTeam = (await submit(page, `${projectPath}equipes/`)).equipe;
      expect(otherTeam.membres.map(member => member.membre)).toEqual([5]);

      const createRolePage = async username => {
        const context = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
        contexts.push(context);
        const rolePage = await context.newPage();
        await login(rolePage, variant, username, credentials.password);
        await rolePage.goto(`/${variant}/projets?projet=${project.id}`);
        await expect(rolePage.getByRole('heading', { name: title, exact: true })).toBeVisible({ timeout: 20000 });
        await expect(rolePage.getByRole('button', { name: 'Nouvelle équipe', exact: true })).toHaveCount(0);
        return rolePage;
      };
      const learnerPage = await createRolePage(members[0].username);
      const otherPage = await createRolePage(members[1].username);
      const evaluatorPage = await createRolePage(evaluator.username);
      const learnerApi = authenticatedApi(learnerPage, variant);
      const evaluatorApi = authenticatedApi(evaluatorPage, variant);
      expect((await evaluatorApi(projectPath)).actions).toMatchObject({ can_manage: false, can_evaluate: true });
      await expect(otherPage.getByLabel('Équipe', { exact: true }).locator('option')).toHaveText(['Individuel Bob']);
      const pdfs = [samplePdf('Individual analysis revision one'), samplePdf('Individual analysis revision two')];
      const filename = `analyse-individuelle-${variant}.pdf`;
      const uploadRevision = async index => {
        const pdf = pdfs[index];
        await learnerPage.getByRole('button', { name: 'Déposer un PDF', exact: true }).click();
        await learnerPage.getByLabel('Fichier PDF').setInputFiles({
          name: filename, mimeType: 'application/pdf', buffer: pdf,
        });
        await learnerPage.getByLabel('Commentaire du dépôt').fill(`Analyse personnelle, révision ${index + 1}.`);
        const { livrable } = await submit(learnerPage, `${teamPath}livrables/`);
        expect(livrable).toMatchObject({
          jalon: jalon.id,
          equipe: equipe.id,
          revision: index + 1,
          depose_par: 4,
          sha256: createHash('sha256').update(pdf).digest('hex'),
        });
        return livrable;
      };
      const deliveries = [await uploadRevision(0), await uploadRevision(1)];
      expect(deliveries[0].sha256).not.toBe(deliveries[1].sha256);
      const downloadRevision = async index => {
        const delivery = deliveries[index];
        const [download] = await Promise.all([
          learnerPage.waitForEvent('download'),
          learnerPage.getByRole('button', {
            name: `Télécharger ${filename} (révision ${delivery.revision})`, exact: true,
          }).click(),
        ]);
        expect(await downloadedBytes(download)).toEqual(pdfs[index]);
        const url = `${apiOrigin}/api/v1/${teamPath}livrables/${delivery.id}/telecharger/`;
        expect((await otherPage.request.get(url)).status()).toBe(404);
      };
      await downloadRevision(0);
      await downloadRevision(1);
      const privateVersion = (await api(projectPath)).version;
      const privateHistory = await api(`${projectPath}historique/`);
      await Promise.all(['livrables/', 'evaluations/'].map(async suffix => {
        expect((await otherPage.request.get(`${apiOrigin}/api/v1/${teamPath}${suffix}`)).status()).toBe(404);
      }));
      const csrf = await otherPage.request.get(`${apiOrigin}/csrf/api/v1/token`);
      expect(csrf.status()).toBe(200);
      const deniedUpload = await otherPage.request.post(`${apiOrigin}/api/v1/${teamPath}livrables/`, {
        headers: { 'X-CSRFToken': (await csrf.json()).csrfToken },
        multipart: {
          version: String(privateVersion),
          jalon: jalon.id,
          fichier: { name: 'intrusion.pdf', mimeType: 'application/pdf', buffer: pdfs[0] },
          commentaire: 'Refus hors équipe attendu',
        },
      });
      expect(deniedUpload.status()).toBe(404);
      await command(otherPage, apiOrigin, `/api/v1/${teamPath}evaluations/`, 'POST', {
        version: privateVersion, jalon: jalon.id, note_groupe: '20', commentaire: 'Intrusion', contributions: [],
      }, 404);
      expect((await api(projectPath)).version).toBe(privateVersion);
      expect(await api(`${projectPath}historique/`)).toEqual(privateHistory);
      expect((await learnerApi(`${teamPath}livrables/`)).results).toHaveLength(2);
      await otherPage.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      await expect(otherPage.getByText(filename, { exact: false })).toHaveCount(0);

      await evaluatorPage.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      await evaluatorPage.getByLabel('Équipe', { exact: true }).selectOption(equipe.id);
      await Promise.all(deliveries.map(async delivery => {
        await expect(evaluatorPage.getByRole('button', {
          name: `Télécharger ${filename} (révision ${delivery.revision})`, exact: true,
        })).toBeVisible();
      }));
      expect((await evaluatorApi(`${teamPath}livrables/`)).results.map(item => item.id).sort())
        .toEqual(deliveries.map(item => item.id).sort());
      await evaluatorPage.getByRole('button', { name: 'Nouveau brouillon d’évaluation', exact: true }).click();
      await expect(evaluatorPage.getByRole('dialog').getByRole('group')).toHaveCount(1);
      await expect(evaluatorPage.getByRole('group', { name: members[0].nom, exact: true })).toBeVisible();
      await evaluatorPage.getByLabel(/^Note du groupe/).fill('17');
      await evaluatorPage.getByLabel('Commentaire du groupe').fill('Évaluation humaine individuelle.');
      await evaluatorPage.getByLabel(`Note de ${members[0].nom}`).fill('17');
      const contributionText = 'Analyse personnelle publiée par un évaluateur distinct.';
      await evaluatorPage.getByLabel(`Contribution de ${members[0].nom}`).fill(contributionText);
      const { evaluation } = await submit(evaluatorPage, `${teamPath}evaluations/`);
      const contribution = { membre: 4, note: '17.00', commentaire: contributionText };
      expect(evaluation).toMatchObject({
        statut: 'brouillon', evalue_par: evaluator.id, published_at: null, contributions: [contribution],
      });
      await learnerPage.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      await expect(learnerPage.getByText('Aucune évaluation accessible pour ce jalon.', { exact: true })).toBeVisible();
      expect((await learnerApi(`${teamPath}evaluations/`)).results).toEqual([]);
      await expect(learnerPage.getByText(contributionText, { exact: true })).toHaveCount(0);
      await expect(learnerPage.getByRole('button', { name: 'Nouveau brouillon d’évaluation', exact: true })).toHaveCount(0);
      await page.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      await page.getByLabel('Équipe', { exact: true }).selectOption(equipe.id);
      await expect(page.getByText('Brouillon non publié', { exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Nouveau brouillon d’évaluation', exact: true })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Publier cette évaluation', exact: true })).toHaveCount(0);
      const draftVersion = (await api(projectPath)).version;
      const draftHistory = await api(`${projectPath}historique/`);
      await command(page, apiOrigin, `/api/v1/${teamPath}evaluations/`, 'POST', {
        version: draftVersion,
        jalon: jalon.id,
        note_groupe: '17',
        commentaire: 'Gestionnaire non habilité',
        contributions: [contribution],
      }, 403);
      const publicationPath = `${teamPath}evaluations/${evaluation.id}/publier/`;
      await command(page, apiOrigin, `/api/v1/${publicationPath}`, 'POST', { version: draftVersion }, 403);
      await command(otherPage, apiOrigin, `/api/v1/${publicationPath}`, 'POST', { version: draftVersion }, 404);
      expect((await api(projectPath)).version).toBe(draftVersion);
      expect(await api(`${projectPath}historique/`)).toEqual(draftHistory);
      expect((await evaluatorApi(`${teamPath}evaluations/`)).results).toEqual([evaluation]);
      await evaluatorPage.getByRole('button', { name: 'Publier cette évaluation', exact: true }).click();
      await expect(evaluatorPage.getByRole('dialog').getByText(/Aucune note officielle ne sera créée/)).toBeVisible();
      const published = await submit(evaluatorPage, publicationPath, 200, 'Confirmer la publication');
      expect(published.version).toBe(draftVersion + 1);
      expect(published.evaluation).toMatchObject({
        statut: 'publiee', publie_par: evaluator.id, contributions: [contribution],
      });
      expect(published.evaluation.published_at).toBeTruthy();
      await learnerPage.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      await expect(learnerPage.getByText(contributionText, { exact: true })).toBeVisible();
      await expect(learnerPage.getByText('Publiée', { exact: true })).toBeVisible();
      const visible = (await learnerApi(`${teamPath}evaluations/`)).results;
      expect(visible).toHaveLength(1);
      expect(visible[0]).toMatchObject({ id: evaluation.id, statut: 'publiee', contributions: [contribution] });
      expect((await otherPage.request.get(`${apiOrigin}/api/v1/${teamPath}evaluations/`)).status()).toBe(404);
      const restored = await api(projectPath);
      expect(restored).toMatchObject({
        mode: 'individuel',
        version: published.version,
        cours: project.cours,
        competences: project.competences,
        responsable: manager.id,
        evaluateurs: [evaluator.id],
      });
      await Promise.all([learnerApi, evaluatorApi].map(async roleApi => {
        const privateProject = await roleApi(projectPath);
        expect(privateProject.cours).toEqual({ disponible: false });
        expect(privateProject.competences).toEqual({ disponible: false });
      }));
      const history = await api(`${projectPath}historique/`);
      const publications = history.results.filter(item => item.action === 'projet_publication');
      expect(publications).toHaveLength(1);
      expect(publications[0].acteur).toBe(evaluator.id);
      fs.writeFileSync(testInfo.outputPath('individual-project-receipt.json'), JSON.stringify({
        isolated: true,
        variant,
        mode: restored.mode,
        projectId: restored.id,
        teamId: equipe.id,
        otherTeamId: otherTeam.id,
        milestoneId: jalon.id,
        deliveryIds: deliveries.map(item => item.id),
        sha256s: deliveries.map(item => item.sha256),
        evaluationId: evaluation.id,
        version: restored.version,
        managerUsername: manager.username,
        evaluatorUsername: evaluator.username,
        managerUserId: manager.id,
        evaluatorUserId: evaluator.id,
        learnerUserId: 4,
        course: restored.cours,
        competencies: restored.competences,
      }, null, 2));
    } finally {
      await Promise.all(contexts.map(context => context.close()));
    }
  });
}
