import React from 'react';
import {
  act, fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import PracticalTrainingPage from './PracticalTrainingPage';
import {
  actor, assessment, audit, evidence, fingerprint, hour, page, partner, scenario, stamp,
} from './practicalTestData';
import { checked, checkedCommand, practicalPermissions } from './practicalContract';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_SUPERIEUR_API_URL: 'https://upper.test/api/v1',
    SIS_SECONDAIRE_API_URL: 'https://secondary.test/api/v1',
  }),
}));
jest.mock('@edx/frontend-platform/auth', () => ({ getAuthenticatedHttpClient: jest.fn() }));
jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));

const base = '/api/v1/stages/pratique/';
const failure = (status, data = {}) => ({
  response: {
    status,
    data: {
      detail: `Erreur ${status}`, code: 'permission_denied', errors: {}, current_version: null, criteres_non_satisfaits: [], ...data,
    },
  },
});
const clients = [];
let state;
let globalCaps;
let profile;
let http;
let getOverride;
let postOverride;
const clone = value => JSON.parse(JSON.stringify(value));
const renderPage = (variant = 'superieur', route = `/${variant}/stages-pratiques`) => {
  state.capabilities.variant = variant;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}><PracticalTrainingPage variant={variant} /></MemoryRouter>
      </QueryClientProvider>,
    ),
  };
};
const change = (label, value, root = screen) => fireEvent.change(root.getByLabelText(label, { exact: false, selector: 'input,textarea,select' }), { target: { value } });
const form = name => within(screen.getByRole('form', { name }));
const openDossier = async () => {
  fireEvent.click(await screen.findByRole('button', { name: /Ouvrir le dossier de Camille/ }));
  await screen.findByRole('heading', { name: 'Camille Apprenant — Pratique professionnelle' });
};
const openProgramme = async () => {
  fireEvent.click(await screen.findByRole('button', { name: /Ouvrir le programme Pratique professionnelle/ }));
  await screen.findByRole('heading', { name: 'Pratique professionnelle', exact: true });
};
const bump = (action = 'heure_creation') => {
  state.dossier.version += 1;
  state.report.version = state.dossier.version;
  state.history.unshift(audit(state.dossier.version, action));
};
const dossierMutation = () => ({
  version: state.dossier.version, dossier: clone(state.dossier), rapport: clone(state.report), heures_annulees: [],
});
const confirm = title => fireEvent.click(form(title).getByRole('button', { name: `Confirmer — ${title}` }));
const pdf = () => new File(['%PDF-1.7\nprivate evidence'], 'preuve.pdf', { type: 'application/pdf' });
const deferred = () => {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
};

beforeEach(() => {
  state = scenario();
  globalCaps = {
    permissions: [...practicalPermissions],
    modules: { 'sis.practical_training': true },
    role: 'etudiant',
    attributes: { permission_scopes: {} },
  };
  profile = {
    id: 8, etablissement: 1, role: 'etudiant', is_staff: false, contact_entreprise: 16,
  };
  getOverride = () => undefined;
  postOverride = async () => { throw new Error('Unexpected POST'); };
  http = {
    get: jest.fn(async (url, options) => {
      const parsed = new URL(url);
      const path = parsed.pathname;
      const override = getOverride(path, parsed.searchParams, options);
      if (override !== undefined) { return { data: await override }; }
      if (path.endsWith('/utilisateurs/comptes/capabilities/')) { return { data: clone(globalCaps) }; }
      if (path.endsWith('/utilisateurs/comptes/me/')) { return { data: clone(profile) }; }
      const routes = {
        'capacites/': state.capabilities,
        'curriculums/': page([state.curriculum]),
        'programmes/': page([state.programme]),
        'programmes/10/': state.programme,
        'programmes/10/revisions/': page(state.revisions),
        'programmes/10/historique/': page(state.programmeHistory),
        'programmes/10/conventions/': page([state.convention]),
        'programmes/10/conventions/14/partenaires/': page([{
          utilisateur: partner, can_consult: true, can_validate: true, can_evaluate: true,
        }]),
        'dossiers/': page([state.dossier]),
        'dossiers/20/': state.dossier,
        'dossiers/20/rapport/': state.report,
        'dossiers/20/heures/': page(state.hours),
        'dossiers/20/heures/31/': state.hours.find(item => item.id === 31),
        'dossiers/20/heures/31/decisions/': page([state.hours[0]?.derniere_decision]),
        'dossiers/20/evaluations/': page(state.evaluations),
        'dossiers/20/historique/': page(state.history),
      };
      const data = routes[path.slice(base.length)];
      if (path.startsWith(base) && data) { return { data: clone(data) }; }
      throw new Error(`Unexpected GET ${url}`);
    }),
    post: jest.fn(async (url, payload) => ({ data: clone(await postOverride(new URL(url).pathname, payload)) })),
  };
  getAuthenticatedHttpClient.mockReturnValue(http);
});
afterEach(() => {
  focusManager.setFocused(undefined);
  clients.splice(0).forEach(client => client.clear());
  jest.restoreAllMocks();
});

it.each(['secondaire', 'superieur'])('groups empty %s programme and dossier controls without a zero-result pagination', async variant => {
  getOverride = path => ([`${base}programmes/`, `${base}dossiers/`].includes(path) ? page([]) : undefined);
  renderPage(variant);
  expect(await screen.findByText(/Aucun programme dans votre périmètre/)).toBeVisible();
  expect(await screen.findByText(/Aucun dossier visible/)).toBeVisible();
  const dossiers = within(screen.getByRole('region', { name: 'Dossiers autorisés' }));
  expect(dossiers.getByRole('combobox', { name: 'État des dossiers' })).toBeVisible();
  expect(dossiers.getByRole('option', { name: 'Tous les états' }).selected).toBe(true);
  expect(dossiers.getByRole('search', { name: 'Recherche — Dossiers autorisés' })).toBeVisible();
  expect(screen.queryByRole('navigation', { name: /Pagination/ })).not.toBeInTheDocument();
  expect(http.post).not.toHaveBeenCalled();
});

it('keeps state filtering and keyboard search working inside the dossier panel', async () => {
  renderPage();
  await screen.findByRole('button', { name: /Ouvrir le dossier de Camille/ });
  let dossiers = within(screen.getByRole('region', { name: 'Dossiers autorisés' }));
  change('État des dossiers', 'clos', dossiers);
  await waitFor(() => expect(http.get.mock.calls.some(([url]) => url.includes('dossiers/?statut=clos&page=1'))).toBe(true));
  dossiers = within(screen.getByRole('region', { name: 'Dossiers autorisés' }));
  const search = dossiers.getByRole('textbox', { name: 'Rechercher — Dossiers autorisés' });
  fireEvent.change(search, { target: { value: '  Camille  ' } });
  fireEvent.keyDown(search, { key: 'Enter' });
  await waitFor(() => expect(http.get.mock.calls.some(([url]) => (
    url.includes('dossiers/?statut=clos&page=1&page_size=20&q=Camille')
  ))).toBe(true));
  expect(http.post).not.toHaveBeenCalled();
});

it('does not submit the enclosing programme form when searching curriculum choices with Enter', async () => {
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Nouveau programme pratique' }));
  const editor = form('Créer le programme');
  const search = editor.getByRole('textbox', { name: 'Rechercher — Cursus autorisés' });
  fireEvent.change(search, { target: { value: 'Formation' } });
  expect(fireEvent.keyDown(search, { key: 'Enter', cancelable: true })).toBe(false);
  await waitFor(() => expect(http.get.mock.calls.some(([url]) => url.includes('curriculums/?page=1&page_size=20&q=Formation'))).toBe(true));
  expect(http.post).not.toHaveBeenCalled();
});

it.each(['secondaire', 'superieur'])('gates the %s module default OFF without role/staff fallback', async variant => {
  globalCaps = {
    permissions: ['*'], role: 'administrateur', is_staff: true, modules: {},
  };
  renderPage(variant);
  expect(await screen.findByText('Le module Stages pratiques est désactivé ou indisponible.')).toBeVisible();
  expect(http.get.mock.calls).toHaveLength(1);
  expect(http.post).not.toHaveBeenCalled();
});

it('denies a direct route without effective named permissions before fetching private data', async () => {
  globalCaps.permissions = ['stages.view_conventionstage'];
  globalCaps.role = 'direction'; globalCaps.is_staff = true;
  renderPage();
  expect(await screen.findByText('Vous n’avez pas la permission d’accéder à ce module.')).toBeVisible();
  expect(http.get.mock.calls).toHaveLength(1);
});

it.each([{}, { permission_scopes: {} }, { permission_scopes: { 'stages.gerer_suivi_pratique': {} } }])(
  'does not suppress separately granted management for a contact or empty/missing scope restrictions: %j',
  async attributes => {
    globalCaps.attributes = attributes;
    renderPage();
    expect(await screen.findByRole('button', { name: 'Nouveau programme pratique' })).toBeVisible();
    await openProgramme();
    expect(screen.getByRole('button', { name: /Ouvrir un dossier depuis/ })).toBeVisible();
  },
);

it('honors server action flags instead of management, role or staff for tutor decisions', async () => {
  state.dossier.permissions = ['stages.gerer_suivi_pratique'];
  state.dossier.actions.can_enter_hours = false;
  state.dossier.actions.can_evaluate = false;
  state.hours[0].actions = {
    can_submit: false,
    can_replace: false,
    can_cancel: true,
    can_validate: false,
    can_reject: false,
    can_invalidate: false,
  };
  profile.is_staff = true; profile.role = 'administrateur';
  renderPage();
  await openDossier();
  expect(screen.queryByRole('button', { name: 'Saisir les heures effectuées' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Valider les heures' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^Évaluer / })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Annuler cette saisie' })).toBeVisible();
  expect(screen.getByText('Évaluation en attente.')).toBeVisible();
});

it('paginates scoped curriculum choices and creates a strict version-zero draft', async () => {
  getOverride = (path, params) => {
    if (path === `${base}curriculums/`) {
      return params.get('page') === '2' ? page([state.curriculum], { count: 2, previous: '?page=1' })
        : page([{ ...state.curriculum, id: 15, libelle: 'Autre cursus' }], { count: 2, next: '?page=2' });
    }
    return undefined;
  };
  postOverride = async (path, payload) => {
    expect(path).toBe(`${base}programmes/`);
    expect(payload).toEqual({
      version: 0,
      curriculum: 11,
      code: 'pratique_nouveau',
      titre: 'Nouveau programme',
      minutes_requises: 0,
      competences: [{ code: 'accueil', label: 'Accueil autonome' }],
    });
    state.programme = {
      ...state.programme,
      version: 1,
      code: payload.code,
      revision_publiee: null,
      revision_courante: {
        ...state.revisions[0],
        titre: payload.titre,
        minutes_requises: 0,
        competences: payload.competences,
        statut: 'brouillon',
        published_at: null,
        publie_par: null,
      },
      actions: {
        can_configure: true, can_publish: true, can_revise: false, can_archive: true, can_open_dossier: false,
      },
    };
    state.revisions = [state.programme.revision_courante];
    return { version: 1, programme: state.programme };
  };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Nouveau programme pratique' }));
  const editor = form('Créer le programme');
  const picker = within(editor.getByRole('region', { name: 'Cursus autorisés' }));
  fireEvent.click(await picker.findByRole('button', { name: 'Page suivante' }));
  fireEvent.click(await picker.findByRole('button', { name: /Choisir Formation professionnelle/ }));
  change('Code stable', 'pratique_nouveau', editor);
  change('Titre du programme', 'Nouveau programme', editor);
  change('Minutes réellement', '0', editor);
  change('Code de compétence 1', 'accueil', editor);
  change('Libellé de compétence 1', 'Accueil autonome', editor);
  confirm('Créer le programme');
  expect(await screen.findByRole('heading', { name: 'Nouveau programme', exact: true })).toBeVisible();
  expect(http.post).toHaveBeenCalledTimes(1);
});

it('configures a draft, publishes it and explicitly revises/archives without editing the prior snapshot', async () => {
  state.programme.revision_courante = {
    ...state.revisions[0], statut: 'brouillon', published_at: null, publie_par: null,
  };
  state.programme.revision_publiee = null;
  state.programme.actions = {
    can_configure: true, can_publish: true, can_revise: false, can_archive: true, can_open_dossier: false,
  };
  state.revisions = [state.programme.revision_courante];
  const snapshot = clone(state.dossier.programme);
  postOverride = async (path, payload) => {
    const { programme } = state;
    expect(payload.version).toBe(programme.version);
    if (path.endsWith('/configurer/')) {
      expect(Object.keys(payload).sort()).toEqual(['competences', 'minutes_requises', 'titre', 'version']);
      programme.revision_courante = { ...programme.revision_courante, ...payload };
      delete programme.revision_courante.version;
      state.revisions = [programme.revision_courante];
    } else if (path.endsWith('/publier/')) {
      expect(payload).toEqual({ version: programme.version });
      programme.revision_courante = {
        ...programme.revision_courante, statut: 'publie', published_at: stamp, publie_par: actor,
      };
      programme.revision_publiee = programme.revision_courante;
      programme.actions = {
        can_configure: false, can_publish: false, can_revise: true, can_archive: true, can_open_dossier: true,
      };
      state.revisions = [programme.revision_courante];
    } else if (path.endsWith('/reviser/')) {
      expect(payload).toEqual({ version: programme.version, revision_source: 1 });
      programme.revision_courante = {
        ...programme.revision_courante, id: 102, numero: 2, statut: 'brouillon', published_at: null, publie_par: null,
      };
      programme.actions.can_revise = false; programme.actions.can_configure = true;
      state.revisions = [programme.revision_courante, programme.revision_publiee];
    } else if (path.endsWith('/archiver/')) {
      expect(payload).toEqual({ version: programme.version, revision: 2, motif: 'Exigences à revoir' });
      programme.revision_courante = {
        ...programme.revision_courante, statut: 'archive', archived_at: stamp, archive_par: actor,
      };
      state.revisions = [programme.revision_courante, programme.revision_publiee];
    } else { throw new Error('Unexpected programme command'); }
    programme.version += 1;
    return { version: programme.version, programme };
  };
  renderPage(); await openProgramme();
  fireEvent.click(screen.getByRole('button', { name: 'Configurer le brouillon', exact: true }));
  const editor = form('Configurer le brouillon');
  change('Minutes réellement', '420', editor);
  confirm('Configurer le brouillon');
  await screen.findByText(/Version : 3/);
  fireEvent.click(screen.getByRole('button', { name: 'Publier les exigences', exact: true }));
  confirm('Publier les exigences');
  await screen.findByText(/Version : 4/);
  fireEvent.click(screen.getByRole('button', { name: 'Réviser depuis la révision 1' }));
  confirm('Créer une nouvelle révision');
  await screen.findByText(/Version : 5/);
  fireEvent.click(screen.getByRole('button', { name: 'Archiver la révision 2' }));
  change('Motif d’archivage', 'Exigences à revoir', form('Archiver la révision'));
  confirm('Archiver la révision');
  await screen.findByText(/Version : 6/);
  expect(state.dossier.programme).toEqual(snapshot);
  expect(http.post).toHaveBeenCalledTimes(4);
});

it.each(['secondaire', 'superieur'])('opens a %s dossier through the published revision and convention picker with the exact partner binding', async variant => {
  state = scenario(variant);
  postOverride = async (path, payload) => {
    expect(path).toBe(`${base}dossiers/`);
    expect(payload).toEqual({
      version: 0,
      programme: 10,
      programme_version: 2,
      revision: 1,
      convention: 14,
      convention_empreinte: fingerprint,
      ...(variant === 'secondaire' ? { partenaire_utilisateur: 9 } : {}),
    });
    state.dossier.version = 1; state.report.version = 1;
    state.hours = []; state.history = [audit(1)];
    return dossierMutation();
  };
  renderPage(variant); await openProgramme();
  fireEvent.click(screen.getByRole('button', { name: /Ouvrir un dossier depuis/ }));
  const editor = form('Ouvrir le dossier pratique');
  fireEvent.click(await editor.findByRole('button', { name: /Choisir Convention signée de Camille/ }));
  if (variant === 'secondaire') {
    fireEvent.click(await editor.findByRole('button', { name: 'Choisir Partenaire habilité' }));
  } else {
    expect(editor.getByText(/Partenaire issu du contact entreprise actuel/)).toBeVisible();
    expect(editor.queryByRole('region', { name: 'Partenaire facultatif' })).not.toBeInTheDocument();
  }
  confirm('Ouvrir le dossier pratique');
  expect(await screen.findByRole('heading', { name: 'Camille Apprenant — Pratique professionnelle' })).toBeVisible();
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(http.get.mock.calls.some(([url]) => url.includes('/partenaires/'))).toBe(variant === 'secondaire');
});

it.each(['can_validate', 'can_evaluate'])('warns before opening when the assigned tutor lacks %s', async missing => {
  state.convention.habilitations_tuteur[missing] = false;
  renderPage(); await openProgramme();
  fireEvent.click(screen.getByRole('button', { name: /Ouvrir un dossier depuis/ }));
  const editor = form('Ouvrir le dossier pratique');
  fireEvent.click(await editor.findByRole('button', { name: /Choisir Convention signée de Camille/ }));
  expect(editor.getByText(/Le tuteur ne dispose pas de toutes les habilitations/)).toBeVisible();
  expect(editor.getByText(/Habilitations actuelles du tuteur/)).toHaveTextContent(
    missing === 'can_validate' ? /validation des heures non autorisée/ : /évaluation des compétences non autorisée/,
  );
  expect(editor.getByRole('button', { name: 'Confirmer — Ouvrir le dossier pratique' })).toBeEnabled();
  expect(http.post).not.toHaveBeenCalled();
});

it.each(['fuseau_modifie', 'acteur_inactif', 'curriculum_inactif'])('explains the %s blockage even when structural bindings remain valid', async blockage => {
  state.dossier.blocages = [blockage];
  state.dossier.actions.can_enter_hours = false;
  state.dossier.actions.can_evaluate = false;
  state.dossier.actions.can_cancel = false;
  state.report.actions.can_cancel = false;
  state.report.competences[0].actions.can_evaluate = false;
  state.hours[0].actions = Object.fromEntries(Object.keys(state.hours[0].actions).map(key => [key, false]));
  renderPage(); await openDossier();
  expect(screen.getByText(/Le contexte institutionnel empêche/)).toHaveTextContent(blockage);
  expect(screen.queryByRole('button', { name: 'Saisir les heures effectuées' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Révoquer l’accès partenaire à ce dossier' })).toBeVisible();
  expect(screen.getByRole('heading', { name: /Bilan des exigences/ })).toBeVisible();
  expect(http.post).not.toHaveBeenCalled();
});

it('explains empty complete-convention/enrolment prerequisites instead of inventing a convention wizard', async () => {
  getOverride = path => (path === `${base}programmes/10/conventions/` ? page([]) : undefined);
  renderPage(); await openProgramme();
  fireEvent.click(screen.getByRole('button', { name: /Ouvrir un dossier depuis/ }));
  expect(await screen.findByText(/Aucune convention admissible : une convention existante complète et signée/)).toBeVisible();
  expect(screen.queryByRole('button', { name: /Créer une convention/ })).not.toBeInTheDocument();
});

it('records institution-local 24:00 work with payload JSON + PDF, then submits and validates against refreshed aggregate versions', async () => {
  state.hours = [];
  postOverride = async (path, body) => {
    const payload = body instanceof FormData ? JSON.parse(body.get('payload')) : body;
    expect(payload.version).toBe(state.dossier.version);
    bump();
    if (path === `${base}dossiers/20/heures/`) {
      expect([...body.keys()]).toEqual(['payload', 'fichier']);
      expect(body.get('fichier').name).toBe('preuve.pdf');
      expect(payload).toEqual({
        version: 3,
        date: '2026-10-09',
        heure_debut: '22:00',
        heure_fin: '24:00',
        pause_minutes: 15,
        activite: 'Travail de soirée réellement effectué',
      });
      state.hours = [hour({
        date: payload.date,
        heure_debut: payload.heure_debut,
        heure_fin: payload.heure_fin,
        pause_minutes: 15,
        minutes: 105,
        activite: payload.activite,
        preuve: evidence(),
      })];
    } else if (path.endsWith('/soumettre/')) {
      expect(payload).toEqual({ version: 4 });
      state.hours[0].statut = 'soumise';
      state.hours[0].actions = {
        can_submit: false,
        can_replace: false,
        can_cancel: true,
        can_validate: true,
        can_reject: true,
        can_invalidate: false,
      };
    } else if (path.endsWith('/valider/')) {
      expect(payload).toEqual({ version: 5 });
      state.hours[0].statut = 'validee';
      state.hours[0].actions = {
        can_submit: false,
        can_replace: false,
        can_cancel: false,
        can_validate: false,
        can_reject: false,
        can_invalidate: true,
      };
      state.report.heures.minutes_validees = 105; state.report.heures.minutes_restantes = 105;
    } else { throw new Error('Unexpected hour command'); }
    return { version: state.dossier.version, heure: state.hours[0], heure_precedente: null };
  };
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Saisir les heures effectuées', exact: true }));
  const editor = form('Saisir les heures effectuées');
  expect(editor.getByText(/Horloge institutionnelle : Africa\/Dakar/)).toBeVisible();
  change('Date locale du travail', '2026-10-09', editor);
  change('Heure de début', '22:00', editor);
  change('Heure de fin', '24:00', editor);
  change('Pause en minutes', '15', editor);
  change('Activité professionnelle', 'Travail de soirée réellement effectué', editor);
  fireEvent.change(editor.getByLabelText('Preuve PDF facultative'), { target: { files: [pdf()] } });
  confirm('Saisir les heures effectuées');
  fireEvent.click(await screen.findByRole('button', { name: 'Soumettre les heures', exact: true }));
  confirm('Soumettre les heures');
  fireEvent.click(await screen.findByRole('button', { name: 'Valider les heures', exact: true }));
  confirm('Valider les heures');
  expect(await screen.findByRole('button', { name: 'Invalider les heures validées', exact: true })).toBeVisible();
  expect(screen.getByText(/Ouvert — version 6/)).toBeVisible();
  expect(http.post).toHaveBeenCalledTimes(3);
});

it.each([
  ['can_reject', 'rejeter', 'Rejeter les heures', 'soumise'],
  ['can_cancel', 'annuler', 'Annuler cette saisie', 'brouillon'],
  ['can_invalidate', 'invalider', 'Invalider les heures validées', 'validee'],
])('uses a reason and dossier version for %s without rewriting hour content', async (flag, action, title, status) => {
  state.hours[0].statut = status;
  state.hours[0].actions[flag] = true;
  postOverride = async (path, payload) => {
    expect(path).toBe(`${base}dossiers/20/heures/31/${action}/`);
    expect(payload).toEqual({ version: 3, motif: 'Décision humaine motivée' });
    bump();
    state.hours[0].statut = action === 'rejeter' ? 'rejetee' : 'annulee';
    state.hours[0].actions[flag] = false;
    return { version: 4, heure: state.hours[0], heure_precedente: null };
  };
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: title, exact: true }));
  change('Motif de la décision', 'Décision humaine motivée', form(title));
  confirm(title);
  await screen.findByText(/Ouvert — version 4/);
  expect(screen.getByText('Activité privée initiale')).toBeVisible();
});

it('replaces rather than edits immutable hours, with optional new proof and an explicit reason', async () => {
  state.hours[0].preuve = evidence();
  postOverride = async (path, payload) => {
    expect(path).toBe(`${base}dossiers/20/heures/31/remplacer/`);
    expect(payload).toEqual({
      version: 3,
      date: '2026-10-09',
      heure_debut: '08:00',
      heure_fin: '12:00',
      pause_minutes: 45,
      activite: 'Activité privée initiale',
      motif: 'Pause corrigée',
    });
    const previous = {
      ...state.hours[0],
      statut: 'annulee',
      remplacement_id: 32,
      actions: {
        ...state.hours[0].actions, can_replace: false, can_submit: false, can_cancel: false,
      },
    };
    const replacement = hour({
      id: 32, pause_minutes: 45, minutes: 195, remplace_id: 31, preuve: null,
    });
    bump(); state.hours = [replacement, previous];
    return { version: 4, heure: replacement, heure_precedente: previous };
  };
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Remplacer cette saisie' }));
  const editor = form('Remplacer la saisie horaire');
  change('Pause en minutes', '45', editor);
  change('Motif de remplacement', 'Pause corrigée', editor);
  confirm('Remplacer la saisie horaire');
  await screen.findByText(/Ouvert — version 4/);
  expect(screen.getByRole('button', { name: 'Télécharger activite.pdf' })).toBeVisible();
  expect(screen.getByText(/Cette saisie a été remplacée/)).toBeVisible();
});

it('records acquired/not-acquired evaluations, requires reassessment reason and retains historical evidence', async () => {
  postOverride = async (path, body) => {
    expect(path).toBe(`${base}dossiers/20/competences/accueil/evaluer/`);
    const payload = body instanceof FormData ? JSON.parse(body.get('payload')) : body;
    expect(payload.version).toBe(state.dossier.version);
    const repeated = state.evaluations.length > 0;
    expect(payload).toEqual({
      version: repeated ? 4 : 3,
      acquise: !repeated,
      contexte_professionnel: 'Accueil observé au poste',
      date_observation: '2026-10-09',
      ...(repeated ? { motif_revision: 'Nouvelle observation contradictoire' } : {}),
    });
    if (!repeated) { expect([...body.keys()]).toEqual(['payload', 'fichier']); }
    bump('competence_evaluation');
    const current = assessment({
      id: repeated ? 42 : 41,
      revision: repeated ? 2 : 1,
      acquise: payload.acquise,
      contexte_professionnel: payload.contexte_professionnel,
      version_creation: state.dossier.version,
      motif_revision: payload.motif_revision || null,
      remplace_id: repeated ? 41 : null,
      preuve: repeated ? null : evidence('evaluations', 41, 'observation.pdf'),
    });
    state.evaluations = [current, ...state.evaluations.map(item => ({ ...item, effective: false }))];
    state.report.competences[0] = {
      ...state.report.competences[0], statut: repeated ? 'non_acquise' : 'acquise', evaluation: current,
    };
    state.report.competences_acquises = repeated ? 0 : 1;
    return { version: state.dossier.version, evaluation: current };
  };
  renderPage(); await openDossier();
  const title = 'Évaluer — Accueillir en situation professionnelle';
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer Accueillir en situation professionnelle' }));
  let editor = form(title);
  change('Acquisition', 'oui', editor);
  change('Contexte professionnel', 'Accueil observé au poste', editor);
  change('Date locale d’observation', '2026-10-09', editor);
  expect(editor.queryByLabelText(/Motif de réévaluation/)).not.toBeInTheDocument();
  fireEvent.change(editor.getByLabelText('Preuve PDF facultative'), { target: { files: [pdf()] } });
  confirm(title);
  await screen.findByText(/Ouvert — version 4/);
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer Accueillir en situation professionnelle' }));
  editor = form(title);
  expect(editor.getByLabelText(/Motif de réévaluation/)).toBeRequired();
  change('Acquisition', 'non', editor);
  change('Contexte professionnel', 'Accueil observé au poste', editor);
  change('Date locale d’observation', '2026-10-09', editor);
  change('Motif de réévaluation', 'Nouvelle observation contradictoire', editor);
  confirm(title);
  await screen.findByText(/Ouvert — version 5/);
  expect(screen.getByText('Acquise — Décision historique remplacée.')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Télécharger observation.pdf' })).toBeVisible();
  expect(http.post).toHaveBeenCalledTimes(2);
});

it.each(['clos', 'annule'])('offers only partner ACL revocation after %s, not terminal business edits', async status => {
  state.dossier.statut = status; state.report.statut = status;
  state.dossier.actions = {
    ...state.dossier.actions, can_enter_hours: false, can_evaluate: false, can_close: false, can_cancel: false,
  };
  state.report.actions = { can_close: false, can_cancel: false };
  if (status === 'clos') {
    state.dossier.closed_at = stamp; state.dossier.clos_par = actor;
    state.report.closed_at = stamp; state.report.clos_par = actor; state.report.cloture_reussie = true;
  } else {
    state.dossier.cancelled_at = stamp; state.dossier.annule_par = actor; state.dossier.motif_annulation = 'Fin administrative';
    state.report.cancelled_at = stamp; state.report.annule_par = actor; state.report.motif_annulation = 'Fin administrative';
  }
  const business = clone({ hours: state.hours, evaluations: state.evaluations, snapshot: state.dossier.programme });
  postOverride = async (path, payload) => {
    expect(path).toBe(`${base}dossiers/20/partenaire/revoquer/`);
    expect(payload).toEqual({ version: 3, motif: 'Retrait de l’accès du partenaire' });
    bump('partenaire_revocation');
    state.dossier.partenaire_revoque_le = stamp; state.dossier.actions.can_revoke_partner = false;
    return dossierMutation();
  };
  renderPage(); await openDossier();
  expect(screen.queryByRole('button', { name: 'Saisir les heures effectuées', exact: true })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Soumettre les heures', exact: true })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Annuler administrativement le dossier' })).not.toBeInTheDocument();
  const title = 'Révoquer l’accès partenaire à ce dossier';
  fireEvent.click(screen.getByRole('button', { name: title, exact: true }));
  expect(form(title).getByText(/droits de gestion accordés séparément ne sont pas retirés/)).toBeVisible();
  change('Motif de la décision', 'Retrait de l’accès du partenaire', form(title));
  confirm(title);
  await screen.findByText(/accès révoqué le/);
  expect(screen.queryByRole('button', { name: title, exact: true })).not.toBeInTheDocument();
  expect({ hours: state.hours, evaluations: state.evaluations, snapshot: state.dossier.programme }).toEqual(business);
  expect(state.dossier.statut).toBe(status);
});

it.each([
  ['clore', 'Clôturer avec succès', 'clos'],
  ['annuler', 'Annuler administrativement le dossier', 'annule'],
])('keeps %s distinct and reports released pending entries', async (action, title, status) => {
  state.dossier.actions.can_close = true; state.report.actions.can_close = true;
  state.report.seuils_atteints = true;
  postOverride = async (path, payload) => {
    expect(path).toBe(`${base}dossiers/20/${action}/`);
    expect(payload).toEqual({ version: 3, ...(action === 'annuler' ? { motif: 'Arrêt administratif' } : {}) });
    bump(action === 'clore' ? 'dossier_cloture' : 'dossier_annulation');
    state.dossier.statut = status; state.report.statut = status;
    state.report.cloture_reussie = status === 'clos';
    state.dossier.actions = {
      ...state.dossier.actions, can_enter_hours: false, can_evaluate: false, can_close: false, can_cancel: false,
    };
    state.report.actions = { can_close: false, can_cancel: false };
    state.hours[0].statut = 'annulee';
    return { ...dossierMutation(), heures_annulees: [31] };
  };
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: title, exact: true }));
  if (action === 'annuler') { change('Motif de la décision', 'Arrêt administratif', form(title)); }
  confirm(title);
  expect(await screen.findByText(/1 saisie\(s\) en attente annulée/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Saisir les heures effectuées', exact: true })).not.toBeInTheDocument();
});

it('shows field-path validation errors without a success banner or discarded form text', async () => {
  postOverride = async () => { throw failure(400, { errors: { pause_minutes: ['Pause trop longue.'] }, code: 'validation_error' }); };
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Annuler cette saisie' }));
  change('Motif de la décision', 'Texte conservé', form('Annuler cette saisie'));
  confirm('Annuler cette saisie');
  expect(await screen.findByText(/pause_minutes : Pause trop longue/)).toBeVisible();
  expect(form('Annuler cette saisie').getByLabelText(/Motif de la décision/)).toHaveValue('Texte conservé');
  expect(screen.queryByText(/Opération confirmée/)).not.toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
});

it('refetches a conflict and requires deliberate retry without automatically replaying a write', async () => {
  let first = true;
  postOverride = async (path, payload) => {
    if (first) {
      first = false; bump();
      throw failure(409, { code: 'version_perimee', current_version: 4 });
    }
    expect(payload).toEqual({ version: 4 });
    bump(); state.hours[0].actions.can_submit = false; state.hours[0].statut = 'soumise';
    return { version: 5, heure: state.hours[0], heure_precedente: null };
  };
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Soumettre les heures', exact: true }));
  confirm('Soumettre les heures');
  const review = await screen.findByRole('checkbox', { name: /J’ai vérifié l’état relu/ });
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(form('Soumettre les heures').getByRole('button', { name: 'Confirmer — Soumettre les heures' })).toBeDisabled();
  expect(screen.getByText(/Ouvert — version 4/)).toBeVisible();
  fireEvent.click(review); confirm('Soumettre les heures');
  expect(await screen.findByText(/Ouvert — version 5/)).toBeVisible();
  expect(http.post).toHaveBeenCalledTimes(2);
});

it('does not combine a newer dossier version with an older report or action set', async () => {
  getOverride = path => (path === `${base}dossiers/20/rapport/` ? { ...state.report, version: 2 } : undefined);
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: /Ouvrir le dossier de Camille/ }));
  expect(await screen.findByText(/Le dossier change pendant la lecture/)).toBeVisible();
  expect(screen.queryByText('Missions privées du dossier')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Saisir les heures effectuées', exact: true })).not.toBeInTheDocument();
  expect(http.post).not.toHaveBeenCalled();
});

it('retains a PDF and form text across a conflict but never automatically reuploads it', async () => {
  let first = true;
  const uploaded = pdf();
  postOverride = async (path, body) => {
    expect(path).toBe(`${base}dossiers/20/heures/`);
    expect(body.get('fichier')).toBe(uploaded);
    const payload = JSON.parse(body.get('payload'));
    if (first) {
      first = false; bump();
      throw failure(409, { code: 'version_perimee', current_version: 4 });
    }
    expect(payload.version).toBe(4);
    expect(payload.activite).toBe('Preuve conservée sans répétition automatique');
    bump();
    const created = hour({
      id: 32, version_creation: 5, activite: payload.activite, preuve: evidence('heures', 32),
    });
    state.hours.unshift(created);
    return { version: 5, heure: created, heure_precedente: null };
  };
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Saisir les heures effectuées', exact: true }));
  const editor = form('Saisir les heures effectuées');
  change('Date locale du travail', '2026-10-09', editor);
  change('Heure de début', '13:00', editor); change('Heure de fin', '14:00', editor);
  change('Activité professionnelle', 'Preuve conservée sans répétition automatique', editor);
  fireEvent.change(editor.getByLabelText('Preuve PDF facultative'), { target: { files: [uploaded] } });
  confirm('Saisir les heures effectuées');
  const review = await screen.findByRole('checkbox', { name: /J’ai vérifié l’état relu/ });
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(editor.getByLabelText(/Activité professionnelle/)).toHaveValue('Preuve conservée sans répétition automatique');
  fireEvent.click(review); confirm('Saisir les heures effectuées');
  await screen.findByText(/Ouvert — version 5/);
  expect(http.post).toHaveBeenCalledTimes(2);
});

it('rejects a non-PDF upload locally without issuing a command', async () => {
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Remplacer cette saisie' }));
  const editor = form('Remplacer la saisie horaire');
  change('Motif de remplacement', 'Correction motivée', editor);
  fireEvent.change(editor.getByLabelText('Preuve PDF facultative'), {
    target: { files: [new File(['not a PDF'], 'preuve.txt', { type: 'text/plain' })] },
  });
  confirm('Remplacer la saisie horaire');
  expect(await screen.findByText(/Une preuve PDF non vide est attendue/)).toBeVisible();
  expect(http.post).not.toHaveBeenCalled();
});

it('blocks repeat submission and success messages after an incompatible mutation envelope', async () => {
  postOverride = async () => ({ version: 4, heure: state.hours[0] });
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Soumettre les heures', exact: true }));
  confirm('Soumettre les heures');
  expect(await screen.findByText(/Une réponse a été reçue, mais la confirmation/)).toBeVisible();
  expect(form('Soumettre les heures').getByRole('button', { name: 'Confirmer — Soumettre les heures' })).toBeDisabled();
  expect(screen.queryByText(/Opération confirmée et données relues/)).not.toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
});

it('does not claim success when reads remain older than the successful mutation version', async () => {
  postOverride = async () => ({ version: 4, heure: state.hours[0], heure_precedente: null });
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Soumettre les heures', exact: true }));
  confirm('Soumettre les heures');
  expect(await screen.findByText(/Une réponse a été reçue, mais la confirmation/)).toBeVisible();
  expect(screen.queryByText('Missions privées du dossier')).not.toBeInTheDocument();
  expect(screen.queryByText(/Opération confirmée et données relues/)).not.toBeInTheDocument();
  expect(form('Soumettre les heures').getByRole('button', { name: 'Confirmer — Soumettre les heures' })).toBeDisabled();
});

it('withdraws successful-close controls on a threshold conflict and does not replay closure', async () => {
  state.dossier.actions.can_close = true; state.report.actions.can_close = true;
  postOverride = async () => {
    state.dossier.actions.can_close = false; state.report.actions.can_close = false;
    throw failure(409, { code: 'seuils_non_atteints', criteres_non_satisfaits: state.report.criteres_non_satisfaits });
  };
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Clôturer avec succès', exact: true }));
  confirm('Clôturer avec succès');
  expect(await screen.findByRole('checkbox', { name: /J’ai vérifié l’état relu/ })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Clôturer avec succès', exact: true })).not.toBeInTheDocument();
  expect(form('Clôturer avec succès').getByRole('button', { name: 'Confirmer — Clôturer avec succès' })).toBeDisabled();
  expect(http.post).toHaveBeenCalledTimes(1);
});

it('loads immutable decision history and refreshes it with the aggregate after a decision', async () => {
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Historique des décisions du 2026-10-09 à 08:00' }));
  await screen.findByRole('heading', { name: /Décisions horaires conservées/ });
  postOverride = async () => {
    bump('heure_soumission');
    state.hours[0].statut = 'soumise';
    state.hours[0].derniere_decision = {
      ...state.hours[0].derniere_decision,
      id: 2,
      sequence: 2,
      action: 'soumission',
      etat_avant: 'brouillon',
      etat_apres: 'soumise',
      version_dossier: 4,
    };
    return { version: 4, heure: state.hours[0], heure_precedente: null };
  };
  fireEvent.click(screen.getByRole('button', { name: 'Soumettre les heures', exact: true }));
  confirm('Soumettre les heures');
  await screen.findByText(/Ouvert — version 4/);
  expect(within(screen.getByRole('region', { name: 'Décisions horaires conservées' })).getByText(/Brouillon → Soumise/)).toBeVisible();
  expect(http.get.mock.calls.filter(([url]) => url.includes('/heures/31/decisions/'))).toHaveLength(2);
});

it.each([
  ['secondaire', 'hour'], ['superieur', 'hour'],
  ['secondaire', 'partner'], ['superieur', 'partner'],
])('preserves the open %s %s form while changing the decision-history query key', async (variant, kind) => {
  state = scenario(variant);
  const pending = deferred();
  renderPage(variant); await openDossier();
  const title = kind === 'hour' ? 'Saisir les heures effectuées' : 'Révoquer l’accès partenaire à ce dossier';
  fireEvent.click(screen.getByRole('button', { name: title, exact: true }));
  const formNode = screen.getByRole('form', { name: title });
  const editor = within(formNode);
  const label = kind === 'hour' ? 'Activité professionnelle réalisée' : 'Motif de la décision';
  change(label, 'Saisie conservée pendant le changement de vue', editor);
  const upload = pdf();
  if (kind === 'hour') {
    fireEvent.change(editor.getByLabelText('Preuve PDF facultative'), { target: { files: [upload] } });
  }
  getOverride = path => (path === `${base}dossiers/20/heures/31/decisions/` ? pending.promise : undefined);
  fireEvent.click(screen.getByRole('button', { name: 'Historique des décisions du 2026-10-09 à 08:00' }));
  await screen.findByText('Relecture cohérente du dossier, des actions et du bilan…');
  expect(formNode).toBeInTheDocument();
  expect(editor.getByRole('button', { name: `Confirmer — ${title}` })).toBeDisabled();
  fireEvent.submit(formNode);
  expect(http.post).not.toHaveBeenCalled();
  await act(async () => { pending.resolve(page([state.hours[0].derniere_decision])); });
  await screen.findByRole('heading', { name: /Décisions horaires conservées/ });
  expect(screen.getByRole('form', { name: title })).toBe(formNode);
  expect(editor.getByLabelText(label, { exact: false })).toHaveValue('Saisie conservée pendant le changement de vue');
  expect(editor.getByRole('button', { name: `Confirmer — ${title}` })).toBeEnabled();
  if (kind === 'hour') { expect(editor.getByLabelText('Preuve PDF facultative').files[0]).toBe(upload); }
});

it.each(['secondaire', 'superieur'])('preserves %s unsaved text, PDF and form identity across unchanged focus verification', async variant => {
  state = scenario(variant);
  const pendingCaps = deferred();
  const pendingProfile = deferred();
  renderPage(variant); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Saisir les heures effectuées', exact: true }));
  const formNode = screen.getByRole('form', { name: 'Saisir les heures effectuées' });
  const editor = within(formNode);
  change('Date locale du travail', '2026-10-09', editor);
  change('Heure de début', '13:00', editor); change('Heure de fin', '14:00', editor);
  change('Activité professionnelle', 'Travail non envoyé conservé après le retour de focus', editor);
  const upload = pdf();
  fireEvent.change(editor.getByLabelText('Preuve PDF facultative'), { target: { files: [upload] } });
  getOverride = path => {
    if (path.endsWith('/utilisateurs/comptes/capabilities/')) { return pendingCaps.promise; }
    if (path.endsWith('/utilisateurs/comptes/me/')) { return pendingProfile.promise; }
    return undefined;
  };
  await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true); });
  await screen.findByText('Vérification des accès en cours. Les formulaires sont conservés et désactivés.');
  expect(formNode).toBeInTheDocument();
  expect(formNode).not.toBeVisible();
  expect(editor.getByLabelText(/Activité professionnelle/)).toBeDisabled();
  fireEvent.submit(formNode);
  expect(http.post).not.toHaveBeenCalled();
  await act(async () => { pendingCaps.resolve(clone(globalCaps)); });
  expect(formNode).not.toBeVisible();
  await act(async () => { pendingProfile.resolve(clone(profile)); });
  await waitFor(() => expect(formNode).toBeVisible());
  expect(screen.getByRole('form', { name: 'Saisir les heures effectuées' })).toBe(formNode);
  expect(editor.getByLabelText(/Activité professionnelle/)).toHaveValue('Travail non envoyé conservé après le retour de focus');
  expect(editor.getByLabelText('Preuve PDF facultative').files[0]).toBe(upload);
  expect(editor.getByRole('button', { name: 'Confirmer — Saisir les heures effectuées' })).toBeEnabled();
  expect(http.post).not.toHaveBeenCalled();
});

it.each([
  ['secondaire', 'capabilities', 403], ['superieur', 'capabilities', 403],
  ['secondaire', 'profile', 404], ['superieur', 'profile', 404],
])('purges %s unsaved data after a background %s HTTP %s denial', async (variant, resource, status) => {
  state = scenario(variant);
  const { client } = renderPage(variant); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Saisir les heures effectuées', exact: true }));
  const editor = form('Saisir les heures effectuées');
  change('Activité professionnelle', 'Saisie à effacer sur retrait', editor);
  fireEvent.change(editor.getByLabelText('Preuve PDF facultative'), { target: { files: [pdf()] } });
  getOverride = path => {
    const endpoint = resource === 'capabilities' ? '/utilisateurs/comptes/capabilities/' : '/utilisateurs/comptes/me/';
    return path.endsWith(endpoint) ? Promise.reject(failure(status)) : undefined;
  };
  await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true); });
  expect(await screen.findByText(/Impossible de vérifier l’accès au suivi pratique/)).toBeVisible();
  expect(screen.queryByRole('form', { hidden: true })).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['practical'] })).toHaveLength(0);
  expect(screen.queryByText(/Opération confirmée/)).not.toBeInTheDocument();
});

it.each(['secondaire', 'superieur'])('clears %s unsaved forms when the authenticated context changes', async variant => {
  state = scenario(variant);
  const { client } = renderPage(variant); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Révoquer l’accès partenaire à ce dossier', exact: true }));
  change('Motif de la décision', 'Ancien contexte privé', form('Révoquer l’accès partenaire à ce dossier'));
  const previousKeys = client.getQueriesData({ queryKey: ['practical'] }).map(([key]) => key);
  profile = { ...profile, id: 70, etablissement: 90 };
  await act(async () => { await client.invalidateQueries({ queryKey: ['profile'] }); });
  await screen.findByRole('heading', { name: 'Camille Apprenant — Pratique professionnelle' });
  expect(screen.queryByRole('form', { hidden: true })).not.toBeInTheDocument();
  previousKeys.forEach(key => expect(client.getQueryData(key)).toBeUndefined());
  expect(http.post).not.toHaveBeenCalled();
});

it.each([403, 404])('clears private panels, form uploads, queries and success state on HTTP %s', async status => {
  const { client } = renderPage();
  await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Saisir les heures effectuées', exact: true }));
  const editor = form('Saisir les heures effectuées');
  change('Activité professionnelle', 'Texte privé en cours', editor);
  fireEvent.change(editor.getByLabelText('Preuve PDF facultative'), { target: { files: [pdf()] } });
  getOverride = path => (path === `${base}dossiers/20/rapport/` ? Promise.reject(failure(status)) : undefined);
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser le suivi pratique' }));
  expect(await screen.findByText(/Accès refusé ou retiré/)).toBeVisible();
  expect(screen.queryByText('Missions privées du dossier')).not.toBeInTheDocument();
  expect(screen.queryByRole('form')).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['practical'] })).toHaveLength(0);
  expect(screen.queryByText(/Opération confirmée/)).not.toBeInTheDocument();
});

it('purges private state on command denial and on practical capability withdrawal', async () => {
  postOverride = async () => { throw failure(403); };
  const { client } = renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Soumettre les heures', exact: true }));
  confirm('Soumettre les heures');
  expect(await screen.findByText(/Accès refusé ou retiré/)).toBeVisible();
  expect(client.getQueriesData({ queryKey: ['practical'] })).toHaveLength(0);
  expect(screen.queryByText('Missions privées du dossier')).not.toBeInTheDocument();
});

it('purges when only the practical effective permissions change while global permissions remain cached', async () => {
  const { client } = renderPage(); await openDossier();
  state.capabilities.permissions = ['stages.consulter_suivi_pratique'];
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser le suivi pratique' }));
  expect(await screen.findByText(/Accès refusé ou retiré/)).toBeVisible();
  expect(client.getQueriesData({ queryKey: ['practical'] })).toHaveLength(0);
  expect(screen.queryByText('Missions privées du dossier')).not.toBeInTheDocument();
});

it.each([
  ['secondaire', 'module'], ['superieur', 'module'], ['secondaire', 'permission'], ['superieur', 'permission'],
])('purges %s private state when global %s access is withdrawn', async (variant, kind) => {
  state = scenario(variant);
  const { client } = renderPage(variant); await openDossier();
  if (kind === 'module') { globalCaps.modules['sis.practical_training'] = false; } else { globalCaps.permissions = []; }
  await act(async () => { await client.invalidateQueries({ queryKey: ['capabilities', variant] }); });
  expect(await screen.findByText(kind === 'module' ? /module Stages pratiques est désactivé/ : /permission d’accéder à ce module/)).toBeVisible();
  expect(screen.queryByText('Missions privées du dossier')).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['practical'] })).toHaveLength(0);
});

it('downloads historical and current PDFs with authenticated returned URLs and immediately revokes blob URLs', async () => {
  state.hours[0].preuve = evidence();
  state.evaluations = [assessment({ effective: false, preuve: evidence('evaluations', 41, 'historique.pdf') })];
  const blob = new Blob(['%PDF-private'], { type: 'application/pdf' });
  getOverride = path => (path.endsWith('/preuve/') ? blob : undefined);
  URL.createObjectURL = jest.fn(() => 'blob:private');
  URL.revokeObjectURL = jest.fn();
  jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger activite.pdf' }));
  await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger historique.pdf' }));
  await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2));
  expect(http.get).toHaveBeenCalledWith(
    `https://upper.test${base}dossiers/20/evaluations/41/preuve/`,
    expect.objectContaining({ responseType: 'blob', signal: expect.anything() }),
  );
  expect(screen.queryByRole('link', { name: /pdf/ })).not.toBeInTheDocument();
});

it('denied evidence access removes all dossier data and cannot yield a cached successful download', async () => {
  state.hours[0].preuve = evidence();
  URL.createObjectURL = jest.fn(); URL.revokeObjectURL = jest.fn();
  getOverride = path => (path.endsWith('/preuve/') ? Promise.reject(failure(403)) : undefined);
  const { client } = renderPage(); await openDossier();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger activite.pdf' }));
  expect(await screen.findByText(/Accès refusé ou retiré/)).toBeVisible();
  expect(URL.createObjectURL).not.toHaveBeenCalled();
  expect(client.getQueriesData({ queryKey: ['practical'] })).toHaveLength(0);
});

it('fails closed on an incompatible DTO instead of coercing a successful-looking response', async () => {
  state.capabilities.contract_version = 2;
  renderPage();
  expect(await screen.findByText(/Réponse Capabilities incompatible/)).toBeVisible();
  expect(http.get.mock.calls.filter(([url]) => url.includes('/stages/pratique/'))).toHaveLength(1);
  expect(http.post).not.toHaveBeenCalled();
});

it.each([
  { version: true }, { version: '3' }, { version: 3, unexpected: true },
])('rejects incompatible strict command values: %j', payload => {
  expect(() => checkedCommand('VersionCommand', payload, 'superieur')).toThrow();
});
it('rejects non-relative evidence URLs, malformed IDs and unknown response fields', () => {
  expect(() => checked('Hour', hour({ id: '31' }))).toThrow();
  expect(() => checked('Hour', hour({ preuve: { ...evidence(), download_url: 'https://public.test/proof.pdf' } }))).toThrow();
  expect(() => checked('Dossier', { ...state.dossier, can_manage: true })).toThrow();
  expect(() => checkedCommand('OpenDossier', {
    version: 0,
    programme: 10,
    programme_version: 2,
    revision: 1,
    convention: 14,
    convention_empreinte: fingerprint,
    partenaire_utilisateur: 9,
  }, 'superieur')).toThrow();
});
