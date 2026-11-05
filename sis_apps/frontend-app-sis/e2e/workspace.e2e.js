const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { authenticatedApi, respectApiRateLimit } = require('./api');
const { assertPresentation } = require('./presentation');

const variants = process.env.SIS_E2E_MODE === 'dual'
  ? ['secondaire', 'superieur'] : [process.env.SIS_E2E_MODE || 'secondaire'];

async function setTheme(page, label) {
  await page.getByRole('button', { name: 'Préférences d’affichage', exact: true }).click();
  // MUI 7 includes the selected value in the combobox name; its label stays stable.
  await page.getByLabel('Thème', { exact: true }).click();
  const menu = page.locator('.MuiMenu-paper');
  await expect(menu).toHaveCSS('border-radius', '20px');
  await expect(menu).toHaveCSS('border-top-width', '4px');
  await expect(menu.getByRole('option', { selected: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('combobox', { name: /^Thème / })).toBeFocused();
  await expect(menu).not.toBeVisible();
  await page.keyboard.press('Enter');
  await page.getByRole('option', { name: label, exact: true }).click();
  await page.getByRole('button', { name: 'Fermer les préférences', exact: true }).click();
}

async function captureTheme(page, variant, theme, testInfo) {
  await assertPresentation(page);
  const expected = theme === 'dark' ? 'rgb(40, 35, 46)' : 'rgb(255, 255, 255)';
  await expect(page.locator('.sis-topbar')).toHaveCSS('background-color', expected);
  const panels = page.locator('.pgn__card, .MuiPaper-outlined').filter({ visible: true });
  await expect(panels.first()).toHaveCSS('background-color', theme === 'dark' ? 'rgb(45, 39, 51)' : 'rgb(249, 249, 251)');
  const contrast = await page.evaluate(() => {
    const luminance = color => {
      const rgb = color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => value / 255)
        .map(value => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
      return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
    };
    const selectors = ['.sis-topbar', '.sis-sidebar__item[aria-current="page"]', '.nav-tabs .nav-link.active'];
    const contrasts = selectors.map(selector => document.querySelector(selector)).filter(Boolean).map(element => {
      const styles = getComputedStyle(element);
      const foreground = luminance(styles.color);
      let surface = element;
      while (surface.parentElement && ['transparent', 'rgba(0, 0, 0, 0)'].includes(getComputedStyle(surface).backgroundColor)) {
        surface = surface.parentElement;
      }
      const background = luminance(getComputedStyle(surface).backgroundColor);
      return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
    });
    return Math.min(...contrasts);
  });
  expect(contrast).toBeGreaterThanOrEqual(4.5);
  await page.screenshot({ path: testInfo.outputPath(`${variant}-${theme}-${page.viewportSize().width}.png`), fullPage: true });
}

for (const variant of variants) {
  test(`${variant}: workspace fills the viewport on desktop, ultrawide and mobile`, async ({ page }, testInfo) => {
    await respectApiRateLimit(page);
    const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
    await page.goto(`/${variant}`);
    await page.getByLabel('Identifiant').fill(credentials.username);
    await page.getByLabel('Mot de passe').fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.locator('.sis-layout')).toBeVisible();
    for (const width of [2560, 1920, 1440, 1024, 768, 390, 320]) {
      // eslint-disable-next-line no-await-in-loop -- Check each viewport on the same authenticated page.
      await test.step(`${width}px`, async () => {
        await page.setViewportSize({ width, height: 1080 });
        await expect.poll(() => page.evaluate(() => {
          const frame = document.querySelector('.sis-layout').getBoundingClientRect();
          const body = document.querySelector('.sis-layout__body').getBoundingClientRect();
          const content = document.querySelector('.sis-content').getBoundingClientRect();
          return {
            left: frame.left,
            top: frame.top + window.scrollY,
            rightGap: document.documentElement.clientWidth - frame.right,
            fillsHeight: frame.height >= window.innerHeight,
            contentLeftGap: content.left - body.left,
            contentRightGap: body.right - content.right,
            overflow: document.documentElement.scrollWidth > window.innerWidth,
          };
        })).toEqual({
          left: 0,
          top: 0,
          rightGap: 0,
          fillsHeight: true,
          contentLeftGap: 0,
          contentRightGap: 0,
          overflow: false,
        });
        if ([2560, 390].includes(width)) {
          await page.screenshot({ path: testInfo.outputPath(`${variant}-fullscreen-${width}.png`), fullPage: true, animations: 'disabled' });
        }
      });
    }
  });

  test(`${variant}: branded workspace, keyboard navigation, favorites and persisted themes`, async ({ page }, testInfo) => {
    test.setTimeout(180000);
    await respectApiRateLimit(page);
    const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
    await page.goto(`/admin/etablissement?sis=${variant}`);
    await page.getByLabel('Identifiant').fill(credentials.username);
    await page.getByLabel('Mot de passe').fill(credentials.password);
    await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Configuration établissement', exact: true })).toBeVisible();
    const type = page.locator('select[name="type"]');
    const originalType = await type.inputValue();
    await expect(type).toHaveCSS('border-radius', '16px');
    await type.focus();
    await page.keyboard.press('Space');
    if (await page.evaluate(() => CSS.supports('appearance', 'base-select'))) {
      await expect.poll(() => type.evaluate(element => element.matches(':open'))).toBe(true);
      await expect(type).toHaveCSS('background-image', 'none');
      await expect(type).toHaveCSS('display', /^(inline-)?flex$/);
      expect(await type.evaluate(element => {
        const style = getComputedStyle(element, '::picker(select)');
        return { radius: style.borderRadius, border: style.borderTopWidth };
      })).toEqual({ radius: '20px', border: '4px' });
      await page.screenshot({ path: testInfo.outputPath(`${variant}-native-dropdown.png`), animations: 'disabled' });
    }
    await page.keyboard.press('Escape');
    await expect(type).toBeFocused();
    const otherType = await type.evaluate(element => Array.from(element.options)
      .find(option => option.value && option.value !== element.value && !option.disabled).value);
    await type.selectOption(otherType);
    await expect(type).toHaveValue(otherType);
    await type.selectOption(originalType);
    const api = authenticatedApi(page, variant);
    const original = await api('etablissement/current/');
    await page.getByRole('tab', { name: 'Apparence', exact: true }).click();
    await page.locator('[name="couleur_primaire"]').fill('#16a34a');
    const saved = page.waitForResponse(response => response.url().endsWith('/etablissement/current/')
      && response.request().method() === 'PATCH');
    await page.getByRole('button', { name: 'Enregistrer la configuration', exact: true }).click();
    expect((await saved).status()).toBe(200);
    const profile = await api('utilisateurs/comptes/me/');
    expect(profile.branding.primary_color.toLowerCase()).toBe('#16a34a');
    await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement)
      .getPropertyValue('--sis-brand').trim().toLowerCase())).toBe('#16a34a');
    await page.getByRole('tab', { name: 'Modules', exact: true }).click();
    await expect(page.getByText('Modules installés', { exact: true })).toBeVisible();
    await expect(page.locator('.sis-sidebar__workspace small')).toHaveText('Administration établissement');
    const target = variant === 'secondaire' ? 'Classes' : 'Formations';
    await page.keyboard.press('Control+k');
    const palette = page.getByRole('dialog', { name: 'Aller à un module', exact: true });
    await expect(palette.getByLabel('Rechercher dans les modules autorisés')).toBeFocused();
    await page.keyboard.press('ArrowUp');
    await expect(palette.getByRole('link').last()).toBeFocused();
    await palette.getByLabel('Rechercher dans les modules autorisés').fill(target);
    await palette.getByRole('button', { name: `Ajouter ${target} aux favoris`, exact: true }).click();
    await expect(palette.getByRole('button', { name: `Retirer ${target} des favoris`, exact: true })).toHaveAttribute('aria-pressed', 'true');
    await palette.getByLabel('Rechercher dans les modules autorisés').focus();
    await page.keyboard.press('ArrowDown');
    await expect(palette.getByRole('link', { name: target, exact: true })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(palette).not.toBeVisible();
    await expect(page.getByRole('button', { name: 'Ouvrir la palette de navigation' })).toBeFocused();
    await page.goto(`/${variant}`);
    await expect(page.getByRole('navigation', { name: 'Favoris' }).getByRole('link', { name: target, exact: true })).toBeVisible();
    await page.goto(`/admin/etablissement?sis=${variant}`);
    await page.getByRole('tab', { name: 'Modules', exact: true }).click();
    await page.setViewportSize({ width: 1440, height: 960 });
    await expect(page.locator('.sis-layout--management')).toHaveCSS('border-width', '0px');
    await expect(page.locator('.sis-layout__sidebar')).toHaveCSS('background-color', 'rgb(247, 246, 249)');
    await expect(page.locator('.sis-layout__sidebar')).toHaveCSS('width', '216px');
    await expect(page.getByRole('navigation', { name: 'Navigation principale' }).getByRole('link')).toHaveCount(7);
    await expect(page.getByRole('navigation', { name: 'Navigation principale' }).getByRole('link').first())
      .toHaveClass(/MuiListItemButton-root/);
    await expect(page.getByRole('navigation', { name: 'Navigation de section : Administration' })).toBeVisible();
    await captureTheme(page, variant, 'light', testInfo);
    await setTheme(page, 'Sombre');
    await captureTheme(page, variant, 'dark', testInfo);
    await page.reload();
    await page.getByRole('tab', { name: 'Modules', exact: true }).click();
    await expect(page.getByText('Modules installés', { exact: true })).toBeVisible();
    const primaryButtonColor = await page.getByRole('button', { name: 'Enregistrer la configuration', exact: true })
      .evaluate(element => getComputedStyle(element).backgroundColor);
    await expect.poll(() => page.locator('.custom-switch input:checked').first()
      .evaluate(input => getComputedStyle(input.labels[0], '::before').backgroundColor)).toBe(primaryButtonColor);
    await captureTheme(page, variant, 'dark', testInfo);
    await page.getByRole('button', { name: 'Ouvrir la palette de navigation' }).click();
    await expect(palette.getByRole('button', { name: `Retirer ${target} des favoris`, exact: true })).toHaveAttribute('aria-pressed', 'true');
    await page.keyboard.press('Escape');
    await page.getByRole('tab', { name: 'Organisation et règles', exact: true }).click();
    await expect(page.getByText('Configuration actuellement effective.')).toBeVisible();
    await expect(page.locator('.MuiAlert-standard.MuiAlert-colorInfo').first())
      .toHaveCSS('background-color', 'rgb(25, 56, 76)');
    await captureTheme(page, `${variant}-hierarchy`, 'dark', testInfo);
    await page.setViewportSize({ width: 390, height: 844 });
    await captureTheme(page, variant, 'dark', testInfo);
    await page.getByRole('button', { name: 'Ouvrir le menu' }).click();
    const drawer = page.getByRole('dialog', { name: 'Menu de navigation' });
    await expect(drawer.getByRole('link')).toHaveCount(7);
    await drawer.getByRole('link', { name: 'Scolarité', exact: true }).click();
    await expect(drawer).not.toBeVisible();
    await page.getByRole('navigation', { name: 'Navigation de section : Scolarité' }).getByRole('link', { name: target, exact: true }).click();
    await expect(page.getByRole('heading', { name: target, exact: true }).first()).toBeVisible();
    await page.getByRole('region', { name: target, exact: true }).getByRole('button', { name: 'Ajouter', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCSS('background-color', 'rgb(40, 35, 46)');
    await page.getByRole('button', { name: 'Annuler', exact: true }).click();
    await page.setViewportSize({ width: 320, height: 740 });
    await assertPresentation(page);
    await setTheme(page, 'Clair');
    await page.getByRole('button', { name: 'Préférences d’affichage', exact: true }).click();
    await page.getByRole('button', { name: 'Effacer mes favoris sur cet appareil', exact: true }).click();
    await page.getByRole('button', { name: 'Fermer les préférences', exact: true }).click();
    await api('etablissement/current/', 'PATCH', { couleur_primaire: original.couleur_primaire });
    await page.reload();
    await expect(page.locator('.sis-topbar')).toHaveCSS('background-color', 'rgb(255, 255, 255)');
    await expect.poll(() => page.evaluate(() => Array.from(document.fonts)
      .some(font => font.family.replace(/["']/g, '') === 'Inter' && font.status === 'loaded'))).toBe(true);
  });
}
