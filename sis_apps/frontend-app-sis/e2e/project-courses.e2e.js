const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { authenticatedApi } = require('./api');
const {
  variants, loadFixture, login, choose, submit,
} = require('./project-helpers');

async function chooseCourse(page, course) {
  await page.getByRole('combobox', { name: 'Cours existant (facultatif)' }).fill(course.nom);
  await page.getByRole('option').filter({ hasText: course.nom }).click();
}

for (const variant of variants) {
  test(`${variant}: project course binding, stale command, explicit removal and private context`, async ({
    page, browser,
  }, testInfo) => {
    const { fixture, credentials, apiOrigin } = loadFixture(variant);
    expect(fixture.courses).toHaveLength(2);
    const [first, second] = fixture.courses;
    for (const course of fixture.courses) {
      expect(Number.isInteger(course.id) && course.id > 0).toBe(true);
      expect(course.nom).toMatch(/^Wave26/);
    }
    expect(first.id).not.toBe(second.id);
    await login(page, variant, credentials.username, credentials.password);
    const api = authenticatedApi(page, variant);
    const modulesPath = 'etablissement/current/modules/';
    const original = await api(modulesPath);
    const setEnabled = async enabled => {
      const current = await api(modulesPath);
      if (current.enabled['sis.projects'] !== enabled) {
        await api(modulesPath, 'PATCH', {
          revision: current.revision, enabled: { 'sis.projects': enabled }, reason: 'Isolated course binding acceptance',
        });
      }
    };
    const context = await browser.newContext({ baseURL: process.env.SIS_E2E_URL });
    try {
      await setEnabled(true);
      const owners = await api(`core/projets/candidats/?type=responsable&q=${encodeURIComponent(credentials.username)}`);
      expect(owners.results).toHaveLength(1);
      const owner = owners.results[0];
      await page.goto(`/${variant}/projets`);
      await page.getByRole('button', { name: 'Nouveau projet', exact: true }).click();
      const title = `Projet rattaché ${variant} ${Date.now()}`;
      await page.getByLabel('Titre du projet').fill(title);
      await choose(page, 'Responsable', credentials.username, owner.nom);
      await chooseCourse(page, first);
      const project = await submit(page, 'core/projets/');
      expect(project.cours).toEqual({ ...first, disponible: true });
      await expect(page.getByText(/^Cours rattaché :/)).toContainText(first.nom);
      const projectPath = `core/projets/${project.id}/`;
      const commandPath = `${projectPath}configurer/`;
      const commands = [];
      page.on('request', request => {
        if (request.method() === 'POST' && new URL(request.url()).pathname === `/api/v1/${commandPath}`) {
          commands.push(request.postDataJSON());
        }
      });
      await api(`${projectPath}equipes/`, 'POST', {
        version: project.version, nom: 'Équipe du cours', membres: [fixture.learnerUserIds[0]],
      });
      await page.getByRole('button', { name: 'Actualiser le projet', exact: true }).click();
      const learnerPage = await context.newPage();
      await login(learnerPage, variant, fixture.learnerUsernames[0], credentials.password);
      await learnerPage.goto(`/${variant}/projets?projet=${project.id}`);
      await expect(learnerPage.getByRole('heading', { name: title, exact: true })).toBeVisible({ timeout: 20000 });
      await expect(learnerPage.getByText('Rattachement conservé — cours indisponible dans votre périmètre actuel.')).toBeVisible();
      await expect(learnerPage.getByText(first.nom, { exact: false })).toHaveCount(0);
      const learnerApi = authenticatedApi(learnerPage, variant);
      expect((await learnerApi(projectPath)).cours).toEqual({ disponible: false });

      await page.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
      await page.getByLabel('Description', { exact: true }).fill('Conserver le cours sans le renvoyer.');
      const preserved = await submit(page, commandPath, 200);
      expect(commands).toHaveLength(1);
      expect(commands[0]).not.toHaveProperty('cours');
      expect(preserved.cours.id).toBe(first.id);

      await page.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
      await page.getByRole('button', { name: 'Choisir un cours', exact: true }).click();
      await chooseCourse(page, second);
      await page.getByLabel('Description', { exact: true }).fill('Choix du second cours à conserver après conflit.');
      await api(commandPath, 'POST', { version: preserved.version, titre: `${title} concurrent` });
      const [conflict] = await Promise.all([
        page.waitForResponse(response => (
          response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/v1/${commandPath}`
        )),
        page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true }).click(),
      ]);
      expect(conflict.status(), await conflict.text()).toBe(409);
      expect(commands).toHaveLength(3);
      await expect(page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
      await expect(page.getByLabel('Description', { exact: true })).toHaveValue('Choix du second cours à conserver après conflit.');
      await page.getByRole('button', { name: 'Recharger le projet sans effacer les saisies', exact: true }).click();
      await expect(page.getByRole('dialog').getByRole('button', { name: 'Enregistrer', exact: true })).toBeEnabled();
      expect(commands).toHaveLength(3);
      expect(await page.getByRole('combobox', { name: 'Cours existant (facultatif)' }).inputValue()).toContain(second.nom);
      const replaced = await submit(page, commandPath, 200);
      expect(commands).toHaveLength(4);
      expect(replaced.cours.id).toBe(second.id);
      await expect(page.getByText(/^Cours rattaché :/)).toContainText(second.nom);

      const historyBefore = await api(`${projectPath}historique/`);
      const csrf = await page.request.get(`${apiOrigin}/csrf/api/v1/token`);
      expect(csrf.status()).toBe(200);
      const refused = await page.request.post(`${apiOrigin}/api/v1/${commandPath}`, {
        headers: { 'X-CSRFToken': (await csrf.json()).csrfToken },
        data: { version: replaced.version, cours: 2147483647 },
      });
      expect(refused.status()).toBe(400);
      const unchanged = await api(projectPath);
      expect(unchanged.version).toBe(replaced.version);
      expect(unchanged.cours).toEqual(replaced.cours);
      expect((await api(`${projectPath}historique/`)).count).toBe(historyBefore.count);

      await page.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
      await page.getByRole('button', { name: 'Retirer le rattachement', exact: true }).click();
      await expect(page.getByText('Retrait du rattachement à confirmer.')).toBeVisible();
      const detached = await submit(page, commandPath, 200);
      expect(commands[commands.length - 1].cours).toBeNull();
      expect(detached.cours).toBeNull();
      await expect(page.getByText('Aucun cours rattaché.', { exact: true })).toBeVisible();
      await learnerPage.reload();
      await expect(learnerPage.getByText('Aucun cours rattaché.', { exact: true })).toBeVisible({ timeout: 20000 });
      expect((await api(`${projectPath}equipes/`)).count).toBe(1);
      await page.getByRole('button', { name: 'Configurer le projet', exact: true }).click();
      await page.getByRole('button', { name: 'Choisir un cours', exact: true }).click();
      await chooseCourse(page, first);
      const restored = await submit(page, commandPath, 200);
      expect(restored.cours.id).toBe(first.id);
      expect((await learnerApi(projectPath)).cours).toEqual({ disponible: false });
      fs.writeFileSync(testInfo.outputPath('project-course-receipt.json'), JSON.stringify({
        isolated: true, variant, projectId: project.id, course: restored.cours, version: restored.version,
      }, null, 2));
    } finally {
      try {
        await setEnabled(original.enabled['sis.projects'] === true);
      } finally {
        await context.close();
      }
    }
  });
}
