import React from 'react';
import {
  fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchApi, postApi } from '../services/api';
import ComplaintsPage from './ComplaintsPage';

jest.mock('@edx/frontend-platform', () => ({ getConfig: () => ({ SIS_SUPERIEUR_API_URL: 'https://sis.test/api/v1' }) }));
jest.mock('../services/api', () => ({
  ...jest.requireActual('../services/api'), fetchApi: jest.fn(), postApi: jest.fn(),
}));
const base = 'https://sis.test/api/v1/core/reclamations/';
let item;
let capabilities;
const renderPage = (path = '/superieur/reclamations') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><ComplaintsPage variant="superieur" /></MemoryRouter>
  </QueryClientProvider>,
);
beforeEach(() => {
  jest.clearAllMocks();
  item = {
    id: 'case-1',
    reference: 'REC-TEST',
    objet: 'Mon résultat',
    categorie: 'resultat',
    description: 'Motif privé',
    statut: 'soumise',
    version: 1,
    updated_at: '2026-01-01T10:00:00Z',
    historique: [],
    pieces: [],
    actions: { echanger: true },
  };
  capabilities = { deposer: true, affecter: false, agents: [] };
  fetchApi.mockImplementation(async (url) => {
    if (url.endsWith('capacites/')) { return capabilities; }
    if (url.includes('?')) { return { count: 1, results: [item] }; }
    if (url === `${base}case-1/`) { return item; }
    throw new Error('Dossier introuvable');
  });
  postApi.mockResolvedValue(item);
});

it('submits a private claim and displays the receipt without management actions', async () => {
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Nouvelle réclamation' }));
  const dialog = within(screen.getByRole('dialog'));
  fireEvent.change(dialog.getByLabelText(/^Objet/), { target: { value: 'Mon résultat' } });
  fireEvent.change(dialog.getByLabelText(/^Motif de la demande/), { target: { value: 'Motif privé' } });
  fireEvent.click(dialog.getByRole('button', { name: 'Envoyer la réclamation' }));
  expect(await screen.findByText('REC-TEST')).toBeInTheDocument();
  expect(postApi).toHaveBeenCalledWith(base, {
    categorie: 'resultat', objet: 'Mon résultat', description: 'Motif privé', reference_dossier: '',
  });
  expect(screen.queryByRole('button', { name: 'Rendre la décision' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Agent responsable')).not.toBeInTheDocument();
});

it('requires a decision reason and uses the current server version', async () => {
  capabilities = { deposer: false, affecter: false, agents: [] };
  item = {
    ...item, statut: 'en_cours', version: 3, actions: { traiter: true, echanger: true },
  };
  renderPage('/superieur/reclamations?dossier=case-1');
  const decision = await screen.findByRole('button', { name: 'Rendre la décision' });
  expect(decision).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Message ou motif de décision'), { target: { value: 'Après vérification.' } });
  fireEvent.click(decision);
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${base}case-1/transition/`, {
    version: 3, statut: 'resolue', message: 'Après vérification.',
  }));
  expect(screen.queryByRole('button', { name: 'Nouvelle réclamation' })).not.toBeInTheDocument();
});

it('keeps unsent text and explains a concurrent update failure', async () => {
  postApi.mockRejectedValue({ response: { data: { detail: 'Ce dossier a été modifié.' } } });
  renderPage('/superieur/reclamations?dossier=case-1');
  fireEvent.change(await screen.findByLabelText('Message ou motif de décision'), { target: { value: 'Mon complément' } });
  fireEvent.click(screen.getByRole('button', { name: 'Envoyer le message' }));
  expect(await screen.findByText(/Ce dossier a été modifié/)).toBeInTheDocument();
  expect(screen.getByLabelText('Message ou motif de décision')).toHaveValue('Mon complément');
  expect(screen.getByRole('button', { name: 'Recharger le dossier' })).toBeInTheDocument();
});

it('does not present a forbidden or missing dossier as a successful empty record', async () => {
  renderPage('/superieur/reclamations?dossier=another-person');
  expect(await screen.findByText(/Dossier indisponible/)).toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Dossier de réclamation' })).not.toBeInTheDocument();
});

it('offers a reasoned appeal only when the server allows it', async () => {
  item = {
    ...item, statut: 'resolue', decision: 'Réponse motivée', actions: { recours: true, cloturer: true },
  };
  renderPage('/superieur/reclamations?dossier=case-1');
  expect(await screen.findByText('Réponse motivée')).toBeInTheDocument();
  const appeal = screen.getByRole('button', { name: 'Déposer un recours' });
  expect(appeal).toBeDisabled();
  expect(screen.queryByLabelText('Justificatif PDF')).not.toBeInTheDocument();
  postApi.mockResolvedValue({ ...item, statut: 'en_cours', actions: { echanger: true } });
  fireEvent.change(screen.getByLabelText('Message ou motif de décision'), { target: { value: 'Nouvel élément' } });
  fireEvent.click(appeal);
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${base}case-1/transition/`, {
    version: 1, statut: 'recours', message: 'Nouvel élément',
  }));
  expect(await screen.findByLabelText('Justificatif PDF')).toBeInTheDocument();
});
