const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { authenticatedApi } = require('./api');
const {
  variants, loadFixture, login, choose, submit,
} = require('./project-helpers');

async function command(page, origin, path, method, data, status) {
  const csrf = await page.request.get(`${origin}/csrf/api/v1/token`);
  expect(csrf.status()).toBe(200);
  const response = await page.request.fetch(`${origin}${path}`, {
    method, data, headers: { 'X-CSRFToken': (await csrf.json()).csrfToken },
  });
  expect(response.status(), await response.text()).toBe(status);
  return status === 204 ? null : response.json();
}

for (const variant of variants) {
  test(`${variant}: nonstaff assigned teacher binds, loses and regains course access without LMS administration`, async ({
    page, browser,
  }, testInfo) => {
    const { fixture, credentials, apiOrigin } = loadFixture(variant);
    expect(fixture.teachers).toHaveLength(2);
    expect(fixture.courses).toHaveLength(2);
    const [teacher, otherTeacher] = fixture.teachers;
    const [course, otherCourse] = fixture.courses;
    for (const [index, account] of fixture.teachers.entries()) {
      expect(account.username).toBe(`wave27-teacher-${index === 0 ? 'a' : 'b'}`);
      expect(Number.isInteger(account.id) && account.id > 0).toBe(true);
      expect(account.is_staff).toBe(false);
      expect(account.is_superuser).toBe(false);
      expect(account.course_id).toBe(fixture.courses[index].id);
      expect(account.permission_scopes['integration.view_edxcoursemapping'].cours).toEqual(
        fixture.courses.map(item => item.id),
      );
      expect(account.admin_revoke.path).toBe(`/api/v1/enseignants/affectations/${account.assignment_id}/`);
      expect(account.admin_restore.path).toBe('/api/v1/enseignants/affectations/');
      expect(account.admin_restore.body.enseignant).toBe(account.profile_id);
    }
    await login(page, variant, credentials.username, credentials.password);
    const adminApi = authenticatedApi(page, variant);
    const modules = await adminApi('etablissement/current/modules/');
    expect(modules.enabled['sis.projects']).toBe(true);
    const context = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    const otherContext = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    let revoked = false;
    try {
      const teacherPage = await context.newPage();
      const otherPage = await otherContext.newPage();
      await login(teacherPage, variant, teacher.username, credentials.password);
      await login(otherPage, variant, otherTeacher.username, credentials.password);
      const api = authenticatedApi(teacherPage, variant);
      const otherApi = authenticatedApi(otherPage, variant);
      const candidates = `core/projets/cours-candidats/?q=Wave26&responsable=${teacher.id}`;
      expect((await api(candidates)).results.map(item => item.id)).toEqual([course.id]);
      expect((await otherApi(`core/projets/cours-candidats/?q=Wave26&responsable=${otherTeacher.id}`))
        .results.map(item => item.id)).toEqual([otherCourse.id]);
      expect((await adminApi(candidates)).results.map(item => item.id)).toEqual([course.id]);
      expect((await teacherPage.request.get(`${apiOrigin}/api/v1/integration/mappings/courses/`)).status()).toBe(403);
      const owners = await api(`core/projets/candidats/?type=responsable&q=${teacher.username}`);
      expect(owners.results.map(item => item.id)).toEqual([teacher.id]);
      await teacherPage.goto(`/${variant}/projets`);
      await teacherPage.getByRole('button', { name: 'Nouveau projet', exact: true }).click();
      const title = `Projet enseignant ${variant} ${Date.now()}`;
      await teacherPage.getByLabel('Titre du projet').fill(title);
      await choose(teacherPage, 'Responsable', teacher.username, owners.results[0].nom);
      await teacherPage.getByRole('combobox', { name: 'Cours existant (facultatif)' }).fill('Wave26');
      const courseOptions = teacherPage.getByRole('listbox').getByRole('option');
      await expect(courseOptions).toHaveCount(1);
      await expect(courseOptions).toContainText(course.nom);
      await courseOptions.click();
      const project = await submit(teacherPage, 'core/projets/');
      expect(project.cours).toEqual({ ...course, disponible: true });
      const projectPath = `core/projets/${project.id}/`;
      const configurePath = `${projectPath}configurer/`;
      await expect(teacherPage.getByText(/^Cours rattaché :/)).toContainText(course.nom);
      expect((await otherPage.request.get(`${apiOrigin}/api/v1/${projectPath}`)).status()).toBe(404);
      await command(otherPage, apiOrigin, `/api/v1/${configurePath}`, 'POST', {
        version: project.version, titre: 'Modification hors périmètre',
      }, 404);
      const { equipe } = await api(`${projectPath}equipes/`, 'POST', {
        version: project.version, nom: 'Équipe enseignant', membres: [fixture.learnerUserIds[0]],
      });
      const before = await api(projectPath);
      const historyBefore = await api(`${projectPath}historique/`);
      await command(page, apiOrigin, teacher.admin_revoke.path, 'DELETE', undefined, 204);
      revoked = true;
      await teacherPage.reload();
      await expect(teacherPage.getByText('Rattachement conservé — cours indisponible dans votre périmètre actuel.'))
        .toBeVisible({ timeout: 20000 });
      expect((await api(projectPath)).cours).toEqual({ disponible: false });
      expect((await api(`${candidates}&projet=${project.id}`)).results).toEqual([]);
      const hiddenHistory = await api(`${projectPath}historique/`);
      expect(JSON.stringify(hiddenHistory)).not.toContain(course.nom);
      expect(JSON.stringify(hiddenHistory)).not.toContain('_scope_fingerprint');
      await command(teacherPage, apiOrigin, `/api/v1/${configurePath}`, 'POST', {
        version: before.version, description: 'Conservation interdite après retrait',
      }, 400);
      expect((await api(projectPath)).version).toBe(before.version);
      expect((await api(`${projectPath}historique/`)).count).toBe(historyBefore.count);
      await teacherPage.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
      await teacherPage.getByRole('button', { name: 'Retirer le rattachement', exact: true }).click();
      expect((await submit(teacherPage, configurePath, 200)).cours).toBeNull();
      expect((await api(`${projectPath}equipes/`)).results.map(item => item.id)).toEqual([equipe.id]);
      const restoredAssignment = await command(page, apiOrigin, teacher.admin_restore.path, 'POST', teacher.admin_restore.body, 201);
      revoked = false;
      expect(Number.isInteger(restoredAssignment.id) && restoredAssignment.id > 0).toBe(true);
      expect(restoredAssignment.id).not.toBe(teacher.assignment_id);
      await teacherPage.reload();
      await expect(teacherPage.getByText('Aucun cours rattaché.', { exact: true })).toBeVisible({ timeout: 20000 });
      await teacherPage.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
      await teacherPage.getByRole('button', { name: 'Choisir un cours', exact: true }).click();
      await teacherPage.getByRole('combobox', { name: 'Cours existant (facultatif)' }).fill('Wave26');
      await expect(courseOptions).toHaveCount(1);
      await expect(courseOptions).toContainText(course.nom);
      await courseOptions.click();
      const restored = await submit(teacherPage, configurePath, 200);
      expect(restored.cours).toEqual({ ...course, disponible: true });
      expect((await teacherPage.request.get(`${apiOrigin}/api/v1/integration/mappings/courses/`)).status()).toBe(403);
      expect(JSON.stringify(await api(`${projectPath}historique/`))).not.toContain('_scope_fingerprint');
      fs.writeFileSync(testInfo.outputPath('project-teacher-receipt.json'), JSON.stringify({
        isolated: true,
        variant,
        projectId: project.id,
        teamId: equipe.id,
        course: restored.cours,
        version: restored.version,
        teacherId: teacher.id,
        teacherUsername: teacher.username,
        otherTeacherUsername: otherTeacher.username,
        restoredAssignmentId: restoredAssignment.id,
        sameSessionRevocationAndRestoration: true,
        administrativeMappingsDenied: true,
      }, null, 2));
    } finally {
      try {
        if (revoked) {
          await command(page, apiOrigin, teacher.admin_restore.path, 'POST', teacher.admin_restore.body, 201);
        }
      } finally {
        await Promise.all([context.close(), otherContext.close()]);
      }
    }
  });
}
