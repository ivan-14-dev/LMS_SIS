import { createTheme } from '@mui/material/styles';
import { contrastText, designTokens, typography } from './tokens';

export const createSISTheme = (mode = 'light', colors = designTokens(mode)) => createTheme({
  palette: {
    mode,
    primary: {
      main: colors.primary,
      light: colors.selected,
      dark: colors.primary,
      contrastText: colors.primaryText,
    },
    secondary: {
      main: colors.action,
      light: colors.subtle,
      dark: colors.action,
      contrastText: colors.actionText,
    },
    success: {
      main: colors.success,
      light: colors.successSurface,
      dark: colors.success,
      contrastText: contrastText(colors.success),
    },
    warning: {
      main: colors.warning,
      light: colors.warningSurface,
      dark: colors.warning,
      contrastText: contrastText(colors.warning),
    },
    error: {
      main: colors.error,
      light: colors.errorSurface,
      dark: colors.error,
      contrastText: contrastText(colors.error),
    },
    info: {
      main: colors.info,
      light: colors.infoSurface,
      dark: colors.info,
      contrastText: contrastText(colors.info),
    },
    background: {
      default: colors.background,
      paper: colors.surface,
    },
    text: {
      primary: colors.ink,
      secondary: colors.muted,
    },
    divider: colors.line,
  },
  typography: {
    fontFamily: typography.fontFamily,
    fontSize: 13,
    h1: {
      fontSize: '1.5rem',
      fontWeight: 500,
      lineHeight: 1.2,
      letterSpacing: '-0.01em',
    },
    h2: {
      fontSize: '1.125rem',
      fontWeight: 500,
      lineHeight: 1.3,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '1rem',
      fontWeight: 500,
      lineHeight: 1.4,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 500,
      lineHeight: 1.25,
      letterSpacing: '-0.01em',
    },
    h5: {
      fontSize: '1.125rem',
      fontWeight: 500,
      lineHeight: 1.5,
    },
    h6: {
      fontSize: '0.875rem',
      fontWeight: 500,
      lineHeight: 1.5,
    },
    body1: {
      fontSize: '0.875rem',
      lineHeight: 1.55,
    },
    body2: {
      fontSize: '0.8125rem',
      lineHeight: 1.6,
    },
    button: {
      textTransform: 'none',
      fontWeight: 500,
    },
    overline: {
      fontSize: '0.75rem',
      fontWeight: 600,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
    },
  },
  shape: {
    borderRadius: typography.radius,
  },
  shadows: [
    'none',
    '0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1)',
    '0px 2px 4px rgba(0, 0, 0, 0.06), 0px 4px 6px rgba(0, 0, 0, 0.1)',
    '0px 4px 6px rgba(0, 0, 0, 0.05), 0px 10px 15px rgba(0, 0, 0, 0.1)',
    '0px 10px 15px rgba(0, 0, 0, 0.04), 0px 20px 25px rgba(0, 0, 0, 0.1)',
    '0px 20px 25px rgba(0, 0, 0, 0.04), 0px 25px 50px rgba(0, 0, 0, 0.1)',
    ...Array(19).fill('0px 25px 50px rgba(0, 0, 0, 0.15)'),
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        ':focus-visible': { outline: `3px solid ${colors.primary}`, outlineOffset: 3 },
        '@media (prefers-reduced-motion: reduce)': {
          '*, *::before, *::after': { scrollBehavior: 'auto', transition: 'none !important', animation: 'none !important' },
        },
        body: {
          scrollbarColor: `${colors.input} ${colors.subtle}`,
          '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
            width: 8,
            height: 8,
          },
          '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
            borderRadius: 8,
            backgroundColor: colors.input,
          },
          '&::-webkit-scrollbar-track, & *::-webkit-scrollbar-track': {
            backgroundColor: colors.subtle,
          },
        },
      },
    },
    MuiButtonBase: {
      styleOverrides: {
        root: { '&.Mui-focusVisible': { outline: `3px solid ${colors.primary}`, outlineOffset: 3 } },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: typography.controlRadius,
          border: `2px solid ${colors.frame}`,
          boxShadow: colors.panelShadow,
        },
        standard: {
          '&.MuiAlert-colorSuccess': { color: colors.success, backgroundColor: colors.successSurface },
          '&.MuiAlert-colorWarning': { color: colors.warning, backgroundColor: colors.warningSurface },
          '&.MuiAlert-colorError': { color: colors.error, backgroundColor: colors.errorSurface },
          '&.MuiAlert-colorInfo': { color: colors.info, backgroundColor: colors.infoSurface },
        },
      },
    },
    MuiTabs: {
      defaultProps: { variant: 'scrollable', scrollButtons: 'auto', allowScrollButtonsMobile: true },
      styleOverrides: {
        root: { borderBottom: 'none', minHeight: 38, padding: '3px 2px' },
        indicator: { display: 'none' },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontSize: '0.75rem',
          padding: '8px 14px',
          minHeight: 32,
          minWidth: 0,
          borderRadius: 24,
          marginRight: 6,
          '&.Mui-selected': {
            fontWeight: 500,
            color: colors.primaryText,
            backgroundColor: colors.primary,
            backgroundImage: colors.primaryGradient,
            boxShadow: colors.primaryShadow,
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 24,
          padding: '9px 16px',
          fontSize: '0.8125rem',
          minHeight: 40,
          transition: 'box-shadow 150ms ease',
          '&.Mui-disabled': { backgroundImage: 'none', boxShadow: 'none' },
          '@media (max-width: 599px)': { minHeight: 44 },
        },
        containedPrimary: {
          backgroundColor: colors.primary,
          backgroundImage: colors.primaryGradient,
          boxShadow: colors.primaryShadow,
          '&:hover': { backgroundImage: colors.primaryGradient, boxShadow: colors.primaryShadow },
        },
        containedSecondary: {
          backgroundColor: colors.lavender,
          backgroundImage: colors.lavenderGradient,
          color: colors.ink,
          boxShadow: colors.panelShadow,
          '&:hover': { backgroundColor: colors.lavender, boxShadow: colors.floatingShadow },
        },
        sizeSmall: { fontSize: '0.75rem', padding: '6px 12px', minHeight: 32 },
        outlined: {
          borderColor: colors.frame,
          backgroundColor: colors.panel,
          boxShadow: colors.controlShadow,
          '&:hover': { borderColor: colors.selected, backgroundColor: colors.selected },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: typography.radius,
          boxShadow: colors.panelShadow,
          border: `${typography.frameWidth}px solid ${colors.frame}`,
          backgroundColor: colors.panel,
          minWidth: 0,
          overflowWrap: 'anywhere',
        },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
        rounded: {
          borderRadius: typography.radius,
        },
        outlined: {
          border: `${typography.frameWidth}px solid ${colors.frame}`,
          backgroundColor: colors.panel,
          boxShadow: colors.panelShadow,
        },
      },
    },
    MuiCardContent: {
      styleOverrides: {
        root: {
          padding: 16,
          '&:last-child': { paddingBottom: 16 },
          '@media (max-width: 599px)': { padding: 16, '&:last-child': { paddingBottom: 16 } },
        },
      },
    },
    MuiCardHeader: {
      styleOverrides: {
        root: {
          padding: '14px 16px 6px',
          '@media (max-width: 599px)': { padding: 16 },
        },
        content: { minWidth: 0 },
        action: { margin: 0, marginLeft: 8, alignSelf: 'center' },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: typography.radius,
          border: `${typography.frameWidth}px solid ${colors.frame}`,
          boxShadow: colors.floatingShadow,
          '& > form': {
            display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden',
          },
          '@media (max-width: 599px)': { margin: 12, width: 'calc(100% - 24px)', maxHeight: 'calc(100% - 24px)' },
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: { root: { padding: '18px 24px', fontSize: '1.125rem', borderBottom: `1px solid ${colors.line}` } },
    },
    MuiDialogContent: {
      styleOverrides: {
        root: {
          padding: 24,
          minWidth: 0,
          '.MuiDialogTitle-root + &': { paddingTop: 24 },
          '@media (max-width: 599px)': { padding: 16, '.MuiDialogTitle-root + &': { paddingTop: 16 } },
        },
      },
    },
    MuiDialogActions: {
      styleOverrides: {
        root: {
          padding: '16px 24px',
          borderTop: `1px solid ${colors.line}`,
          gap: 8,
          flexWrap: 'wrap',
          '& > :not(:first-of-type)': { marginLeft: 0 },
          '@media (max-width: 599px)': { padding: 16 },
        },
      },
    },
    MuiInputLabel: {
      defaultProps: { shrink: true },
      styleOverrides: {
        root: {
          position: 'static',
          transform: 'none',
          maxWidth: '100%',
          whiteSpace: 'normal',
          fontSize: '0.8125rem',
          fontWeight: 500,
          color: colors.ink,
          marginBottom: 6,
          lineHeight: 1.5,
          '&.MuiInputLabel-shrink': { transform: 'none' },
        },
      },
    },
    MuiFormHelperText: { styleOverrides: { root: { marginLeft: 0, marginRight: 0 } } },
    MuiOutlinedInput: {
      defaultProps: { notched: false },
      styleOverrides: {
        root: {
          borderRadius: typography.controlRadius,
          minHeight: 44,
          backgroundColor: colors.subtle,
          boxShadow: colors.controlShadow,
          '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: colors.selected },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: colors.action, borderWidth: 1 },
          '&.Mui-error .MuiOutlinedInput-notchedOutline': { borderColor: colors.error },
        },
        input: { padding: '11px 14px', fontSize: '0.875rem' },
        notchedOutline: { borderColor: colors.frame, '& legend': { display: 'none' } },
      },
    },
    MuiSelect: {
      styleOverrides: {
        select: { minHeight: 'auto', padding: '11px 36px 11px 14px', fontSize: '0.875rem' },
        icon: { right: 12, fontSize: 18, color: colors.ink },
      },
    },
    MuiMenu: {
      styleOverrides: {
        paper: {
          borderRadius: 20,
          border: `${typography.frameWidth}px solid ${colors.frame}`,
          backgroundColor: colors.panel,
          boxShadow: colors.floatingShadow,
          minWidth: 160,
        },
        list: { padding: 4 },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          minHeight: 36,
          padding: '9px 12px',
          fontSize: '0.8125rem',
          whiteSpace: 'normal',
          '&:hover, &.Mui-focusVisible': { backgroundColor: colors.selected },
          '&.Mui-selected': {
            backgroundColor: colors.selected,
            backgroundImage: colors.lavenderGradient,
            color: colors.ink,
            '&:hover': { backgroundColor: colors.selected },
          },
        },
      },
    },
    MuiAutocomplete: {
      styleOverrides: {
        paper: {
          borderRadius: 20,
          border: `${typography.frameWidth}px solid ${colors.frame}`,
          backgroundColor: colors.panel,
          boxShadow: colors.floatingShadow,
        },
        listbox: {
          padding: 4,
          '& .MuiAutocomplete-option': {
            fontSize: '0.8125rem',
            borderRadius: 12,
            padding: '9px 12px',
            '&[aria-selected="true"], &.Mui-focused': { backgroundColor: colors.selected },
          },
        },
      },
    },
    MuiTablePagination: {
      styleOverrides: {
        toolbar: {
          flexWrap: 'wrap', justifyContent: 'flex-end', gap: 4, padding: '8px 16px',
        },
        spacer: { flex: '1 1 0%' },
        selectLabel: { margin: 0 },
        displayedRows: { margin: 0 },
        actions: { marginLeft: 8 },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          border: 'none',
          boxShadow: colors.floatingShadow,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.08)',
          backdropFilter: 'blur(8px)',
          backgroundColor: colors.surface,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: `1px solid ${colors.line}`,
          padding: '10px 14px',
          fontSize: '0.8125rem',
          overflowWrap: 'normal',
        },
        head: {
          fontWeight: 500,
          backgroundColor: colors.selected,
          color: colors.ink,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:nth-of-type(even) td': { backgroundColor: colors.surface },
          '&:hover': {
            backgroundColor: colors.subtle,
            '& td': { backgroundColor: colors.subtle },
          },
        },
        MuiTableContainer: {
          styleOverrides: {
            root: {
              border: `${typography.frameWidth}px solid ${colors.frame}`,
              borderRadius: typography.radius,
              backgroundColor: colors.panel,
              boxShadow: colors.panelShadow,
            },
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          borderRadius: 16,
          fontSize: '0.6875rem',
          '&.MuiChip-colorDefault': { backgroundColor: colors.selected, color: colors.ink },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: typography.controlRadius,
          },
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: typography.controlRadius,
          margin: '4px 8px',
          '&.Mui-selected': {
            backgroundColor: colors.selected,
            '&:hover': {
              backgroundColor: colors.selected,
            },
          },
        },
      },
    },
    MuiAvatar: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          height: 8,
        },
      },
    },
  },
});

export default createSISTheme();
