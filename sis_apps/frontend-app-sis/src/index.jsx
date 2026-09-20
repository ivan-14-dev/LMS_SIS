import 'core-js/stable';
import 'regenerator-runtime/runtime';

import {
  APP_INIT_ERROR, APP_READY, auth, initialize, subscribe,
} from '@edx/frontend-platform';
import { AppProvider } from '@edx/frontend-platform/react';
import ReactDOM from 'react-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

import App from './App';
import sisTheme from './theme/muiTheme';
import { isMockMode } from './services/mockApi';

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

subscribe(APP_READY, () => {
  ReactDOM.render(
    <AppProvider wrapWithRouter={false}>
      <ThemeProvider theme={sisTheme}>
        <CssBaseline />
        {isMockMode() && (
          <div role="status">
            Mode démonstration : données fictives, les modifications ne sont pas enregistrées.
          </div>
        )}
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </ThemeProvider>
    </AppProvider>,
    document.getElementById('root'),
  );
});

subscribe(APP_INIT_ERROR, () => {
  ReactDOM.render(
    <div role="alert">
      Impossible de démarrer le SIS. Vérifiez la configuration et la connexion au LMS, puis rechargez la page.
    </div>,
    document.getElementById('root'),
  );
});

initialize({
  messages: {},
  requireAuthenticatedUser: true,
  hydrateAuthenticatedUser: true,
  handlers: {
    auth: (requireUser, hydrateUser) => (isMockMode() ? undefined : auth(requireUser, hydrateUser)),
  },
});
