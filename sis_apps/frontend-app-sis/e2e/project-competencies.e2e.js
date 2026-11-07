const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { authenticatedApi } = require('./api');
const {
  variants, loadFixture, login, choose, submit, command,
} = require('./project-helpers');

function competencyFixture(variant) {
  const loaded = loadFixture(variant);
  const { competencyCourses: courses, competencyTeacher: teacher } = loaded.fixture;
  expect(courses).toHaveLength(3);
  expect(new Set(courses.map(course => course.id)).size).toBe(3);
  for (const course of courses) {
    expect(Number.isInteger(course.id) && course.id > 3).toBe(true);
    expect(course.name).toMatch(/^Wave28/);
  }
  expect(teacher.username).toBe('wave28-teacher');
  expect(teacher.is_staff).toBe(false);
  expect(teacher.course_id).toBe(courses[0].id);
  expect(teacher.admin_revoke.path).toBe(`/api/v1/enseignants/affectations/${teacher.assignment_id}/`);
  expect(teacher.admin_restore.path).toBe('/api/v1/enseignants/affectations/');
  expect(teacher.admin_restore.body.enseignant).toBe(teacher.profile_id);
  return { ...loaded, courses, teacher };
}

async function selectCourse(page, course) {
  await page.getByRole('combobox', { name: 'Cours existant (facultatif)' }).fill(course.name);
  await page.getByRole('listbox').getByRole('option').filter({ hasText: course.name }).click();
}

async function selectObjective(page, criterion) {
  await page.getByRole('button', { name: 'Nouvelle sélection des compétences visées', exact: true }).click();
  await page.getByRole('checkbox', { name: `${criterion.label} (${criterion.code})`, exact: true }).check();
}

for (const variant of variants) {
  test(`${variant}: explicit competency objectives, empty source, conflict, preservation and removal`, async ({
    page,
  }, testInfo) => {
    const {
      fixture, credentials, apiOrigin, courses,
    } = competencyFixture(variant);
    const [first, second, numeric] = courses;
    await login(page, variant, credentials.username, credentials.password);
    const api = authenticatedApi(page, variant);
    const owners = await api(`core/projets/candidats/?type=responsable&q=${credentials.username}`);
    expect(owners.results).toHaveLength(1);
    await page.goto(`/${variant}/projets`);
    await page.getByRole('button', { name: 'Nouveau projet', exact: true }).click();
    const title = `Objectifs pédagogiques ${variant} ${Date.now()}`;
    await page.getByLabel('Titre du projet').fill(title);
    await choose(page, 'Responsable', credentials.username, owners.results[0].nom);
    await selectCourse(page, numeric);
    await page.getByRole('button', { name: 'Nouvelle sélection des compétences visées', exact: true }).click();
    await expect(page.getByText('Aucune compétence disponible : offre absente ou sans critères de compétences.'))
      .toBeVisible();
    await selectCourse(page, first);
    await selectObjective(page, first.offering.assessment.criteria[0]);
    const project = await submit(page, 'core/projets/');
    expect(project.competences).toEqual(first.expected_public_snapshot);
    const projectPath = `core/projets/${project.id}/`;
    const configurePath = `${projectPath}configurer/`;
    const { equipe } = await api(`${projectPath}equipes/`, 'POST', {
      version: project.version, nom: 'Équipe objectifs', membres: [fixture.learnerUserIds[0]],
    });
    await page.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
    const commands = [];
    page.on('request', request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === `/api/v1/${configurePath}`) {
        commands.push(request.postDataJSON());
      }
    });
    await page.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
    await page.getByLabel('Description', { exact: true }).fill('Conservation sans renvoyer les codes.');
    const preserved = await submit(page, configurePath, 200);
    expect(commands).toHaveLength(1);
    expect(commands[0]).not.toHaveProperty('competences');
    expect(preserved.competences).toEqual(project.competences);
    await page.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
    await page.getByRole('button', { name: 'Choisir un cours', exact: true }).click();
    await selectCourse(page, second);
    await expect(page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
    const criterion = second.offering.assessment.criteria[1];
    await selectObjective(page, criterion);
    await api(configurePath, 'POST', { version: preserved.version, description: 'Commande concurrente' });
    const [conflict] = await Promise.all([
      page.waitForResponse(response => (
        response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/v1/${configurePath}`
      )),
      page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true }).click(),
    ]);
    expect(conflict.status()).toBe(409);
    expect(commands).toHaveLength(3);
    await expect(page.getByRole('checkbox', { name: `${criterion.label} (${criterion.code})` })).toBeChecked();
    await page.getByRole('button', { name: 'Recharger le projet sans effacer les saisies', exact: true }).click();
    await expect(page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true })).toBeEnabled();
    expect(commands).toHaveLength(3);
    const replaced = await submit(page, configurePath, 200);
    expect(commands).toHaveLength(4);
    expect(replaced.cours.id).toBe(second.id);
    expect(replaced.competences).toEqual({ version: 1, disponible: true, criteria: [criterion] });
    const history = await api(`${projectPath}historique/`);
    expect(JSON.stringify(history)).toContain(first.offering.assessment.criteria[0].label);
    expect(JSON.stringify(history)).not.toContain('_offre');
    expect(JSON.stringify(history)).not.toContain('_contexte');
    await command(page, apiOrigin, `/api/v1/${configurePath}`, 'POST', {
      version: replaced.version, competences: ['unknown'],
    }, 400);
    await command(page, apiOrigin, `/api/v1/${configurePath}`, 'POST', {
      version: replaced.version, cours: null,
    }, 400);
    expect((await api(projectPath)).version).toBe(replaced.version);
    expect((await api(`${projectPath}historique/`)).count).toBe(history.count);
    await page.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
    await page.getByRole('button', { name: 'Retirer le rattachement', exact: true }).click();
    await expect(page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
    await page.getByRole('button', { name: 'Retirer les compétences visées', exact: true }).click();
    const cleared = await submit(page, configurePath, 200);
    expect(cleared.cours).toBeNull();
    expect(cleared.competences).toBeNull();
    expect((await api(`${projectPath}equipes/`)).results.map(team => team.id)).toEqual([equipe.id]);
    await page.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
    await page.getByRole('button', { name: 'Choisir un cours', exact: true }).click();
    await selectCourse(page, first);
    await selectObjective(page, first.offering.assessment.criteria[0]);
    const restored = await submit(page, configurePath, 200);
    expect(restored.competences).toEqual(first.expected_public_snapshot);
    fs.writeFileSync(testInfo.outputPath('project-competency-receipt.json'), JSON.stringify({
      isolated: true,
      variant,
      projectId: restored.id,
      teamId: equipe.id,
      version: restored.version,
      course: restored.cours,
      competencies: restored.competences,
      managerUsername: credentials.username,
    }, null, 2));
  });

  test(`${variant}: teacher and learner competency privacy through assignment withdrawal and restoration`, async ({
    page, browser,
  }, testInfo) => {
    const {
      fixture, credentials, apiOrigin, courses, teacher,
    } = competencyFixture(variant);
    const [course] = courses;
    await login(page, variant, credentials.username, credentials.password);
    const context = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    const learnerContext = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    let revoked = false;
    try {
      const teacherPage = await context.newPage();
      const learnerPage = await learnerContext.newPage();
      await login(teacherPage, variant, teacher.username, credentials.password);
      const api = authenticatedApi(teacherPage, variant);
      const owners = await api(`core/projets/candidats/?type=responsable&q=${teacher.username}`);
      expect(owners.results.map(owner => owner.id)).toEqual([teacher.id]);
      await teacherPage.goto(`/${variant}/projets`);
      await teacherPage.getByRole('button', { name: 'Nouveau projet', exact: true }).click();
      const title = `Objectifs enseignant ${variant} ${Date.now()}`;
      await teacherPage.getByLabel('Titre du projet').fill(title);
      await choose(teacherPage, 'Responsable', teacher.username, owners.results[0].nom);
      await selectCourse(teacherPage, course);
      await selectObjective(teacherPage, course.offering.assessment.criteria[0]);
      const project = await submit(teacherPage, 'core/projets/');
      expect(project.competences).toEqual(course.expected_public_snapshot);
      const projectPath = `core/projets/${project.id}/`;
      const { equipe } = await api(`${projectPath}equipes/`, 'POST', {
        version: project.version, nom: 'Équipe objectifs enseignant', membres: [fixture.learnerUserIds[0]],
      });
      await login(learnerPage, variant, fixture.learnerUsernames[0], credentials.password);
      await learnerPage.goto(`/${variant}/projets?projet=${project.id}`);
      const hidden = 'Compétences visées conservées — indisponibles dans votre périmètre actuel.';
      await expect(learnerPage.getByText(hidden)).toBeVisible({ timeout: 20000 });
      await expect(learnerPage.getByText(course.offering.assessment.criteria[0].label, { exact: false }))
        .toHaveCount(0);
      const learnerApi = authenticatedApi(learnerPage, variant);
      expect((await learnerApi(projectPath)).competences).toEqual({ disponible: false });
      await command(page, apiOrigin, teacher.admin_revoke.path, 'DELETE', undefined, 204);
      revoked = true;
      await teacherPage.reload();
      await expect(teacherPage.getByText(hidden)).toBeVisible({ timeout: 20000 });
      const unavailable = await api(projectPath);
      expect(unavailable.competences).toEqual({ disponible: false });
      expect(JSON.stringify(await api(`${projectPath}historique/`))).not.toContain('Wave28 analyse A');
      await command(teacherPage, apiOrigin, `/api/v1/${projectPath}configurer/`, 'POST', {
        version: unavailable.version, competences: ['analyse'],
      }, 400);
      const { jalon } = await api(`${projectPath}jalons/`, 'POST', {
        version: unavailable.version,
        titre: 'Jalon autonome',
        consignes: '',
        ordre: 1,
        echeance: '2030-01-01T12:00:00Z',
        bareme: '20.00',
      });
      expect(jalon.titre).toBe('Jalon autonome');
      const assignment = await command(page, apiOrigin, teacher.admin_restore.path, 'POST', teacher.admin_restore.body, 201);
      revoked = false;
      expect(assignment.id).not.toBe(teacher.assignment_id);
      await teacherPage.reload();
      await expect(teacherPage.getByText('Compétences visées : Wave28 analyse A (analyse)', { exact: true }))
        .toBeVisible({ timeout: 20000 });
      const restored = await api(projectPath);
      expect(restored.competences).toEqual(project.competences);
      expect((await teacherPage.request.get(`${apiOrigin}/api/v1/integration/mappings/courses/`)).status()).toBe(403);
      fs.writeFileSync(testInfo.outputPath('teacher-competency-receipt.json'), JSON.stringify({
        isolated: true,
        variant,
        projectId: restored.id,
        teamId: equipe.id,
        version: restored.version,
        course: restored.cours,
        competencies: restored.competences,
        managerUsername: teacher.username,
        restoredAssignmentId: assignment.id,
        sameSessionRevocationAndRestoration: true,
      }, null, 2));
    } finally {
      try {
        if (revoked) {
          await command(page, apiOrigin, teacher.admin_restore.path, 'POST', teacher.admin_restore.body, 201);
        }
      } finally {
        await Promise.all([context.close(), learnerContext.close()]);
      }
    }
  });
}
