const fs = require('fs');
const { createHash, createHmac } = require('crypto');
const { test, expect } = require('@playwright/test');
const escapeRegExp = require('lodash/escapeRegExp');
const { assertPresentation, capturePresentation, captureDialog } = require('./presentation');
const { authenticatedApi, respectApiRateLimit } = require('./api');

const variants = process.env.SIS_E2E_MODE === 'dual'
  ? ['secondaire', 'superieur'] : [process.env.SIS_E2E_MODE || 'secondaire'];

async function createResource(page, title, endpoint, fields) {
  const region = page.getByRole('region', { name: title, exact: true });
  if (!await region.count()) {
    const back = page.getByRole('link', { name: 'Toutes les rubriques', exact: true });
    if (await back.count()) { await back.click(); }
    const entry = page.locator('.sis-section-entries').getByRole('link', { name: title, exact: true });
    if (await entry.count()) { await entry.click(); }
  }
  const tab = page.locator('.sis-records-tabs').getByRole('tab', { name: title, exact: true });
  if (await tab.count()) { await tab.click(); }
  await page.getByRole('region', { name: title, exact: true }).getByRole('button', { name: 'Ajouter', exact: true }).click();
  const dialog = page.getByRole('dialog');
  /* eslint-disable no-await-in-loop -- Un seul menu de sélection peut être ouvert à la fois. */
  for (const [label, value] of Object.entries(fields)) {
    const input = dialog.getByLabel(new RegExp(`^${label}`));
    if (await input.getAttribute('role') === 'combobox') {
      await input.click();
      for (const option of (Array.isArray(value) ? value : [value])) {
        await page.getByRole('option', { name: option, exact: true }).click();
      }
      if (Array.isArray(value)) { await page.keyboard.press('Escape'); }
    } else {
      await input.fill(value);
    }
    /* eslint-enable no-await-in-loop */
  }
  const created = page.waitForResponse(response => response.url().endsWith(`/api/v1/${endpoint}/`)
    && response.request().method() === 'POST');
  await dialog.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  const response = await created;
  expect(response.status(), await response.text()).toBe(201);
  await expect(dialog).not.toBeVisible();
  return response.json();
}

async function verifyWorkspace(page, variant, testInfo) {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto(`/${variant}`);
  await expect(page.getByRole('heading', { name: 'Votre espace de travail' })).toBeVisible();
  await expect(page.locator('.sis-topbar__context strong')).toHaveText(`Installation ${variant}`);
  const homeLink = page.getByRole('navigation', { name: 'Navigation principale' })
    .getByRole('link', { name: 'Accueil', exact: true });
  await expect(homeLink).toHaveCSS('display', 'flex');
  await expect(homeLink).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('.sis-summary__count strong')).toHaveCount(variant === 'secondaire' ? 2 : 3);
  await expect(page.getByRole('navigation', { name: 'Navigation principale' }).getByRole('link')).toHaveCount(7);
  await expect(page.getByText('Compteur indisponible.')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'À consulter' })).toBeVisible();
  await expect(page.getByText('Aucune notification workflow non lue.')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath(`${variant}-desktop.png`), fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'Réduire le menu' }).click();
  await expect(page.getByRole('button', { name: 'Déployer le menu' })).toHaveAttribute('aria-expanded', 'false');
  await page.getByRole('button', { name: 'Déployer le menu' }).click();
  await page.getByRole('button', { name: 'Ouvrir la palette de navigation' }).click();
  await page.getByLabel('Rechercher dans les modules autorisés').fill('module inexistant');
  await expect(page.getByText('Aucun module autorisé ne correspond.')).toBeVisible();
  await page.keyboard.press('Escape');

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('navigation', { name: 'Navigation principale' })).toHaveCount(0);
  const opener = page.getByRole('button', { name: 'Ouvrir le menu' });
  await opener.click();
  const drawer = page.getByRole('dialog', { name: 'Menu de navigation' });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole('link', { name: 'Accueil', exact: true })).toHaveCSS('display', 'flex');
  await page.screenshot({ path: testInfo.outputPath(`${variant}-mobile-menu.png`), animations: 'disabled' });
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
  await expect(opener).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath(`${variant}-mobile.png`), fullPage: true, animations: 'disabled' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('link', { name: 'Ouvrir mon compte', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sécurité du compte' })).toBeVisible();
  await expect(drawer).not.toBeVisible();
  await capturePresentation(page, `${variant}-account`, testInfo);
  await page.setViewportSize({ width: 1440, height: 960 });
}

async function verifyComplaint(page, learnerPage, variant, api, testInfo) {
  await learnerPage.goto(`/${variant}/reclamations`);
  await learnerPage.getByRole('button', { name: 'Nouvelle réclamation' }).click();
  await learnerPage.getByLabel(/^Objet/).fill('Vérification de résultat navigateur');
  await learnerPage.getByLabel(/^Motif de la demande/).fill('Je demande la vérification de mon résultat.');
  await captureDialog(learnerPage, `${variant}-complaint-form`, testInfo);
  const created = learnerPage.waitForResponse(response => response.url().endsWith('/core/reclamations/')
    && response.request().method() === 'POST');
  await learnerPage.getByRole('button', { name: 'Envoyer la réclamation' }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const item = await response.json();
  await expect(learnerPage.getByText(item.reference)).toBeVisible();
  await assertPresentation(learnerPage);
  await expect(learnerPage.getByRole('button', { name: 'Rendre la décision' })).toHaveCount(0);
  const pdf = Buffer.from('%PDF-1.4\nbrowser private proof');
  await learnerPage.getByLabel('Justificatif PDF').setInputFiles({
    name: 'preuve.pdf', mimeType: 'application/pdf', buffer: pdf,
  });
  await learnerPage.getByRole('button', { name: 'Ajouter le justificatif' }).click();
  await expect(learnerPage.getByRole('button', { name: 'Télécharger preuve.pdf' })).toBeVisible();
  const downloaded = learnerPage.waitForEvent('download');
  await learnerPage.getByRole('button', { name: 'Télécharger preuve.pdf' }).click();
  const download = await downloaded;
  expect(fs.readFileSync(await download.path())).toEqual(pdf);
  await learnerPage.getByRole('heading', { name: 'Réclamations', exact: true }).click();
  await learnerPage.evaluate(() => window.scrollTo(0, 0));
  expect(await learnerPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await learnerPage.screenshot({
    path: testInfo.outputPath(`${variant}-complaint-mobile.png`), fullPage: true, animations: 'disabled',
  });

  const admin = await api('utilisateurs/comptes/me/');
  await page.goto(`/${variant}/reclamations?dossier=${item.id}`);
  await page.getByLabel('Agent responsable').selectOption(String(admin.id));
  await page.getByRole('button', { name: 'Affecter le dossier' }).click();
  await expect(page.getByRole('button', { name: 'Rendre la décision' })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath(`${variant}-complaint-agent.png`), fullPage: true, animations: 'disabled',
  });
  await page.getByLabel('Message ou motif de décision').fill('Résultat examiné. Une rectification suit son circuit distinct.');
  await page.getByRole('button', { name: 'Rendre la décision' }).click();
  await expect(page.getByText('Dernière décision motivée :')).toBeVisible();
  await learnerPage.getByRole('button', { name: 'Actualiser', exact: true }).click();
  await expect(learnerPage.getByText('Dernière décision motivée :')).toBeVisible();
  await learnerPage.getByLabel('Message ou motif de décision').fill('Je transmets un nouvel élément pour recours.');
  await learnerPage.getByRole('button', { name: 'Déposer un recours' }).click();
  await expect(learnerPage.getByRole('button', { name: 'Envoyer le message' })).toBeVisible();
  await learnerPage.goto(`/${variant}`);
  await expect(learnerPage.getByRole('link', { name: 'Consulter la réclamation' }).first()).toBeVisible();
}

async function verifyDocuments(learnerPage, variant, api, learner, academic, testInfo) {
  const { year, period, parent } = academic;
  const common = { etudiant: learner.id, date_emission: new Date().toISOString().slice(0, 10), pdf_path: 'generated.pdf' };
  const cases = variant === 'secondaire' ? [{
    resource: 'bulletins',
    tab: 'Bulletins',
    action: 'publier',
    payload: {
      eleve: learner.id, classe: parent.id, periode: period.id, moyenne_generale: '0.00',
    },
  }] : [
    {
      resource: 'releves', tab: 'Relevés de notes', action: 'signer', payload: { ...common, semestre: period.id, numero_serie: 'DOC-REL' },
    },
    {
      resource: 'releves/transcripts',
      tab: 'Transcripts',
      action: 'signer',
      payload: {
        ...common, annees: [year.id], numero_serie: 'DOC-TRANSCRIPT', credits_total: 60, credits_valides: 30,
      },
    },
    {
      resource: 'releves/attestations', tab: 'Attestations', action: 'signer', payload: { ...common, type: 'inscription', numero: 'DOC-ATTESTATION' },
    },
  ];
  await learnerPage.goto(`/${variant}/documents`);
  const issued = [];
  const verify = async ({
    resource, tab, action, payload,
  }) => {
    const document = await api(`${resource}/`, 'POST', payload);
    await learnerPage.getByRole('tab', { name: tab, exact: true }).click();
    await learnerPage.getByRole('button', { name: 'Actualiser', exact: true }).click();
    await expect(learnerPage.getByText('Aucun document disponible pour le moment.')).toBeVisible();
    await api(`${resource}/${document.id}/${action}/`, 'POST', {});
    issued.push({ ...document, resource });
    await learnerPage.getByRole('button', { name: 'Actualiser', exact: true }).click();
    await expect(learnerPage.getByRole('cell', { name: 'Workspace Learner', exact: true })).toBeVisible();
    const downloaded = learnerPage.waitForEvent('download');
    await learnerPage.getByRole('button', { name: 'Télécharger le PDF', exact: true }).click();
    expect(fs.readFileSync(await (await downloaded).path()).subarray(0, 5).toString()).toBe('%PDF-');
    expect((await api(`${resource}/${document.id}/historique/`)).some(event => event.action === 'telechargement')).toBe(true);
    await learnerPage.getByLabel('Rechercher', { exact: true }).fill('Workspace');
    const exported = learnerPage.waitForEvent('download');
    await learnerPage.getByRole('button', { name: 'Exporter la liste filtrée (CSV)' }).click();
    const csv = fs.readFileSync(await (await exported).path(), 'utf8');
    expect(csv).toContain('Workspace Learner');
    expect(csv).not.toContain('Name000');
    await capturePresentation(learnerPage, `${variant}-${resource.replaceAll('/', '-')}-documents`, testInfo);
  };
  for (const document of cases) {
    // The cases navigate the same authenticated page and must run sequentially.
    // eslint-disable-next-line no-await-in-loop
    await verify(document);
  }
  return issued;
}

async function verifyDelegatedAccess(page, learnerPage, variant, api, academic, testInfo) {
  const learnerApi = authenticatedApi(learnerPage, variant);
  const user = await learnerApi('utilisateurs/comptes/me/');
  const resource = variant === 'secondaire' ? 'classes' : 'formations';
  const beneficiaries = await api('core/delegations/beneficiaires/?page_size=100');
  const beneficiary = beneficiaries.results.find(item => item.id === user.id);
  const choices = await api(`core/delegations/choix/?ressource=${resource}`);
  const choice = choices.results.find(item => item.id === academic.parent.id);
  await page.goto(`/${variant}/missions`);
  const mission = await createResource(page, 'Accès délégués', 'core/delegations', {
    Apprenant: beneficiary.label,
    'Dossiers autorisés': [choice.label],
    'Début de la mission': new Date(Date.now() - 3600000).toISOString().slice(0, 16),
    'Fin de la mission': new Date(Date.now() + 86400000).toISOString().slice(0, 16),
    'Objet de la mission et justification': 'Observation administrative en stage',
  });
  await learnerPage.goto(`/${variant}/missions`);
  await learnerPage.getByRole('cell', { name: mission.motif, exact: true }).click();
  await expect(learnerPage.getByRole('cell', { name: choice.label, exact: true })).toBeVisible();
  await expect(learnerPage.getByRole('button', { name: 'Ajouter', exact: true })).toHaveCount(0);
  expect((await learnerApi('utilisateurs/comptes/me/')).role).toBe(variant === 'secondaire' ? 'eleve' : 'etudiant');
  await capturePresentation(learnerPage, `${variant}-delegated-mission`, testInfo);
  await page.getByRole('button', { name: 'Révoquer', exact: true }).click();
  await page.getByLabel(/^Motif de révocation/).fill('Fin de la mission de stage');
  await page.getByRole('dialog').getByRole('button', { name: 'Révoquer', exact: true }).click();
  await expect(page.getByText('Révoquer : opération effectuée.')).toBeVisible();
  await learnerPage.reload();
  await learnerPage.getByRole('cell', { name: mission.motif, exact: true }).click();
  await expect(learnerPage.getByText(/Cette mission n’est pas active/)).toBeVisible();
  await expect(learnerPage.getByRole('cell', { name: choice.label, exact: true })).toHaveCount(0);
}

async function verifySignedArchive(page, learnerPage, variant, api, credentials, document, testInfo) {
  const types = await api('core/signatures/types/');
  const type = types[0];
  await page.goto(`/${variant}/signatures`);
  const signature = await createResource(page, 'Mes signatures', 'core/signatures', {
    'Fonction institutionnelle': 'Direction de recette',
    'Types de documents autorisés': [type.label],
    'Début de validité': new Date(Date.now() - 3600000).toISOString().slice(0, 16),
    'Fin de validité': new Date(Date.now() + 86400000).toISOString().slice(0, 16),
  });
  await expect(page.getByRole('button', { name: 'Valider', exact: true })).toHaveCount(0);
  const username = `signature-reviewer-${variant}`;
  await api('utilisateurs/comptes/', 'POST', {
    username,
    email: `${username}@example.test`,
    first_name: 'Validation',
    last_name: 'Indépendante',
    role: 'autre',
    password: credentials.password,
    password_confirm: credentials.password,
  });
  const reviewer = (await api(`utilisateurs/comptes/?search=${username}`)).results[0];
  const permission = (await api('utilisateurs/permissions/?search=approve_signature')).results
    .find(item => item.app_label === 'core' && item.codename === 'approve_signature');
  await api(`utilisateurs/comptes/${reviewer.id}/`, 'PATCH', { user_permissions: [permission.id] });
  const context = await page.context().browser().newContext({ baseURL: process.env.SIS_E2E_URL });
  try {
    const approvalPage = await context.newPage();
    await approvalPage.goto(`/${variant}/signatures`);
    await approvalPage.getByLabel('Identifiant').fill(username);
    await approvalPage.getByLabel('Mot de passe').fill(credentials.password);
    await approvalPage.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await approvalPage.getByRole('tab', { name: 'Validations indépendantes' }).click();
    await approvalPage.getByRole('button', { name: 'Valider', exact: true }).click();
    await approvalPage.getByLabel(/^Justification et contrôles effectués/).fill('Identité et fonction vérifiées');
    await captureDialog(approvalPage, `${variant}-signature-approval`, testInfo);
    await approvalPage.getByRole('dialog').getByRole('button', { name: 'Valider', exact: true }).click();
    await expect(approvalPage.getByText('Valider : opération effectuée.')).toBeVisible();
  } finally {
    await context.close();
  }
  expect((await api(`core/signatures/${signature.id}/`)).statut).toBe('validee');
  const source = (await api(`core/documents-signes/sources/?source_type=${type.value}`)).results
    .find(item => item.id === document.id);
  await page.goto(`/${variant}/archives`);
  const archive = await createResource(page, 'Versions signées et archivées', 'core/documents-signes', {
    'Signature approuvée': signature.fonction, 'Document publié ou validé': source.label,
  });
  const notifications = (await api('core/notifications/?page_size=100')).results;
  expect(notifications.filter(item => item.category === 'signature_apposee' && item.event.object_id === archive.id)).toHaveLength(1);
  await learnerPage.goto(`/${variant}/documents`);
  await learnerPage.getByRole('tab', { name: 'Versions signées', exact: true }).click();
  await learnerPage.getByRole('cell', { name: 'Workspace Learner', exact: true }).click();
  await learnerPage.getByRole('button', { name: 'Vérifier l’intégrité', exact: true }).click();
  await expect(learnerPage.getByText(/Intégrité confirmée/)).toBeVisible();
  const pdfDownload = learnerPage.waitForEvent('download');
  await learnerPage.getByRole('button', { name: 'Télécharger le PDF archivé' }).click();
  const pdf = fs.readFileSync(await (await pdfDownload).path());
  expect(createHash('sha256').update(pdf).digest('hex')).toBe(archive.sha256);
  const proofDownload = learnerPage.waitForEvent('download');
  await learnerPage.getByRole('button', { name: 'Télécharger la preuve JSON' }).click();
  const proof = JSON.parse(fs.readFileSync(await (await proofDownload).path(), 'utf8'));
  expect(proof.manifeste.sha256).toBe(archive.sha256);
  await capturePresentation(learnerPage, `${variant}-signed-archive`, testInfo);
}

async function verifyLearnerWorkspace(page, variant, api, credentials, testInfo, academic) {
  const resource = variant === 'secondaire' ? 'eleves' : 'etudiants';
  const username = `workspace-${variant}`;
  await api(`${resource}/`, 'POST', {
    username,
    password: credentials.password,
    email: `${username}@example.test`,
    first_name: 'Workspace',
    last_name: 'Learner',
    date_naissance: '2005-01-01',
    lieu_naissance: 'Paris',
    sexe: 'F',
    adresse: '1 Test',
    code_postal: '75000',
    ville: 'Paris',
    ...(variant === 'superieur' ? { matricule: 'WORKSPACE-1', telephone: '+33100000000' } : {}),
  });
  const matches = await api(`${resource}/?search=${encodeURIComponent(`${username}@example.test`)}`);
  expect(matches.count).toBe(1);
  const [learner] = matches.results;
  const context = await page.context().browser().newContext({
    baseURL: process.env.SIS_E2E_URL, viewport: { width: 390, height: 844 },
  });
  try {
    const learnerPage = await context.newPage();
    await learnerPage.goto(`/${variant}`);
    await learnerPage.getByLabel('Identifiant').fill(username);
    await learnerPage.getByLabel('Mot de passe').fill(credentials.password);
    await learnerPage.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(learnerPage.getByRole('heading', {
      name: variant === 'secondaire' ? 'Mon espace élève' : 'Mon espace étudiant',
    })).toBeVisible();
    await learnerPage.setViewportSize({ width: 1440, height: 960 });
    await expect(learnerPage.locator('.sis-layout__sidebar')).toBeVisible();
    await expect(learnerPage.getByRole('navigation', { name: 'Navigation principale' }).getByRole('link')).toHaveCount(5);
    await expect(learnerPage.locator('.sis-stat-card.MuiCard-root')).toHaveCount(4);
    await expect(learnerPage.locator('.sis-content .pgn__card, .sis-content .btn')).toHaveCount(0);
    await capturePresentation(learnerPage, `${variant}-learner-home`, testInfo);
    const recordsTitle = variant === 'secondaire' ? 'Bulletins publiés' : 'Relevés de notes';
    await learnerPage.getByRole('tab', { name: recordsTitle, exact: true }).click();
    await expect(learnerPage.getByRole('table', { name: recordsTitle, exact: true })).toBeVisible();
    await expect(learnerPage.getByRole('table', { name: 'Notes récentes', exact: true })).toHaveCount(0);
    const tableWidth = (await learnerPage.getByRole('region', { name: `Tableau : ${recordsTitle}`, exact: true }).boundingBox()).width;
    expect(tableWidth).toBeGreaterThan((await learnerPage.locator('.sis-content').boundingBox()).width * 0.8);
    await capturePresentation(learnerPage, `${variant}-learner-records`, testInfo);
    await learnerPage.getByRole('tab', { name: 'Notes récentes', exact: true }).click();
    await learnerPage.setViewportSize({ width: 390, height: 844 });
    await learnerPage.getByRole('button', { name: 'Ouvrir le menu' }).click();
    const menu = learnerPage.getByRole('navigation', { name: 'Navigation principale' });
    await expect(menu.getByRole('link', { name: 'Mon dossier' })).toBeVisible();
    await expect(menu.getByRole('link', { name: 'Mes documents' })).toBeVisible();
    await expect(menu.getByRole('link', { name: 'Utilisateurs' })).toHaveCount(0);
    await expect(menu.getByRole('link', { name: 'Établissement' })).toHaveCount(0);
    await learnerPage.keyboard.press('Escape');
    await expect(learnerPage.getByRole('dialog', { name: 'Menu de navigation' })).toHaveCount(0);
    await expect(learnerPage.getByText('Aucune notification workflow non lue.')).toBeVisible();
    await assertPresentation(learnerPage);
    await learnerPage.screenshot({
      path: testInfo.outputPath(`${variant}-learner-mobile.png`), fullPage: true, animations: 'disabled',
    });
    expect(await learnerPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const documents = await verifyDocuments(learnerPage, variant, api, learner, academic, testInfo);
    await verifyDelegatedAccess(page, learnerPage, variant, api, academic, testInfo);
    await verifySignedArchive(page, learnerPage, variant, api, credentials, documents[0], testInfo);
    await verifyComplaint(page, learnerPage, variant, api, testInfo);
    const complaintCount = (await api('core/reclamations/')).count;
    await page.goto(`/admin/etablissement?sis=${variant}`);
    await page.getByRole('tab', { name: 'Modules', exact: true }).click();
    await expect(page.getByLabel('Identité et autorisations', { exact: true })).toBeDisabled();
    await page.getByText('Réclamations privées', { exact: true }).click();
    await expect(page.getByLabel('Réclamations privées', { exact: true })).not.toBeChecked();
    await page.getByLabel('Motif du changement de modules').fill('Suspension de recette');
    await page.getByRole('button', { name: 'Simuler les modules' }).click();
    await expect(page.getByText(/Simulation validée/)).toBeVisible();
    expect((await api('core/reclamations/')).count).toBe(complaintCount);
    await page.getByRole('button', { name: 'Appliquer les modules' }).click();
    await expect(page.getByText('Configuration des modules enregistrée.')).toBeVisible();
    await page.getByRole('button', { name: 'Ouvrir la palette de navigation' }).click();
    await expect(page.getByRole('dialog').getByRole('link', { name: 'Réclamations', exact: true })).toHaveCount(0);
    await page.keyboard.press('Escape');
    await learnerPage.goto(`/${variant}/reclamations`);
    await expect(learnerPage.getByText(/Ce module est désactivé pour votre établissement/).first()).toBeVisible();
    await capturePresentation(page, `${variant}-module-catalogue`, testInfo);
    await page.getByText('Réclamations privées', { exact: true }).click();
    await expect(page.getByLabel('Réclamations privées', { exact: true })).toBeChecked();
    await page.getByLabel('Motif du changement de modules').fill('Réactivation de recette');
    await page.getByRole('button', { name: 'Simuler les modules' }).click();
    await expect(page.getByText(/Simulation validée/)).toBeVisible();
    await page.getByRole('button', { name: 'Appliquer les modules' }).click();
    await expect(page.getByText('Configuration des modules enregistrée.')).toBeVisible();
    expect((await api('core/reclamations/')).count).toBe(complaintCount);
  } finally {
    await context.close();
  }
}

function totp(secret) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  const bits = [...secret].map(character => alphabet.indexOf(character).toString(2).padStart(5, '0')).join('');
  const key = Buffer.from(bits.match(/.{8}/g).map(byte => parseInt(byte, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const digest = createHmac('sha1', key).update(counter).digest();
  const offset = digest[digest.length - 1] % 16;
  return String((digest.readUInt32BE(offset) % (2 ** 31)) % 1000000).padStart(6, '0');
}

async function verifyAcademicOperations(page, variant, api, data, testInfo) {
  const {
    year, period, parent, subject, learner, dates,
  } = data;
  const secondary = variant === 'secondaire';
  const today = new Date().toISOString().slice(0, 10);
  const select = async (label, text) => {
    await page.getByRole('combobox', { name: new RegExp(`^${escapeRegExp(label)}(?:\\s|$)`) }).click();
    await page.getByRole('option', { name: text, exact: true }).click();
  };
  await page.goto(`/${variant}/examens`);
  const session = await createResource(page, 'Sessions d’examen', 'examens/sessions', {
    ...(secondary ? { Nom: 'Session navigateur', 'Année scolaire': year.libelle } : { Semestre: period.libelle }),
    Type: secondary ? 'examen_blanc' : 'normale',
    Début: dates.date_debut,
    Fin: dates.date_fin,
  });
  await page.getByRole('tab', { name: 'Épreuves', exact: true }).click();
  const exam = await createResource(page, 'Épreuves', 'examens/epreuves', {
    Session: session.libelle,
    ...(secondary ? { Matière: subject.nom, Classes: [parent.nom] } : { ECUE: subject.nom, Lieu: 'Salle navigateur' }),
    Date: today,
    Heure: '09:00',
    'Ouverture de la saisie': new Date(Date.now() - 86400000).toISOString().slice(0, 16),
    'Fin de la saisie': new Date(Date.now() + 86400000).toISOString().slice(0, 16),
  });
  const examLabel = (await api('examens/epreuves/')).results.find(item => item.id === exam.id).libelle;
  await page.getByRole('tab', { name: 'Convocations', exact: true }).click();
  await createResource(page, 'Convocations', 'examens/convocations', {
    Épreuve: examLabel, [secondary ? 'Élève' : 'Étudiant']: learner.full_name, 'Numéro de place': '1',
  });
  await page.getByRole('tab', { name: 'Résultats d’examen', exact: true }).click();
  const result = await createResource(page, 'Résultats d’examen', 'examens/resultats', {
    Épreuve: examLabel, [secondary ? 'Élève' : 'Étudiant']: learner.full_name, Note: '14',
  });
  /* eslint-disable no-await-in-loop -- Les transitions métier sont successives. */
  for (const label of ['Soumettre', 'Vérifier', 'Valider', 'Publier']) {
    await page.getByRole('button', { name: label, exact: true }).click();
    await expect(page.getByText(`${label} : opération effectuée.`)).toBeVisible();
  }
  /* eslint-enable no-await-in-loop */
  expect((await api(`examens/resultats/${result.id}/`)).statut).toBe('published');
  await capturePresentation(page, `${variant}-exam-results`, testInfo);

  if (!secondary) {
    await page.goto(`/superieur/formations/${parent.id}`);
    await page.getByRole('row').filter({ hasText: year.libelle }).click();
    const ue = await createResource(page, `UE — ${year.libelle}`, 'ue-ecue/ues', {
      Code: 'UI-UE', Nom: 'Unité navigateur', Semestre: period.libelle, Crédits: '6',
    });
    await page.getByRole('row').filter({ hasText: 'Unité navigateur' }).click();
    const ecue = await createResource(page, 'ECUE — Unité navigateur', 'ue-ecue/ecues', {
      Code: 'UI-EC', Nom: 'Cours navigateur', Crédits: '6',
    });
    expect(ecue.ue).toBe(ue.id);
    await capturePresentation(page, 'superieur-curriculum', testInfo);
    await page.getByRole('tab', { name: 'Étudiants', exact: true }).click();
    await expect(page.getByRole('cell', { name: learner.full_name, exact: true })).toBeVisible();

    const building = await api('edt/batiments/', 'POST', { code: 'UI', nom: 'Bâtiment navigateur' });
    await api('edt/salles/', 'POST', {
      batiment: building.id, code: 'UI1', nom: 'Salle navigateur', capacite: 40,
    });
    await page.goto('/superieur/emploi-du-temps');
    await page.getByRole('tab', { name: 'Horaires types', exact: true }).click();
    await createResource(page, 'Horaires types', 'edt/creneaux-horaires', { Début: '08:30', Fin: '10:00', Ordre: '1' });
    await page.getByRole('tab', { name: 'Créneaux', exact: true }).click();
    await createResource(page, 'Créneaux de cours', 'edt/creneaux-cours', {
      Semestre: period.libelle,
      Formation: parent.nom,
      ECUE: 'Cours navigateur',
      Salle: 'Salle navigateur',
      Jour: 'Lundi',
      Horaire: '08:30-10:00',
    });
    await page.getByRole('tab', { name: 'Emploi du temps', exact: true }).click();
    await select('Formation', parent.nom);
    const planningLoaded = page.waitForResponse(response => response.url().includes('/edt/creneaux-cours/par_formation/'));
    await select('Semestre', `${year.libelle} — ${period.libelle}`);
    expect((await planningLoaded).status()).toBe(200);
    await expect(page.getByText('08:30-10:00 — Cours navigateur', { exact: true })).toBeVisible();
    await capturePresentation(page, 'superieur-timetable', testInfo);
    await page.getByRole('tab', { name: 'Réservations', exact: true }).click();
    await createResource(page, 'Réservations de salles', 'edt/reservations', {
      Salle: 'Salle navigateur', Date: today, Début: '14:00', Fin: '15:00', Motif: 'reunion',
    });
    await page.getByRole('button', { name: 'Décider', exact: true }).click();
    await select('Décision', 'confirmer');
    await page.getByRole('dialog').getByRole('button', { name: 'Décider', exact: true }).click();
    await expect(page.getByRole('cell', { name: 'Confirmée', exact: true })).toBeVisible();
  }
  const candidate = (await api(`${secondary ? 'eleves' : 'etudiants'}/?search=Name001`)).results[0];
  if (secondary) {
    const source = await api('classes/classes/', 'POST', {
      nom: 'Classe départ', niveau: parent.niveau, annee_scolaire: year.id,
    });
    const target = await api('classes/classes/', 'POST', {
      nom: 'Classe arrivée', niveau: parent.niveau, annee_scolaire: year.id,
    });
    const enrollment = await api('eleves/inscriptions/', 'POST', {
      eleve: candidate.id, classe: source.id, annee_scolaire: year.id, date_inscription: today,
    });
    await api(`eleves/inscriptions/${enrollment.id}/valider/`, 'POST', {});
    await page.goto('/secondaire/classes');
    await page.getByRole('region', { name: 'Classes', exact: true }).getByRole('row').filter({ hasText: 'Classe départ' }).click();
    await page.getByRole('button', { name: 'Changer de classe', exact: true }).click();
    await select('Classe de destination', target.nom);
    await page.getByLabel(/^Motif du transfert/).fill('Réorientation navigateur');
    await page.getByRole('dialog').getByRole('button', { name: 'Changer de classe', exact: true }).click();
    await expect(page.getByText('Changer de classe : opération effectuée.')).toBeVisible();
    expect((await api(`eleves/inscriptions/${enrollment.id}/`)).classe).toBe(target.id);
    expect((await api(`eleves/${candidate.id}/`)).classe_actuelle).toBe(target.id);
  } else {
    const source = await api('formations/formations/', 'POST', { code: 'FROM', nom: 'Formation départ', type: 'licence' });
    const target = await api('formations/formations/', 'POST', { code: 'TO', nom: 'Formation arrivée', type: 'licence' });
    const enrollment = await api('inscriptions/', 'POST', {
      etudiant: candidate.id, formation: source.id, annee_universitaire: year.id, date_inscription: today,
    });
    await api(`inscriptions/${enrollment.id}/valider/`, 'POST', {});
    await page.goto('/superieur/inscriptions');
    await page.getByRole('row').filter({ hasText: candidate.full_name }).getByRole('button', { name: 'Transférer' }).click();
    await select('Formation de destination', target.nom);
    await page.getByLabel(/^Motif du transfert/).fill('Réorientation navigateur');
    await page.getByRole('dialog').getByRole('button', { name: 'Transférer', exact: true }).click();
    await expect(page.getByText('Transférer : opération effectuée.')).toBeVisible();
    expect((await api(`inscriptions/${enrollment.id}/`)).formation).toBe(target.id);
  }
  await page.goto(`/${variant}/workflows`);
  await select('Personne', 'pilot-admin');
  const audit = await api('core/workflow-events/?action=transfert');
  const transfers = Array.isArray(audit) ? audit : audit.results;
  expect(transfers.length).toBeGreaterThan(0);
  // The audit timestamp uses the institution's timezone, not the runner's UTC date.
  const auditDay = transfers[0].created_at.slice(0, 10);
  await page.getByLabel('Du', { exact: true }).fill(auditDay);
  await page.getByLabel('Au (inclus)', { exact: true }).fill(auditDay);
  await expect(page.getByRole('cell', { name: 'transfert', exact: true })).toBeVisible();
  const enrollments = secondary ? 'eleves/inscriptions' : 'inscriptions';
  const yearField = secondary ? 'annee_scolaire' : 'annee_universitaire';
  const targetField = secondary ? 'classe' : 'formation';
  const original = (await api(`${enrollments}/?${secondary ? 'eleve' : 'etudiant'}=${learner.id}`)).results
    .find(item => item[secondary ? 'eleve' : 'etudiant'] === learner.id);
  const nextYearNumber = Number(year.date_fin.slice(0, 4)) + 1;
  const nextYear = await api('etablissement/annees/', 'POST', {
    libelle: 'Année suivante', date_debut: `${nextYearNumber}-01-01`, date_fin: `${nextYearNumber}-12-31`,
  });
  const target = secondary ? await api('classes/classes/', 'POST', {
    nom: 'Classe suivante', niveau: parent.niveau, annee_scolaire: nextYear.id,
  }) : await api('formations/formations/', 'POST', { code: 'NEXT', nom: 'Cursus suivant', type: 'licence' });
  await page.goto(`/${variant}/${secondary ? 'classes' : 'inscriptions'}`);
  if (secondary) { await page.getByRole('tab', { name: 'Inscriptions annuelles', exact: true }).click(); }
  await page.getByRole('row').filter({ hasText: learner.full_name })
    .getByRole('button', { name: 'Réinscrire / changer de cursus', exact: true }).click();
  await select('Nouvelle année', nextYear.libelle);
  await select(secondary ? 'Nouvelle classe' : 'Nouvelle formation', target.nom);
  await page.getByLabel(/^Date de la nouvelle demande/).fill(today);
  await page.getByLabel(/^Justification/).fill('Poursuite de cursus sans conversion des acquis');
  await captureDialog(page, `${variant}-reenrollment`, testInfo);
  await page.getByRole('dialog').getByRole('button', { name: 'Réinscrire / changer de cursus', exact: true }).click();
  await expect(page.getByText('Réinscrire / changer de cursus : opération effectuée.')).toBeVisible();
  const renewed = (await api(`${enrollments}/?${yearField}=${nextYear.id}`)).results[0];
  expect(renewed[targetField]).toBe(target.id);
  expect(renewed.statut).toBe(secondary ? 'en_cours' : 'provisoire');
  expect((await api(`${enrollments}/${original.id}/`))[targetField]).toBe(original[targetField]);
  await capturePresentation(page, `${variant}-admissions`, testInfo);
}

async function verifySchoolServices(page, api, learner, year, period, credentials) {
  const today = new Date().toISOString().slice(0, 10);
  const instant = `${today}T10:15`;
  const accounts = (await api('utilisateurs/comptes/')).results;
  const admin = accounts.find(user => user.username === credentials.username);
  const responsible = admin.full_name || admin.username;
  await page.goto('/secondaire/clubs');
  await createResource(page, 'Clubs', 'clubs', {
    Nom: 'Club navigateur',
    Description: 'Recette',
    Responsable: responsible,
    Horaires: 'Mercredi',
    'Date de création': today,
  });
  await createResource(page, 'Membres des clubs', 'clubs/membres-clubs', { Club: 'Club navigateur', Élève: learner.matricule });
  await createResource(page, 'Séances des clubs', 'clubs/activites-clubs', {
    Club: 'Club navigateur', Date: today, Début: '14:00', Fin: '15:00', Activité: 'Recette',
  });
  await page.goto('/secondaire/cantine');
  await createResource(page, 'Menus de la cantine', 'cantine/menus', { Date: today, Plat: 'Repas navigateur', Prix: '3.75' });
  const meal = await createResource(page, 'Inscriptions à la cantine', 'cantine/inscriptions-cantine', {
    Élève: learner.matricule, Début: today, Fin: today,
  });
  const section = page.getByRole('region', { name: 'Inscriptions à la cantine', exact: true });
  await section.getByRole('button', { name: 'Modifier', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Fin', { exact: true }).fill('');
  await page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  expect((await api(`cantine/inscriptions-cantine/${meal.id}/`)).date_fin).toBeNull();
  await createResource(page, 'Présences à la cantine', 'cantine/presences-cantine', { Menu: today, Élève: learner.matricule });

  await page.goto('/secondaire/transport');
  await createResource(page, 'Lignes de transport', 'transport/lignes-transport', { Nom: 'Ligne navigateur', Itinéraire: 'Route recette' });
  await createResource(page, 'Arrêts', 'transport/arrets', { Ligne: 'Ligne navigateur', Nom: 'Arrêt navigateur', Passage: '07:30' });
  const vehicle = await createResource(page, 'Véhicules', 'transport/vehicules', {
    Immatriculation: 'TEST-UI-1', Capacité: '30', Chauffeur: 'Conducteur recette',
  });
  expect(vehicle.chauffeur).toBe('Conducteur recette');
  await createResource(page, 'Inscriptions au transport', 'transport/inscriptions-transport', {
    Élève: learner.matricule,
    Ligne: 'Ligne navigateur',
    'Arrêt de montée': 'Ligne navigateur - Arrêt navigateur',
    'Arrêt de descente': 'Ligne navigateur - Arrêt navigateur',
    'Année scolaire': year.libelle,
  });
  await page.goto('/secondaire/internat');
  await createResource(page, 'Bâtiments', 'internat/batiments', { Nom: 'Bâtiment navigateur' });
  await createResource(page, 'Chambres', 'internat/chambres', { Bâtiment: 'Bâtiment navigateur', Numéro: 'A1' });
  const room = (await api('internat/chambres/')).results[0];
  await createResource(page, "Séjours à l'internat", 'internat/occupants-chambres', {
    Chambre: room.libelle, Élève: learner.matricule, Début: today,
  });
  await page.goto('/secondaire/discipline');
  const incident = await createResource(page, 'Incidents disciplinaires', 'discipline/incidents', {
    Élève: learner.matricule, 'Date et heure': instant, Description: 'Incident fictif', Rapporteur: 'Grade Teacher',
  });
  const incidentLabel = (await api('discipline/incidents/')).results.find(row => row.id === incident.id).libelle;
  await createResource(page, 'Sanctions disciplinaires', 'discipline/sanctions', {
    Incident: incidentLabel, Motif: 'Recette', "Date d'effet": today,
  });
  await page.goto('/secondaire/conseil-classe');
  const council = await createResource(page, 'Conseils de classe', 'conseils/conseils-classe', {
    Classe: 'Classe recette', Période: period.libelle, 'Date et heure': instant, Président: responsible,
  });
  await page.getByRole('button', { name: 'Marquer tenu', exact: true }).click();
  await expect(page.getByText('Marquer tenu : opération effectuée.')).toBeVisible();
  await page.getByRole('button', { name: 'Valider', exact: true }).click();
  await expect(page.getByText('Valider : opération effectuée.')).toBeVisible();
  expect((await api(`conseils/conseils-classe/${council.id}/`)).statut).toBe('valide');
  await page.goto('/secondaire/infirmerie');
  const visit = await createResource(page, "Visites à l'infirmerie", 'infirmerie/visites-infirmerie', {
    Élève: learner.matricule, 'Date et heure': instant, Arrivée: '10:15', Motif: 'Visite fictive de recette',
  });
  expect(visit.infirmier).toBe(admin.id);
  await createResource(page, "Stock de l'infirmerie", 'infirmerie/stock-medicaments', { Nom: 'Article fictif' });
}

async function verifyGradeEntry(page, variant, credentials, dates, testInfo) {
  const api = authenticatedApi(page, variant);
  const year = (await api('etablissement/annees/')).results[0];
  const resource = variant === 'secondaire' ? 'eleves' : 'etudiants';
  const learner = (await api(`${resource}/?search=Name000`)).results[0];
  const teacher = {
    username: 'grade-teacher',
    first_name: 'Grade',
    last_name: 'Teacher',
    email: 'grade-teacher@example.test',
    role: 'enseignant',
    password: credentials.password,
  };
  let subject;
  let period;
  let parent;
  let parentEndpoint;
  if (variant === 'secondaire') {
    const level = await api('etablissement/niveaux/', 'POST', { code: '6e', libelle: 'Sixième' });
    parentEndpoint = 'classes/classes';
    await page.goto('/secondaire/classes');
    parent = await createResource(page, 'Classes', parentEndpoint, {
      'Nom de la classe': 'Classe recette',
      Niveau: level.libelle,
      'Année scolaire': year.libelle,
      'Offre institutionnelle': 'Collège / lycée',
    });
    expect(parent.offre_configuration.profile).toBe('secondary');
    await page.getByRole('tab', { name: 'Inscriptions annuelles', exact: true }).click();
    const enrollment = await createResource(page, 'Inscriptions annuelles', 'eleves/inscriptions', {
      Élève: learner.full_name, Classe: parent.nom, 'Année scolaire': year.libelle, 'Date d’inscription': dates.date_debut,
    });
    expect(enrollment.offre_configuration).toEqual(parent.offre_configuration);
    await page.getByRole('region', { name: 'Inscriptions annuelles', exact: true })
      .getByRole('button', { name: 'Valider', exact: true }).click();
    await expect(page.getByText('Valider : opération effectuée.')).toBeVisible();
    subject = await api('classes/matieres/', 'POST', { code: 'MAT', nom: 'Mathématiques' });
    period = await api('etablissement/periodes/', 'POST', {
      annee_scolaire: year.id, type: 'trimestre', numero: 1, libelle: 'Trimestre recette', ...dates,
    });
    await api('enseignants/personnel/', 'POST', { ...teacher, date_embauche: dates.date_debut });
  } else {
    await api('utilisateurs/comptes/', 'POST', { ...teacher, password_confirm: credentials.password });
    period = await api('etablissement/semestres/', 'POST', {
      annee_universitaire: year.id, type: 'impair', numero: 1, ...dates,
    });
    parentEndpoint = 'formations/formations';
    await page.goto('/superieur/formations');
    parent = await createResource(page, 'Formations', parentEndpoint, {
      Code: 'LIC', 'Nom de la formation': 'Licence recette', 'Offre institutionnelle': 'Université / grande école',
    });
    expect(parent.offre_configuration.profile).toBe('higher_education');
    const maquette = await api('formations/maquettes/', 'POST', {
      formation: parent.id, annee_universitaire: year.id,
    });
    const ue = await api('ue-ecue/ues/', 'POST', {
      maquette: maquette.id, semestre: period.id, code: 'UE1', nom: 'UE recette', credits_ects: 6,
    });
    subject = await api('ue-ecue/ecues/', 'POST', {
      ue: ue.id, code: 'EC1', nom: 'Mathématiques', credits_ects: 6,
    });
    await page.goto('/superieur/inscriptions');
    const enrollment = await createResource(page, 'Inscriptions administratives', 'inscriptions', {
      Étudiant: learner.full_name,
      Formation: parent.nom,
      'Année universitaire': year.libelle,
      'Date d’inscription': dates.date_debut,
    });
    expect(enrollment.offre_configuration).toEqual(parent.offre_configuration);
    await api(`inscriptions/${enrollment.id}/valider/`, 'POST', {});
    await api(`etudiants/${learner.id}/matieres-individuelles/`, 'POST', {
      inscription_admin: enrollment.id, semestre_cible: period.id, ecue: subject.id,
    });
  }
  await page.goto(`/${variant}/${variant === 'secondaire' ? 'evaluations' : 'notes'}`);
  await page.getByRole('button', { name: 'Ajouter', exact: true }).click();
  await page.getByLabel(/^Titre/).fill('Contrôle navigateur');
  const choose = async (label, option) => {
    await page.getByLabel(label).click();
    await page.getByRole('option', { name: option, exact: true }).click();
  };
  if (variant === 'secondaire') {
    await choose(/^Classe/, 'Classe recette');
    await choose(/^Matière/, subject.nom);
    await choose(/^Période/, period.libelle);
  } else {
    await choose(/^ECUE/, subject.nom);
    await choose(/^Semestre/, period.libelle);
  }
  await choose(/^Enseignant/, 'Grade Teacher');
  await page.getByLabel(/^Date/).fill(new Date().toISOString().slice(0, 10));
  const created = page.waitForResponse(response => response.url().endsWith('/notes/evaluations/')
    && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const evaluation = await response.json();
  expect(evaluation.offre_configuration).toEqual(parent.offre_configuration);
  await expect(page.getByText('Enregistrement effectué.')).toBeVisible();
  await page.getByRole('button', { name: 'Saisir les notes', exact: true }).click();
  await page.getByLabel(`Note ${learner.matricule}`, { exact: true }).fill('15.75');
  await captureDialog(page, `${variant}-numeric-grades`, testInfo);
  await page.getByRole('button', { name: 'Enregistrer les notes', exact: true }).click();
  await expect(page.getByText('Notes enregistrées.', { exact: true })).toBeVisible();
  const notes = await api(`notes/evaluations/${evaluation.id}/notes/`);
  expect(notes).toHaveLength(1);
  expect(notes[0].valeur).toBe('15.75');
  expect(notes[0].resultat_offre.status).toBe('passed');
  await verifyAcademicOperations(page, variant, api, {
    year, period, parent, subject, learner, dates,
  }, testInfo);
  if (variant === 'secondaire') {
    await verifySchoolServices(page, api, learner, year, period, credentials);
  }
  await api(`${parentEndpoint}/${parent.id}/`, 'PATCH', { offre_code: 'vocational-1' });
  const typed = await api('notes/evaluations/', 'POST', {
    titre: 'Pratique par compétences',
    date: evaluation.date,
    enseignant: evaluation.enseignant,
    ...(variant === 'secondaire'
      ? {
        classe: parent.id, matiere: subject.id, periode: period.id, type: 'tp',
      }
      : { ecue: subject.id, semestre: period.id, modalite: 'tp' }),
  });
  expect(typed.offre_configuration.profile).toBe('vocational');
  await page.goto(`/${variant}/${variant === 'secondaire' ? 'evaluations' : 'notes'}`);
  const typedRow = page.getByRole('row').filter({ hasText: 'Pratique par compétences' });
  await typedRow.getByRole('button', { name: 'Saisir les notes', exact: true }).click();
  await choose(`Compétence à personnaliser ${learner.matricule}`, 'Acquis / validé');
  await captureDialog(page, `${variant}-competency-grades`, testInfo);
  await page.getByRole('button', { name: 'Enregistrer les notes', exact: true }).click();
  await expect(page.getByText('Notes enregistrées.', { exact: true })).toBeVisible();
  const typedNotes = await api(`notes/evaluations/${typed.id}/notes/`);
  expect(typedNotes[0].valeur).toBeNull();
  expect(typedNotes[0].resultat_offre.status).toBe('passed');
  expect((await api(`notes/evaluations/${evaluation.id}/`)).offre_configuration).toEqual(parent.offre_configuration);
  expect((await api(`notes/evaluations/${evaluation.id}/notes/`))[0].valeur).toBe('15.75');
  await typedRow.getByRole('button', { name: 'Saisir les notes', exact: true }).click();
  await expect(page.getByLabel(`Compétence à personnaliser ${learner.matricule}`, { exact: true }))
    .toHaveText('Acquis / validé');
  await page.getByRole('button', { name: 'Annuler', exact: true }).click();
  await page.goto(`/${variant}/${variant === 'secondaire' ? 'eleves' : 'etudiants'}/${learner.id}`);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(learner.full_name);
  if (variant === 'secondaire') {
    await expect(page.getByText('Inscrit', { exact: true })).toHaveCSS('color', 'rgb(36, 102, 61)');
    await expect(page.getByText('Inscrit', { exact: true })).toHaveCSS('background-color', 'rgb(238, 247, 241)');
  }
  await capturePresentation(page, `${variant}-learner-record`, testInfo);
  await page.goto(`/${variant}/workflows`);
  await expect(page.getByRole('heading', { name: 'Filtres', exact: true })).toBeVisible();
  await capturePresentation(page, `${variant}-workflow`, testInfo);
  await verifyLearnerWorkspace(page, variant, api, credentials, testInfo, { year, period, parent });
}

async function verifyInstitutionalProfiles(page, variant, testInfo) {
  const initial = page.waitForResponse(response => response.url().endsWith('/etablissement/current/')
    && response.request().method() === 'GET');
  await page.goto(`/admin/etablissement?sis=${variant}`);
  const original = (await (await initial).json()).configuration_academique;
  await capturePresentation(page, `${variant}-institution-form`, testInfo);
  await page.getByRole('tab', { name: 'Organisation académique' }).click();
  const dimensions = page.locator('.pgn__card').filter({
    has: page.getByRole('heading', { name: 'Dimensions dynamiques', exact: true }),
  });
  await dimensions.getByRole('button', { name: 'Ajouter', exact: true }).click();
  await expect(dimensions.getByLabel('Code', { exact: true }).last()).toBeVisible();
  await capturePresentation(page, `${variant}-academic-sections`, testInfo);
  await dimensions.getByRole('button', { name: 'Supprimer', exact: true }).last().click();
  await expect(page.getByRole('tab', { name: 'Profils et offres' })).toBeVisible();
  await page.getByRole('tab', { name: 'Profils et offres' }).click();
  const labels = ['École primaire', 'Collège / lycée', 'Université / grande école', 'Formation professionnelle'];
  /* eslint-disable no-await-in-loop -- Les offres sont ajoutées successivement dans le même formulaire. */
  for (const label of labels) {
    await page.getByLabel('Profil à ajouter', { exact: true }).click();
    await page.getByRole('option', { name: label, exact: true }).click();
    await page.getByRole('button', { name: 'Ajouter une offre', exact: true }).click();
    await expect(page.getByRole('region', { name: label, exact: true })).toBeVisible();
  }
  /* eslint-enable no-await-in-loop */
  const primary = page.getByRole('region', { name: 'École primaire', exact: true });
  const secondary = page.getByRole('region', { name: 'Collège / lycée', exact: true });
  const university = page.getByRole('region', { name: 'Université / grande école', exact: true });
  const vocational = page.getByRole('region', { name: 'Formation professionnelle', exact: true });
  const removeCriterion = primary.getByRole('button', { name: 'Retirer Compétence à personnaliser', exact: true });
  expect(await removeCriterion.evaluate(button => {
    const text = [...button.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
    const range = document.createRange();
    range.selectNodeContents(text);
    return range.getClientRects().length;
  })).toBe(1);
  await expect(primary.getByLabel('Utiliser des crédits')).not.toBeChecked();
  await expect(university.getByLabel('Utiliser des crédits')).toBeChecked();
  await expect(vocational.getByLabel('Calendrier')).toHaveText('Sessions courtes');
  await secondary.getByLabel('Note à simuler').fill('0');
  const preview = page.waitForResponse(response => response.url().endsWith('/offering-preview/')
    && response.request().method() === 'POST');
  await secondary.getByRole('button', { name: 'Simuler', exact: true }).click();
  const simulated = await preview;
  expect(simulated.status()).toBe(200);
  expect((await simulated.json()).status).toBe('failed');
  await expect(secondary.getByText(/Critères non satisfaits/)).toBeVisible();
  const saved = page.waitForResponse(response => response.url().endsWith('/etablissement/current/')
    && response.request().method() === 'PATCH');
  await page.getByRole('button', { name: 'Enregistrer la configuration', exact: true }).click();
  const response = await saved;
  expect(response.status()).toBe(200);
  const configuration = (await response.json()).configuration_academique;
  expect(configuration.learning_offerings).toHaveLength(4);
  expect(configuration.grading_scale).toEqual(original.grading_scale);
  await expect(page.getByText('La configuration a été enregistrée.')).toBeVisible();
  await capturePresentation(page, `${variant}-offering-sections`, testInfo);
  await primary.screenshot({ path: testInfo.outputPath(`${variant}-offering-form-desktop.png`), animations: 'disabled' });
  await page.setViewportSize({ width: 390, height: 2600 });
  await primary.screenshot({ path: testInfo.outputPath(`${variant}-offering-form-mobile.png`), animations: 'disabled' });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.reload();
  await page.getByRole('tab', { name: 'Profils et offres' }).click();
  await expect(page.getByRole('region', { name: 'École primaire', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Formation professionnelle', exact: true })).toBeVisible();
}

for (const variant of variants) {
  test(`${variant}: real login, academic year, import, export, pagination and MFA`, async ({ page }, testInfo) => {
    test.setTimeout(720000);
    await respectApiRateLimit(page);
    const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
    await page.goto(`/admin/annees-academiques?sis=${variant}`);
    await expect(page.getByRole('heading', { name: 'Connexion SIS', exact: true })).toBeVisible();
    await capturePresentation(page, `${variant}-login`, testInfo);
    await page.getByLabel('Identifiant').fill(credentials.username);
    await page.getByLabel('Mot de passe').fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.getByRole('heading', {
      name: variant === 'secondaire' ? 'Années scolaires et périodes' : 'Années universitaires et semestres', level: 1, exact: true,
    })).toBeVisible();
    await page.getByRole('button', { name: 'Ajouter', exact: true }).first().click();
    const year = new Date().getUTCFullYear();
    const dates = { date_debut: `${year}-01-01`, date_fin: `${year}-12-31` };
    await page.getByLabel('Année (ex. 2026-2027)').fill(`${year}-${year + 1}`);
    await page.getByLabel('Date de début').fill(dates.date_debut);
    await page.getByLabel('Date de fin').fill(dates.date_fin);
    await captureDialog(page, `${variant}-year-form`, testInfo);
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
    await expect(page.getByText('Enregistrement effectué.')).toBeVisible();
    await page.getByRole('button', { name: 'Activer', exact: true }).click();
    await expect(page.getByText('Activer : opération effectuée.')).toBeVisible();

    await verifyWorkspace(page, variant, testInfo);
    await page.goto(`/admin/integration-lms?sis=${variant}`);
    await expect(page.getByRole('heading', { name: 'Intégration LMS', exact: true })).toBeVisible();
    await expect(page.getByRole('progressbar')).toHaveCount(1);
    await expect(page.getByText('Déconnecté', { exact: true })).toBeVisible();
    await expect(page.locator('.MuiChip-colorError').first()).toHaveCSS('background-color', 'rgb(180, 35, 24)');
    await expect(page.locator('.MuiChip-colorWarning').first()).toHaveCSS('background-color', 'rgb(148, 96, 0)');
    await capturePresentation(page, `${variant}-integration-cards`, testInfo);
    await verifyInstitutionalProfiles(page, variant, testInfo);

    const resource = variant === 'secondaire' ? 'eleves' : 'etudiants';
    await page.goto(`/${variant}/${resource}`);
    const columns = [
      'username', 'email', 'first_name', 'last_name', 'date_naissance', 'lieu_naissance',
      'sexe', 'adresse', 'code_postal', 'ville', ...(variant === 'superieur' ? ['matricule', 'telephone'] : []),
    ];
    const rows = Array.from({ length: 61 }, (_, index) => {
      const suffix = String(index).padStart(3, '0');
      return [
        `learner-${suffix}`, `learner-${suffix}@example.test`, `Name${suffix}`, 'Test', '2005-01-01',
        'Paris', 'F', '1 Test', '75000', 'Paris', ...(variant === 'superieur' ? [`IMPORT-${suffix}`, '+33100000000'] : []),
      ].join(',');
    });
    await page.getByLabel('Fichier des apprenants').setInputFiles({
      name: 'learners.csv', mimeType: 'text/csv', buffer: Buffer.from([columns.join(','), ...rows].join('\n')),
    });
    await page.getByRole('button', { name: 'Prévisualiser', exact: true }).click();
    await expect(page.getByText(/61 lignes : 61 à créer/)).toBeVisible();
    await page.getByRole('button', { name: 'Confirmer l’import', exact: true }).click();
    await expect(page.getByText(/61 dossiers créés/)).toBeVisible({ timeout: 60000 });
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Exporter tous les résultats' }).click();
    const download = await downloadPromise;
    expect(fs.readFileSync(await download.path(), 'utf8')).toContain('Name060');
    await page.getByRole('button', { name: 'Go to next page' }).click();
    await expect(page.getByText('Name025 Test', { exact: true })).toBeVisible();
    await page.getByPlaceholder('Rechercher...').fill('Name060');
    await expect(page.getByText('Name060 Test', { exact: true })).toBeVisible();
    await expect(page.getByText('Name025 Test', { exact: true })).toHaveCount(0);
    await capturePresentation(page, `${variant}-management-table`, testInfo);
    await page.setViewportSize({ width: 390, height: 844 });
    const emailCell = page.getByRole('cell', { name: 'learner-060@example.test', exact: true });
    expect((await emailCell.boundingBox()).height).toBeLessThan(100);
    await page.setViewportSize({ width: 1440, height: 960 });

    await verifyGradeEntry(page, variant, credentials, dates, testInfo);

    await page.goto(`/${variant}/compte`);
    await page.getByRole('button', { name: 'Configurer le MFA' }).click();
    const secret = await page.locator('code').innerText();
    await page.getByLabel('Code MFA', { exact: true }).fill(totp(secret));
    await page.getByRole('button', { name: 'Activer le MFA', exact: true }).click();
    await expect(page.getByText('MFA local : activé', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Connexion SIS' })).toBeVisible();
    await page.getByLabel('Identifiant').fill(credentials.username);
    await page.getByLabel('Mot de passe').fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.getByText(/Code MFA requis ou invalide/)).toBeVisible();
    await page.getByLabel('Code MFA (si activé)').fill(totp(secret));
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.getByText('MFA local : activé', { exact: true })).toBeVisible();
  });
}
