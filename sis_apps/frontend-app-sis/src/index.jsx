import 'core-js/stable';
import 'regenerator-runtime/runtime';

import {
  APP_INIT_ERROR, APP_READY, auth, initialize, subscribe,
} from '@edx/frontend-platform';
import { AppProvider } from '@edx/frontend-platform/react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import App from './App';
import AppearanceProvider from './theme/AppearanceProvider';
import { isMockMode } from './services/mockApi';
import { isRecoveryPage, usesLocalSession } from './services/localSession';

import './index.scss';
import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import '@fontsource/inter/latin-600.css';
import '@fontsource/inter/latin-700.css';

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
      <AppearanceProvider>
        {isMockMode() && (
          <div role="status">
            Mode démonstration : données fictives, les modifications ne sont pas enregistrées.
          </div>
        )}
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AppearanceProvider>
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
