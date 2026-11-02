import 'core-js/stable';
import 'regenerator-runtime/runtime';

import {
  APP_INIT_ERROR, APP_READY, auth, initialize, subscribe,
} from '@edx/frontend-platform';
import { AppProvider } from '@edx/frontend-platform/react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

import App from './App';
import sisTheme from './theme/muiTheme';
import { isMockMode } from './services/mockApi';
import { isRecoveryPage, usesLocalSession } from './services/localSession';

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

let root;
const renderApplication = (content) => {
  if (!root) { root = createRoot(document.getElementById('root')); }
  root.render(content);
};

subscribe(APP_READY, () => {
  renderApplication(
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
  );
});

subscribe(APP_INIT_ERROR, () => {
  renderApplication(
    <div role="alert">
      Impossible de démarrer le SIS. Vérifiez la configuration et la connexion au LMS, puis rechargez la page.
    </div>,
  );
});

initialize({
  messages: {},
  requireAuthenticatedUser: true,
  hydrateAuthenticatedUser: true,
  handlers: {
    auth: (requireUser, hydrateUser) => (
      isMockMode() || usesLocalSession() || isRecoveryPage() ? undefined : auth(requireUser, hydrateUser)
    ),
  },
});
