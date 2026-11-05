const { expect } = require('@playwright/test');

async function assertPresentation(page, { allowEmptySurfaces = false } = {}) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const surfaces = await page.locator('.pgn__card, .MuiCard-root, .MuiPaper-outlined, .sis-panel, .sis-module-card').evaluateAll(elements => elements
    .filter(element => element.getBoundingClientRect().width > 0)
    .map(element => {
      const style = window.getComputedStyle(element);
      return {
        radius: style.borderTopLeftRadius,
        border: style.borderTopWidth,
        shadow: style.boxShadow,
        nested: Boolean(element.parentElement.closest('.MuiCard-root, .MuiPaper-outlined, .pgn__card, .sis-panel, .sis-auth-layout')),
      };
    }));
  if (!allowEmptySurfaces) { expect(surfaces.length).toBeGreaterThan(0); }
  expect(surfaces.filter(surface => surface.radius !== (surface.nested ? '0px' : '24px')
    || surface.border !== (surface.nested ? '0px' : '4px') || (surface.nested && surface.shadow !== 'none')))
    .toEqual([]);
}

async function capturePresentation(page, name, testInfo, options = {}) {
  const original = page.viewportSize();
  await page.setViewportSize({ width: 1440, height: 960 });
  if (await page.locator('.sis-topbar').count()) {
    await expect(page.locator('.sis-sidebar__workspace strong')).toContainText('Installation', { timeout: 15000 });
    await expect(page.getByRole('navigation', { name: 'Navigation principale' }).getByRole('link').first())
      .toBeVisible({ timeout: 15000 });
  }
  await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
  await assertPresentation(page, options);
  await page.screenshot({ path: testInfo.outputPath(`${name}-desktop.png`), animations: 'disabled' });
  await page.setViewportSize({ width: 390, height: 844 });
  await assertPresentation(page, options);
  await page.screenshot({ path: testInfo.outputPath(`${name}-mobile.png`), animations: 'disabled' });
  await page.setViewportSize({ width: 320, height: 740 });
  await assertPresentation(page, options);
  await page.setViewportSize(original);
}

async function captureDialog(page, name, testInfo) {
  const original = page.viewportSize();
  await page.setViewportSize({ width: 1440, height: 960 });
  const dialog = page.getByRole('dialog');
  await expect(dialog).toHaveCSS('border-radius', '24px');
  await page.screenshot({ path: testInfo.outputPath(`${name}-desktop.png`), animations: 'disabled' });
  await page.setViewportSize({ width: 390, height: 844 });
  const actions = dialog.locator('.MuiDialogActions-root');
  await expect(actions.getByRole('button').last()).toBeInViewport();
  await expect(dialog.locator('.MuiDialogContent-root')).toHaveCSS('padding-left', '16px');
  const bounds = await dialog.boundingBox();
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(390);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(844);
  await actions.getByRole('button').first().focus();
  await page.keyboard.press('Tab');
  await expect(actions.getByRole('button').last()).toBeFocused();
  await expect(actions.getByRole('button').last()).toHaveCSS('outline-style', 'solid');
  await page.screenshot({ path: testInfo.outputPath(`${name}-mobile.png`), animations: 'disabled' });
  await page.setViewportSize(original);
}

module.exports = { assertPresentation, capturePresentation, captureDialog };
