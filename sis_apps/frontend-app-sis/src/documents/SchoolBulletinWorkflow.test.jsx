import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import SchoolBulletinWorkflow from './SchoolBulletinWorkflow';
import { fetchApi, postApi } from '../services/api';
import { fetchAllResourcePages } from '../services/resources';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({ SIS_SECONDAIRE_API_URL: 'https://school.example/api/v1' }),
}));
jest.mock('../services/api', () => ({
  ...jest.requireActual('../services/api'), fetchApi: jest.fn(), postApi: jest.fn(),
}));
jest.mock('../services/resources', () => ({
  ...jest.requireActual('../services/resources'), fetchAllResourcePages: jest.fn(),
}));

const draft = {
  id: 8,
  eleve_nom: 'Camille Recette',
  classe_nom: '6e A',
  moyenne_generale: '16.50',
  updated_at: '2026-11-09T15:00:00Z',
  publie: false,
  date_validation: null,
  calcul_detail: {
    methode: 'moyenne_ponderee_20_v1',
    matieres: [{
      id: 1,
      nom: 'Mathématiques',
      moyenne: '16.50',
      coefficient: '1',
      notes: [{
        id: 4, titre: 'Contrôle', valeur: '16.50', bareme: '20', coefficient: '1', ponderation: '100',
      }],
    }],
    exclusions: [],
  },
};

const show = (props = {}) => {
  const onSelect = jest.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <SchoolBulletinWorkflow onSelect={onSelect} onClose={jest.fn()} canPrepare canManage {...props} />
    </QueryClientProvider>,
  );
  return onSelect;
};

beforeEach(() => {
  jest.clearAllMocks();
  crypto.randomUUID = jest.fn(() => 'c99be92c-bfcc-4c86-a4fa-2a194da04f58');
  fetchApi.mockResolvedValue(draft);
  postApi.mockResolvedValue(draft);
  fetchAllResourcePages.mockImplementation(async url => {
    if (url.endsWith('/eleves/')) { return [{ id: 11, full_name: 'Camille Recette' }]; }
    if (url.endsWith('/classes/classes/')) { return [{ id: 21, nom: '6e A', annee_libelle: '2026-2027' }]; }
    return [{ id: 31, libelle: 'Trimestre 1' }];
  });
});

it('prepares from authorized references without sending a client-computed grade', async () => {
  const selected = show();
  fireEvent.click(screen.getByRole('button', { name: 'Préparer un bulletin' }));
  const select = async (label, option) => {
    await waitFor(() => expect(screen.getByLabelText(label)).not.toHaveAttribute('aria-disabled', 'true'));
    fireEvent.mouseDown(screen.getByLabelText(label));
    fireEvent.click(await screen.findByRole('option', { name: option, exact: true }));
  };
  await select(/^Élève/, 'Camille Recette');
  await select(/^Classe/, '6e A — 2026-2027');
  await select(/^Période/, 'Trimestre 1');
  fireEvent.click(screen.getByRole('button', { name: 'Calculer le brouillon' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(
    'https://school.example/api/v1/bulletins/preparer/',
    {
      eleve: 11, classe: 21, periode: 31, methode: 'moyenne_ponderee_20_v1',
    },
  ));
  await waitFor(() => expect(selected).toHaveBeenCalledWith(8));
});

it('requires explicit human validation and uses the reviewed version', async () => {
  show({ selectedId: 8 });
  await screen.findByText('Moyenne calculée : 16.50/20');
  expect(screen.getByRole('button', { name: 'Publier le bulletin' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Appréciation du conseil'), { target: { value: 'Notes vérifiées.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Valider après vérification' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(
    'https://school.example/api/v1/bulletins/8/valider/',
    {
      version: draft.updated_at, confirmer: true, appreciation_conseil: 'Notes vérifiées.', decision: '',
    },
  ));
});

it('reports a source conflict without silently replaying validation', async () => {
  postApi.mockRejectedValue({
    response: { status: 409, data: { detail: 'Les sources ont changé. Recalculez.' } },
  });
  show({ selectedId: 8 });
  await screen.findByText('Moyenne calculée : 16.50/20');
  fireEvent.click(screen.getByRole('button', { name: 'Valider après vérification' }));
  expect(await screen.findByText(/Les sources ont changé/)).toBeVisible();
  expect(postApi).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Publier le bulletin' })).toBeDisabled();
});

it('keeps published results read-only even for a manager', async () => {
  fetchApi.mockResolvedValue({ ...draft, publie: true, date_validation: '2026-11-09T16:00:00Z' });
  show({ selectedId: 8 });
  await screen.findByText(/Bulletin publié/);
  expect(screen.queryByRole('button', { name: 'Recalculer' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Publier le bulletin' })).not.toBeInTheDocument();
  expect(screen.getByLabelText('Appréciation du conseil')).toBeDisabled();
});

it('does not expose mutations when the account can only read the bulletin', async () => {
  show({ selectedId: 8, canPrepare: false, canManage: false });
  await screen.findByText('Moyenne calculée : 16.50/20');
  expect(screen.queryByRole('button', { name: 'Préparer un bulletin' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Valider après vérification' })).not.toBeInTheDocument();
});

it('creates a separate rectification using a reason and the published version', async () => {
  fetchApi.mockResolvedValue({ ...draft, publie: true, revision: 1 });
  postApi.mockResolvedValue({
    ...draft, id: 9, revision: 2, rectifie: 8,
  });
  const selected = show({ selectedId: 8 });
  await screen.findByText(/Bulletin publié/);
  const button = screen.getByRole('button', { name: 'Créer une rectification' });
  expect(button).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/^Motif de rectification/), { target: { value: 'Erreur de transcription.' } });
  fireEvent.click(button);
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(
    'https://school.example/api/v1/bulletins/8/rectifier/',
    {
      version: draft.updated_at,
      motif: 'Erreur de transcription.',
      cle_idempotence: 'c99be92c-bfcc-4c86-a4fa-2a194da04f58',
    },
  ));
  await waitFor(() => expect(selected).toHaveBeenCalledWith(9));
  expect(screen.queryByRole('button', { name: 'Valider après vérification' })).not.toBeInTheDocument();
});

it('retains the same idempotency key and payload when retrying a lost response', async () => {
  fetchApi.mockResolvedValue({ ...draft, publie: true });
  postApi.mockRejectedValueOnce(new Error('Connexion interrompue'));
  postApi.mockResolvedValueOnce({
    ...draft, id: 9, rectifie: 8, revision: 2,
  });
  const selected = show({ selectedId: 8 });
  await screen.findByText(/Bulletin publié/);
  fireEvent.change(screen.getByLabelText(/^Motif de rectification/), { target: { value: 'Erreur de saisie.' } });
  const button = screen.getByRole('button', { name: 'Créer une rectification' });
  fireEvent.click(button);
  await waitFor(() => expect(postApi).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(button).not.toBeDisabled());
  fireEvent.click(button);
  await waitFor(() => expect(selected).toHaveBeenCalledWith(9));
  expect(postApi).toHaveBeenCalledTimes(2);
  expect(postApi.mock.calls[0]).toEqual(postApi.mock.calls[1]);
  expect(crypto.randomUUID).toHaveBeenCalledTimes(1);
});

it('navigates to a published rectification instead of offering a competing branch', async () => {
  fetchApi.mockResolvedValue({ ...draft, publie: true, rectification_publiee: 9 });
  const selected = show({ selectedId: 8 });
  await screen.findByText(/Une rectification publiée est disponible/);
  expect(screen.queryByRole('button', { name: 'Créer une rectification' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Voir la rectification publiée' }));
  expect(selected).toHaveBeenCalledWith(9);
});

it('refreshes the cached original when returning after publishing its rectification', async () => {
  const url = 'https://school.example/api/v1/bulletins/';
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  const original = { ...draft, publie: true, rectification_publiee: null };
  const correction = {
    ...draft, id: 9, rectifie: 8, revision: 2, date_validation: '2026-11-09T16:00:00Z',
  };
  client.setQueryData(['bulletin-calculation', url, 8], original);
  client.setQueryData(['bulletin-calculation', url, 9], correction);
  let published = false;
  fetchApi.mockImplementation(async endpoint => (endpoint === `${url}8/`
    ? { ...original, rectification_publiee: published ? 9 : null }
    : { ...correction, publie: published }));
  postApi.mockImplementation(async () => { published = true; return { ...correction, publie: true }; });
  const tree = selectedId => (
    <QueryClientProvider client={client}>
      <SchoolBulletinWorkflow
        selectedId={selectedId}
        onSelect={jest.fn()}
        onClose={jest.fn()}
        canPrepare
        canManage
      />
    </QueryClientProvider>
  );
  const view = render(tree(9));
  fireEvent.click(await screen.findByRole('button', { name: 'Publier le bulletin' }));
  await screen.findByText(/Bulletin publié/);
  view.rerender(tree(8));
  expect(await screen.findByRole('button', { name: 'Voir la rectification publiée' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Créer une rectification' })).not.toBeInTheDocument();
});

it('shows provenance and requires fresh validation for a correction draft', async () => {
  fetchApi.mockResolvedValue({
    ...draft, id: 9, revision: 2, rectifie: 8, motif_rectification: 'Correction de saisie.',
  });
  const selected = show({ selectedId: 9 });
  await screen.findByText(/Rectifie BUL-8/);
  expect(screen.getByRole('button', { name: 'Publier le bulletin' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Valider après vérification' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Voir la version précédente' }));
  expect(selected).toHaveBeenCalledWith(8);
});

it('requires creation rights as well as management rights to rectify', async () => {
  fetchApi.mockResolvedValue({ ...draft, publie: true });
  show({ selectedId: 8, canPrepare: false, canManage: true });
  await screen.findByText(/Bulletin publié/);
  expect(screen.queryByRole('button', { name: 'Créer une rectification' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/^Motif de rectification/)).not.toBeInTheDocument();
});
