import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import HierarchyEditor from './HierarchyEditor';
import { fetchApi, patchApi, postApi } from '../../services/api';
import { fetchAllResourcePages } from '../../services/resources';

jest.mock('../../services/api', () => ({ fetchApi: jest.fn(), patchApi: jest.fn(), postApi: jest.fn() }));
jest.mock('../../services/resources', () => ({
  ...jest.requireActual('../../services/resources'), fetchAllResourcePages: jest.fn(),
}));
jest.mock('../../components/common/ResourceManager', () => function MockResources() {
  return <div>Unités d’organisation</div>;
});
const endpoint = 'https://sis.example/api/v1/etablissement/current/';
const effective = {
  at: '2026-01-01T00:00:00Z',
  values: { 'learning.offering': null },
  origins: { 'learning.offering': { label: 'Établissement', revision: 0 } },
  locks: {},
  ignored_overrides: [],
  local: { values: {}, locks: [], revision: 0 },
};
const configuration = { revision: 3, effective, history: [] };
const start = async () => {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <HierarchyEditor endpoint={endpoint} variant="admin" />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Règles héritées' }));
  await screen.findByText('Configuration actuellement effective.');
  expect(screen.getByRole('combobox', { name: 'Périmètre des règles' })).toHaveTextContent('Établissement entier');
  fireEvent.change(screen.getByLabelText('Motif de publication'), { target: { value: 'Restaurer l’héritage' } });
};
beforeEach(() => {
  jest.clearAllMocks();
  fetchApi.mockImplementation(url => Promise.resolve(url.includes('/catalogue/') ? { kinds: [], targets: [] } : configuration));
  fetchAllResourcePages.mockResolvedValue([]);
  postApi.mockResolvedValue({ saved: false, effective, impacts: [] });
  patchApi.mockResolvedValue({ revision: 4, effective, impacts: [] });
});

it('requires a simulation and invalidates it whenever the reviewed payload changes', async () => {
  await start();
  expect(screen.getByRole('button', { name: 'Publier les règles' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Simuler les règles' }));
  await screen.findByText('Simulation — aucun changement enregistré.');
  expect(patchApi).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Motif de publication'), { target: { value: 'Motif corrigé' } });
  expect(screen.getByRole('button', { name: 'Publier les règles' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Simuler les règles' }));
  await screen.findByText('Simulation — aucun changement enregistré.');
  fireEvent.click(screen.getByRole('button', { name: 'Publier les règles' }));
  await screen.findByText('Configuration publiée. Les dossiers existants sont conservés.');
  expect(patchApi).toHaveBeenCalledWith(`${endpoint}hierarchy/`, {
    unit: null, base_revision: 3, values: {}, locks: [], reason: 'Motif corrigé', effective_from: null,
  });
});

it('keeps failed publications visible and reloads after a revision conflict', async () => {
  patchApi.mockRejectedValue({ response: { data: { detail: 'Configuration périmée.' } } });
  await start();
  fireEvent.click(screen.getByRole('button', { name: 'Simuler les règles' }));
  await screen.findByText('Simulation — aucun changement enregistré.');
  fireEvent.click(screen.getByRole('button', { name: 'Publier les règles' }));
  expect(await screen.findByText(/Configuration périmée/)).toBeVisible();
  expect(screen.queryByText('Configuration publiée. Les dossiers existants sont conservés.')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Recharger les règles' }));
  await waitFor(() => expect(fetchApi.mock.calls.filter(([url]) => url.includes('/hierarchy/'))).toHaveLength(2));
  expect(screen.getByRole('button', { name: 'Publier les règles' })).toBeDisabled();
});

it('consults dated rules without publishing and shows overrides blocked by ancestors', async () => {
  await start();
  fireEvent.change(screen.getByLabelText('Date à consulter (heure de cet appareil)'), {
    target: { value: '2025-12-31T10:00' },
  });
  fetchApi.mockResolvedValue({
    ...configuration,
    effective: { ...effective, ignored_overrides: [{ unit: 2, key: 'learning.offering' }] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Consulter les règles à cette date' }));
  await screen.findByText('Configuration à la date consultée.');
  expect(await screen.findByText(/Des valeurs locales sont neutralisées/)).toBeVisible();
  expect(fetchApi.mock.lastCall[0]).toContain('?at=');
  expect(postApi).not.toHaveBeenCalled();
  expect(patchApi).not.toHaveBeenCalled();
});
