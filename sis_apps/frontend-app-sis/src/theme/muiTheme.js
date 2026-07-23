import { createTheme } from '@mui/material/styles';

// Modern SIS Theme with Material Design 3 principles
const sisTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976D2',
      light: '#42A5F5',
      dark: '#1565C0',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#7C4DFF',
      light: '#B47CFF',
      dark: '#3F1DCB',
      contrastText: '#ffffff',
    },
    success: {
      main: '#2E7D32',
      light: '#4CAF50',
      dark: '#1B5E20',
    },
    warning: {
      main: '#ED6C02',
      light: '#FF9800',
      dark: '#E65100',
    },
    error: {
      main: '#D32F2F',
      light: '#EF5350',
      dark: '#C62828',
    },
    info: {
      main: '#0288D1',
      light: '#03A9F4',
      dark: '#01579B',
    },
    background: {
      default: '#F5F7FA',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#1A1A2E',
      secondary: '#64748B',
    },
    divider: 'rgba(0, 0, 0, 0.08)',
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 700,
      lineHeight: 1.2,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
      lineHeight: 1.3,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '1.5rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h4: {
      fontSize: '1.25rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h5: {
      fontSize: '1.125rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.6,
    },
    button: {
      textTransform: 'none',
      fontWeight: 600,
    },
    overline: {
      fontSize: '0.75rem',
      fontWeight: 600,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
    },
  },
  shape: {
    borderRadius: 6,
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
        body: {
          scrollbarColor: '#CBD5E1 #F1F5F9',
          '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
            width: 8,
            height: 8,
          },
          '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
            borderRadius: 8,
            backgroundColor: '#CBD5E1',
          },
          '&::-webkit-scrollbar-track, & *::-webkit-scrollbar-track': {
            backgroundColor: '#F1F5F9',
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          padding: '8px 16px',
          fontSize: '0.875rem',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.12)',
          },
        },
        containedPrimary: {
          background: 'linear-gradient(135deg, #1976D2 0%, #1565C0 100%)',
        },
        containedSecondary: {
          background: 'linear-gradient(135deg, #7C4DFF 0%, #651FFF 100%)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.08)',
          border: '1px solid rgba(0, 0, 0, 0.08)',
          transition: 'box-shadow 0.2s ease-in-out',
          '&:hover': {
            boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.1)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
        rounded: {
          borderRadius: 8,
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          border: 'none',
          boxShadow: '4px 0px 24px rgba(0, 0, 0, 0.08)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.08)',
          backdropFilter: 'blur(8px)',
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(0, 0, 0, 0.06)',
          padding: '16px',
        },
        head: {
          fontWeight: 600,
          backgroundColor: '#F8FAFC',
          color: '#475569',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(25, 118, 210, 0.04)',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
        filled: {
          background: 'linear-gradient(135deg, rgba(25, 118, 210, 0.1) 0%, rgba(25, 118, 210, 0.05) 100%)',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 10,
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: '#1976D2',
            },
          },
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          margin: '4px 8px',
          '&.Mui-selected': {
            backgroundColor: 'rgba(25, 118, 210, 0.12)',
            '&:hover': {
              backgroundColor: 'rgba(25, 118, 210, 0.18)',
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

export default sisTheme;
