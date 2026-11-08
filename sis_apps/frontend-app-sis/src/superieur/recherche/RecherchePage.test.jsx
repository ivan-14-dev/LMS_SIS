import React from 'react';
import {
  act, fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import RecherchePage from './RecherchePage';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({ SIS_SUPERIEUR_API_URL: 'https://university.test/api/v1' }),
}));
jest.mock('@edx/frontend-platform/auth', () => ({ getAuthenticatedHttpClient: jest.fn() }));
jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));

const base = '/api/v1/recherche/';
const page = (results, extra = {}) => ({
  count: results.length, results, next: null, previous: null, ...extra,
});
const failure = (status, data = { detail: `Erreur serveur ${status}` }) => ({ response: { status, data } });
const teacher = { id: 21, nom: 'Chercheuse locale' };
const lab = {
  id: 4, nom: 'Laboratoire local', acronyme: 'LOCAL', version: 1, can_manage: true, can_archiver: false,
};
let project;
let profile;
let globalCaps;
let caps;
let milestones;
let publications;
let operations;
let report;
let getOverride;
let postOverride;
let patchOverride;
let http;
const clients = [];

const renderPage = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}><MemoryRouter><RecherchePage /></MemoryRouter></QueryClientProvider>,
    ),
  };
};
const change = (label, value, root = screen) => fireEvent.change(
  root.getByLabelText(label, { exact: false, selector: 'input,textarea,select' }),
  { target: { value } },
);
const openProject = async () => {
  fireEvent.click(await screen.findByRole('button', { name: 'Projet Alpha', exact: true }));
  await screen.findByRole('heading', { name: 'Projet Alpha', exact: true });
};
const form = name => within(screen.getByRole('form', { name }));
const fillFinance = async () => {
  fireEvent.click(await screen.findByRole('button', { name: 'Nouvelle opération financière' }));
  const root = form('Enregistrer une opération financière');
  change('Nature de l’opération', 'financement', root);
  change('Montant exact', '100.05', root);
  change('Référence unique', 'GRANT-EXPLICIT-2026', root);
  change('Date de l’opération', '2026-01-03', root);
  change('Libellé / motif', 'Réception confirmée par le service habilité', root);
  const proof = new File(['%PDF-1.7\nproof'], 'preuve.pdf', { type: 'application/pdf' });
  fireEvent.change(root.getByLabelText('Justificatif obligatoire', { exact: false }), { target: { files: [proof] } });
  fireEvent.click(root.getByRole('checkbox', { name: /Je confirme cette opération humaine/ }));
  return { root, proof };
};

beforeEach(() => {
  globalCaps = { modules: { 'sis.research': true }, permissions: ['recherche.gerer_recherche'] };
  profile = {
    id: 1, etablissement: 8, role: 'etudiant', is_staff: false,
  };
  caps = {
    can_create_laboratoire: true, can_create_projet: true, can_manage: true, can_contribute: true, can_finance: false,
  };
  project = {
    id: 7,
    titre: 'Projet Alpha',
    description: 'Description académique privée',
    laboratoire: lab.id,
    laboratoire_nom: lab.acronyme,
    responsable: teacher.id,
    responsable_nom: teacher.nom,
    membres_list: [teacher],
    budget: '5000.00',
    date_debut: '2026-01-01',
    date_fin: '2027-12-31',
    version: 3,
    statut: 'en_cours',
    archive: false,
    can_manage: true,
    can_read_academic: true,
    can_contribute: true,
    can_finance: false,
    can_terminer: false,
  };
  milestones = [{
    id: 30, titre: 'Rapport intermédiaire', description: 'Première analyse', echeance: '2026-06-01', statut: 'a_faire', livrables: [],
  }];
  publications = [];
  operations = [];
  report = {
    projet_id: 7,
    devise: 'EUR',
    budget: '5000.00',
    encaissements: '0.00',
    depenses: '0.00',
    engagements_ouverts: '0.00',
    disponible_budgetaire: '5000.00',
    solde_tresorerie: '0.00',
    total_debit: '0.00',
    total_credit: '0.00',
    rapproche: true,
    version: 3,
  };
  getOverride = () => undefined;
  postOverride = async () => ({ ...project, version: project.version + 1 });
  patchOverride = async (path, payload) => {
    project = { ...project, ...payload, version: project.version + 1 };
    return project;
  };
  http = {
    get: jest.fn(async (url, options) => {
      const parsed = new URL(url);
      const path = parsed.pathname;
      const override = getOverride(path, parsed.searchParams, options);
      if (override !== undefined) { return { data: await override }; }
      if (path.endsWith('/utilisateurs/comptes/capabilities/')) { return { data: globalCaps }; }
      if (path.endsWith('/utilisateurs/comptes/me/')) { return { data: profile }; }
      if (path === `${base}projets-recherche/capacites/`) { return { data: caps }; }
      if (path === `${base}projets-recherche/`) { return { data: page([project]) }; }
      if (path === `${base}projets-recherche/7/`) { return { data: project }; }
      if (path === `${base}laboratoires/`) { return { data: page([lab]) }; }
      if (path === `${base}laboratoires/selecteurs/`) { return { data: page(parsed.searchParams.get('type') === 'enseignants' ? [teacher] : []) }; }
      if (path === `${base}projets-recherche/7/jalons/`) { return { data: page(milestones) }; }
      if (path === `${base}productions-scientifiques/`) { return { data: page(publications) }; }
      if (path === `${base}theses/`) { return { data: page([]) }; }
      if (path === `${base}projets-recherche/7/rapport-financier/`) { return { data: report }; }
      if (path === `${base}projets-recherche/7/operations-financieres/`) { return { data: page(operations) }; }
      throw new Error(`Unexpected GET ${url}`);
    }),
    post: jest.fn(async (url, payload) => ({ data: await postOverride(new URL(url).pathname, payload) })),
    patch: jest.fn(async (url, payload) => ({ data: await patchOverride(new URL(url).pathname, payload) })),
  };
  getAuthenticatedHttpClient.mockReturnValue(http);
});
afterEach(() => { clients.splice(0).forEach(client => client.clear()); });

it('gates collections behind real capabilities and prevents staff/role fallback when the module is disabled', async () => {
  globalCaps.modules['sis.research'] = false;
  profile = { ...profile, role: 'administrateur', is_staff: true };
  renderPage();
  expect(await screen.findByText('Le module Recherche est désactivé ou indisponible.')).toBeVisible();
  expect(http.get.mock.calls.some(([url]) => url.includes('/recherche/'))).toBe(false);
  expect(http.post).not.toHaveBeenCalled();
});

it('denies an enabled module without an explicit research grant before loading profile or research data', async () => {
  globalCaps = {
    modules: { 'sis.research': true }, permissions: [], role: 'doyen', is_staff: true,
  };
  profile = { ...profile, role: 'administrateur', is_staff: true };
  renderPage();
  expect(await screen.findByText('Vous n’avez pas la permission d’accéder à ce module.')).toBeVisible();
  expect(http.get.mock.calls.map(([url]) => new URL(url).pathname)).toEqual([
    '/api/v1/utilisateurs/comptes/capabilities/',
  ]);
  expect(http.post).not.toHaveBeenCalled();
});

it('removes private data when the explicit grant is revoked', async () => {
  const { client } = renderPage();
  await openProject();
  expect(screen.getByText('Description académique privée')).toBeVisible();
  globalCaps = {
    ...globalCaps, permissions: [], role: 'doyen', is_staff: true,
  };
  await act(async () => { await client.invalidateQueries({ queryKey: ['capabilities', 'superieur'] }); });
  expect(await screen.findByText('Vous n’avez pas la permission d’accéder à ce module.')).toBeVisible();
  expect(screen.queryByText('Description académique privée')).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['research'] })).toHaveLength(0);
});

it('loads real selector pages and creates a project with exact decimal budget and selected local relations', async () => {
  getOverride = (path, params) => {
    if (path === `${base}laboratoires/selecteurs/` && params.get('type') === 'enseignants') {
      return params.get('page') === '2' ? page([teacher], { count: 2, previous: 'https://university.test/previous' })
        : page([{ id: 22, nom: 'Autre chercheur' }], { count: 2, next: 'https://university.test/next' });
    }
    return undefined;
  };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Créer — Projets' }));
  const root = form('Créer le projet');
  change('Titre du projet', 'Recherche réelle', root);
  change('Description du projet', 'Protocole', root);
  change('Budget (EUR)', '2500.10', root);
  change('Date de début', '2026-01-01', root);
  change('Date de fin', '2027-01-01', root);
  fireEvent.click(await root.findByRole('button', { name: 'Choisir Laboratoire local' }));
  const lead = within(root.getByRole('group', { name: 'Responsable du projet' }));
  fireEvent.click(await lead.findByRole('button', { name: 'Page suivante' }));
  fireEvent.click(await lead.findByRole('button', { name: 'Choisir Chercheuse locale' }));
  fireEvent.click(root.getByRole('button', { name: 'Confirmer — Créer le projet' }));
  await waitFor(() => expect(http.post).toHaveBeenCalledWith(
    expect.stringContaining('/projets-recherche/'),
    expect.objectContaining({
      laboratoire: 4, responsable: 21, budget: '2500.10', membres: [],
    }),
    expect.anything(),
  ));
  expect(http.get.mock.calls.findIndex(([url]) => url.includes('/capacites/')))
    .toBeLessThan(http.get.mock.calls.findIndex(([url]) => url.includes('/projets-recherche/?')));
});

it('preserves metadata on a stale version and uses the new version only after explicit reread confirmation', async () => {
  patchOverride = async (path, payload) => {
    if (payload.version === 3) { project = { ...project, version: 4, titre: 'Titre serveur concurrent' }; throw failure(409); }
    project = { ...project, ...payload, version: 5 };
    return project;
  };
  renderPage();
  await openProject();
  fireEvent.click(screen.getByRole('button', { name: 'Modifier les métadonnées' }));
  const root = form('Modifier le projet');
  change('Titre du projet', 'Mon titre conservé', root);
  fireEvent.click(root.getByRole('button', { name: 'Confirmer — Modifier le projet' }));
  await root.findByText(/Conflit : état/);
  expect(root.getByLabelText('Titre du projet', { exact: false })).toHaveValue('Mon titre conservé');
  fireEvent.click(root.getByRole('button', { name: 'Relire la version actuelle sans effacer ma saisie' }));
  fireEvent.click(await root.findByRole('button', { name: 'Utiliser explicitement cette version' }));
  expect(root.getByLabelText('Titre du projet', { exact: false })).toHaveValue('Mon titre conservé');
  fireEvent.click(root.getByRole('button', { name: 'Confirmer — Modifier le projet' }));
  await waitFor(() => expect(http.patch).toHaveBeenLastCalledWith(expect.any(String), expect.objectContaining({ titre: 'Mon titre conservé', version: 4 }), expect.anything()));
  expect(await screen.findByRole('heading', { name: 'Mon titre conservé' })).toBeVisible();
});

it('allows an explicit student contributor to upload a real immutable PDF revision but never financial controls', async () => {
  globalCaps.permissions = ['recherche.contribuer_recherche'];
  caps = {
    ...caps, can_manage: false, can_create_projet: false, can_create_laboratoire: false,
  };
  project = { ...project, can_manage: false };
  postOverride = async (path, body) => {
    expect(path).toBe(`${base}projets-recherche/7/livrables/`);
    milestones = [{
      ...milestones[0],
      statut: 'soumis',
      livrables: [{
        id: 45,
        revision: 1,
        nom: 'analyse.pdf',
        taille: 19,
        sha256: 'abc123',
        commentaire: body.get('commentaire'),
        created_at: '2026-06-01T10:00:00Z',
      }],
    }];
    project = { ...project, version: 4 };
    return project;
  };
  renderPage();
  await openProject();
  expect(screen.queryByText('Finances du projet — EUR')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Modifier les métadonnées' })).not.toBeInTheDocument();
  fireEvent.click(await screen.findByRole('button', { name: 'Déposer pour Rapport intermédiaire' }));
  const root = form('Déposer une révision PDF');
  const file = new File(['%PDF-1.7\nanalysis'], 'analyse.pdf', { type: 'application/pdf' });
  fireEvent.change(root.getByLabelText('Livrable PDF', { exact: false }), { target: { files: [file] } });
  change('Commentaire de la révision', 'Version relue', root);
  fireEvent.submit(screen.getByRole('form', { name: 'Déposer une révision PDF' }));
  expect(await screen.findByText('Révision 1 — analyse.pdf')).toBeVisible();
  const sent = http.post.mock.calls[0][1];
  expect(sent).toBeInstanceOf(FormData);
  expect(sent.get('fichier')).toBe(file);
  expect(sent.get('version')).toBe('3');
  expect(sent.get('jalon')).toBe('30');
  expect(http.get.mock.calls.some(([url]) => /rapport-financier|operations-financieres/.test(url))).toBe(false);
});

it('shows only minimal financial metadata to finance-only actors and serializes/replays identical exact input', async () => {
  globalCaps.permissions = ['recherche.comptabiliser_recherche'];
  caps = {
    ...caps,
    can_manage: false,
    can_contribute: false,
    can_finance: true,
    can_create_projet: false,
    can_create_laboratoire: false,
  };
  project = {
    ...project, can_manage: false, can_read_academic: false, can_contribute: false, can_finance: true,
  };
  let first = true;
  postOverride = async (path, payload) => {
    if (first) { first = false; throw new Error('Connexion interrompue après envoi'); }
    operations = [{
      id: '61874fa9-2496-4882-b7be-b719a20c043d',
      type: 'financement',
      montant: payload.get('montant'),
      reference: payload.get('reference'),
      date_operation: '2026-01-03',
      libelle: 'Encaissement',
      justificatif_nom: 'preuve.pdf',
      justificatif_sha256: 'test-digest',
      lignes: [],
    }];
    project = { ...project, version: 4 };
    report = {
      ...report, encaissements: '100.05', solde_tresorerie: '100.05', total_debit: '100.05', total_credit: '100.05', version: 4,
    };
    return { operation: operations[0], version: 4, replayed: true };
  };
  renderPage();
  await openProject();
  expect(screen.queryByText('Description académique privée')).not.toBeInTheDocument();
  const { root, proof } = await fillFinance();
  fireEvent.submit(screen.getByRole('form', { name: 'Enregistrer une opération financière' }));
  await root.findByText(/Connexion interrompue/);
  expect(screen.queryByText(/Opération enregistrée/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Journal rapproché par le serveur/)).not.toBeInTheDocument();
  fireEvent.click(root.getByRole('button', { name: 'Rejouer exactement cette opération' }));
  expect(await root.findByText(/Rejeu reconnu, sans nouvelle écriture/)).toBeVisible();
  const firstBody = http.post.mock.calls[0][1];
  const secondBody = http.post.mock.calls[1][1];
  expect(firstBody.get('montant')).toBe('100.05');
  expect(firstBody.get('justificatif')).toBe(proof);
  expect(firstBody.get('idempotency_key')).toMatch(/^[a-f0-9-]{36}$/);
  expect(Array.from(secondBody.entries())).toEqual(Array.from(firstBody.entries()));
  expect(http.get.mock.calls.some(([url]) => /\/(theses|productions-scientifiques|jalons)\//.test(url))).toBe(false);
});

it('does not display cached balances after financial reconciliation errors', async () => {
  globalCaps.permissions = ['recherche.gerer_recherche', 'recherche.comptabiliser_recherche'];
  project = { ...project, can_finance: true };
  let corrupt = false;
  getOverride = path => {
    if (corrupt && path.endsWith('/rapport-financier/')) { return Promise.reject(failure(409, { detail: 'Journal incohérent' })); }
    return undefined;
  };
  const { client } = renderPage();
  await openProject();
  expect(await screen.findByText(/Journal rapproché par le serveur/)).toBeVisible();
  corrupt = true;
  await act(async () => { await client.invalidateQueries({ queryKey: ['research'] }); });
  expect(await screen.findByText(/Journal incohérent/)).toBeVisible();
  expect(screen.queryByText(/Journal rapproché par le serveur/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Nouvelle opération financière' })).toBeDisabled();
});

it('purges academic data on a private download denial and uses authenticated blob HTTP, never a storage link', async () => {
  globalCaps.permissions = ['recherche.consulter_recherche'];
  caps = {
    ...caps, can_manage: false, can_create_projet: false, can_create_laboratoire: false, can_contribute: false,
  };
  project = { ...project, can_manage: false, can_contribute: false };
  publications = [{
    id: 60, titre: 'Publication publiée', statut: 'publiee', can_manage: false, fichier: '/api/v1/recherche/productions-scientifiques/60/fichier/',
  }];
  getOverride = path => {
    if (path === `${base}productions-scientifiques/60/`) { return publications[0]; }
    if (path === `${base}productions-scientifiques/60/fichier/`) { return Promise.reject(failure(403)); }
    return undefined;
  };
  renderPage();
  await openProject();
  fireEvent.click(await screen.findByRole('button', { name: 'Publication publiée', exact: true }));
  fireEvent.click(await screen.findByRole('button', { name: 'Télécharger le PDF privé' }));
  expect(await screen.findByText(/Accès refusé ou module Recherche désactivé/)).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'Publication publiée' })).not.toBeInTheDocument();
  expect(http.get).toHaveBeenCalledWith(
    expect.stringContaining('/productions-scientifiques/60/fichier/'),
    expect.objectContaining({ responseType: 'blob', signal: expect.anything() }),
  );
});

it('discards late private responses when the active identity changes', async () => {
  let resolveDetail;
  getOverride = path => {
    if (path === `${base}projets-recherche/7/`) { return new Promise(resolve => { resolveDetail = resolve; }); }
    return undefined;
  };
  const { client } = renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Projet Alpha', exact: true }));
  await waitFor(() => expect(resolveDetail).toBeDefined());
  const old = project;
  profile = { ...profile, id: 2, etablissement: 9 };
  project = { ...project, id: 8, titre: 'Projet nouvel établissement' };
  await act(async () => { await client.invalidateQueries({ queryKey: ['profile'] }); });
  await act(async () => { resolveDetail(old); });
  expect(await screen.findByRole('button', { name: 'Projet nouvel établissement' })).toBeVisible();
  expect(screen.queryByText('Description académique privée')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Projet Alpha' })).not.toBeInTheDocument();
});

it('creates a PDF publication from real project authors and performs versioned validation then publication', async () => {
  let publication;
  getOverride = path => (path === `${base}productions-scientifiques/61/` ? publication : undefined);
  postOverride = async (path, body) => {
    if (path === `${base}productions-scientifiques/`) {
      expect(body).toBeInstanceOf(FormData);
      expect(body.getAll('auteurs')).toEqual(['21']);
      expect(body.get('projet')).toBe('7');
      expect(body.get('laboratoire')).toBe('4');
      expect(body.get('fichier').name).toBe('article.pdf');
      publication = {
        id: 61,
        titre: body.get('titre'),
        projet: 7,
        laboratoire: 4,
        projet_titre: project.titre,
        auteurs_list: [teacher],
        annee: '2026',
        version: 1,
        statut: 'brouillon',
        can_manage: true,
        fichier: '/api/v1/recherche/productions-scientifiques/61/fichier/',
      };
    } else {
      expect(body.version).toBe(publication.version);
      publication = { ...publication, version: publication.version + 1, statut: path.endsWith('/valider/') ? 'validee' : 'publiee' };
    }
    publications = [publication];
    project = { ...project, version: project.version + 1 };
    return publication;
  };
  renderPage();
  await openProject();
  fireEvent.click(screen.getByRole('button', { name: 'Nouvelle publication liée' }));
  const root = form('Créer la publication');
  change('Titre de la publication', 'Article avec preuve', root);
  change('Année de publication', '2026', root);
  const authors = within(root.getByRole('group', { name: 'Auteurs du projet' }));
  fireEvent.click(await authors.findByRole('button', { name: 'Choisir Chercheuse locale' }));
  const pdf = new File(['%PDF-1.7\narticle'], 'article.pdf', { type: 'application/pdf' });
  fireEvent.change(root.getByLabelText('PDF de la publication'), { target: { files: [pdf] } });
  fireEvent.submit(screen.getByRole('form', { name: 'Créer la publication' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Article avec preuve', exact: true }));
  fireEvent.click(await screen.findByRole('button', { name: 'Valider la publication', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer — Valider la publication' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Publier la publication', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer — Publier la publication' }));
  expect(await screen.findByRole('button', { name: 'Archiver la publication' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Modifier les métadonnées' })).not.toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(3);
});

it('creates local supervision and submits an explicit dated defense using the current thesis version', async () => {
  let thesis;
  getOverride = (path, params) => {
    if (path === `${base}laboratoires/selecteurs/` && params.get('type') === 'etudiants') {
      return page([{ id: 70, nom: 'Doctorante active' }]);
    }
    if (path === `${base}theses/`) { return page(thesis ? [thesis] : []); }
    if (path === `${base}theses/71/`) { return thesis; }
    return undefined;
  };
  postOverride = async (path, body) => {
    if (path === `${base}theses/`) {
      expect(body).toEqual(expect.objectContaining({
        projet: 7,
        laboratoire: 4,
        doctorant: 70,
        directeur: 21,
        co_directeur: null,
        date_debut: '2026-02-01',
      }));
      thesis = {
        ...body,
        id: 71,
        version: 1,
        statut: 'en_cours',
        can_manage: true,
        doctorant_nom: 'Doctorante active',
        directeur_nom: teacher.nom,
      };
    } else {
      expect(path).toBe(`${base}theses/71/soutenir/`);
      expect(body).toEqual({ version: 1, date_soutenance: '2026-10-01' });
      thesis = {
        ...thesis, ...body, statut: 'soutenue', version: 2,
      };
    }
    return thesis;
  };
  renderPage();
  await openProject();
  fireEvent.click(screen.getByRole('button', { name: 'Nouvelle thèse liée' }));
  const root = form('Créer la thèse');
  change('Titre de la thèse', 'Thèse doctorale locale', root);
  change('Résumé', 'Recherche suivie', root);
  change('Date de début de thèse', '2026-02-01', root);
  fireEvent.click(await root.findByRole('button', { name: 'Choisir Doctorante active' }));
  const director = within(root.getByRole('group', { name: 'Directeur de thèse' }));
  fireEvent.click(await director.findByRole('button', { name: 'Choisir Chercheuse locale' }));
  fireEvent.click(root.getByRole('button', { name: 'Confirmer — Créer la thèse' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Thèse doctorale locale', exact: true }));
  fireEvent.click(await screen.findByRole('button', { name: 'Enregistrer la soutenance', exact: true }));
  change('Date de soutenance', '2026-10-01', form('Enregistrer la soutenance'));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer — Enregistrer la soutenance' }));
  expect(await screen.findByRole('button', { name: 'Archiver la thèse' })).toBeVisible();
});

it('keeps entered metadata and the actual project state after field validation and server errors', async () => {
  patchOverride = async () => { throw failure(400, { titre: ['Titre déjà utilisé dans ce périmètre.'] }); };
  renderPage();
  await openProject();
  fireEvent.click(screen.getByRole('button', { name: 'Modifier les métadonnées' }));
  const root = form('Modifier le projet');
  change('Titre du projet', 'Titre conservé en erreur', root);
  fireEvent.click(root.getByRole('button', { name: 'Confirmer — Modifier le projet' }));
  expect(await root.findByText(/Titre déjà utilisé/)).toBeVisible();
  expect(root.getByLabelText('Titre du projet', { exact: false })).toHaveValue('Titre conservé en erreur');
  patchOverride = async () => { throw failure(500, { detail: 'Indisponibilité du stockage' }); };
  fireEvent.click(root.getByRole('button', { name: 'Confirmer — Modifier le projet' }));
  expect(await root.findByText(/Indisponibilité du stockage/)).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Projet Alpha', exact: true })).toBeVisible();
  expect(screen.queryByText(/Commande reçue par le serveur/)).not.toBeInTheDocument();
});

it('rejects malformed financial amounts locally and preserves an expense commitment and UUID through stale-version replay', async () => {
  globalCaps.permissions = ['recherche.gerer_recherche', 'recherche.comptabiliser_recherche'];
  project = { ...project, can_finance: true };
  operations = [{
    id: '61874fa9-2496-4882-b7be-b719a20c043d',
    type: 'engagement',
    montant: '500.00',
    reference: 'ENG-EXISTANT',
    justificatif_nom: 'engagement.pdf',
    lignes: [],
  }];
  let first = true;
  postOverride = async (path, body) => {
    if (first) { first = false; project = { ...project, version: 4 }; throw failure(409); }
    project = { ...project, version: 5 };
    report = { ...report, version: 5 };
    return {
      operation: { id: '61874fa9-2496-4882-b7be-b719a20c043e', reference: body.get('reference'), montant: body.get('montant') },
      version: 5,
      replayed: false,
    };
  };
  renderPage();
  await openProject();
  const { root } = await fillFinance();
  change('Nature de l’opération', 'depense', root);
  fireEvent.click(await root.findByRole('button', { name: 'Choisir ENG-EXISTANT — 500.00 EUR' }));
  change('Montant exact', '1e2', root);
  fireEvent.submit(screen.getByRole('form', { name: 'Enregistrer une opération financière' }));
  expect(await root.findByText(/Montant invalide/)).toBeVisible();
  expect(http.post).not.toHaveBeenCalled();
  change('Montant exact', '0.30', root);
  fireEvent.submit(screen.getByRole('form', { name: 'Enregistrer une opération financière' }));
  fireEvent.click(await root.findByRole('button', { name: 'Relire la version du projet' }));
  fireEvent.click(await root.findByRole('button', { name: 'Utiliser cette version pour le rejeu' }));
  fireEvent.click(root.getByRole('button', { name: 'Rejouer exactement cette opération' }));
  expect(await root.findByText(/Opération enregistrée/)).toBeVisible();
  const firstBody = http.post.mock.calls[0][1];
  const nextBody = http.post.mock.calls[1][1];
  expect(nextBody.get('engagement')).toBe(operations[0].id);
  expect(nextBody.get('montant')).toBe('0.30');
  expect(nextBody.get('version')).toBe('4');
  expect(firstBody.get('idempotency_key')).toBe(nextBody.get('idempotency_key'));
});
