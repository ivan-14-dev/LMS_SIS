import { getContrastRatio } from '@mui/material/styles';
import { contrastText, designTokens, statusColors } from './tokens';
import { createSISTheme } from './muiTheme';

it.each(['light', 'dark'])('preserves readable ERP controls and institutional identity in %s mode', mode => {
  ['#FFFFFF', '#000000', '#FFFF00', '#16A34A', '#2563EB', '#0A3055'].forEach(brand => {
    const colors = designTokens(mode, brand);
    const theme = createSISTheme(mode, colors);
    [colors.surface, colors.background, colors.selected, colors.subtle, colors.panel].forEach(surface => {
      expect(getContrastRatio(colors.primary, surface)).toBeGreaterThanOrEqual(4.5);
      expect(getContrastRatio(colors.institution, surface)).toBeGreaterThanOrEqual(4.5);
      expect(getContrastRatio(colors.ink, surface)).toBeGreaterThanOrEqual(4.5);
      expect(getContrastRatio(colors.muted, surface)).toBeGreaterThanOrEqual(4.5);
    });
    [colors.lavender, colors.pink, colors.yellow].forEach(surface => {
      expect(getContrastRatio(colors.ink, surface)).toBeGreaterThanOrEqual(4.5);
    });
    [colors.lavenderGradient, colors.pinkGradient, colors.yellowGradient].forEach(gradient => {
      gradient.match(/#[\da-f]{6}/gi).forEach(stop => {
        expect(getContrastRatio(colors.ink, stop)).toBeGreaterThanOrEqual(4.5);
      });
    });
    colors.primaryGradient.match(/#[\da-f]{6}/gi).forEach(stop => {
      expect(getContrastRatio(colors.primaryText, stop)).toBeGreaterThanOrEqual(4.5);
    });
    const { primary } = theme.palette;
    expect(getContrastRatio(primary.main, primary.contrastText)).toBeGreaterThanOrEqual(4.5);
    expect(getContrastRatio(colors.action, colors.actionText)).toBeGreaterThanOrEqual(4.5);
    expect(getContrastRatio(colors.institution, colors.institutionText)).toBeGreaterThanOrEqual(4.5);
    ['success', 'warning', 'error', 'info'].forEach(key => {
      expect(getContrastRatio(colors[key], colors[`${key}Surface`])).toBeGreaterThanOrEqual(4.5);
      expect(getContrastRatio(colors[key], contrastText(colors[key]))).toBeGreaterThanOrEqual(4.5);
    });
  });
});

it('keeps the common action palette when an institution changes its identity color', () => {
  const standard = designTokens();
  const branded = designTokens('light', '#16A34A');
  expect(branded.primary).toBe(standard.primary);
  expect(branded.action).toBe(standard.action);
  expect(branded.institution).not.toBe(standard.institution);
  expect(branded.brand).toBe('#16A34A');
});

it('does not insert invalid institution colors into generated CSS', () => {
  const colors = designTokens('light', 'url(https://example.test/track)');
  expect(colors.primary).toBe(designTokens().primary);
  expect(colors.invalidBrand).toBe(true);
});

it.each(['light', 'dark'])('keeps every status label readable on its colored badge in %s mode', mode => {
  Object.values(statusColors[mode]).forEach(([text, surface]) => {
    expect(getContrastRatio(text, surface)).toBeGreaterThanOrEqual(4.5);
  });
});
