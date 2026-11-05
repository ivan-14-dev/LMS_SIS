import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { fetchApi } from '../services/api';
import { useCapabilities } from '../components/auth/PermissionGuard';
import SignaturesPage from './SignaturesPage';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({ SIS_SECONDAIRE_API_URL: 'https://school.example/api/v1' }),
}));
jest.mock('../services/api', () => ({ ...jest.requireActual('../services/api'), fetchApi: jest.fn() }));
jest.mock('../components/auth/PermissionGuard', () => ({ useCapabilities: jest.fn() }));
jest.mock('../components/common', () => ({
  ...jest.requireActual('../components/common'), WorkflowNotificationsPanel: () => null,
}));

const show = () => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><SignaturesPage variant="secondaire" /></MemoryRouter>
  </QueryClientProvider>,
);
beforeEach(() => {
  jest.clearAllMocks();
  useCapabilities.mockReturnValue({ data: { role: 'super_admin', permissions: ['*'] } });
  fetchApi.mockImplementation(async url => (url.endsWith('types/')
    ? [{ value: 'notes.bulletin', label: 'Bulletins' }]
    : {
      count: 1, results: [{ id: 'key-uuid', fonction: 'Direction', statut: 'en_attente' }],
    }));
});

it('never offers self-approval in the personal tab, even for an administrator', async () => {
  show();
  await screen.findByText('Direction');
  expect(screen.queryByRole('button', { name: 'Valider', exact: true })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'Validations indépendantes' }));
  expect(await screen.findByRole('button', { name: 'Valider', exact: true })).toBeVisible();
  expect(fetchApi.mock.calls.some(([url]) => url.includes('vue=validation'))).toBe(true);
});

it('does not expose signing controls to a learner with accidentally assigned permissions', async () => {
  useCapabilities.mockReturnValue({ data: { role: 'eleve', permissions: ['core.approve_signature'] } });
  show();
  expect(await screen.findByText(/La gestion des signatures exige/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Ajouter' })).not.toBeInTheDocument();
});
