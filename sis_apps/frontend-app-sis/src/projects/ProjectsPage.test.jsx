import React from 'react';
import {
  act, fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import ProjectsPage from './ProjectsPage';

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

const projectId = '20ecdd8e-f14b-4895-8a55-c15175f052e1';
const teamId = '39fcd9ad-5149-45f1-b7b4-30f641a37b2a';
const milestoneId = 'b95e188b-5dbd-4c70-9b1e-c0e85d57e79c';
const evaluationId = '708d5356-ab7b-4aeb-adb9-b5392f7e2837';
const deliveryId = 'd174ed05-c074-48a5-98ac-aab03c4fc342';
const basePath = '/api/v1/core/projets/';
const detailPath = `${basePath}${projectId}/`;
const teamPath = `${detailPath}equipes/${teamId}/`;
const page = results => ({
  count: results.length, next: null, previous: null, results,
});
const failure = status => ({ response: { status, data: { detail: `Refus serveur ${status}` } } });
let http;
let project;
let teams;
let milestones;
let evaluations;
let deliveries;
let modules;
let canCreate;
let courses;
let getFailure;
let postHandler;
let pendingResolve;
const clients = [];

const renderPage = (variant = 'superieur', detail = true) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[`/${variant}/projets${detail ? `?projet=${projectId}` : ''}`]}>
          <ProjectsPage variant={variant} />
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
};
const change = (label, value, scope = screen) => fireEvent.change(scope.getByLabelText(label), { target: { value } });
const choose = async (label, text, name) => {
  await waitFor(() => expect(screen.getByLabelText(label)).toBeEnabled());
  change(label, text);
  fireEvent.click(await screen.findByRole('option', { name }, { timeout: 5000 }));
};
const save = () => fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Enregistrer' }));
const waitSaved = async () => {
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getByText('Enregistrement confirmé par le serveur.')).toBeInTheDocument();
};

beforeEach(() => {
  modules = { 'sis.projects': true };
  canCreate = true;
  getFailure = null;
  pendingResolve = null;
  courses = ['A', 'B'].map((code, index) => ({
    id: 101 + index,
    nom: `Cours projet ${code}`,
    contexte: { ecue: { id: 201 + index, code, nom: `ECUE ${code}` } },
  }));
  project = {
    id: projectId,
    titre: 'Projet énergie',
    description: 'Description privée',
    mode: 'collectif',
    responsable: 91,
    evaluateurs: [92],
    cours: null,
    cree_par: 91,
    version: 1,
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-01T10:00:00Z',
    actions: { can_manage: true, can_evaluate: true, can_submit: false },
  };
  teams = [{
    id: teamId,
    projet: projectId,
    nom: 'Équipe solaire',
    cree_par: 91,
    created_at: '2026-11-01T10:00:00Z',
    membres: [
      {
        membre: 11, nom: 'Alice Martin', ajoute_par: 91, created_at: '2026-11-01T10:00:00Z',
      },
      {
        membre: 12, nom: 'Bob Durand', ajoute_par: 91, created_at: '2026-11-01T10:00:00Z',
      },
    ],
    actions: { can_manage: true, can_evaluate: true, can_submit: false },
  }];
  milestones = [{
    id: milestoneId,
    projet: projectId,
    titre: 'Rapport final',
    consignes: 'Décrire les résultats',
    ordre: 1,
    echeance: '2026-11-10T18:00:00Z',
    bareme: '20.00',
    cree_par: 91,
    created_at: '2026-11-01T10:00:00Z',
  }];
  deliveries = [];
  evaluations = [];
  postHandler = async () => { throw new Error('POST non prévu'); };
  http = {
    get: jest.fn(async (rawUrl, options) => {
      const { pathname, searchParams } = new URL(rawUrl);
      if (getFailure) { getFailure(pathname); }
      let data;
      if (pathname.endsWith('/utilisateurs/comptes/capabilities/')) {
        data = { role: 'custom-role', permissions: [], modules };
      } else if (pathname === `${basePath}capacites/`) {
        data = { can_create: canCreate, permissions: ['core.gerer_projet_pedagogique', 'core.evaluer_projet_pedagogique'] };
      } else if (pathname === `${basePath}cours-candidats/`) {
        expect(searchParams.get('q').length).toBeGreaterThanOrEqual(2);
        expect(searchParams.get('q').length).toBeLessThanOrEqual(100);
        expect(['91', '93']).toContain(searchParams.get('responsable'));
        expect(searchParams.get('page_size')).toBe('20');
        if (searchParams.has('projet')) { expect(searchParams.get('projet')).toBe(projectId); }
        const currentPage = Number(searchParams.get('page'));
        data = {
          count: courses.length,
          next: currentPage < courses.length ? 'https://superieur.test/next-page' : null,
          previous: currentPage > 1 ? 'https://superieur.test/previous-page' : null,
          results: courses.slice(currentPage - 1, currentPage),
        };
      } else if (pathname === `${basePath}candidats/`) {
        expect(['responsable', 'evaluateur', 'membre']).toContain(searchParams.get('type'));
        expect(searchParams.get('q').length).toBeGreaterThanOrEqual(2);
        expect(searchParams.get('q').length).toBeLessThanOrEqual(100);
        if (searchParams.has('projet')) {
          expect(searchParams.get('projet')).toBe(projectId);
          expect(searchParams.has('responsable')).toBe(false);
        } else if (searchParams.get('type') === 'evaluateur') {
          expect(searchParams.get('responsable')).toBe('91');
        } else {
          expect(searchParams.has('responsable')).toBe(false);
        }
        const users = {
          responsable: [{ id: 91, nom: 'Responsable habilité' }, { id: 93, nom: 'Autre responsable habilité' }],
          evaluateur: [{ id: 92, nom: 'Évaluatrice habilitée' }],
          membre: [{ id: 11, nom: 'Alice Martin' }, { id: 12, nom: 'Bob Durand' }],
        };
        data = { results: users[searchParams.get('type')] };
      } else if (pathname === basePath) {
        expect([...searchParams.keys()].sort()).toEqual(searchParams.has('q') ? ['page', 'page_size', 'q'] : ['page', 'page_size']);
        data = page(project.titre.toLowerCase().includes((searchParams.get('q') || '').toLowerCase()) ? [project] : []);
      } else if (pathname === detailPath) {
        data = project;
      } else if (pathname === `${detailPath}equipes/`) {
        data = page(teams);
      } else if (pathname === `${detailPath}jalons/`) {
        data = page(milestones);
      } else if (pathname === `${teamPath}livrables/`) {
        expect(searchParams.get('jalon')).toBe(milestoneId);
        data = page(deliveries);
      } else if (pathname === `${teamPath}evaluations/`) {
        expect(searchParams.get('jalon')).toBe(milestoneId);
        data = page(evaluations);
      } else if (pathname === `${teamPath}livrables/${deliveryId}/telecharger/`) {
        expect(options.responseType).toBe('blob');
        data = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
      } else {
        throw new Error(`GET non prévu : ${rawUrl}`);
      }
      return { data };
    }),
    post: jest.fn(async (url, payload) => ({ data: await postHandler(new URL(url).pathname, payload) })),
  };
  getAuthenticatedHttpClient.mockReturnValue(http);
});
afterEach(() => {
  clients.splice(0).forEach(client => client.clear());
  jest.restoreAllMocks();
});

it.each(['secondaire', 'superieur'])('creates a real %s project using scoped named candidates', async variant => {
  postHandler = async (path, payload) => {
    expect(path).toBe(basePath);
    expect(payload).toEqual({
      titre: 'Projet énergie', description: 'Description privée', mode: 'individuel', responsable: 91, evaluateurs: [92],
    });
    project = { ...project, ...payload };
    return project;
  };
  renderPage(variant, false);
  fireEvent.click(await screen.findByRole('button', { name: 'Nouveau projet' }));
  change(/^Titre du projet/, 'Projet énergie');
  change('Description', 'Description privée');
  change('Mode du projet', 'individuel');
  expect(screen.getByLabelText('Évaluateurs')).toBeDisabled();
  await choose(/^Responsable/, 'Re', 'Responsable habilité');
  await choose('Évaluateurs', 'Ev', 'Évaluatrice habilitée');
  save();
  expect(await screen.findByRole('heading', { name: 'Projet énergie' })).toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(http.post.mock.calls[0][0]).toBe(`https://${variant}.test${basePath}`);
  expect(http.get.mock.calls.some(([url]) => url.includes('/utilisateurs/') && !url.includes('/capabilities/'))).toBe(false);
});

it.each(['secondaire', 'superieur'])('selects a paginated existing course at %s project creation', async variant => {
  if (variant === 'secondaire') {
    courses = courses.map(course => ({
      ...course,
      contexte: { classe: { id: 41, nom: 'Classe 6A' }, matiere: { id: 42, nom: 'Mathématiques' } },
    }));
  }
  postHandler = async (path, payload) => {
    expect(path).toBe(basePath);
    expect(payload).toEqual({
      titre: 'Avec cours', description: '', mode: 'collectif', responsable: 91, evaluateurs: [], cours: 102,
    });
    project = { ...project, ...payload, cours: { ...courses[1], disponible: true } };
    return project;
  };
  renderPage(variant, false);
  fireEvent.click(await screen.findByRole('button', { name: 'Nouveau projet' }));
  change(/^Titre du projet/, 'Avec cours');
  expect(screen.getByLabelText('Cours existant (facultatif)')).toBeDisabled();
  await choose(/^Responsable/, 'Re', 'Responsable habilité');
  change('Cours existant (facultatif)', 'cours');
  expect(await screen.findByRole('option', { name: /Cours projet A/ }, { timeout: 5000 })).toHaveTextContent(
    variant === 'secondaire' ? 'Classe 6A / Mathématiques' : 'ECUE A — ECUE A',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Cours suivants' }));
  await waitFor(() => expect(http.get.mock.calls.some(([url]) => (
    url.includes('cours-candidats/') && new URL(url).searchParams.get('page') === '2'
  ))).toBe(true));
  fireEvent.keyDown(screen.getByLabelText('Cours existant (facultatif)'), { key: 'ArrowDown' });
  fireEvent.click(await screen.findByRole('option', { name: /Cours projet B/ }, { timeout: 5000 }));
  expect(screen.getByRole('button', { name: 'Cours suivants' })).toBeDisabled();
  save();
  expect(await screen.findByText(/Cours rattaché : Cours projet B/)).toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(http.get.mock.calls.some(([url]) => url.includes('/integration/') || url.includes('recherche-academique'))).toBe(false);
});

it('preserves selected course and owner through a 409 and sends only the reconfirmed version', async () => {
  let first = true;
  postHandler = async (path, payload) => {
    expect(path).toBe(`${detailPath}configurer/`);
    expect(payload).toEqual({
      version: first ? 1 : 7, titre: 'Projet énergie', description: 'Description privée', responsable: 93, cours: 101,
    });
    if (first) { first = false; throw failure(409); }
    project = {
      ...project, ...payload, version: 8, cours: { ...courses[0], disponible: true },
    };
    return project;
  };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Configurer le projet' }));
  await choose('Nouveau responsable (facultatif)', 'Autre', 'Autre responsable habilité');
  fireEvent.click(screen.getByRole('button', { name: 'Choisir un cours' }));
  await choose('Cours existant (facultatif)', 'cours', /Cours projet A/);
  const search = http.get.mock.calls.find(([url]) => url.includes('cours-candidats/'));
  expect(new URL(search[0]).searchParams.get('responsable')).toBe('93');
  expect(new URL(search[0]).searchParams.get('projet')).toBe(projectId);
  save();
  expect(await screen.findByText(/Refus serveur 409/)).toBeInTheDocument();
  expect(screen.getByLabelText('Cours existant (facultatif)')).toHaveValue('Cours projet A · ECUE A — ECUE A');
  expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled();
  project = { ...project, version: 7 };
  fireEvent.click(screen.getByRole('button', { name: 'Recharger le projet sans effacer les saisies' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeEnabled());
  expect(screen.getByLabelText('Cours existant (facultatif)')).toHaveValue('Cours projet A · ECUE A — ECUE A');
  expect(http.post).toHaveBeenCalledTimes(1);
  save();
  await waitSaved();
  expect(http.post).toHaveBeenCalledTimes(2);
});

it('distinguishes an unavailable binding from no binding and clears it only by an explicit versioned command', async () => {
  project = { ...project, cours: { disponible: false } };
  postHandler = async (path, payload) => {
    expect(path).toBe(`${detailPath}configurer/`);
    expect(payload).toEqual({
      version: 1, titre: 'Projet énergie', description: 'Description privée', cours: null,
    });
    project = { ...project, cours: null, version: 2 };
    return project;
  };
  renderPage();
  expect(await screen.findByText(/Rattachement conservé — cours indisponible/)).toBeInTheDocument();
  expect(screen.queryByText('Aucun cours rattaché.')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Configurer le projet' }));
  fireEvent.click(screen.getByRole('button', { name: 'Retirer le rattachement' }));
  expect(screen.getByText('Retrait du rattachement à confirmer.')).toBeInTheDocument();
  expect(http.post).not.toHaveBeenCalled();
  save();
  await waitSaved();
  expect(screen.getByText('Aucun cours rattaché.')).toBeInTheDocument();
});

it('keeps an incompatible course draft after 400 without claiming success or falling back to a catalogue', async () => {
  postHandler = async () => { throw failure(400); };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Configurer le projet' }));
  fireEvent.click(screen.getByRole('button', { name: 'Choisir un cours' }));
  await choose('Cours existant (facultatif)', 'cours', /Cours projet A/);
  save();
  expect(await screen.findByText(/Refus serveur 400/)).toBeInTheDocument();
  expect(screen.getByLabelText('Cours existant (facultatif)')).toHaveValue('Cours projet A · ECUE A — ECUE A');
  expect(screen.queryByText('Enregistrement confirmé par le serveur.')).not.toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
});

it.each([403, 404])('purges private course choices and the project on selector HTTP %s', async status => {
  const { client } = renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Configurer le projet' }));
  fireEvent.click(screen.getByRole('button', { name: 'Choisir un cours' }));
  await choose('Cours existant (facultatif)', 'cours', /Cours projet A/);
  getFailure = path => { if (path === `${basePath}cours-candidats/`) { throw failure(status); } };
  change('Cours existant (facultatif)', 'nouveau');
  expect(await screen.findByText(/Accès aux projets refusé/, {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByText(/Cours projet A/)).not.toBeInTheDocument();
  await waitFor(() => expect(client.getQueriesData({ queryKey: ['projects'] })).toEqual([]));
  expect(http.post).not.toHaveBeenCalled();
});

it('removes course candidate cache on unmount and never searches before a bounded term', async () => {
  const { client, unmount } = renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Configurer le projet' }));
  fireEvent.click(screen.getByRole('button', { name: 'Choisir un cours' }));
  change('Cours existant (facultatif)', 'c');
  await act(async () => new Promise(resolve => { setTimeout(resolve, 300); }));
  expect(http.get.mock.calls.some(([url]) => url.includes('cours-candidats/'))).toBe(false);
  await choose('Cours existant (facultatif)', 'cours', /Cours projet A/);
  expect(client.getQueriesData({ queryKey: ['projects'] }).length).toBeGreaterThan(0);
  unmount();
  await waitFor(() => expect(client.getQueriesData({ queryKey: ['projects'] })).toEqual([]));
});

it('searches on the server and distinguishes an empty selection from a failed list', async () => {
  renderPage('superieur', false);
  await screen.findByText('Projet énergie');
  change('Rechercher', 'introuvable');
  expect(await screen.findByText('Aucun projet accessible dans cette sélection.')).toBeInTheDocument();
  expect(http.get.mock.calls.some(([url]) => new URL(url).searchParams.get('q') === 'introuvable')).toBe(true);
  getFailure = path => { if (path === basePath) { throw failure(500); } };
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }));
  expect(await screen.findByText(/Liste indisponible/)).toBeInTheDocument();
  expect(screen.queryByText('Aucun projet accessible dans cette sélection.')).not.toBeInTheDocument();
});

it('creates an immutable dated milestone then replaces active memberships with the returned version', async () => {
  postHandler = async (path, payload) => {
    if (path === `${detailPath}jalons/`) {
      expect(payload).toEqual({
        version: 1,
        titre: 'Rapport complémentaire',
        consignes: 'Consigne nouvelle',
        ordre: 2,
        echeance: new Date('2026-12-01T16:30').toISOString(),
        bareme: '10',
      });
      const jalon = { ...milestones[0], ...payload, id: 'ead839df-fbe1-45f0-a94a-35b3f6b6eb10' };
      milestones = [...milestones, jalon];
      project = { ...project, version: 2 };
      return { version: 2, jalon };
    }
    expect(path).toBe(`${teamPath}membres/`);
    expect(payload).toEqual({ version: 2, membres: [11] });
    teams = [{ ...teams[0], membres: teams[0].membres.slice(0, 1) }];
    project = { ...project, version: 3 };
    return { version: 3, equipe: teams[0] };
  };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Nouveau jalon' }));
  change(/^Titre du jalon/, 'Rapport complémentaire');
  change('Consignes', 'Consigne nouvelle');
  change(/^Ordre/, '2');
  change(/^Échéance \(heure locale\)/, '2026-12-01T16:30');
  change(/^Barème/, '10');
  save();
  await waitSaved();
  fireEvent.click(screen.getByRole('button', { name: 'Remplacer les membres actifs' }));
  const dialog = within(screen.getByRole('dialog'));
  fireEvent.click(dialog.getByText('Bob Durand').parentElement.querySelector('[data-testid="CancelIcon"]'));
  save();
  await waitSaved();
  expect(screen.getByText('Membres actifs : Alice Martin')).toBeInTheDocument();
  expect(screen.getByText(/Version 3/)).toBeInTheDocument();
});

it('creates an individual team with a named member and retains the empty team after removal', async () => {
  project = { ...project, mode: 'individuel' };
  const member = teams[0].membres[0];
  const emptyTeam = { ...teams[0], membres: [] };
  teams = [];
  postHandler = async (path, payload) => {
    if (path === `${detailPath}equipes/`) {
      expect(payload).toEqual({ version: 1, nom: 'Équipe solaire', membres: [11] });
      teams = [{ ...emptyTeam, membres: [member] }];
      project = { ...project, version: 2 };
      return { version: 2, equipe: teams[0] };
    }
    expect(path).toBe(`${teamPath}membres/`);
    expect(payload).toEqual({ version: 2, membres: [] });
    teams = [emptyTeam];
    project = { ...project, version: 3 };
    return { version: 3, equipe: emptyTeam };
  };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Nouvelle équipe' }));
  change(/^Nom de l’équipe/, 'Équipe solaire');
  await choose(/^Membres actifs/, 'Al', 'Alice Martin');
  save();
  await waitSaved();
  expect(screen.getByText('Membres actifs : Alice Martin')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Remplacer les membres actifs' }));
  const dialog = within(screen.getByRole('dialog'));
  fireEvent.click(dialog.getByText('Alice Martin').parentElement.querySelector('[data-testid="CancelIcon"]'));
  save();
  await waitSaved();
  expect(screen.getByText('Membres actifs : Aucun membre actif')).toBeInTheDocument();
  expect(screen.getByText(/Équipe vide : preuves conservées/)).toBeInTheDocument();
  expect(screen.getByLabelText('Équipe')).toHaveValue(teamId);
  expect(screen.queryByRole('button', { name: 'Déposer un PDF' })).not.toBeInTheDocument();
});

it('saves group and personal contributions as a draft before an explicit publication', async () => {
  postHandler = async (path, payload) => {
    if (path === `${teamPath}evaluations/`) {
      expect(payload).toEqual({
        version: 1,
        jalon: milestoneId,
        note_groupe: '16',
        commentaire: 'Travail collectif',
        contributions: [
          { membre: 11, note: '17', commentaire: 'Analyse personnelle' },
          { membre: 12, note: '15', commentaire: 'Expérimentation' },
        ],
      });
      const evaluation = {
        id: evaluationId,
        equipe: teamId,
        jalon: milestoneId,
        revision: 1,
        bareme: '20.00',
        note_groupe: payload.note_groupe,
        commentaire: payload.commentaire,
        contributions: payload.contributions,
        statut: 'brouillon',
        evalue_par: 92,
        created_at: '2026-11-07T10:00:00Z',
        publie_par: null,
        published_at: null,
      };
      evaluations = [evaluation];
      project = { ...project, version: 2 };
      return { version: 2, evaluation };
    }
    expect(path).toBe(`${teamPath}evaluations/${evaluationId}/publier/`);
    expect(payload).toEqual({ version: 2 });
    evaluations = [{
      ...evaluations[0], statut: 'publiee', published_at: '2026-11-07T11:00:00Z', publie_par: 92,
    }];
    project = { ...project, version: 3 };
    return { version: 3, evaluation: evaluations[0] };
  };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Nouveau brouillon d’évaluation' }));
  change(/^Note du groupe/, '16');
  change(/^Commentaire du groupe/, 'Travail collectif');
  change('Note de Alice Martin', '17');
  change(/^Contribution de Alice Martin/, 'Analyse personnelle');
  change('Note de Bob Durand', '15');
  change(/^Contribution de Bob Durand/, 'Expérimentation');
  save();
  await waitSaved();
  expect(screen.getByText('Brouillon non publié')).toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Publier cette évaluation' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer la publication' }));
  expect(await screen.findByText('Évaluation publiée.')).toBeInTheDocument();
  expect(screen.getByText('Publiée')).toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(2);
});

it('lets a learner submit a private PDF revision and download with the same session, without management buttons', async () => {
  canCreate = false;
  project = { ...project, actions: { can_manage: false, can_evaluate: false, can_submit: true } };
  teams = [{ ...teams[0], actions: project.actions }];
  const file = new File(['%PDF-1.4 test'], 'rapport.pdf', { type: 'application/pdf' });
  postHandler = async (path, payload) => {
    expect(path).toBe(`${teamPath}livrables/`);
    expect(payload).toBeInstanceOf(FormData);
    expect([...payload.keys()].sort()).toEqual(['commentaire', 'fichier', 'jalon', 'version']);
    expect(payload.get('version')).toBe('1');
    expect(payload.get('jalon')).toBe(milestoneId);
    expect(payload.get('fichier')).toBe(file);
    expect(payload.get('commentaire')).toBe('Ma remise');
    await new Promise(resolve => { pendingResolve = resolve; });
    const livrable = {
      id: deliveryId,
      equipe: teamId,
      jalon: milestoneId,
      nom: 'rapport.pdf',
      taille: file.size,
      sha256: 'a'.repeat(64),
      revision: 1,
      depose_par: 11,
      created_at: '2026-11-11T10:00:00Z',
      en_retard: true,
      commentaire: 'Ma remise',
    };
    deliveries = [livrable];
    project = { ...project, version: 2 };
    return { version: 2, livrable };
  };
  URL.createObjectURL = jest.fn(() => 'blob:private');
  URL.revokeObjectURL = jest.fn();
  const anchor = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  renderPage('secondaire');
  fireEvent.click(await screen.findByRole('button', { name: 'Déposer un PDF' }));
  ['Configurer le projet', 'Nouvelle équipe', 'Nouveau jalon', 'Remplacer les membres actifs', 'Nouveau brouillon d’évaluation'].forEach(name => {
    expect(screen.queryByRole('button', { name, hidden: true })).not.toBeInTheDocument();
  });
  fireEvent.change(screen.getByLabelText('Fichier PDF'), { target: { files: [file] } });
  change('Commentaire du dépôt', 'Ma remise');
  // jsdom does not update a file input's validity from a synthetic FileList.
  fireEvent.submit(screen.getByRole('dialog').querySelector('form'));
  await waitFor(() => expect(pendingResolve).not.toBeNull());
  expect(screen.getByRole('button', { name: 'Annuler' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Retour aux projets', hidden: true })).toBeDisabled();
  expect(screen.getByLabelText('Équipe')).toBeDisabled();
  expect(screen.getByLabelText('Jalon')).toBeDisabled();
  await act(async () => pendingResolve());
  await waitSaved();
  expect(screen.getByText('En retard')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger rapport.pdf (révision 1)' }));
  await waitFor(() => expect(anchor).toHaveBeenCalledTimes(1));
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private');
  expect(http.get).toHaveBeenCalledWith(`https://secondaire.test${teamPath}livrables/${deliveryId}/telecharger/`, { responseType: 'blob' });
});

it('shows only the published contribution returned for the learner without inventing teammates’ grades', async () => {
  canCreate = false;
  project = { ...project, actions: { can_manage: false, can_evaluate: false, can_submit: true } };
  teams = [{ ...teams[0], actions: project.actions }];
  evaluations = [{
    id: evaluationId,
    equipe: teamId,
    jalon: milestoneId,
    revision: 1,
    bareme: '20.00',
    note_groupe: '16.00',
    commentaire: 'Évaluation publiée au groupe',
    contributions: [{ membre: 11, note: '17.00', commentaire: 'Ma contribution personnelle' }],
    statut: 'publiee',
    evalue_par: 92,
    created_at: '2026-11-07T10:00:00Z',
    publie_par: 92,
    published_at: '2026-11-07T11:00:00Z',
  }];
  renderPage();
  const evaluation = within(await screen.findByRole('region', { name: 'Évaluation révision 1' }));
  expect(evaluation.getByText('Note du groupe : 16.00 / 20.00')).toBeInTheDocument();
  expect(evaluation.getByText('Alice Martin : 17.00 / 20.00')).toBeInTheDocument();
  expect(evaluation.getByText('Ma contribution personnelle')).toBeInTheDocument();
  expect(evaluation.queryByText(/Bob Durand/)).not.toBeInTheDocument();
  expect(evaluation.queryByText('Brouillon non publié')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Publier|brouillon d’évaluation/ })).not.toBeInTheDocument();
});

it.each([400, 409, 500])('preserves failed drafts and never claims success for HTTP %s', async status => {
  postHandler = async () => { throw failure(status); };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Nouveau jalon' }));
  change(/^Titre du jalon/, 'Mon brouillon conservé');
  change(/^Ordre/, '2');
  change(/^Échéance \(heure locale\)/, '2026-12-01T16:30');
  save();
  expect(await screen.findByText(new RegExp(`Refus serveur ${status}`))).toBeInTheDocument();
  expect(screen.getByLabelText(/^Titre du jalon/)).toHaveValue('Mon brouillon conservé');
  expect(screen.queryByText('Enregistrement confirmé par le serveur.')).not.toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
  if (status === 409) {
    expect(screen.getByText(/Aucun renvoi automatique/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled();
    project = { ...project, version: 8 };
    fireEvent.click(screen.getByRole('button', { name: 'Recharger le projet sans effacer les saisies' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeEnabled());
    expect(screen.getByLabelText(/^Titre du jalon/)).toHaveValue('Mon brouillon conservé');
    expect(http.post).toHaveBeenCalledTimes(1);
    save();
    await waitFor(() => expect(http.post).toHaveBeenCalledTimes(2));
    expect(http.post.mock.calls[1][1].version).toBe(8);
  }
});

it.each([undefined, {}, { 'sis.projects': false }])('denies a direct project URL when module flags are %j', async flags => {
  modules = flags;
  renderPage();
  expect(await screen.findByText(/module Projets pédagogiques est désactivé/)).toBeInTheDocument();
  expect(http.get.mock.calls).toHaveLength(1);
  expect(screen.queryByText('Description privée')).not.toBeInTheDocument();
});

it('rejects an invalid command response rather than reporting a simulated success', async () => {
  postHandler = async (path, payload) => {
    expect(path).toBe(`${detailPath}configurer/`);
    expect(payload).toEqual({ version: 1, titre: 'Titre non confirmé', description: 'Description privée' });
    return { version: 2 };
  };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Configurer le projet' }));
  change(/^Titre du projet/, 'Titre non confirmé');
  save();
  expect(await screen.findByText(/Réponse de commande invalide/)).toBeInTheDocument();
  expect(screen.getByLabelText(/^Titre du projet/)).toHaveValue('Titre non confirmé');
  expect(screen.queryByText('Enregistrement confirmé par le serveur.')).not.toBeInTheDocument();
});

it('closes an already open detail when the module is withdrawn', async () => {
  const { client } = renderPage();
  expect(await screen.findByText('Description privée')).toBeInTheDocument();
  modules = {};
  await act(async () => client.invalidateQueries({ queryKey: ['capabilities', 'superieur'] }));
  expect(await screen.findByText(/module Projets pédagogiques est désactivé/)).toBeInTheDocument();
  expect(screen.queryByText('Description privée')).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['projects'] })).toHaveLength(0);
});

it.each([403, 404])('hides private cached data on current access refusal %s', async status => {
  renderPage();
  expect(await screen.findByText('Description privée')).toBeInTheDocument();
  await screen.findByText('Aucun livrable pour ce jalon.');
  getFailure = path => { if (path === `${teamPath}evaluations/`) { throw failure(status); } };
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser le projet' }));
  expect(await screen.findByText(/Accès aux projets refusé/)).toBeInTheDocument();
  expect(screen.queryByText('Description privée')).not.toBeInTheDocument();
  expect(screen.queryByText(/Membres actifs :/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Nouvelle équipe' })).not.toBeInTheDocument();
});
