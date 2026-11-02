const fs = require('fs');
const { createHmac } = require('crypto');
const { test, expect } = require('@playwright/test');

const variants = process.env.SIS_E2E_MODE === 'dual'
  ? ['secondaire', 'superieur'] : [process.env.SIS_E2E_MODE || 'secondaire'];

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

async function createResource(page, title, endpoint, fields) {
  await page.getByRole('region', { name: title, exact: true }).getByRole('button', { name: 'Ajouter', exact: true }).click();
  const dialog = page.getByRole('dialog');
  /* eslint-disable no-await-in-loop -- Un seul menu de sélection peut être ouvert à la fois. */
  for (const [label, value] of Object.entries(fields)) {
    const input = dialog.getByLabel(new RegExp(`^${label}`));
    if (await input.getAttribute('role') === 'combobox') {
      await input.click();
      await page.getByRole('option', { name: value, exact: true }).click();
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

async function verifyGradeEntry(page, variant, credentials, dates) {
  const origin = new URL(process.env.SIS_E2E_URL);
  origin.hostname = `${variant}.validation.localhost`;
  const api = async (path, method = 'GET', data = undefined) => {
    const result = await page.evaluate(async (request) => {
      const headers = { 'Content-Type': 'application/json' };
      if (request.method !== 'GET') {
        const csrf = await fetch(`${request.origin}/csrf/api/v1/token`, { credentials: 'include' });
        if (!csrf.ok) { throw new Error(`CSRF failed: ${csrf.status}`); }
        headers['X-CSRFToken'] = (await csrf.json()).csrfToken;
      }
      const response = await fetch(`${request.origin}/api/v1/${request.path}`, {
        method: request.method,
        credentials: 'include',
        headers,
        body: request.data === undefined ? undefined : JSON.stringify(request.data),
      });
      return { status: response.status, body: await response.text() };
    }, {
      origin: origin.origin, path, method, data,
    });
    expect(result.status, result.body).toBeGreaterThanOrEqual(200);
    expect(result.status, result.body).toBeLessThan(300);
    return JSON.parse(result.body);
  };
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
  if (variant === 'secondaire') {
    const level = await api('etablissement/niveaux/', 'POST', { code: '6e', libelle: 'Sixième' });
    const classe = await api('classes/classes/', 'POST', {
      nom: 'Classe recette', niveau: level.id, annee_scolaire: year.id,
    });
    subject = await api('classes/matieres/', 'POST', { code: 'MAT', nom: 'Mathématiques' });
    period = await api('etablissement/periodes/', 'POST', {
      annee_scolaire: year.id, type: 'trimestre', numero: 1, libelle: 'Trimestre recette', ...dates,
    });
    await api('enseignants/personnel/', 'POST', { ...teacher, date_embauche: dates.date_debut });
    await api(`eleves/${learner.id}/`, 'PATCH', { classe_actuelle: classe.id });
  } else {
    await api('utilisateurs/comptes/', 'POST', { ...teacher, password_confirm: credentials.password });
    period = await api('etablissement/semestres/', 'POST', {
      annee_universitaire: year.id, type: 'impair', numero: 1, ...dates,
    });
    const formation = await api('formations/formations/', 'POST', {
      code: 'LIC', nom: 'Licence recette', type: 'licence',
    });
    const maquette = await api('formations/maquettes/', 'POST', {
      formation: formation.id, annee_universitaire: year.id,
    });
    const ue = await api('ue-ecue/ues/', 'POST', {
      maquette: maquette.id, semestre: period.id, code: 'UE1', nom: 'UE recette', credits_ects: 6,
    });
    subject = await api('ue-ecue/ecues/', 'POST', {
      ue: ue.id, code: 'EC1', nom: 'Mathématiques', credits_ects: 6,
    });
    const enrollment = await api('inscriptions/', 'POST', {
      etudiant: learner.id,
      formation: formation.id,
      annee_universitaire: year.id,
      date_inscription: dates.date_debut,
    });
    await api(`inscriptions/${enrollment.id}/valider/`, 'POST', {});
    await api(`etudiants/${learner.id}/matieres-individuelles/`, 'POST', {
      inscription_admin: enrollment.id, semestre_cible: period.id, ecue: subject.id,
    });
  }
  await page.goto(`/${variant}/${variant === 'secondaire' ? 'evaluations' : 'notes'}`);
  await page.getByRole('button', { name: 'Ajouter', exact: true }).click();
  await page.getByLabel(/^Titre/).fill('Contrôle navigateur');
  const choose = async (label, option) => {
    await page.getByRole('combobox', { name: label }).click();
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
  await expect(page.getByText('Enregistrement effectué.')).toBeVisible();
  await page.getByRole('button', { name: 'Saisir les notes', exact: true }).click();
  await page.getByLabel(`Note ${learner.matricule}`, { exact: true }).fill('15.75');
  await page.getByRole('button', { name: 'Enregistrer les notes', exact: true }).click();
  await expect(page.getByText('Notes enregistrées.', { exact: true })).toBeVisible();
  const notes = await api(`notes/evaluations/${evaluation.id}/notes/`);
  expect(notes).toHaveLength(1);
  expect(notes[0].valeur).toBe('15.75');
  if (variant === 'secondaire') {
    await verifySchoolServices(page, api, learner, year, period, credentials);
  }
}

async function verifyInstitutionalProfiles(page, variant) {
  const initial = page.waitForResponse(response => response.url().endsWith('/etablissement/current/')
    && response.request().method() === 'GET');
  await page.goto(`/admin/etablissement?sis=${variant}`);
  const original = (await (await initial).json()).configuration_academique;
  await expect(page.getByRole('tab', { name: 'Profils et offres' })).toBeVisible();
  await page.getByRole('tab', { name: 'Profils et offres' }).click();
  const labels = ['École primaire', 'Collège / lycée', 'Université / grande école', 'Formation professionnelle'];
  /* eslint-disable no-await-in-loop -- Les offres sont ajoutées successivement dans le même formulaire. */
  for (const label of labels) {
    await page.getByRole('combobox', { name: 'Profil à ajouter', exact: true }).click();
    await page.getByRole('option', { name: label, exact: true }).click();
    await page.getByRole('button', { name: 'Ajouter une offre', exact: true }).click();
    await expect(page.getByRole('region', { name: label, exact: true })).toBeVisible();
  }
  /* eslint-enable no-await-in-loop */
  const primary = page.getByRole('region', { name: 'École primaire', exact: true });
  const secondary = page.getByRole('region', { name: 'Collège / lycée', exact: true });
  const university = page.getByRole('region', { name: 'Université / grande école', exact: true });
  const vocational = page.getByRole('region', { name: 'Formation professionnelle', exact: true });
  await expect(primary.getByLabel('Utiliser des crédits')).not.toBeChecked();
  await expect(university.getByLabel('Utiliser des crédits')).toBeChecked();
  await expect(vocational.getByRole('combobox', { name: 'Calendrier' })).toHaveText('Sessions courtes');
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
  await page.reload();
  await page.getByRole('tab', { name: 'Profils et offres' }).click();
  await expect(page.getByRole('region', { name: 'École primaire', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Formation professionnelle', exact: true })).toBeVisible();
}

for (const variant of variants) {
  test(`${variant}: real login, academic year, import, export, pagination and MFA`, async ({ page }) => {
    if (variant === 'secondaire') {
      test.setTimeout(300000);
      let nextRequest = 0;
      await page.route('**/api/v1/**', async (route) => {
        // Respect the real 100 requests/minute limit during this extended workflow.
        const scheduled = Math.max(Date.now(), nextRequest);
        nextRequest = scheduled + 700;
        await new Promise(resolve => { setTimeout(resolve, Math.max(0, scheduled - Date.now())); });
        await route.continue();
      });
    }
    const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
    await page.goto(`/admin/annees-academiques?sis=${variant}`);
    await page.getByLabel('Identifiant').fill(credentials.username);
    await page.getByLabel('Mot de passe').fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.getByRole('heading', { name: variant === 'secondaire' ? 'Années scolaires' : 'Années universitaires', exact: true }).first()).toBeVisible();
    await page.getByRole('button', { name: 'Ajouter', exact: true }).first().click();
    const year = new Date().getUTCFullYear();
    const dates = { date_debut: `${year}-01-01`, date_fin: `${year}-12-31` };
    await page.getByLabel('Année (ex. 2026-2027)').fill(`${year}-${year + 1}`);
    await page.getByLabel('Date de début').fill(dates.date_debut);
    await page.getByLabel('Date de fin').fill(dates.date_fin);
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
    await expect(page.getByText('Enregistrement effectué.')).toBeVisible();
    await page.getByRole('button', { name: 'Activer', exact: true }).click();
    await expect(page.getByText('Activer : opération effectuée.')).toBeVisible();

    await verifyInstitutionalProfiles(page, variant);

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

    await verifyGradeEntry(page, variant, credentials, dates);

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
