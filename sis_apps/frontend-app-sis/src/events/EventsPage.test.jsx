import React from 'react';
import {
  act, configure, fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import EventsPage from './EventsPage';

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

const id = 'c0c70352-3355-41da-91bb-b393e8428214';
const base = '/api/v1/core/evenements/';
const failure = (status, data = { detail: `Refus serveur ${status}` }) => ({ response: { status, data } });
const page = (results, extra = {}) => ({
  count: results.length, results, next: null, previous: null, ...extra,
});
const alice = { id: 11, nom: 'Alice Privée' };
const bob = { id: 12, nom: 'Benoît Invité' };
const chloe = { id: 13, nom: 'Chloé Compte' };
const room = {
  id: 7, code: 'A101', nom: 'Auditorium', capacite: 30,
};
const types = [
  { value: 'conference', label: 'Conférence' }, { value: 'examen', label: 'Examen' },
  { value: 'reunion', label: 'Réunion' }, { value: 'ceremonie', label: 'Cérémonie' },
  { value: 'activite', label: 'Activité institutionnelle' },
];
let current;
let events;
let caps;
let globalCaps;
let profile;
let onGet;
let onPost;
let http;
let dialogElement;
const clients = [];

// Query all matching nodes without JSDOM's costly CSS visibility walk; visibility is asserted separately.
beforeAll(() => configure({ defaultHidden: true }));
afterAll(() => configure({ defaultHidden: false }));

const renderPage = (variant = 'secondaire', suffix = `?evenement=${id}`) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[`/${variant}/evenements${suffix}`]}>
          <EventsPage variant={variant} />
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
};
const change = (label, value, container = screen) => fireEvent.change(container.getByLabelText(label, { exact: false, selector: 'input, textarea, select' }), { target: { value } });
const dialog = () => {
  if (!dialogElement?.isConnected) { dialogElement = screen.getByRole('dialog'); }
  return within(dialogElement);
};
const saveButton = () => dialog().getByText('Enregistrer l’événement', { selector: 'button' });
const submit = () => fireEvent.click(saveButton());
const grantManagement = () => {
  caps = { ...caps, can_create: true, can_manage: true };
  current = { ...current, can_manage: true };
  globalCaps = { ...globalCaps, permissions: ['core.gerer_evenement_institutionnel'] };
};
const openEdit = async () => {
  fireEvent.click(await screen.findByText('Modifier l’horaire, la salle ou les invitations', { selector: 'button' }));
  expect(await screen.findByRole('dialog')).toBeVisible();
  await waitFor(() => expect(saveButton()).toBeEnabled());
};
const openCreate = async () => {
  fireEvent.click(await screen.findByRole('button', { name: 'Nouvel événement' }));
  expect(await screen.findByRole('dialog')).toBeVisible();
  await waitFor(() => expect(saveButton()).toBeEnabled());
};
const setDates = (container = dialog()) => {
  act(() => {
    change(/Début de l’événement/, '2027-03-28T01:30:00', container);
    change(/Fin de l’événement/, '2027-03-28T03:30:00', container);
  });
  act(() => {
    change('Décalage UTC — début', '+01:00', container);
    change('Décalage UTC — fin', '+02:00', container);
  });
};
const searchPerson = async (term, name) => {
  change('Rechercher un participant', term, dialog());
  fireEvent.click(dialog().getByText('Rechercher des participants', { selector: 'button' }));
  fireEvent.click(await dialog().findByText(`Ajouter ${name}`, { selector: 'button' }));
};
const eventCalls = () => http.get.mock.calls.filter(([url]) => new URL(url).pathname.startsWith(base));
const listCalls = () => http.get.mock.calls.filter(([url]) => new URL(url).pathname === base);

beforeEach(() => {
  dialogElement = null;
  profile = {
    id: 3, etablissement: 9, is_staff: false, role: 'parent',
  };
  globalCaps = {
    role: 'parent', permissions: ['core.consulter_evenement_institutionnel'], modules: { 'sis.events': true },
  };
  caps = {
    can_create: false,
    can_manage: false,
    can_consult: true,
    types,
    statuts: [{ value: 'planifie', label: 'Planifié' }, { value: 'annule', label: 'Annulé' }],
    notifications: 'internes',
  };
  current = {
    id,
    titre: 'Conférence autorisée',
    description: 'Programme privé',
    type: 'conference',
    statut: 'planifie',
    debut: '2027-03-08T10:00:00+01:00',
    fin: '2027-03-08T11:00:00+01:00',
    salle: room,
    effectif: 12,
    version: 1,
    can_manage: false,
    participants: [alice],
  };
  events = [id];
  onGet = () => undefined;
  onPost = async (path, payload) => {
    if (path === base) {
      current = {
        ...current,
        ...payload,
        id,
        can_manage: true,
        salle: room,
        version: 1,
        participants: [alice, bob, chloe].filter(person => payload.participants.includes(person.id)),
      };
      events = [id];
      caps = { ...caps, can_manage: true };
    } else if (path === `${base}${id}/modifier/`) {
      current = {
        ...current,
        ...payload,
        salle: room,
        version: payload.version + 1,
        participants: [alice, bob, chloe].filter(person => payload.participants.includes(person.id)),
      };
    } else if (path === `${base}${id}/annuler/`) {
      current = { ...current, statut: 'annule', version: payload.version + 1 };
    } else { throw new Error(`POST inattendu ${path}`); }
    return { ...current };
  };
  http = {
    get: jest.fn(async rawUrl => {
      const parsed = new URL(rawUrl);
      const custom = onGet(parsed);
      if (custom !== undefined) { return { data: await custom }; }
      let data;
      if (parsed.pathname.endsWith('/utilisateurs/comptes/capabilities/')) {
        data = globalCaps;
      } else if (parsed.pathname.endsWith('/utilisateurs/comptes/me/')) {
        data = profile;
      } else if (parsed.pathname === `${base}capacites/`) {
        data = caps;
      } else if (parsed.pathname === base) {
        const { participants, ...row } = current;
        data = page(events.map(() => row));
      } else if (parsed.pathname === `${base}${id}/`) {
        data = { ...current };
      } else if (parsed.pathname === `${base}salles/`) {
        data = page([room]);
      } else if (parsed.pathname === `${base}participants/`) {
        data = page([alice, bob, chloe]);
      } else { throw new Error(`GET inattendu ${rawUrl}`); }
      return { data };
    }),
    post: jest.fn(async (rawUrl, payload) => ({ data: await onPost(new URL(rawUrl).pathname, payload) })),
  };
  getAuthenticatedHttpClient.mockReturnValue(http);
});
afterEach(() => {
  clients.splice(0).forEach(client => client.clear());
  jest.clearAllMocks();
});

it.each(['secondaire', 'superieur'])('shows only invited participant data in the bounded %s agenda', async variant => {
  const { client } = renderPage(variant, '');
  fireEvent.click(await screen.findByRole('button', { name: 'Ouvrir Conférence autorisée' }));
  expect(await screen.findByText('Événement accessible dans le périmètre de votre invitation active.')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Notifications internes' })).toHaveAttribute('href', `/${variant}/workflows`);
  expect(screen.queryByText(alice.nom)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Nouvel événement' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Modifier l’horaire/ })).not.toBeInTheDocument();
  expect(eventCalls().every(([url]) => url.startsWith(`https://${variant}.test/`))).toBe(true);
  expect(eventCalls().some(([url]) => /\/(participants|salles)\//.test(url))).toBe(false);
  const request = new URL(listCalls()[0][0]);
  expect(request.searchParams.get('debut')).toMatch(/[+-]\d{2}:\d{2}$/);
  expect(new Date(request.searchParams.get('fin')) - new Date(request.searchParams.get('debut'))).toBeLessThanOrEqual(93 * 86400000);
  client.getQueriesData({ queryKey: ['events'] }).forEach(([, data]) => {
    expect(JSON.stringify(data)).not.toContain(alice.nom);
  });
});

it.each(['secondaire', 'superieur'])('creates a conference or ceremony from an empty %s agenda as a nonstaff manager', async variant => {
  grantManagement();
  caps.can_manage = false;
  events = [];
  renderPage(variant, '');
  await screen.findByText('Aucun événement accessible pendant cette période.');
  await openCreate();
  expect(dialog().getByText(/Choisir une salle ne garantit pas sa disponibilité/)).toBeInTheDocument();
  expect(within(dialog().getByRole('combobox', { name: /Type d’événement/ })).getAllByRole('option')).toHaveLength(5);
  act(() => {
    change(/^Titre/, 'Rencontre du campus', dialog());
    change(/^Description/, 'Accueil', dialog());
    change(/Type d’événement/, variant === 'secondaire' ? 'conference' : 'ceremonie', dialog());
    change('Salle existante', '7', dialog());
    change(/^Effectif total/, '20', dialog());
  });
  setDates();
  await searchPerson('Al', alice.nom);
  submit();
  expect(await screen.findByText('Opération confirmée par le serveur et état relu.')).toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(http.post.mock.calls[0][0]).toBe(`https://${variant}.test${base}`);
  expect(http.post.mock.calls[0][1]).toEqual({
    titre: 'Rencontre du campus',
    description: 'Accueil',
    type: variant === 'secondaire' ? 'conference' : 'ceremonie',
    salle: 7,
    debut: '2027-03-28T01:30:00+01:00',
    fin: '2027-03-28T03:30:00+02:00',
    effectif: 20,
    participants: [11],
  });
  expect(eventCalls().filter(([url]) => new URL(url).pathname === `${base}${id}/`).length).toBeGreaterThanOrEqual(1);
  expect(eventCalls().some(([url]) => new URL(url).searchParams.has('evenement_id'))).toBe(false);
});

it('rereads authoritative detail before editing and sends the complete invitation replacement and version', async () => {
  grantManagement();
  renderPage('superieur', '');
  fireEvent.click(await screen.findByRole('button', { name: 'Ouvrir Conférence autorisée' }));
  await screen.findByText(alice.nom);
  current = { ...current, participants: [alice, bob], version: 4 };
  await openEdit();
  expect(dialog().getByText(bob.nom)).toBeInTheDocument();
  fireEvent.click(dialog().getByRole('button', { name: `Retirer ${alice.nom}` }));
  setDates();
  submit();
  expect(await screen.findByText('Opération confirmée par le serveur et état relu.')).toBeInTheDocument();
  expect(http.post.mock.calls[0][0].endsWith(`${base}${id}/modifier/`)).toBe(true);
  expect(http.post.mock.calls[0][1]).toEqual({
    titre: current.titre,
    description: current.description,
    type: 'conference',
    salle: 7,
    debut: '2027-03-28T01:30:00+01:00',
    fin: '2027-03-28T03:30:00+02:00',
    effectif: 12,
    participants: [12],
    version: 4,
  });
  expect(current.version).toBe(5);
  expect(screen.queryByText(alice.nom)).not.toBeInTheDocument();
  expect(eventCalls().filter(([url]) => /\/(salles|participants)\//.test(url)).every(
    ([url]) => new URL(url).searchParams.get('evenement_id') === id,
  )).toBe(true);
});

it('keeps a 409 draft unchanged, rereads separately, and requires explicit confirmation before one new POST', async () => {
  grantManagement();
  current = { ...current, participants: [alice, bob] };
  const originalPost = onPost;
  onPost = async (path, payload) => {
    if (http.post.mock.calls.length === 1) {
      current = {
        ...current, titre: 'Titre serveur concurrent', participants: [chloe], version: 2,
      };
      throw failure(409, { detail: 'L’événement a changé.' });
    }
    return originalPost(path, payload);
  };
  renderPage();
  await openEdit();
  change(/^Titre/, 'Mon brouillon conservé', dialog());
  submit();
  await dialog().findByText(/Votre brouillon est conservé/);
  expect(dialog().getByDisplayValue('Mon brouillon conservé')).toBeInTheDocument();
  expect(saveButton()).toBeDisabled();
  expect(http.post).toHaveBeenCalledTimes(1);
  fireEvent.click(dialog().getByText('Relire la version serveur', { selector: 'button' }));
  await dialog().findByText('Titre serveur concurrent');
  expect(dialog().getByDisplayValue('Mon brouillon conservé')).toBeInTheDocument();
  expect(dialog().getByText(chloe.nom)).toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(saveButton()).toBeDisabled();
  fireEvent.click(dialog().getByLabelText(/J’ai comparé cette version/));
  submit();
  await screen.findByText('Opération confirmée par le serveur et état relu.');
  expect(http.post).toHaveBeenCalledTimes(2);
  expect(http.post.mock.calls[1][1]).toMatchObject({ titre: 'Mon brouillon conservé', version: 2, participants: [11, 12] });
});

it('retains the draft but cannot replay a cancelled server version after 409', async () => {
  grantManagement();
  onPost = async () => {
    current = { ...current, statut: 'annule', version: 2 };
    throw failure(409);
  };
  renderPage();
  await openEdit();
  change(/^Titre/, 'Brouillon à conserver', dialog());
  submit();
  fireEvent.click(await dialog().findByRole('button', { name: 'Relire la version serveur' }));
  await dialog().findByText(/Cet événement est annulé définitivement/);
  expect(dialog().getByDisplayValue('Brouillon à conserver')).toBeInTheDocument();
  expect(saveButton()).toBeDisabled();
  expect(http.post).toHaveBeenCalledTimes(1);
});

it.each([403, 404])('purges invitations, selectors and draft after a mutation refusal %s', async status => {
  grantManagement();
  onPost = async () => { throw failure(status); };
  const { client } = renderPage();
  await openEdit();
  change(/^Titre/, 'Brouillon privé', dialog());
  await searchPerson('Ch', chloe.nom);
  submit();
  await screen.findByText(/anciennes données privées ont été purgées/);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByText(alice.nom)).not.toBeInTheDocument();
  expect(screen.queryByText(chloe.nom)).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue('Brouillon privé')).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['events'] }).some(([, data]) => Boolean(data))).toBe(false);
  expect(http.post).toHaveBeenCalledTimes(1);
});

it.each([403, 404])('purges a previously visible invitation after the next agenda read returns %s', async status => {
  const { client } = renderPage();
  await screen.findByText('Programme privé');
  onGet = parsed => {
    if (parsed.pathname === base) { throw failure(status); }
    return undefined;
  };
  await act(async () => { await client.invalidateQueries({ queryKey: ['events'] }); });
  await screen.findByText(/anciennes données privées ont été purgées/);
  expect(screen.queryByText('Programme privé')).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['events'] }).some(([, data]) => Boolean(data))).toBe(false);
});

it('drops manager-only fields and the open editor when detail becomes participant-only', async () => {
  grantManagement();
  const { client } = renderPage();
  await openEdit();
  current = { ...current, can_manage: false };
  await act(async () => { await client.invalidateQueries({ queryKey: ['events'] }); });
  expect(await screen.findByText('Événement accessible dans le périmètre de votre invitation active.')).toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByText(alice.nom)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Modifier l’horaire/ })).not.toBeInTheDocument();
  client.getQueriesData({ queryKey: ['events'] }).forEach(([, data]) => expect(JSON.stringify(data)).not.toContain(alice.nom));
});

it('purges old manager detail when the latest capabilities withdraw management but still allow consultation', async () => {
  grantManagement();
  const { client } = renderPage();
  await openEdit();
  caps = { ...caps, can_manage: false, can_create: false };
  await act(async () => {
    await client.invalidateQueries({ predicate: query => query.queryKey[0] === 'events' && query.queryKey[2] === 'capabilities' });
  });
  await screen.findByText(/anciennes données privées ont été purgées/);
  expect(screen.queryByText(alice.nom)).not.toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['events'] }).some(([, data]) => Boolean(data))).toBe(false);
  expect(http.post).not.toHaveBeenCalled();
});

it('also purges formerly managed agenda rows after capability withdrawal, before another list read', async () => {
  grantManagement();
  const { client } = renderPage('secondaire', '');
  await screen.findByRole('button', { name: 'Ouvrir Conférence autorisée' });
  caps = { ...caps, can_manage: false, can_create: false };
  await act(async () => {
    await client.invalidateQueries({ predicate: query => query.queryKey[0] === 'events' && query.queryKey[2] === 'capabilities' });
  });
  await screen.findByText(/anciennes données privées ont été purgées/);
  expect(screen.queryByText('Conférence autorisée')).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['events'] }).some(([, data]) => Boolean(data))).toBe(false);
});

it.each(['module', 'permissions', 'tenant', 'account', 'logout'])('discards local private data on %s context change', async changeKind => {
  grantManagement();
  const { client } = renderPage();
  await openEdit();
  change(/^Titre/, 'Brouillon de l’ancien contexte', dialog());
  const originalScope = client.getQueryCache().findAll({ queryKey: ['events'] })[0].queryKey[1];
  if (changeKind === 'module') { globalCaps = { ...globalCaps, modules: { 'sis.events': false } }; }
  if (changeKind === 'permissions') {
    globalCaps = { ...globalCaps, permissions: [] };
    caps = {
      ...caps, can_create: false, can_manage: false, can_consult: false,
    };
  }
  if (changeKind === 'tenant') { profile = { ...profile, etablissement: 10 }; }
  if (changeKind === 'account') { profile = { ...profile, id: 4 }; }
  if (['tenant', 'account'].includes(changeKind)) {
    current = {
      ...current, titre: 'Autre contexte', description: 'Nouvelles données', participants: [bob],
    };
  }
  if (changeKind === 'logout') {
    onGet = parsed => {
      if (parsed.pathname.endsWith('/me/')) { throw failure(401); }
      return undefined;
    };
  }
  await act(async () => {
    await client.invalidateQueries({ queryKey: ['capabilities'] });
    await client.invalidateQueries({ queryKey: ['profile'] });
  });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.queryByDisplayValue('Brouillon de l’ancien contexte')).not.toBeInTheDocument();
  expect(screen.queryByText(alice.nom)).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['events', originalScope] }).some(([, data]) => Boolean(data))).toBe(false);
  expect(http.post).not.toHaveBeenCalled();
});

it.each([
  ['effectif', 'L’effectif dépasse la capacité de la salle.'],
  ['salle', 'La salle est occupée ou sa disponibilité ne peut pas être établie.'],
])('keeps the form and explains the authoritative %s refusal without success', async (field, message) => {
  grantManagement();
  onPost = async () => { throw failure(400, { [field]: message }); };
  renderPage();
  await openEdit();
  change(/^Titre/, 'En attente de résolution', dialog());
  submit();
  expect(await dialog().findByText(`${field}: ${message}`)).toBeInTheDocument();
  expect(dialog().getByDisplayValue('En attente de résolution')).toBeInTheDocument();
  expect(screen.queryByText(/Opération confirmée/)).not.toBeInTheDocument();
  expect(http.post).toHaveBeenCalledTimes(1);
});

it.each([
  ['31', [alice], 'L’effectif dépasse la capacité de la salle sélectionnée.'],
  ['1', [alice, bob], 'L’effectif total doit être positif et inclure tous les participants invités.'],
])('validates total attendance %s against capacity and invitations before a command', async (attendance, people, message) => {
  grantManagement();
  current = { ...current, participants: people };
  renderPage();
  await openEdit();
  change(/^Effectif total/, attendance, dialog());
  submit();
  await dialog().findByText(message);
  expect(http.post).not.toHaveBeenCalled();
});

it.each([
  ['2027-03-08T10:00:00', '2027-03-16T10:00:00', '+01:00', /limité à 7 jours/],
  ['2027-03-08T10:00:00', '2027-03-08T10:00:00', '+01:00', /limité à 7 jours/],
  ['2027-03-08T10:00:00', '2027-03-08T11:00:00', '+14:30', /décalage UTC explicite valide/],
])('rejects invalid event bounds %s / %s / %s without sending naive dates', async (start, end, offset, message) => {
  grantManagement();
  renderPage();
  await openEdit();
  change(/Début de l’événement/, start, dialog());
  change(/Fin de l’événement/, end, dialog());
  change('Décalage UTC — début', offset, dialog());
  change('Décalage UTC — fin', offset, dialog());
  submit();
  await dialog().findByText(message);
  expect(http.post).not.toHaveBeenCalled();
});

it('requires a separate cancellation confirmation and never sends delete or an implicit cancellation', async () => {
  grantManagement();
  renderPage('superieur');
  fireEvent.click(await screen.findByRole('button', { name: 'Annuler l’événement' }));
  await screen.findByRole('dialog');
  expect(http.post).not.toHaveBeenCalled();
  expect(dialog().getByText(/annulation définitive de « Conférence autorisée »/)).toBeInTheDocument();
  fireEvent.click(dialog().getByRole('button', { name: 'Confirmer l’annulation définitive' }));
  await screen.findByText('Opération confirmée par le serveur et état relu.');
  expect(http.post.mock.calls[0][0]).toBe(`https://superieur.test${base}${id}/annuler/`);
  expect(http.post.mock.calls[0][1]).toEqual({ version: 1 });
  expect(screen.queryByRole('button', { name: 'Annuler l’événement' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Modifier l’horaire/ })).not.toBeInTheDocument();
  expect(current.statut).toBe('annule');
});

it('requires re-reading and renewed cancellation consent after a version conflict', async () => {
  grantManagement();
  const originalPost = onPost;
  onPost = async (path, payload) => {
    if (http.post.mock.calls.length === 1) { current = { ...current, version: 2 }; throw failure(409); }
    return originalPost(path, payload);
  };
  renderPage();
  fireEvent.click(await screen.findByRole('button', { name: 'Annuler l’événement' }));
  await screen.findByRole('dialog');
  fireEvent.click(await dialog().findByRole('button', { name: 'Confirmer l’annulation définitive' }));
  fireEvent.click(await dialog().findByRole('button', { name: 'Relire la version serveur' }));
  await dialog().findByRole('checkbox', { name: /J’ai relu cette version/ });
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(dialog().getByRole('button', { name: 'Confirmer l’annulation définitive' })).toBeDisabled();
  fireEvent.click(dialog().getByRole('checkbox', { name: /J’ai relu cette version/ }));
  fireEvent.click(dialog().getByRole('button', { name: 'Confirmer l’annulation définitive' }));
  await screen.findByText('Opération confirmée par le serveur et état relu.');
  expect(http.post.mock.calls[1][1]).toEqual({ version: 2 });
});

it('paginates the bounded agenda and resets to page one when the interval changes', async () => {
  onGet = parsed => (parsed.pathname === base ? page(
    [{ ...current, titre: parsed.searchParams.get('page') === '2' ? 'Page deux' : current.titre }],
    { count: 26, next: '?page=2' },
  ) : undefined);
  renderPage('secondaire', '');
  await screen.findByRole('button', { name: 'Ouvrir Conférence autorisée' });
  fireEvent.click(screen.getByRole('button', { name: /next page/i }));
  await screen.findByRole('button', { name: 'Ouvrir Page deux' });
  expect(new URL(listCalls().at(-1)[0]).searchParams.get('page')).toBe('2');
  const before = listCalls().length;
  change(/Début de la période/, '2027-01-01T00:00:00');
  change(/Fin de la période/, '2027-05-01T00:00:00');
  fireEvent.click(screen.getByRole('button', { name: 'Afficher cette période' }));
  await screen.findByText('L’intervalle doit être positif et limité à 93 jours.');
  expect(listCalls()).toHaveLength(before);
  change(/Fin de la période/, '2027-01-02T00:00:00');
  fireEvent.click(screen.getByRole('button', { name: 'Afficher cette période' }));
  await screen.findByRole('button', { name: 'Ouvrir Conférence autorisée' });
  const last = new URL(listCalls().at(-1)[0]);
  expect(last.searchParams.get('page')).toBe('1');
  expect(last.searchParams.get('page_size')).toBe('25');
  expect(last.searchParams.get('debut')).toMatch(/^2027-01-01T00:00:00[+-]/);
});

it('paginates existing rooms while preserving the choice and event scope', async () => {
  grantManagement();
  const otherRoom = { ...room, id: 8, nom: 'Salle deuxième page' };
  onGet = parsed => {
    if (parsed.pathname === `${base}salles/`) {
      return page(parsed.searchParams.get('page') === '2' ? [otherRoom] : [room], { count: 51, next: '?page=2' });
    }
    return undefined;
  };
  renderPage('superieur');
  await openEdit();
  fireEvent.click(dialog().getByRole('button', { name: 'Salles suivantes' }));
  await dialog().findByRole('option', { name: /Salle deuxième page/ });
  change('Salle existante', '8', dialog());
  fireEvent.click(dialog().getByRole('button', { name: 'Salles précédentes' }));
  await dialog().findByText('Page 1 — 51 résultat(s)');
  expect(dialog().getByRole('combobox', { name: /Salle existante/ })).toHaveValue('8');
  expect(eventCalls().filter(([url]) => url.includes('/salles/')).every(
    ([url]) => new URL(url).searchParams.get('evenement_id') === id,
  )).toBe(true);
});

it('bounds and paginates participant search while retaining invited accounts without global user permissions', async () => {
  grantManagement();
  onGet = parsed => (parsed.pathname === `${base}participants/`
    ? page(parsed.searchParams.get('page') === '2' ? [chloe] : [bob], { count: 51, next: '?page=2' })
    : undefined);
  renderPage('superieur');
  await openEdit();
  change('Rechercher un participant', 'B', dialog());
  expect(dialog().getByText('Rechercher des participants', { selector: 'button' })).toBeDisabled();
  expect(eventCalls().some(([url]) => url.includes('/participants/'))).toBe(false);
  await searchPerson('Be', bob.nom);
  fireEvent.click(dialog().getByText('Participants suivants', { selector: 'button' }));
  fireEvent.click(await dialog().findByText(`Ajouter ${chloe.nom}`, { selector: 'button' }));
  expect(dialog().getByLabelText(`Retirer ${bob.nom}`)).toBeInTheDocument();
  expect(dialog().getByLabelText(`Retirer ${chloe.nom}`)).toBeInTheDocument();
  expect(eventCalls().filter(([url]) => /\/(salles|participants)\//.test(url)).every(
    ([url]) => new URL(url).searchParams.get('evenement_id') === id,
  )).toBe(true);
});

it('waits for the command and authoritative refetch before success and blocks duplicate clicks', async () => {
  grantManagement();
  const originalPost = onPost;
  let releasePost;
  onPost = (path, payload) => new Promise(resolve => {
    releasePost = async () => resolve(await originalPost(path, payload));
  });
  renderPage();
  await openEdit();
  submit();
  submit();
  expect(http.post).toHaveBeenCalledTimes(1);
  expect(screen.queryByText(/Opération confirmée/)).not.toBeInTheDocument();
  let releaseRead;
  onGet = parsed => (parsed.pathname === `${base}${id}/` ? new Promise(resolve => { releaseRead = () => resolve({ ...current }); }) : undefined);
  await act(async () => { await releasePost(); });
  await waitFor(() => expect(releaseRead).toBeDefined());
  expect(screen.queryByText(/Opération confirmée/)).not.toBeInTheDocument();
  onGet = () => undefined;
  await act(async () => { releaseRead(); });
  await screen.findByText('Opération confirmée par le serveur et état relu.');
  expect(http.post).toHaveBeenCalledTimes(1);
});

it('does not repopulate the previous session or report success for a late POST after logout', async () => {
  grantManagement();
  let releasePost;
  onPost = () => new Promise(resolve => { releasePost = () => resolve({ ...current, version: 2 }); });
  const { client } = renderPage();
  await openEdit();
  submit();
  expect(http.post).toHaveBeenCalledTimes(1);
  onGet = parsed => {
    if (parsed.pathname.endsWith('/me/')) { throw failure(401); }
    return undefined;
  };
  await act(async () => { await client.invalidateQueries({ queryKey: ['profile'] }); });
  await screen.findByText(/Impossible de vérifier l’accès aux événements/);
  const reads = eventCalls().length;
  await act(async () => { releasePost(); });
  expect(eventCalls()).toHaveLength(reads);
  expect(client.getQueriesData({ queryKey: ['events'] })).toHaveLength(0);
  expect(screen.queryByText(/Opération confirmée/)).not.toBeInTheDocument();
  expect(screen.queryByText(alice.nom)).not.toBeInTheDocument();
});

it('preserves the exact UTC offset and fractional instant through an unchanged autumn DST hour', async () => {
  grantManagement();
  const dates = { debut: '2027-10-31T02:15:00.250+01:00', fin: '2027-10-31T02:45:00.250+01:00' };
  current = { ...current, ...dates };
  renderPage();
  expect(await screen.findByText(/UTC\+01:00.*UTC\+01:00/)).toBeInTheDocument();
  await openEdit();
  expect(dialog().getByLabelText('Décalage UTC — début', { exact: false, selector: 'input' })).toHaveValue('+01:00');
  change(/^Titre/, 'Titre changé, horaire conservé', dialog());
  submit();
  await screen.findByText('Opération confirmée par le serveur et état relu.');
  expect(http.post.mock.calls[0][1]).toMatchObject(dates);
});

it.each(['response', 'detail', 'list'])('never reports success for an invalid %s confirmation and never retries the POST', async broken => {
  grantManagement();
  const originalPost = onPost;
  onPost = async (path, payload) => {
    const result = await originalPost(path, payload);
    if (broken === 'response') { return { id }; }
    onGet = parsed => {
      if (parsed.pathname === (broken === 'detail' ? `${base}${id}/` : base)) { throw failure(500); }
      return undefined;
    };
    return result;
  };
  renderPage();
  await openEdit();
  submit();
  await dialog().findByText(/Résultat non confirmé/);
  expect(screen.queryByText(/Opération confirmée par le serveur/)).not.toBeInTheDocument();
  expect(saveButton()).toBeDisabled();
  expect(http.post).toHaveBeenCalledTimes(1);
});

it.each(['secondaire', 'superieur'])('does not request the disabled event module in %s even with management permissions', async variant => {
  grantManagement();
  globalCaps = { ...globalCaps, modules: { 'sis.events': false } };
  renderPage(variant);
  await screen.findByText('Le module Événements institutionnels est désactivé ou indisponible.');
  expect(eventCalls()).toHaveLength(0);
});

it('refuses staff and role-only access when event capabilities grant nothing', async () => {
  profile = { ...profile, is_staff: true, role: 'direction' };
  globalCaps = { ...globalCaps, role: 'direction', permissions: [] };
  caps = { ...caps, can_consult: false };
  renderPage();
  await screen.findByText(/anciennes données privées ont été purgées/);
  expect(listCalls()).toHaveLength(0);
  expect(screen.queryByRole('button', { name: 'Nouvel événement' })).not.toBeInTheDocument();
});
