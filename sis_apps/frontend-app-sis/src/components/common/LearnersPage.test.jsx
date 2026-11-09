import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import LearnersPage from './LearnersPage';
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
jest.mock('./LearnerImport', () => () => null);

const show = variant => render(
  <MemoryRouter>
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LearnersPage variant={variant} />
    </QueryClientProvider>
  </MemoryRouter>,
);

beforeEach(() => {
  jest.clearAllMocks();
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  fetchAllResourcePages.mockResolvedValue([]);
  postApi.mockResolvedValue({});
  patchApi.mockResolvedValue({});
});

it('creates an unassigned pupil and directs the administrator to annual enrollment', async () => {
  show('secondaire');
  expect(screen.getByRole('link', { name: 'Classes et inscriptions annuelles' }))
    .toHaveAttribute('href', '/secondaire/classes');
  fireEvent.click(await screen.findByRole('button', { name: 'Ajouter' }));
  expect(screen.queryByLabelText(/^Classe actuelle/)).not.toBeInTheDocument();
  const fields = [
    [/^Identifiant/, 'recette.eleve'],
    [/^Prénom/, 'Camille'],
    [/^Nom/, 'Recette'],
    [/^Email/, 'camille@example.test'],
    [/^Mot de passe initial/, 'Only-for-unit-tests-976!'],
    [/^Date de naissance/, '2013-01-10'],
    [/^Lieu de naissance/, 'Ville fictive'],
  ];
  fields.forEach(([label, value]) => fireEvent.change(screen.getByLabelText(label), { target: { value } }));
  fireEvent.mouseDown(screen.getByLabelText(/^Sexe/));
  fireEvent.click(screen.getByRole('option', { name: 'Féminin' }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(
    'https://secondary.example/api/v1/eleves/',
    expect.objectContaining({ username: 'recette.eleve', sexe: 'F' }),
  ));
  expect(postApi.mock.calls[0][1]).not.toHaveProperty('classe_actuelle');
});

it('edits pupil details without changing the existing class assignment', async () => {
  const pupil = {
    id: 8,
    full_name: 'Camille Recette',
    classe_actuelle: 4,
    classe_nom: 'Classe existante',
    date_naissance: '2013-01-10',
    lieu_naissance: 'Ville fictive',
    sexe: 'F',
  };
  fetchApi.mockImplementation(async url => (url.endsWith('/8/')
    ? pupil : { count: 1, results: [pupil] }));
  show('secondaire');
  fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
  await screen.findByRole('dialog');
  expect(screen.queryByLabelText(/^Classe actuelle/)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/^Lieu de naissance/), { target: { value: 'Autre ville fictive' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith(
    'https://secondary.example/api/v1/eleves/8/',
    expect.objectContaining({ lieu_naissance: 'Autre ville fictive' }),
  ));
  expect(patchApi.mock.calls[0][1]).not.toHaveProperty('classe_actuelle');
});

it('keeps the university learner form without a school enrollment link', async () => {
  show('superieur');
  expect(screen.queryByRole('link', { name: 'Classes et inscriptions annuelles' })).not.toBeInTheDocument();
  fireEvent.click(await screen.findByRole('button', { name: 'Ajouter' }));
  expect(screen.getByLabelText(/^Matricule/)).toBeRequired();
  expect(screen.getByLabelText(/^Téléphone/)).toBeRequired();
});
