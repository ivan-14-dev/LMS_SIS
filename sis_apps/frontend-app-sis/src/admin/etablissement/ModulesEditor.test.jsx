import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ModulesEditor from './ModulesEditor';
import { fetchApi, patchApi, postApi } from '../../services/api';

jest.mock('../../services/api', () => ({ fetchApi: jest.fn(), patchApi: jest.fn(), postApi: jest.fn() }));
const endpoint = 'https://sis.example/api/v1/etablissement/current/';
const configuration = {
  revision: 3,
  enabled: { 'core.identity': true, 'sis.complaints': true },
  modules: [
    {
      identifier: 'core.identity', label: 'Identité', required: true, dependencies: [], version: '1.0.0', origin: 'default',
    },
    {
      identifier: 'sis.complaints',
      label: 'Réclamations privées',
      required: false,
      dependencies: ['core.identity'],
      version: '1.0.0',
      origin: 'default',
      ui: ['reclamations'],
      api: ['core/reclamations/'],
      data_retention: 'preserve',
      publisher: 'LMS_SIS',
      variants: ['secondaire', 'superieur'],
      permissions: ['core.traiter_reclamation'],
      contract_version: 1,
    },
  ],
};

const start = async () => {
  fetchApi.mockResolvedValue(configuration);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ModulesEditor endpoint={endpoint} />
    </QueryClientProvider>,
  );
  const optional = await screen.findByLabelText('Réclamations privées');
  expect(screen.getByLabelText('Identité')).toBeDisabled();
  fireEvent.click(optional);
  fireEvent.change(screen.getByLabelText('Motif du changement de modules'), { target: { value: 'Suspension' } });
};

beforeEach(() => {
  jest.clearAllMocks();
  postApi.mockResolvedValue({ saved: false, changes: { 'sis.complaints': { before: true, after: false } } });
});

it('simulates without saving, then applies the reviewed revision with a reason', async () => {
  patchApi.mockResolvedValue({
    ...configuration, revision: 4, enabled: { ...configuration.enabled, 'sis.complaints': false },
  });
  await start();
  expect(screen.getByRole('button', { name: 'Appliquer les modules' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Simuler les modules' }));
  await screen.findByText(/Simulation validée/);
  expect(screen.getByText(/accès bloqués pour tous les comptes/)).toBeVisible();
  expect(screen.getByText(/Dossiers et historique conservés/)).toBeVisible();
  expect(screen.getByText(/Entrées de navigation retirées/)).toBeVisible();
  expect(patchApi).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Appliquer les modules' }));
  await screen.findByText('Configuration des modules enregistrée.');
  expect(patchApi).toHaveBeenCalledWith(`${endpoint}modules/`, {
    revision: 3, enabled: { 'core.identity': true, 'sis.complaints': false }, reason: 'Suspension',
  });
  await waitFor(() => expect(screen.getByLabelText('Réclamations privées')).not.toBeChecked());
});

it('keeps a conflicting change visible and offers a reload instead of reporting success', async () => {
  patchApi.mockRejectedValue({ response: { data: { detail: 'Configuration périmée.' } } });
  await start();
  fireEvent.click(screen.getByRole('button', { name: 'Simuler les modules' }));
  await screen.findByText(/Simulation validée/);
  fireEvent.click(screen.getByRole('button', { name: 'Appliquer les modules' }));
  expect(await screen.findByText(/Configuration périmée\./)).toBeVisible();
  expect(screen.queryByText('Configuration des modules enregistrée.')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Recharger les modules' })).toBeVisible();
});
