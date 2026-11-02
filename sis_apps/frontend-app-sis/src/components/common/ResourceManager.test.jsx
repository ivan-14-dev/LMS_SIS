import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchApi, patchApi, postApi } from '../../services/api';
import ResourceManager from './ResourceManager';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({ SIS_SECONDAIRE_API_URL: 'https://secondary.example/api/v1' }),
}));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  patchApi: jest.fn(),
  postApi: jest.fn(),
}));

const show = (fields = []) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ResourceManager
      variant="secondaire"
      resource="classes/classes"
      title="Classes"
      columns={[{ Header: 'Nom', accessor: 'nom' }]}
      fields={fields}
    />
  </QueryClientProvider>,
);

beforeEach(() => {
  jest.clearAllMocks();
});

it('requests server pages and server search rather than filtering only page one', async () => {
  fetchApi.mockImplementation(async (request) => {
    const params = new URL(request).searchParams;
    return {
      count: 51,
      results: [{ id: 1, nom: params.get('search') || (params.get('page') === '2' ? 'Classe tardive' : 'Classe initiale') }],
    };
  });
  show();
  await screen.findByText('Classe initiale');
  fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }));
  await screen.findByText('Classe tardive');
  fireEvent.change(screen.getByPlaceholderText('Rechercher...'), { target: { value: 'Recherche distante' } });
  await screen.findByText('Recherche distante');
  const finalRequest = new URL(fetchApi.mock.calls.at(-1)[0]);
  expect(finalRequest.searchParams.get('page')).toBe('1');
  expect(finalRequest.searchParams.get('search')).toBe('Recherche distante');
});

it('posts real form values and reports backend validation errors', async () => {
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  postApi.mockRejectedValue({ response: { data: { nom: ['Ce nom existe déjà.'] } } });
  show([{ name: 'nom', label: 'Nom', required: true }]);
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
  fireEvent.change(screen.getByLabelText(/Nom/), { target: { value: '6e A' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/', { nom: '6e A' }));
  expect(await screen.findAllByText(/Ce nom existe déjà/)).not.toHaveLength(0);
});

it('loads details before editing and clears an optional number with null', async () => {
  fetchApi.mockImplementation(async request => (request.endsWith('/1/')
    ? { id: 1, nom: 'Classe', retard_minutes: 5 }
    : { count: 1, results: [{ id: 1, nom: 'Classe' }] }));
  patchApi.mockResolvedValue({ id: 1 });
  show([
    { name: 'nom', label: 'Nom', required: true },
    { name: 'retard_minutes', label: 'Retard', type: 'number' },
  ]);
  fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
  fireEvent.change(await screen.findByLabelText('Retard'), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/1/', { nom: 'Classe', retard_minutes: null }));
});

it.each(['2026-11-02T08:17:31.125Z', '2026-10-25T01:17:31.125Z'])(
  'roundtrips %s without losing precision or DST offset and clears optional dates and times',
  async (instant) => {
    fetchApi.mockImplementation(async request => (request.endsWith('/1/')
      ? {
        id: 1, nom: 'Visite', date: instant, fin: '2026-11-03', sortie: '09:00:00',
      }
      : { count: 1, results: [{ id: 1, nom: 'Visite' }] }));
    patchApi.mockResolvedValue({ id: 1 });
    show([
      {
        name: 'date', label: 'Date et heure', type: 'datetime-local', required: true,
      },
      { name: 'fin', label: 'Fin', type: 'date' },
      { name: 'sortie', label: 'Sortie', type: 'time' },
    ]);
    fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
    const input = await screen.findByLabelText(/Date et heure/);
    expect(Number(input.value.slice(11, 13))).toBe(new Date(instant).getHours());
    fireEvent.change(screen.getByLabelText('Fin'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Sortie'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
    await waitFor(() => expect(patchApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/1/', { date: instant, fin: null, sortie: null }));
  },
);
