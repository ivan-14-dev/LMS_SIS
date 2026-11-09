import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { postApi } from '../../services/api';
import { fetchAllResourcePages } from '../../services/resources';
import AdmissionRequestPanel from './AdmissionRequestPanel';

jest.mock('../../services/api', () => ({ postApi: jest.fn() }));
jest.mock('../../services/resources', () => ({
  fetchAllResourcePages: jest.fn(),
  resourceUrl: (variant, resource) => `/${variant}/${resource}/`,
  apiErrorMessage: error => error.message,
}));
jest.mock('./WorkflowHistoryPanel', () => function History({ endpoint }) {
  return <div data-testid="history">{endpoint}</div>;
});

let enrollments;
let failCatalogue;
const renderPanel = (variant = 'secondaire') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AdmissionRequestPanel variant={variant} />
  </QueryClientProvider>,
);
const choose = async (label, choice) => {
  fireEvent.mouseDown(screen.getByLabelText(new RegExp(`^${label}`)));
  fireEvent.click(await screen.findByRole('option', { name: choice }));
};

beforeEach(() => {
  jest.clearAllMocks();
  enrollments = [];
  failCatalogue = false;
  fetchAllResourcePages.mockImplementation(async (url) => {
    if (url.endsWith('inscriptions/')) { return enrollments; }
    if (failCatalogue) { throw new Error('Catalogue inaccessible'); }
    if (url.includes('etablissement/annees')) {
      return [{ id: 8, libelle: 'Année ouverte', cloturee: false }, { id: 9, libelle: 'Année close', cloturee: true }];
    }
    if (url.includes('classes/classes')) {
      return [{ id: 4, nom: 'Classe A', annee_scolaire: 8 }, { id: 5, nom: 'Autre année', annee_scolaire: 9 }];
    }
    if (url.includes('formations/formations')) { return [{ id: 4, nom: 'Formation A' }]; }
    if (url.includes('formations/parcours')) {
      return [{ id: 6, nom: 'Parcours A', formation: 4 }, { id: 7, nom: 'Autre formation', formation: 5 }];
    }
    throw new Error(`Unexpected catalogue ${url}`);
  });
  postApi.mockImplementation(async () => {
    enrollments = [{
      id: 12, annee_libelle: 'Année ouverte', classe_nom: 'Classe A', statut_display: 'En cours',
    }];
    return enrollments[0];
  });
});

it.each(['secondaire', 'superieur'])('deposits the authenticated learner first request once in %s', async (variant) => {
  renderPanel(variant);
  await screen.findByText(/Votre profil existe déjà/);
  await waitFor(() => expect(screen.getByLabelText(/^Année de la demande/)).not.toHaveAttribute('aria-disabled', 'true'));
  await choose('Année de la demande', 'Année ouverte');
  await choose(variant === 'secondaire' ? 'Classe demandée' : 'Formation demandée', variant === 'secondaire' ? 'Classe A' : 'Formation A');
  if (variant === 'superieur') { await choose('Parcours', 'Parcours A'); }
  fireEvent.change(screen.getByLabelText('Message à la scolarité'), { target: { value: 'Première demande' } });
  fireEvent.click(screen.getByRole('button', { name: 'Déposer ma première demande' }));
  expect(await screen.findByText(/Votre demande a été déposée/)).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Déposer ma première demande' })).not.toBeInTheDocument());
  expect(postApi).toHaveBeenCalledTimes(1);
  expect(postApi).toHaveBeenCalledWith(
    variant === 'secondaire' ? '/secondaire/eleves/inscriptions/deposer/' : '/superieur/inscriptions/deposer/',
    variant === 'secondaire'
      ? { annee_scolaire: 8, classe: 4, motif: 'Première demande' }
      : {
        annee_universitaire: 8, formation: 4, parcours: 6, motif: 'Première demande',
      },
  );
  expect(screen.getByTestId('history')).toHaveTextContent('12/historique/');
});

it('does not present a failed catalogue or rejected request as a success', async () => {
  failCatalogue = true;
  renderPanel();
  expect(await screen.findByText('Catalogue inaccessible')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Déposer ma première demande' })).toBeDisabled();
  failCatalogue = false;
  fireEvent.click(screen.getByRole('button', { name: 'Recharger les choix' }));
  await waitFor(() => expect(screen.queryByText('Catalogue inaccessible')).not.toBeInTheDocument());
  await choose('Année de la demande', 'Année ouverte');
  await choose('Classe demandée', 'Classe A');
  postApi.mockRejectedValue(new Error('Cette année est clôturée.'));
  fireEvent.click(screen.getByRole('button', { name: 'Déposer ma première demande' }));
  expect(await screen.findByText('Cette année est clôturée.')).toBeInTheDocument();
  expect(screen.queryByText(/Votre demande a été déposée/)).not.toBeInTheDocument();
});

it('shows existing decisions without allowing another first admission', async () => {
  enrollments = [{ id: 12, annee_libelle: 'Année ouverte', classe_nom: 'Classe A', statut_display: 'Suspendue' }];
  renderPanel();
  expect(await screen.findByText('Suspendue')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Déposer ma première demande' })).not.toBeInTheDocument();
  expect(screen.getByTestId('history')).toHaveTextContent('eleves/inscriptions/12/historique/');
  expect(fetchAllResourcePages).toHaveBeenCalledTimes(1);
});
