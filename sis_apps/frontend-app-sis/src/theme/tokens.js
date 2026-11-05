import { getContrastRatio } from '@mui/material/styles';

export const typography = {
  fontFamily: 'Inter, "Helvetica Neue", Arial, sans-serif',
  radius: 24,
  controlRadius: 16,
  frameWidth: 4,
};

export const statusColors = {
  light: {
    neutral: ['#475569', '#F1F5F9'],
    pending: ['#854D0E', '#FEF3C7'],
    submitted: ['#1D4ED8', '#DBEAFE'],
    scheduled: ['#4338CA', '#E0E7FF'],
    processing: ['#7E22CE', '#F3E8FF'],
    approved: ['#166534', '#DCFCE7'],
    completed: ['#115E59', '#CCFBF1'],
    attention: ['#9A3412', '#FFEDD5'],
    rejected: ['#991B1B', '#FEE2E2'],
    revoked: ['#9D174D', '#FCE7F3'],
    cancelled: ['#713F12', '#F5E9DB'],
    archived: ['#374151', '#DDE1E8'],
    adjusted: ['#155E75', '#CFFAFE'],
  },
  dark: {
    neutral: ['#CBD5E1', '#334155'],
    pending: ['#FDE68A', '#493A14'],
    submitted: ['#BFDBFE', '#1E3A5F'],
    scheduled: ['#C7D2FE', '#312E63'],
    processing: ['#E9D5FF', '#4A2563'],
    approved: ['#BBF7D0', '#14532D'],
    completed: ['#99F6E4', '#134E4A'],
    attention: ['#FED7AA', '#632E13'],
    rejected: ['#FECACA', '#621C24'],
    revoked: ['#FBCFE8', '#601C3E'],
    cancelled: ['#E7CDB4', '#473322'],
    archived: ['#CBD5E1', '#28303C'],
    adjusted: ['#A5F3FC', '#164E63'],
  },
};

const palettes = {
  light: {
    primary: '#19181F',
    action: '#7037A0',
    ink: '#17161D',
    muted: '#605B68',
    line: '#E8E5ED',
    input: '#8A8493',
    surface: '#FFFFFF',
    frame: '#FFFFFF',
    panel: '#F9F9FB',
    background: '#F0EDF4',
    subtle: '#F7F6F9',
    selected: '#EBDDFA',
    success: '#24663D',
    warning: '#946000',
    error: '#B42318',
    info: '#0369A1',
    successSurface: '#EEF7F1',
    warningSurface: '#FFF8E5',
    errorSurface: '#FFF0EE',
    infoSurface: '#E8F0FE',
    navigation: '#F7F6F9',
    navigationText: '#514B5B',
    navigationSelected: '#E9D7F8',
    accent: '#BA85DD',
    lavender: '#D1B2F3',
    pink: '#F2A0BB',
    yellow: '#FFE3A3',
    panelShadow: '0 4px 16px rgba(48, 36, 68, .025), inset 0 1px 5px rgba(255, 255, 255, .95)',
    controlShadow: 'inset 1px 2px 4px rgba(48, 36, 68, .035), 0 1px 4px rgba(48, 36, 68, .035)',
    floatingShadow: '0 12px 36px rgba(42, 29, 62, .12), 0 2px 8px rgba(42, 29, 62, .04)',
    primaryGradient: 'linear-gradient(180deg, #39383F 0%, #17161D 55%, #0F0E14 100%)',
    primaryShadow: 'inset 0 1px 4px rgba(255, 255, 255, .45), 0 3px 10px rgba(26, 21, 36, .18)',
    lavenderGradient: 'radial-gradient(ellipse at 8% 90%, #EDDEFB 0%, transparent 65%), linear-gradient(140deg, #E2CAF7 0%, #BD88ED 100%)',
    pinkGradient: 'radial-gradient(ellipse at 0% 90%, #FBE3ED 0%, transparent 65%), linear-gradient(140deg, #F6C4D7 0%, #EF91B1 100%)',
    yellowGradient: 'linear-gradient(135deg, #FFF0C4 0%, #FFDB8F 100%)',
    hero: '#242129',
    heroText: '#FFFFFF',
  },
  dark: {
    primary: '#F2EBFA',
    action: '#DAB4F4',
    ink: '#F1F5F9',
    muted: '#BCC8D8',
    line: '#49414F',
    input: '#8393A9',
    surface: '#28232E',
    frame: '#3C3546',
    panel: '#2D2733',
    background: '#16131D',
    subtle: '#302936',
    selected: '#40304F',
    success: '#86EFAC',
    warning: '#FCD34D',
    error: '#FDA4AF',
    info: '#7DD3FC',
    successSurface: '#163B2A',
    warningSurface: '#403518',
    errorSurface: '#48232D',
    infoSurface: '#19384C',
    navigation: '#302936',
    navigationText: '#BCC8D8',
    navigationSelected: '#40304F',
    accent: '#C392E8',
    lavender: '#503565',
    pink: '#573748',
    yellow: '#51412A',
    panelShadow: '0 4px 16px rgba(0, 0, 0, .12), inset 0 1px 5px rgba(255, 255, 255, .035)',
    controlShadow: 'inset 1px 2px 4px rgba(0, 0, 0, .18), 0 1px 4px rgba(0, 0, 0, .06)',
    floatingShadow: '0 12px 36px rgba(0, 0, 0, .35), 0 2px 8px rgba(0, 0, 0, .15)',
    primaryGradient: 'linear-gradient(180deg, #FCFAFF 0%, #E8E0F2 100%)',
    primaryShadow: 'inset 0 1px 4px rgba(255, 255, 255, .5), 0 3px 10px rgba(0, 0, 0, .2)',
    lavenderGradient: 'radial-gradient(ellipse at 8% 90%, #624579 0%, transparent 65%), linear-gradient(140deg, #503565 0%, #68418A 100%)',
    pinkGradient: 'radial-gradient(ellipse at 0% 90%, #694858 0%, transparent 65%), linear-gradient(140deg, #573748 0%, #78445B 100%)',
    yellowGradient: 'linear-gradient(135deg, #51412A 0%, #624B27 100%)',
    hero: '#302936',
    heroText: '#FFFFFF',
  },
};

export const contrastText = color => (
  getContrastRatio(color, '#FFFFFF') >= getContrastRatio(color, '#111827') ? '#FFFFFF' : '#111827'
);

export const designTokens = (mode = 'light', brand = undefined) => {
  const colors = palettes[mode];
  const validBrand = typeof brand === 'string' && /^#[a-f0-9]{6}$/i.test(brand);
  const requested = validBrand ? brand : '#00262B';
  let institution = requested;
  const rgb = requested.match(/[a-f0-9]{2}/gi).map(value => parseInt(value, 16));
  // Keep the institution's hue, adjusting luminance only where readable text requires it.
  const readable = () => [colors.surface, colors.background, colors.selected, colors.subtle]
    .every(bg => getContrastRatio(institution, bg) >= 4.5);
  for (let step = 1; step <= 20 && !readable(); step += 1) {
    institution = `#${rgb.map(value => Math.round(value + ((mode === 'dark' ? 255 : 0) - value) * (step / 20))
      .toString(16).padStart(2, '0')).join('')}`;
  }
  return {
    ...colors,
    ...Object.fromEntries(Object.entries(statusColors[mode]).flatMap(([tone, [text, surface]]) => [
      [`status-${tone}-text`, text], [`status-${tone}-surface`, surface],
    ])),
    primaryText: contrastText(colors.primary),
    actionText: contrastText(colors.action),
    institution,
    institutionText: contrastText(institution),
    brand: requested,
    brandAdjusted: institution.toLowerCase() !== requested.toLowerCase(),
    invalidBrand: Boolean(brand) && !validBrand,
  };
};

export const cssTokens = colors => ({
  ...Object.fromEntries(Object.entries(colors).filter(([, value]) => typeof value === 'string')
    .map(([key, value]) => [`--sis-${key.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`)}`, value])),
  '--sis-font-family': typography.fontFamily,
  '--sis-radius': `${typography.radius}px`,
  '--sis-control-radius': `${typography.controlRadius}px`,
  '--sis-frame-width': `${typography.frameWidth}px`,
});
