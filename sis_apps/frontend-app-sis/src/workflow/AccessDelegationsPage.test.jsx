import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { getConfig } from '@edx/frontend-platform';
import { fetchApi } from '../services/api';
import { fetchAllResourcePages } from '../services/resources';
import { useCapabilities } from '../components/auth/PermissionGuard';
import AccessDelegationsPage from './AccessDelegationsPage';

jest.mock('@edx/frontend-platform', () => ({ getConfig: jest.fn() }));
jest.mock('../services/api', () => ({ ...jest.requireActual('../services/api'), fetchApi: jest.fn() }));
jest.mock('../services/resources', () => ({
  ...jest.requireActual('../services/resources'), fetchAllResourcePages: jest.fn(),
}));
jest.mock('../components/auth/PermissionGuard', () => ({ useCapabilities: jest.fn() }));
jest.mock('../components/common', () => ({
  ...jest.requireActual('../components/common'), WorkflowHistoryPanel: () => null,
}));

const renderPage = () => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>
      <AccessDelegationsPage variant="secondaire" />
    </MemoryRouter>
  </QueryClientProvider>,
);
let grant;
beforeEach(() => {
  jest.clearAllMocks();
  grant = {
    id: 8, motif: 'Mission d’observation', statut: 'active', beneficiaire_nom: 'Apprenant',
  };
  getConfig.mockReturnValue({ SIS_SECONDAIRE_API_URL: 'https://school.example/api/v1' });
  useCapabilities.mockReturnValue({ data: { role: 'eleve', permissions: [] } });
  fetchApi.mockImplementation(async url => {
    if (url.endsWith('catalogue/')) { return [{ code: 'classes', label: 'Classes' }]; }
    if (url.endsWith('/8/')) { return grant; }
    return { count: 1, results: [grant], next: null };
  });
  fetchAllResourcePages.mockResolvedValue([{ id: 9, label: 'Groupe autorisé' }]);
});

it('lets a learner consult the assigned records without management or editing controls', async () => {
  renderPage();
  fireEvent.click(await screen.findByText('Mission d’observation'));
  expect(await screen.findByText('Groupe autorisé')).toBeVisible();
  expect(fetchAllResourcePages).toHaveBeenCalledWith('https://school.example/api/v1/core/delegations/8/dossiers/');
  expect(screen.queryByRole('button', { name: 'Ajouter' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Révoquer' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Modifier' })).not.toBeInTheDocument();
});

it('does not request records for an expired assignment and exposes an access refusal', async () => {
  grant.statut = 'expiree';
  renderPage();
  fireEvent.click(await screen.findByText('Mission d’observation'));
  expect(await screen.findByText(/Cette mission n’est pas active/)).toBeVisible();
  expect(fetchAllResourcePages).not.toHaveBeenCalled();
});
