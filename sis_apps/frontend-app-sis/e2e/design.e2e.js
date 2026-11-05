const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { authenticatedApi, respectApiRateLimit } = require('./api');
const { capturePresentation } = require('./presentation');

const variants = process.env.SIS_E2E_MODE === 'dual'
  ? ['secondaire', 'superieur'] : [process.env.SIS_E2E_MODE || 'secondaire'];
const shared = ['compte', 'missions', 'reclamations', 'signatures', 'archives', 'workflows', 'examens', 'emploi-du-temps', 'portail-staff'];
const routes = {
  secondaire: ['eleves', 'classes', 'evaluations', 'bulletins', 'conseil-classe', 'presences', 'discipline', 'cantine', 'transport', 'infirmerie', 'internat', 'clubs'],
  superieur: ['etudiants', 'formations', 'inscriptions', 'notes', 'jurys', 'releves', 'diplomes', 'bourses', 'stages', 'memoires', 'mobilite', 'bibliotheque', 'enseignants', 'recherche', 'paiements'],
};

async function assertControls(page) {
  const mismatches = await page.locator('.MuiButton-root, .btn, .MuiOutlinedInput-root, .form-control, .form-select')
    .evaluateAll(elements => elements.filter(element => element.getBoundingClientRect().width > 0)
      .map(element => ({
        tag: element.tagName,
        label: element.getAttribute('aria-label') || element.textContent.slice(0, 60),
        radius: getComputedStyle(element).borderTopLeftRadius,
        font: getComputedStyle(element).fontFamily,
      }))
      .filter(style => parseFloat(style.radius) < 12 || !style.font.includes('Inter')));
  expect(mismatches).toEqual([]);
}

for (const variant of variants) {
  test(`${variant}: ERP presentation across every management route`, async ({ page }, testInfo) => {
    test.setTimeout(600000);
    await respectApiRateLimit(page);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
    await page.goto(`/${variant}`);
    await expect(page.getByRole('heading', { name: 'Connexion SIS', exact: true })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await assertControls(page);
    await page.screenshot({ path: testInfo.outputPath(`${variant}-login-desktop.png`) });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`${variant}-login-mobile.png`) });
    await page.getByLabel('Identifiant').fill(credentials.username);
    await page.getByLabel('Mot de passe').fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Votre espace de travail', exact: true })).toBeVisible();
    const paths = [
      `/${variant}`,
      ...[...routes[variant], ...shared].map(route => `/${variant}/${route}`),
      ...['etablissement', 'utilisateurs', 'structure', 'annees-academiques', 'integration-lms']
        .map(route => `/admin/${route}?sis=${variant}`),
    ];
    for (const path of paths) {
      // eslint-disable-next-line no-await-in-loop -- All routes share this authenticated browser page.
      await test.step(path, async () => {
        await page.goto(path);
        await expect(page.locator('.sis-content h1').first()).toBeVisible({ timeout: 20000 });
        await expect(page.locator('.sis-content h1')).toHaveCount(1);
        await expect(page.locator('.sis-content [role="progressbar"]:not([aria-valuenow]), .sis-content .spinner-border')).toHaveCount(0, { timeout: 20000 });
        await page.evaluate(() => document.fonts.ready);
        await assertControls(page);
        if ([`/${variant}`, `/${variant}/portail-staff`].includes(path)) {
          await expect(page.locator('.sis-content .MuiCard-root').first()).toBeVisible();
          await expect(page.locator('.sis-content .pgn__card, .sis-content .btn, .sis-content .spinner-border')).toHaveCount(0);
        }
        // The timetable has no panels until an academic year is selected.
        await capturePresentation(page, path.replace(/[/?=]/g, '-'), testInfo, {
          allowEmptySurfaces: path === '/superieur/emploi-du-temps',
        });
        expect(await page.locator('.sis-content table:visible').count()).toBeLessThanOrEqual(1);
        const entries = await page.locator('.sis-section-entry').evaluateAll(links => links.map(link => link.href));
        if (entries.length) { await expect(page.locator('.sis-content table')).toHaveCount(0); }
        /* eslint-disable no-await-in-loop -- Each section uses the same authenticated browser. */
        for (const entry of entries) {
          await page.goto(entry);
          await expect(page.getByRole('link', { name: 'Toutes les rubriques', exact: true })).toBeVisible();
          await expect(page.locator('.sis-content [role="progressbar"]:not([aria-valuenow]), .sis-content .spinner-border')).toHaveCount(0, { timeout: 20000 });
          await expect(page.locator('.sis-content h1')).toHaveCount(1);
          expect(await page.locator('.sis-content table:visible').count()).toBeLessThanOrEqual(1);
          await capturePresentation(page, `${path.replace(/[/?=]/g, '-')}-${new URL(entry).searchParams.get('rubrique').replace(/\//g, '-')}`, testInfo);
        }
        /* eslint-enable no-await-in-loop */
      });
    }
    expect(errors).toEqual([]);
  });

  test(`${variant}: one table at a time through record details and section history`, async ({ page }, testInfo) => {
    test.setTimeout(240000);
    await respectApiRateLimit(page);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
    await page.goto(`/${variant}`);
    await page.getByLabel('Identifiant').fill(credentials.username);
    await page.getByLabel('Mot de passe').fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Votre espace de travail', exact: true })).toBeVisible();
    const api = authenticatedApi(page, variant);
    const key = Date.now().toString(36);
    const yearNumber = new Date().getUTCFullYear();
    const dates = { date_debut: `${yearNumber}-01-01`, date_fin: `${yearNumber}-12-31` };
    const year = await api('etablissement/annees/', 'POST', { libelle: `Vues ${key}`, ...dates });
    await page.goto(`/admin/annees-academiques?sis=${variant}`);
    await expect(page.locator('.sis-content table')).toHaveCount(0);
    const entry = page.locator('.sis-section-entry').first();
    const sectionUrl = await entry.getAttribute('href');
    await entry.click();
    await expect(page.getByRole('cell', { name: year.libelle, exact: true })).toBeVisible();
    await expect(page.locator('.sis-content table')).toHaveCount(1);
    expect(new URL(page.url()).searchParams.get('sis')).toBe(variant);
    await page.reload();
    await expect(page.getByRole('cell', { name: year.libelle, exact: true })).toBeVisible();
    await page.getByRole('link', { name: 'Toutes les rubriques', exact: true }).click();
    await expect(page.locator('.sis-content table')).toHaveCount(0);
    await page.goBack();
    await expect(page).toHaveURL(new URL(sectionUrl, process.env.SIS_E2E_URL).href);
    await expect(page.getByRole('cell', { name: year.libelle, exact: true })).toBeVisible();

    let delegatedRecord;
    if (variant === 'secondaire') {
      const level = await api('etablissement/niveaux/', 'POST', { code: `V${key.slice(-5)}`, libelle: `Niveau ${key}` });
      const group = await api('classes/classes/', 'POST', {
        nom: `Classe ${key}`, niveau: level.id, annee_scolaire: year.id,
      });
      delegatedRecord = group.id;
      await page.goto('/secondaire/classes');
      await page.getByRole('textbox', { name: 'Rechercher', exact: true }).fill(group.nom);
      await page.getByRole('cell', { name: group.nom, exact: true }).click();
      await expect(page.getByRole('heading', { name: `Classe : ${group.nom}`, exact: true })).toBeVisible();
      await expect(page.locator('.sis-content table')).toHaveCount(1);
      await expect(page.getByRole('region', { name: 'Classes', exact: true })).toHaveCount(0);
      await capturePresentation(page, 'secondaire-class-details', testInfo);
      await page.getByRole('tab', { name: 'Historique', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Historique de la classe', exact: true })).toBeVisible();
      await expect(page.locator('.sis-content table')).toHaveCount(0);
      await page.getByRole('button', { name: 'Retour aux classes', exact: true }).click();
      await expect(page.getByRole('region', { name: 'Classes', exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: `Classe : ${group.nom}`, exact: true })).toHaveCount(0);
    } else {
      const period = await api('etablissement/semestres/', 'POST', {
        annee_universitaire: year.id, type: 'impair', numero: 1, ...dates,
      });
      const formation = await api('formations/formations/', 'POST', { code: key, nom: `Formation ${key}`, type: 'licence' });
      delegatedRecord = formation.id;
      const curriculum = await api('formations/maquettes/', 'POST', {
        formation: formation.id, annee_universitaire: year.id,
      });
      const unit = await api('ue-ecue/ues/', 'POST', {
        maquette: curriculum.id, semestre: period.id, code: key, nom: `UE ${key}`, credits_ects: 6,
      });
      await page.goto(`/superieur/formations/${formation.id}`);
      await page.getByRole('cell', { name: year.libelle, exact: true }).click();
      await expect(page.getByRole('region', { name: `UE — ${year.libelle}`, exact: true })).toBeVisible();
      await expect(page.getByRole('region', { name: 'Maquettes annuelles', exact: true })).toHaveCount(0);
      await expect(page.locator('.sis-content table')).toHaveCount(1);
      await page.getByRole('cell', { name: unit.nom, exact: true }).click();
      const details = page.getByRole('region', { name: `ECUE — ${unit.nom}`, exact: true });
      await expect(details).toBeVisible();
      await expect(page.getByRole('region', { name: `UE — ${year.libelle}`, exact: true })).toHaveCount(0);
      await expect(page.locator('.sis-content table')).toHaveCount(1);
      await details.getByRole('button', { name: 'Ajouter', exact: true }).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByLabel(/^Code/).fill(key);
      await dialog.getByLabel(/^Nom/).fill(`ECUE ${key}`);
      const created = page.waitForResponse(response => response.url().endsWith('/api/v1/ue-ecue/ecues/')
        && response.request().method() === 'POST');
      await dialog.getByRole('button', { name: 'Enregistrer', exact: true }).click();
      const response = await created;
      expect(response.status(), await response.text()).toBe(201);
      expect((await response.json()).ue).toBe(unit.id);
      await expect(dialog).not.toBeVisible();
      await expect(page.getByRole('cell', { name: `ECUE ${key}`, exact: true })).toBeVisible();
      await capturePresentation(page, 'superieur-curriculum-details', testInfo);
      await page.getByRole('button', { name: `Retour aux UE — ${year.libelle}`, exact: true }).click();
      await expect(page.getByRole('cell', { name: unit.nom, exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Toutes les maquettes', exact: true }).click();
      await expect(page.getByRole('cell', { name: year.libelle, exact: true })).toBeVisible();
      await expect(page.locator('.sis-content table')).toHaveCount(1);
      await page.getByRole('tab', { name: 'Historique', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Historique de la formation', exact: true })).toBeVisible();
      await expect(page.locator('.sis-content table')).toHaveCount(0);
    }

    const types = await api('core/signatures/types/');
    const signature = await api('core/signatures/', 'POST', {
      fonction: `Recette ${key}`,
      types_documents: [types[0].value],
      debut: new Date(Date.now() - 60000).toISOString(),
      fin: new Date(Date.now() + 86400000).toISOString(),
    });
    await page.goto(`/${variant}/signatures`);
    const signatureRow = page.getByRole('row').filter({ hasText: signature.fonction });
    await expect(signatureRow.locator('.sis-status-badge')).toHaveAttribute('data-status-tone', 'pending');
    await signatureRow.getByRole('cell', { name: signature.fonction, exact: true }).click();
    await expect(page.getByRole('table', { name: 'Appositions', exact: true })).toBeVisible();
    await expect(page.locator('.sis-content table')).toHaveCount(1);
    await page.getByRole('tab', { name: 'Historique', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Historique des décisions', exact: true })).toBeVisible();
    await expect(page.locator('.sis-content table')).toHaveCount(0);
    await page.getByRole('button', { name: 'Retour aux signatures', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Mes signatures', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Passer au thème sombre', exact: true }).click();
    await expect(signatureRow.locator('.sis-status-badge')).toHaveCSS('background-color', 'rgb(73, 58, 20)');
    await capturePresentation(page, `${variant}-status-table-dark`, testInfo);
    await page.getByRole('button', { name: 'Passer au thème clair', exact: true }).click();

    const username = `views-${key}`;
    await api('utilisateurs/comptes/', 'POST', {
      username,
      first_name: 'Recette',
      last_name: key,
      email: `${username}@example.test`,
      role: variant === 'secondaire' ? 'eleve' : 'etudiant',
      password: credentials.password,
      password_confirm: credentials.password,
    });
    const beneficiaries = await api('core/delegations/beneficiaires/?page_size=100');
    const learner = beneficiaries.results.find(item => item.label.endsWith(`(${username})`));
    expect(learner).toBeDefined();
    const mission = await api('core/delegations/', 'POST', {
      beneficiaire: learner.id,
      ressource: variant === 'secondaire' ? 'classes' : 'formations',
      dossiers_ids: [delegatedRecord],
      debut: new Date(Date.now() - 60000).toISOString(),
      fin: new Date(Date.now() + 86400000).toISOString(),
      motif: `Mission ${key}`,
    });
    const learnerContext = await page.context().browser().newContext();
    try {
      const learnerPage = await learnerContext.newPage();
      await respectApiRateLimit(learnerPage);
      await learnerPage.goto(new URL(`/${variant}/missions`, process.env.SIS_E2E_URL).href);
      await learnerPage.getByLabel('Identifiant').fill(username);
      await learnerPage.getByLabel('Mot de passe').fill(credentials.password);
      await learnerPage.getByRole('button', { name: 'Se connecter', exact: true }).click();
      await learnerPage.getByRole('cell', { name: mission.motif, exact: true }).click();
      await expect(learnerPage.getByRole('table', { name: 'Dossiers de la mission', exact: true })).toBeVisible();
      await expect(learnerPage.locator('.sis-content table')).toHaveCount(1);
      await expect(learnerPage.getByRole('button', { name: 'Ajouter', exact: true })).toHaveCount(0);
      await learnerPage.getByRole('tab', { name: 'Historique', exact: true }).click();
      await expect(learnerPage.locator('.sis-content table')).toHaveCount(0);
      await learnerPage.getByRole('button', { name: 'Retour aux missions', exact: true }).click();
      await expect(learnerPage.getByRole('cell', { name: mission.motif, exact: true })).toBeVisible();
      await learnerPage.goto(new URL(`/${variant}/reclamations`, process.env.SIS_E2E_URL).href);
      await learnerPage.getByRole('button', { name: 'Nouvelle réclamation', exact: true }).click();
      await learnerPage.getByLabel(/^Objet/).fill(`Demande ${key}`);
      await learnerPage.getByLabel(/^Motif de la demande/).fill('Vérification synthétique de la navigation du dossier.');
      await learnerPage.getByRole('button', { name: 'Envoyer la réclamation', exact: true }).click();
      const complaint = learnerPage.getByRole('region', { name: 'Dossier de réclamation', exact: true });
      await expect(complaint).toBeVisible();
      await expect(learnerPage.locator('.sis-content table')).toHaveCount(0);
      await expect(complaint.locator('.sis-status-badge')).toHaveAttribute('data-status-tone', 'submitted');
      await expect(learnerPage.getByRole('button', { name: 'Rendre la décision', exact: true })).toHaveCount(0);
      const complaintUrl = learnerPage.url();
      await learnerPage.getByRole('button', { name: 'Actualiser', exact: true }).click();
      await expect(complaint).toBeVisible();
      await capturePresentation(learnerPage, `${variant}-complaint-only`, testInfo);
      await learnerPage.getByRole('button', { name: 'Retour aux réclamations', exact: true }).click();
      await expect(complaint).toHaveCount(0);
      await expect(learnerPage.getByRole('table', { name: 'Réclamations accessibles', exact: true })).toBeVisible();
      await learnerPage.goBack();
      await expect(learnerPage).toHaveURL(complaintUrl);
      await expect(complaint).toBeVisible();
      await expect(learnerPage.locator('.sis-content table')).toHaveCount(0);
    } finally {
      await learnerContext.close();
    }
    expect(errors).toEqual([]);
  });
}
