import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { CssBaseline, GlobalStyles } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import { createSISTheme } from './muiTheme';
import { cssTokens, designTokens } from './tokens';

const AppearanceProvider = ({ mode, brand, children }) => {
  const colors = useMemo(() => designTokens(mode, brand), [mode, brand]);
  const theme = useMemo(() => createSISTheme(mode, colors), [mode, colors]);
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <GlobalStyles styles={{ ':root': { ...cssTokens(colors), colorScheme: mode } }} />
      {children}
    </ThemeProvider>
  );
};
AppearanceProvider.propTypes = {
  mode: PropTypes.oneOf(['light', 'dark']),
  brand: PropTypes.string,
  children: PropTypes.node.isRequired,
};
AppearanceProvider.defaultProps = { mode: 'light', brand: undefined };
export default AppearanceProvider;
