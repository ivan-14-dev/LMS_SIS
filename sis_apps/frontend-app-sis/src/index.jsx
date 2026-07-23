import 'core-js/stable';
import 'regenerator-runtime/runtime';

import { setConfig } from '@edx/frontend-platform';
import ReactDOM from 'react-dom';
import { IntlProvider } from 'react-intl';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

import App from './App';
import sisTheme from './theme/muiTheme';

import './index.scss';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
});

const standaloneModeConfig = {
  BASE_URL: 'http://localhost:8080',
  LMS_BASE_URL: 'http://localhost:18000',
  LOGIN_URL: 'http://localhost:18000/login',
  LOGOUT_URL: 'http://localhost:18000/logout',
  LOGO_URL: '/logo.svg',
  LOGO_TRADEMARK_URL: '/logo.svg',
  SITE_NAME: 'SIS',
  SIS_API_BASE_URL: 'http://localhost:8000/api/sis',
  SIS_SUPERIEUR_API_URL: 'http://localhost:8000/api/sis-superieur',
  SIS_SECONDAIRE_API_URL: 'http://localhost:8000/api/sis-secondaire',
  SUPPORT_URL: '#',
  MARKETING_SITE_BASE_URL: 'http://localhost:8080',
  ORDER_HISTORY_URL: '#',
  TERMS_OF_SERVICE_URL: '#',
  PRIVACY_POLICY_URL: '#',
};

console.log('SIS MFE running in standalone mode (mock data)');
setConfig(standaloneModeConfig);

ReactDOM.render(
  <ThemeProvider theme={sisTheme}>
    <CssBaseline />
    <IntlProvider locale="fr" messages={{}}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </IntlProvider>
  </ThemeProvider>,
  document.getElementById('root'),
);
