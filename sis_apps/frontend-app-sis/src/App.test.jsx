import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getConfig } from '@edx/frontend-platform';
import { fetchApi } from './services/api';
import App from './App';

jest.mock('@edx/frontend-platform', () => ({ getConfig: jest.fn() }));
jest.mock('./services/api', () => ({
  ...jest.requireActual('./services/api'),
  fetchApi: jest.fn(),
}));
jest.mock('./components/layout/SISLayout', () => {
  const { Outlet } = jest.requireActual('react-router-dom');
  const MockLayout = () => <Outlet />;
  return MockLayout;
});
jest.mock('./secondaire/portails/PortailApprenantFamille', () => {
  const MockFamilyPortal = () => <h1>Portail famille</h1>;
  return MockFamilyPortal;
});

const renderRoute = (path, capabilities) => {
  window.history.replaceState({}, '', path);
  getConfig.mockReturnValue({
    PUBLIC_PATH: '/',
    SIS_MODE: 'dual',
    SIS_SECONDAIRE_API_URL: 'https://secondaire.example.test/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superieur.example.test/api/v1',
  });
  fetchApi.mockImplementation(async (url) => {
    if (url.endsWith('/capabilities/')) { return capabilities; }
    return { count: 0, results: [] };
  });
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <App />
    </QueryClientProvider>,
  );
};

afterEach(() => {
  jest.clearAllMocks();
  window.history.replaceState({}, '', '/');
});

it.each([
  ['élève', { role: 'eleve', permissions: [], affiliations: [{ kind: 'learner', active: true }] }],
  ['parent', { role: 'parent', permissions: [], affiliations: [{ kind: 'parent', active: true }] }],
])('blocks a direct discipline URL for a %s without the effective permission', async (role, capabilities) => {
  renderRoute('/secondaire/discipline', capabilities);

  expect(await screen.findByText(/permission d’accéder à ce module/)).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Discipline' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Incidents disciplinaires' })).not.toBeInTheDocument();
  expect(fetchApi).toHaveBeenCalledWith('https://secondaire.example.test/api/v1/utilisateurs/comptes/capabilities/');
  expect(fetchApi.mock.calls.every(([url]) => url.endsWith('/capabilities/'))).toBe(true);
});

it('allows authorized staff into the mounted discipline route', async () => {
  renderRoute('/secondaire/discipline', {
    role: 'vie_scolaire',
    permissions: ['discipline.view_incident'],
    affiliations: [{ kind: 'staff', active: true }],
  });

  expect(await screen.findByRole('heading', { name: 'Discipline' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Incidents disciplinaires' })).toBeInTheDocument();
});

it('keeps the secondary parent portal accessible to affiliated parents', async () => {
  renderRoute('/secondaire/portail-apprenant', {
    role: 'parent',
    portals: { parent: true },
    affiliations: [{ kind: 'parent', active: true }],
  });

  expect(await screen.findByRole('heading', { name: 'Portail famille' })).toBeInTheDocument();
});

it.each([
  ['secondaire', 'eleve'], ['secondaire', 'parent'], ['secondaire', 'enseignant'],
  ['superieur', 'etudiant'], ['superieur', 'parent'], ['superieur', 'enseignant'],
])('mounts the targeted %s library for %s without a staff portal grant', async (variant, role) => {
  renderRoute(`/${variant}/bibliotheque`, {
    role,
    is_staff: false,
    permissions: ['bibliotheque.consulter_ressource_numerique'],
    affiliations: [],
    portals: { staff: false },
  });
  expect(await screen.findByRole('heading', { name: 'Bibliothèque', level: 1 })).toBeVisible();
  await waitFor(() => expect(fetchApi).toHaveBeenCalledWith(
    expect.stringContaining(`https://${variant}.example.test/api/v1/bibliotheque/livres/?`),
    expect.objectContaining({ signal: expect.anything() }),
  ));
  expect(fetchApi.mock.calls.every(([url]) => !url.includes('/portail/'))).toBe(true);
});

it.each(['secondaire', 'superieur'])('blocks the direct %s library route without explicit permissions', async variant => {
  renderRoute(`/${variant}/bibliotheque`, { role: 'bibliothecaire', is_staff: true, permissions: [] });
  expect(await screen.findByText(/nécessite une habilitation explicite/)).toBeVisible();
  expect(fetchApi.mock.calls.every(([url]) => url.endsWith('/capabilities/'))).toBe(true);
});
