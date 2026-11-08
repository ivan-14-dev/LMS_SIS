import React from 'react';
import {
  act, fireEvent, render, screen,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import SurveysPage from './SurveysPage';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_SUPERIEUR_API_URL: 'https://superieur.test/api/v1',
    SIS_SECONDAIRE_API_URL: 'https://secondaire.test/api/v1',
  }),
}));
jest.mock('@edx/frontend-platform/auth', () => ({ getAuthenticatedHttpClient: jest.fn() }));
jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));

const id = '35c8b3c2-68b4-4754-87c8-22af756532f0';
const portal = '/api/v1/portail/enquetes/';
const management = '/api/v1/core/enquetes/';
const failure = status => ({ response: { status, data: { detail: `Refus serveur ${status}` } } });
const page = results => ({
  count: results.length, results, next: null, previous: null,
});
let survey;
let manager;
let enabled;
let getFailure;
let postHandler;
let http;
const clients = [];

const renderPage = (variant = 'secondaire', suffix = `?enquete=${id}`) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[`/${variant}/portail-enquetes${suffix}`]}>
          <SurveysPage variant={variant} />
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
};
const change = (label, value) => fireEvent.change(screen.getByLabelText(label, { exact: false, selector: 'input, textarea' }), { target: { value } });

beforeEach(() => {
  manager = false;
  enabled = true;
  getFailure = null;
  survey = {
    id,
    titre: 'Services du campus',
    description: 'Votre avis sur les services',
    politique: 'nominative',
    statut: 'publiee',
    version: 2,
    questionnaire: [{
      id: 'avis', libelle: 'Votre avis', type: 'texte', choix: [],
    }],
    destinataires: [{
      id: 11, nom: 'Alice', profil: 'Apprenant', revoked_at: null,
    }],
    ma_reponse: null,
    peut_repondre: true,
  };
  postHandler = async () => { throw new Error('POST inattendu'); };
  http = {
    get: jest.fn(async rawUrl => {
      const { pathname } = new URL(rawUrl);
      if (getFailure) { getFailure(pathname); }
      let data;
      if (pathname.endsWith('/utilisateurs/comptes/capabilities/')) {
        data = { role: 'parent', permissions: [], modules: { 'sis.surveys': enabled } };
      } else if (pathname === `${portal}capacites/`) {
        data = { can_manage: manager, politique: 'nominative' };
      } else if ([portal, management].includes(pathname)) {
        data = page([survey]);
      } else if ([`${portal}${id}/`, `${management}${id}/`].includes(pathname)) {
        data = { ...survey };
      } else if (pathname === `${management}${id}/resultats/`) {
        data = {
          destinataires: 1,
          reponses_recues: 1,
          choix: [],
          reponses: [{ destinataire: { id: 11, nom: 'Alice' }, reponses: { avis: 'Texte privé gestionnaire' } }],
        };
      } else if (pathname === `${management}candidats/`) {
        data = page([{ id: 11, nom: 'Alice', profil: 'Apprenant' }, { id: 12, nom: 'Parent', profil: 'Parent' }]);
      } else {
        throw new Error(`GET inattendu ${rawUrl}`);
      }
      return { data };
    }),
    post: jest.fn(async (rawUrl, payload) => ({ data: await postHandler(new URL(rawUrl).pathname, payload) })),
  };
  getAuthenticatedHttpClient.mockReturnValue(http);
});

afterEach(() => {
  clients.splice(0).forEach(client => client.clear());
  jest.clearAllMocks();
});

it.each(['secondaire', 'superieur'])('submits one explicit nominative response through the %s portal', async variant => {
  postHandler = async (path, payload) => {
    expect(path).toBe(`${portal}${id}/repondre/`);
    expect(payload).toEqual({ politique: 'nominative', reponses: { avis: 'Avis personnel' } });
    survey = { ...survey, ma_reponse: { reponses: payload.reponses }, peut_repondre: false };
    return survey;
  };
  renderPage(variant);
  expect(await screen.findByText(/Aucun anonymat/)).toBeInTheDocument();
  await screen.findByLabelText('Votre avis', { exact: false });
  expect(screen.queryByRole('button', { name: 'Gérer les enquêtes' })).not.toBeInTheDocument();
  expect(screen.queryByText('Alice')).not.toBeInTheDocument();
  expect(screen.queryByText(/Texte privé gestionnaire/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Envoyer ma réponse' })).toBeDisabled();
  change('Votre avis', 'Avis personnel');
  fireEvent.click(screen.getByRole('checkbox', { name: /Je comprends/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Envoyer ma réponse' }));
  expect(await screen.findByText(/Votre réponse a été enregistrée/)).toBeInTheDocument();
  expect(screen.getByText('Votre avis : Avis personnel')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Envoyer ma réponse' })).not.toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(http.get.mock.calls.some(([url]) => url.includes('/core/enquetes/'))).toBe(false);
});

it.each([400, 403, 404, 409])('discards stale form data on submission error %s', async status => {
  postHandler = async () => { throw failure(status); };
  renderPage();
  await screen.findByLabelText('Votre avis', { exact: false });
  change('Votre avis', 'Réponse non confirmée');
  fireEvent.click(screen.getByRole('checkbox', { name: /Je comprends/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Envoyer ma réponse' }));
  expect(await screen.findByText(/Aucune donnée précédemment chargée/)).toBeInTheDocument();
  expect(screen.queryByDisplayValue('Réponse non confirmée')).not.toBeInTheDocument();
  expect(screen.queryByText('Services du campus')).not.toBeInTheDocument();
  expect(screen.queryByText(/Enregistrement confirmé/)).not.toBeInTheDocument();
});

it('submits the selected single choice without adding answers for another question', async () => {
  survey = {
    ...survey,
    questionnaire: [{
      id: 'accueil', libelle: 'Accueil', type: 'choix', choix: ['Bien', 'À améliorer'],
    }],
  };
  postHandler = async (path, payload) => {
    expect(path).toBe(`${portal}${id}/repondre/`);
    expect(payload).toEqual({ politique: 'nominative', reponses: { accueil: 'À améliorer' } });
    survey = { ...survey, ma_reponse: { reponses: payload.reponses }, peut_repondre: false };
    return survey;
  };
  renderPage('superieur');
  fireEvent.mouseDown(await screen.findByRole('combobox', { name: /Accueil/ }));
  fireEvent.click(await screen.findByRole('option', { name: 'À améliorer' }));
  fireEvent.click(screen.getByRole('checkbox', { name: /Je comprends/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Envoyer ma réponse' }));
  expect(await screen.findByText('Accueil : À améliorer')).toBeInTheDocument();
});

it('clears loaded results after management revocation and refetch denial', async () => {
  manager = true;
  const { client } = renderPage('superieur', `?gestion=1&enquete=${id}`);
  expect(await screen.findByText('Votre avis : Texte privé gestionnaire')).toBeInTheDocument();
  getFailure = path => { if (path.startsWith(management)) { throw failure(403); } };
  await act(async () => { await client.invalidateQueries({ queryKey: ['surveys'] }); });
  expect(await screen.findByText(/Aucune donnée précédemment chargée/)).toBeInTheDocument();
  expect(screen.queryByText('Votre avis : Texte privé gestionnaire')).not.toBeInTheDocument();
  expect(screen.queryByText(/Alice/)).not.toBeInTheDocument();
});

it('creates an explicit draft with selected recipients then publishes and closes it', async () => {
  manager = true;
  survey = { ...survey, statut: 'brouillon', version: 1 };
  postHandler = async (path, payload) => {
    if (path === management) {
      expect(payload.destinataires).toEqual([11]);
      expect(payload.politique).toBe('nominative');
      expect(payload.questionnaire).toEqual([{
        id: 'q1', libelle: 'Votre retour', type: 'texte', choix: [],
      }]);
      survey = { ...survey, ...payload, destinataires: [{ id: 11, nom: 'Alice', profil: 'Apprenant' }] };
    } else if (path === `${management}${id}/publier/`) {
      expect(payload).toEqual({ version: 1 });
      survey = { ...survey, statut: 'publiee', version: 2 };
    } else if (path === `${management}${id}/fermer/`) {
      expect(payload).toEqual({ version: 2 });
      survey = { ...survey, statut: 'fermee', version: 3 };
    } else { throw new Error(`POST inattendu ${path}`); }
    return survey;
  };
  renderPage('superieur', '?gestion=1');
  fireEvent.click(await screen.findByRole('button', { name: 'Nouvelle enquête' }));
  change('Titre', 'Améliorations');
  change('Question 1', 'Votre retour');
  change('Rechercher un destinataire', 'Al');
  fireEvent.click(await screen.findByRole('button', { name: /Ajouter Alice/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le brouillon' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Publier dans les portails' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Fermer l’enquête' }));
  expect(await screen.findByText('Statut : fermee')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Modifier le brouillon' })).not.toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(3);
});

it('denies a direct manager URL without a grant and a disabled module', async () => {
  const first = renderPage('secondaire', `?gestion=1&enquete=${id}`);
  expect(await screen.findByText(/exige une habilitation explicite/)).toBeInTheDocument();
  expect(http.get.mock.calls.some(([url]) => url.includes('/core/enquetes/'))).toBe(false);
  first.unmount();
  enabled = false;
  renderPage('superieur');
  expect(await screen.findByText(/désactivé ou indisponible/)).toBeInTheDocument();
  expect(screen.queryByLabelText('Votre avis', { exact: false })).not.toBeInTheDocument();
});

it('offers only the saved personal response on a closed survey', async () => {
  survey = {
    ...survey, statut: 'fermee', peut_repondre: false, ma_reponse: { reponses: { avis: 'Mon ancien avis' } },
  };
  renderPage();
  expect(await screen.findByText('Votre avis : Mon ancien avis')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Envoyer ma réponse' })).not.toBeInTheDocument();
  expect(http.get.mock.calls.some(([url]) => url.includes('/resultats/'))).toBe(false);
});

it('waits for the server before confirming a response and prevents double clicks', async () => {
  let resolve;
  postHandler = () => new Promise(done => { resolve = done; });
  renderPage();
  await screen.findByLabelText('Votre avis', { exact: false });
  change('Votre avis', 'En attente');
  fireEvent.click(screen.getByRole('checkbox', { name: /Je comprends/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Envoyer ma réponse' }));
  expect(screen.getByRole('button', { name: 'Envoyer ma réponse' })).toBeDisabled();
  expect(screen.queryByText(/Enregistrement confirmé/)).not.toBeInTheDocument();
  await act(async () => {
    survey = { ...survey, ma_reponse: { reponses: { avis: 'En attente' } }, peut_repondre: false };
    resolve(survey);
  });
  expect(await screen.findByText(/Votre réponse a été enregistrée/)).toBeInTheDocument();
});
