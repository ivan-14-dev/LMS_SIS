import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import AnneesAcademiquesPage from './AnneesAcademiquesPage';
import { fetchApi, patchApi, postApi } from '../../services/api';
import { fetchAllResourcePages } from '../../services/resources';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_MODE: 'dual',
    SIS_SECONDAIRE_API_URL: 'https://secondary.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://higher.example/api/v1',
  }),
}));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  patchApi: jest.fn(),
  postApi: jest.fn(),
}));
jest.mock('../../services/resources', () => ({
  ...jest.requireActual('../../services/resources'),
  fetchAllResourcePages: jest.fn(),
}));

const variants = [
  ['secondaire', 'periodes', 'annee_scolaire', 'Périodes', 'secondary'],
  ['superieur', 'semestres', 'annee_universitaire', 'Semestres', 'higher'],
];

const show = (variant, title) => {
  render(
    <MemoryRouter initialEntries={[`/admin/annees-academiques?sis=${variant}`]}>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <AnneesAcademiquesPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole('link', { name: title, exact: true }));
};

const select = async (label, option) => {
  fireEvent.mouseDown(await screen.findByLabelText(label));
  fireEvent.click(await screen.findByRole('option', { name: option, exact: true }));
};

beforeEach(() => {
  jest.clearAllMocks();
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  fetchAllResourcePages.mockImplementation(async url => (url.endsWith('/types/')
    ? [{ code: 'session_courte', label: 'Session courte' }]
    : [{ id: 1, libelle: '2026-2027' }]));
  postApi.mockResolvedValue({ id: 7 });
  patchApi.mockResolvedValue({ id: 7 });
});

it.each(variants)('creates a %s period with the configured type code and label', async (variant, resource, yearField, title, host) => {
  show(variant, title);
  fireEvent.click(await screen.findByRole('button', { name: 'Ajouter' }));
  await select(/^Année/, '2026-2027');
  fireEvent.change(screen.getByLabelText(/^Numéro/), { target: { value: '2' } });
  await select(/^Type/, 'Session courte');
  fireEvent.change(screen.getByLabelText(/^Date de début/), { target: { value: '2026-10-01' } });
  fireEvent.change(screen.getByLabelText(/^Date de fin/), { target: { value: '2026-11-30' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(
    `https://${host}.example/api/v1/etablissement/${resource}/`,
    {
      [yearField]: 1,
      numero: 2,
      type: 'session_courte',
      date_debut: '2026-10-01',
      date_fin: '2026-11-30',
    },
  ));
});

it.each(variants)('preserves a removed type when editing a %s period', async (variant, resource, yearField, title, host) => {
  const record = {
    id: 7,
    [yearField]: 1,
    annee_libelle: '2026-2027',
    numero: 1,
    type: 'ancien',
    type_display: 'Ancienne session',
    date_debut: '2026-10-01',
    date_fin: '2026-11-30',
  };
  fetchApi.mockImplementation(async url => (url.endsWith('/7/')
    ? record : { count: 1, results: [record] }));
  show(variant, title);
  fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
  expect(await screen.findByLabelText(/^Type/)).toHaveTextContent('ancien (configuration conservée)');
  await waitFor(() => expect(screen.getByLabelText(/^Année/)).toHaveTextContent('2026-2027'));
  fireEvent.change(screen.getByLabelText(/^Date de fin/), { target: { value: '2026-11-29' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith(
    `https://${host}.example/api/v1/etablissement/${resource}/7/`,
    {
      [yearField]: 1,
      numero: 1,
      type: 'ancien',
      date_debut: '2026-10-01',
      date_fin: '2026-11-29',
    },
  ));
});

it('reports a failed catalog request and prevents saving with missing choices', async () => {
  fetchAllResourcePages.mockImplementation(async (url) => {
    if (url.endsWith('/types/')) { throw new Error('Catalogue indisponible.'); }
    return [{ id: 1, libelle: '2026-2027' }];
  });
  show('secondaire', 'Périodes');
  fireEvent.click(await screen.findByRole('button', { name: 'Ajouter' }));
  expect(await screen.findByText('Catalogue indisponible.')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled();
  expect(postApi).not.toHaveBeenCalled();
});
