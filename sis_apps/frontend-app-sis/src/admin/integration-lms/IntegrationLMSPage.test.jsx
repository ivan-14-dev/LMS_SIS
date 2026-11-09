import React from 'react';
import {
  act, fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import {
  MemoryRouter, Outlet, Route, Routes,
} from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getConfig } from '@edx/frontend-platform';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import {
  useIntegrationCourseMappings, useIntegrationHealth, useIntegrationStats, useIntegrationUserMappings,
} from '../../services/api';
import IntegrationLMSPage from './IntegrationLMSPage';

jest.setTimeout(20000);

jest.mock('@edx/frontend-platform', () => ({ getConfig: jest.fn() }));
jest.mock('@edx/frontend-platform/auth', () => ({ getAuthenticatedHttpClient: jest.fn() }));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  useIntegrationCourseMappings: jest.fn(),
  useIntegrationHealth: jest.fn(),
  useIntegrationStats: jest.fn(),
  useIntegrationUserMappings: jest.fn(),
}));

const event = {
  id: 11,
  event_type: 'access.set',
  aggregate_type: 'access',
  aggregate_id: '6',
  statut: 'pending',
  nb_tentatives: 6,
  created_at: '2026-11-04T10:00:00Z',
  erreur: 'Retrait en attente après une réponse perdue.',
};
const failedEvent = {
  ...event, id: 12, statut: 'dead', statut_display: 'Dead letter', erreur: 'Conflit permanent : accès natif modifié.',
};
const queued = { status: 202, data: { status: 'queued', task_id: 'outbox-task-123' } };
const endpoint = variant => `https://${variant}.example/api/v1/integration`;
const get = jest.fn();
const post = jest.fn();
const statsRefresh = jest.fn();
const deferred = () => {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
};
const urls = () => get.mock.calls.map(([url]) => url);
const clickProcess = () => fireEvent.click(screen.getByRole('button', { name: 'Demander le traitement' }));

const page = (client, isStaff = true) => (
  <QueryClientProvider client={client}>
    <MemoryRouter>
      <Routes>
        <Route element={<Outlet context={{ profile: { is_staff: isStaff } }} />}>
          <Route index element={<IntegrationLMSPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  </QueryClientProvider>
);
const renderPage = async (isStaff = true) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const view = render(page(client, isStaff));
  fireEvent.click(screen.getByRole('tab', { name: "File d'attente" }));
  await screen.findByText(event.erreur);
  return { ...view, client };
};

beforeEach(() => {
  jest.clearAllMocks();
  getConfig.mockReturnValue({
    SIS_MODE: 'dual',
    SIS_SECONDAIRE_API_URL: 'https://secondaire.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superieur.example/api/v1',
  });
  window.history.replaceState({}, '', '/admin/integration-lms?sis=secondaire');
  getAuthenticatedHttpClient.mockReturnValue({ get, post });
  post.mockResolvedValue(queued);
  get.mockImplementation(async (url) => {
    const parsed = new URL(url);
    const failures = parsed.searchParams.getAll('statut');
    return {
      data: {
        results: [failures.length ? failedEvent : event],
        count: failures.length ? 1 : 51,
        next: failures.length || parsed.searchParams.get('page') === '2' ? null : `${url}&page=2`,
        previous: parsed.searchParams.get('page') === '2' ? endpoint('secondaire') : null,
      },
    };
  });
  [useIntegrationCourseMappings, useIntegrationHealth, useIntegrationUserMappings]
    .forEach(hook => hook.mockReturnValue({ data: {}, refetch: jest.fn(), invalidatePages: jest.fn() }));
  useIntegrationStats.mockReturnValue({
    data: { outbox: { pending: 1, dead: 1 } }, refetch: statsRefresh,
  });
});

describe('LMS contract availability', () => {
  it('distinguishes local SIS authentication from an unavailable LMS', async () => {
    useIntegrationHealth.mockReturnValue({
      data: {
        configured: false,
        connected: false,
        missing_configuration: ['EDX_OAUTH_CLIENT_ID'],
        oauth_status: 'unavailable',
        webhook_status: 'unverified',
      },
      refetch: jest.fn(),
    });
    await renderPage();
    expect(screen.getByText('LMS indisponible')).toBeInTheDocument();
    expect(screen.getByText(/L’authentification locale du SIS ne donne pas accès/)).toBeInTheDocument();
    expect(screen.getByText(/Paramètres manquants : EDX_OAUTH_CLIENT_ID/)).toBeInTheDocument();
    expect(screen.queryByText('Contrat disponible')).not.toBeInTheDocument();
  });

  it('does not present a heartbeat or an unverified extension as ready', async () => {
    useIntegrationHealth.mockReturnValue({
      data: {
        configured: true, connected: false, oauth_status: 'unverified', webhook_status: 'unverified',
      },
      refetch: jest.fn(),
    });
    await renderPage();
    expect(screen.getByText(/Un heartbeat seul ne valide pas/)).toBeInTheDocument();
    expect(screen.getByText(/Les notes LMS restent des propositions/)).toBeInTheDocument();
  });
});

describe('first SIS to LMS association', () => {
  const candidate = {
    user_sis: 41,
    user_sis_name: 'Premier utilisateur',
    user_sis_username: 'premier',
    username_edx: 'sis_server_canonical_41',
    user_id_edx: null,
    actif: true,
  };
  const laterCandidate = {
    ...candidate, user_sis: 91, user_sis_name: 'Candidat suivant', username_edx: 'sis_server_canonical_91',
  };
  const mapping = {
    ...candidate, id: 107, user_id_edx: 83, date_sync: '2026-11-04T10:00:00Z',
  };
  const receipt = { status: 200, data: { status: 'ok', username_edx: candidate.username_edx, user_id_edx: 83 } };
  const candidateUrls = () => urls().filter(url => url.includes('/mappings/users/candidates/'));
  const emptyPage = {
    count: 0, results: [], next: null, previous: null,
  };
  let associated;
  const renderUsers = async (isStaff = true) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
    const view = render(page(client, isStaff));
    await screen.findByText('Aucune association LMS enregistrée.');
    return { ...view, client };
  };
  const showCandidates = async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Associer un utilisateur' }));
    await screen.findByText(candidate.user_sis_name);
  };
  const openCandidate = (selected = candidate) => fireEvent.click(screen.getByRole('button', {
    name: `Associer l’identité LMS de ${selected.user_sis_name} (${selected.username_edx})`,
  }));
  const confirm = () => fireEvent.click(screen.getByRole('checkbox', { name: /Je confirme la création/ }));
  const associate = () => fireEvent.click(screen.getByRole('button', { name: 'Associer cette identité' }));
  const close = async (name = 'Fermer') => {
    fireEvent.click(screen.getByRole('button', { name }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  };

  beforeEach(() => {
    associated = false;
    useIntegrationUserMappings.mockImplementation(jest.requireActual('../../services/api').useIntegrationUserMappings);
    const otherGet = get.getMockImplementation();
    get.mockImplementation(async (url, options) => {
      if (url.includes('/mappings/users/candidates/')) {
        return { data: { ...emptyPage, count: associated ? 0 : 1, results: associated ? [] : [candidate] } };
      }
      if (url.includes('/mappings/users/')) {
        return { data: { ...emptyPage, count: associated ? 1 : 0, results: associated ? [mapping] : [] } };
      }
      return otherGet(url, options);
    });
    post.mockResolvedValue(receipt);
  });

  it.each(['secondaire', 'superieur'])('associates a candidate without mapping.id once, after confirmation only, in %s', async (variant) => {
    window.history.replaceState({}, '', `/admin/integration-lms?sis=${variant}`);
    const pending = deferred();
    post.mockImplementation(() => {
      associated = true;
      return pending.promise;
    });
    await renderUsers();
    expect(candidateUrls()).toEqual([]);
    await showCandidates();
    expect(screen.getAllByRole('table')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Synchroniser tous' })).toBeDisabled();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    openCandidate();
    expect(screen.getByRole('dialog')).toHaveTextContent('Première association');
    expect(screen.getByRole('dialog')).toHaveTextContent(candidate.username_edx);
    expect(screen.getByRole('button', { name: 'Associer cette identité' })).toBeDisabled();
    associate();
    confirm();
    await close('Annuler');
    expect(post).not.toHaveBeenCalled();
    openCandidate();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    confirm();
    associate();
    associate();
    expect(post.mock.calls).toEqual([[`${endpoint(variant)}/sync/user/41/`, {}]]);
    expect(screen.getByRole('checkbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Fermer' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Associer cette identité' })).toBeDisabled();
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.queryByText(/Synchronisation de l’identité confirmée/)).not.toBeInTheDocument();
    await act(async () => pending.resolve(receipt));
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    expect(screen.getByRole('dialog')).toHaveTextContent('ID LMS : 83');
    await waitFor(() => expect(candidateUrls()).toHaveLength(2));
    await close();
    expect(await screen.findByText('Aucun utilisateur actif sans association LMS.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Voir les associations' }));
    await screen.findByText('83');
    expect(screen.getAllByRole('table')).toHaveLength(1);
    expect(candidateUrls()).toEqual(Array(2).fill(`${endpoint(variant)}/mappings/users/candidates/?page=1`));
    expect(post).toHaveBeenCalledTimes(1);
  });

  it('does not load or reveal candidates outside the admin users view, even from cached data after role loss', async () => {
    const view = await renderUsers(false);
    expect(screen.queryByRole('button', { name: 'Associer un utilisateur' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }));
    expect(candidateUrls()).toEqual([]);
    view.rerender(page(view.client));
    fireEvent.click(screen.getByRole('tab', { name: 'Cours' }));
    expect(candidateUrls()).toEqual([]);
    fireEvent.click(screen.getByRole('tab', { name: 'Utilisateurs' }));
    await showCandidates();
    view.rerender(page(view.client, false));
    expect(screen.queryByText(candidate.user_sis_name)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Associer un utilisateur' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }));
    expect(candidateUrls()).toHaveLength(1);
    expect(post).not.toHaveBeenCalled();
  });

  it.each([
    [403, 'Accès refusé'],
    [404, 'Page introuvable'],
    [503, 'Service indisponible'],
    [null, 'Réseau indisponible'],
  ])('shows an explicit candidate read failure (%s), not a false empty list, and retries on refresh', async (status, detail) => {
    await renderUsers();
    const currentGet = get.getMockImplementation();
    get.mockImplementation((url, options) => {
      if (url.includes('/candidates/')) {
        return Promise.reject(status ? { response: { status, data: { detail } } } : new Error(detail));
      }
      return currentGet(url, options);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Associer un utilisateur' }));
    const error = await screen.findByText(/Impossible de charger les utilisateurs à associer/);
    expect(error).toHaveTextContent(detail);
    if (status) { expect(error).toHaveTextContent(`HTTP ${status}`); }
    expect(screen.queryByText('Aucun utilisateur actif sans association LMS.')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Associer l’identité/ })).not.toBeInTheDocument();
    get.mockImplementation(currentGet);
    fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }));
    await screen.findByText(candidate.user_sis_name);
    expect(candidateUrls()).toHaveLength(2);
    expect(screen.getAllByRole('table')).toHaveLength(1);
    expect(post).not.toHaveBeenCalled();
  });

  it.each(['forbidden', 'wrong identity'])('does not confirm a first association for %s and requires a new confirmation', async (failure) => {
    if (failure === 'forbidden') {
      post.mockRejectedValueOnce({ response: { status: 403, data: { detail: 'Association refusée.' } } });
    } else {
      post.mockResolvedValueOnce({ ...receipt, data: { ...receipt.data, username_edx: 'wrong_identity' } });
    }
    await renderUsers();
    await showCandidates();
    openCandidate();
    confirm();
    associate();
    await screen.findByText(/Synchronisation non confirmée/);
    expect(screen.queryByText(/Synchronisation de l’identité confirmée/)).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Réessayer la même identité' })).toBeDisabled();
    expect(post).toHaveBeenCalledTimes(1);
  });

  it('retains uncertainty across candidate disappearance, refresh and reopening the new mapping by the same scoped identity', async () => {
    post.mockImplementationOnce(async () => {
      associated = true;
      throw new Error('Réponse perdue après le premier commit.');
    });
    const view = await renderUsers();
    await showCandidates();
    openCandidate();
    confirm();
    associate();
    await screen.findByText(/Synchronisation non confirmée/);
    await waitFor(() => expect(candidateUrls()).toHaveLength(2));
    await close();
    await screen.findByText('Aucun utilisateur actif sans association LMS.');
    fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }));
    fireEvent.click(screen.getByRole('button', { name: 'Voir les associations' }));
    const actionName = `Synchroniser l’identité LMS de ${mapping.user_sis_name} (${mapping.username_edx})`;
    await waitFor(() => expect(screen.getByRole('button', { name: actionName })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: actionName }));
    expect(screen.getByRole('dialog')).toHaveTextContent('Réponse perdue après le premier commit.');
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Réessayer la même identité' })).toBeDisabled();
    await close();
    window.history.replaceState({}, '', '/admin/integration-lms?sis=superieur');
    view.rerender(page(view.client));
    await waitFor(() => expect(screen.getByRole('button', { name: actionName })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: actionName }));
    expect(screen.queryByText(/Synchronisation non confirmée/)).not.toBeInTheDocument();
    await close('Annuler');
    window.history.replaceState({}, '', '/admin/integration-lms?sis=secondaire');
    view.rerender(page(view.client));
    await waitFor(() => expect(screen.getByRole('button', { name: actionName })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: actionName }));
    expect(screen.getByRole('dialog')).toHaveTextContent('Synchronisation non confirmée');
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    confirm();
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer la même identité' }));
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    expect(post.mock.calls).toEqual(Array(2).fill([`${endpoint('secondaire')}/sync/user/41/`, {}]));
  });

  it('locks a pending first association when returning to its new mapping after a SIS switch', async () => {
    const pending = deferred();
    post.mockImplementationOnce(() => {
      associated = true;
      return pending.promise;
    });
    const view = await renderUsers();
    await showCandidates();
    openCandidate();
    confirm();
    associate();
    window.history.replaceState({}, '', '/admin/integration-lms?sis=superieur');
    view.rerender(page(view.client));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const actionName = `Synchroniser l’identité LMS de ${mapping.user_sis_name} (${mapping.username_edx})`;
    await waitFor(() => expect(screen.getByRole('button', { name: actionName })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: actionName }));
    expect(screen.getByRole('checkbox')).toBeEnabled();
    expect(screen.queryByText(/Synchronisation en cours/)).not.toBeInTheDocument();
    await close('Annuler');
    window.history.replaceState({}, '', '/admin/integration-lms?sis=secondaire');
    view.rerender(page(view.client));
    await waitFor(() => expect(screen.getByRole('button', { name: actionName })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: actionName }));
    expect(screen.getByRole('checkbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Fermer' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Synchroniser cette identité' }));
    expect(post).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve({ status: 200, data: null }));
    await screen.findByText(/Synchronisation non confirmée/);
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    post.mockResolvedValueOnce({ ...receipt, data: { ...receipt.data, user_id_edx: 84 } });
    confirm();
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer la même identité' }));
    await screen.findByText(/Synchronisation non confirmée/);
    expect(screen.queryByText(/Synchronisation de l’identité confirmée/)).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    confirm();
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer la même identité' }));
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    expect(post.mock.calls).toEqual(Array(3).fill([`${endpoint('secondaire')}/sync/user/41/`, {}]));
    expect(candidateUrls().every(url => url.startsWith(endpoint('secondaire')))).toBe(true);
  });

  it('recovers a removed last candidate page explicitly, keeps its receipt, and invalidates only own cached pages', async () => {
    let removed = false;
    const currentGet = get.getMockImplementation();
    get.mockImplementation(async (url, options) => {
      if (!url.includes('/candidates/')) { return currentGet(url, options); }
      const second = new URL(url).searchParams.get('page') === '2';
      if (second && removed) {
        throw Object.assign(new Error('Page non valide.'), { response: { status: 404 } });
      }
      return {
        data: {
          count: removed ? 1 : 2,
          results: second ? [laterCandidate] : [candidate],
          next: second || removed ? null : '?page=2',
          previous: second ? '?page=1' : null,
        },
      };
    });
    post.mockImplementation(async () => {
      removed = true;
      return { ...receipt, data: { ...receipt.data, username_edx: laterCandidate.username_edx } };
    });
    const view = await renderUsers();
    const ownKeys = [
      ['integration', 'user-mappings', 2, endpoint('secondaire')],
      ['integration', 'user-candidates', 3, endpoint('secondaire')],
    ];
    const otherKeys = ownKeys.map(key => [...key.slice(0, 3), endpoint('superieur')]);
    [...ownKeys, ...otherKeys].forEach(key => view.client.setQueryData(key, emptyPage));
    await showCandidates();
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
    await screen.findByText(laterCandidate.user_sis_name);
    openCandidate(laterCandidate);
    confirm();
    associate();
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    await waitFor(() => expect(screen.getByText(/La page 2 n’existe plus \(404\)/)).toBeInTheDocument());
    expect(screen.getByRole('dialog')).toHaveTextContent(laterCandidate.username_edx);
    expect(screen.getByRole('dialog')).toHaveTextContent('ID LMS : 83');
    ownKeys.forEach(key => expect(view.client.getQueryState(key).isInvalidated).toBe(true));
    otherKeys.forEach(key => expect(view.client.getQueryState(key).isInvalidated).toBe(false));
    await close();
    await screen.findByText(candidate.user_sis_name);
    expect(screen.getByText(/1 résultat\(s\) — page 1/)).toBeInTheDocument();
    expect(screen.queryByText('Aucun utilisateur actif sans association LMS.')).not.toBeInTheDocument();
    expect(candidateUrls().filter(url => url.endsWith('?page=1'))).toHaveLength(2);
    expect(post.mock.calls).toEqual([[`${endpoint('secondaire')}/sync/user/91/`, {}]]);
  });
});

it.each(['secondaire', 'superieur'])('requests one current-tenant task and reports queued, not completed, for %s', async (variant) => {
  window.history.replaceState({}, '', `/admin/integration-lms?sis=${variant}`);
  const pending = deferred();
  post.mockReturnValue(pending.promise);
  await renderPage();
  clickProcess();
  const button = screen.getByRole('button', { name: 'Demande en cours…' });
  expect(button).toBeDisabled();
  fireEvent.click(button);
  expect(post).toHaveBeenCalledTimes(1);
  expect(post).toHaveBeenCalledWith(`${endpoint(variant)}/outbox/process/`, {});
  expect(screen.queryByText(/La mise en file est confirmée/)).not.toBeInTheDocument();
  await act(async () => pending.resolve(queued));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'La mise en file est confirmée, pas la synchronisation.',
  );
  expect(screen.getByRole('alert')).toHaveTextContent('outbox-task-123');
  await waitFor(() => expect(urls()).toHaveLength(2));
  expect(urls().every(url => url.startsWith(endpoint(variant)))).toBe(true);
  expect(statsRefresh).toHaveBeenCalledTimes(1);
  expect(screen.getByText(event.erreur)).toBeInTheDocument();
});

it('displays broker failure without announcing success and permits another request', async () => {
  post.mockRejectedValueOnce({ response: { status: 503, data: { error: 'La mise en file n’est pas confirmée.' } } });
  await renderPage();
  clickProcess();
  expect(await screen.findByRole('alert')).toHaveTextContent('La mise en file n’est pas confirmée.');
  expect(screen.queryByText(/Traitement demandé pour cet établissement/)).not.toBeInTheDocument();
  expect(screen.getByText(event.erreur)).toBeInTheDocument();
  expect(statsRefresh).toHaveBeenCalledTimes(1);
  clickProcess();
  await screen.findByText(/Traitement demandé pour cet établissement/);
  expect(post).toHaveBeenCalledTimes(2);
});

it.each([
  { status: 200, data: { status: 'ok', task_id: '123' } },
  { status: 202, data: { status: 'queued' } },
])('does not claim queuing for an invalid response %p', async (response) => {
  post.mockResolvedValue(response);
  await renderPage();
  clickProcess();
  expect(await screen.findByRole('alert')).toHaveTextContent('Le serveur n’a pas confirmé la mise en file');
  expect(screen.queryByText(/Traitement demandé pour cet établissement/)).not.toBeInTheDocument();
});

it('filters failures server-side, resets pagination, and keeps details read-only', async () => {
  await renderPage();
  fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
  await waitFor(() => expect(urls()).toContain(`${endpoint('secondaire')}/outbox/?page=2`));
  fireEvent.click(screen.getByRole('button', { name: 'Voir les échecs' }));
  await screen.findByText(failedEvent.erreur);
  expect(urls()).toContain(`${endpoint('secondaire')}/outbox/?page=1&statut=failed&statut=dead`);
  expect(screen.getByText(/1 résultat\(s\) — page 1/)).toBeInTheDocument();
  expect(screen.queryByText(event.erreur)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Voir les détails de l’événement 12' }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText(failedEvent.erreur)).toBeInTheDocument();
  expect(within(dialog).getByText(/Aucune décision d’accès, version ou preuve/)).toBeInTheDocument();
  expect(within(dialog).getAllByRole('button')).toHaveLength(1);
  fireEvent.click(within(dialog).getByRole('button', { name: 'Fermer' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Voir tous les événements' }));
  await screen.findByText(event.erreur);
  expect(screen.queryByRole('button', { name: /Purger|Relancer/ })).not.toBeInTheDocument();
  expect(post).not.toHaveBeenCalled();
});

it('hides processing from lower roles and refuses demo requests rather than simulating success', async () => {
  const view = await renderPage(false);
  expect(screen.queryByRole('button', { name: 'Demander le traitement' })).not.toBeInTheDocument();
  view.rerender(page(view.client, true));
  getConfig.mockReturnValue({ ...getConfig(), USE_MOCK_API: true });
  clickProcess();
  expect(await screen.findByRole('alert')).toHaveTextContent('indisponible en mode démonstration');
  expect(post).not.toHaveBeenCalled();
});

it('shows a failed filter request and restores the unfiltered pending evidence', async () => {
  await renderPage();
  get.mockRejectedValueOnce(new Error('API unavailable'));
  fireEvent.click(screen.getByRole('button', { name: 'Voir les échecs' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Impossible de charger la supervision Open edX');
  fireEvent.click(screen.getByRole('button', { name: 'Voir tous les événements' }));
  await screen.findByText(event.erreur);
  expect(post).not.toHaveBeenCalled();
});

it('does not show a late result or refetch the other institution after a scope switch', async () => {
  const pending = deferred();
  post.mockReturnValue(pending.promise);
  const view = await renderPage();
  clickProcess();
  window.history.replaceState({}, '', '/admin/integration-lms?sis=superieur');
  view.rerender(page(view.client));
  await waitFor(() => expect(urls()).toContain(`${endpoint('superieur')}/outbox/?page=1`));
  await act(async () => pending.resolve(queued));
  expect(screen.queryByText(/Traitement demandé pour cet établissement/)).not.toBeInTheDocument();
  expect(post).toHaveBeenCalledWith(`${endpoint('secondaire')}/outbox/process/`, {});
  expect(urls().filter(url => url.startsWith(endpoint('superieur')))).toHaveLength(1);
});

describe('individual user synchronization', () => {
  const mapping = {
    id: 7,
    user_sis: 41,
    user_sis_name: 'Alice Martin',
    user_sis_username: 'alice',
    username_edx: 'sis_owned_alice',
    user_id_edx: null,
    date_sync: null,
    actif: true,
  };
  const inactive = {
    ...mapping, id: 8, user_sis: 42, user_sis_name: 'Compte inactif', username_edx: 'sis_owned_inactive', actif: false,
  };
  const secondPage = {
    ...mapping, id: 57, user_sis: 91, user_sis_name: 'Dernière page', username_edx: 'sis_owned_last',
  };
  const receipt = { status: 200, data: { status: 'ok', username_edx: mapping.username_edx, user_id_edx: 83 } };
  const userUrls = () => urls().filter(url => url.includes('/mappings/users/'));
  const openIdentity = (userMapping = mapping) => fireEvent.click(screen.getByRole('button', {
    name: `Synchroniser l’identité LMS de ${userMapping.user_sis_name} (${userMapping.username_edx})`,
  }));
  const confirmIdentity = () => fireEvent.click(screen.getByRole('checkbox', { name: /Je confirme la création/ }));
  const synchronize = () => fireEvent.click(screen.getByRole('button', { name: 'Synchroniser cette identité' }));
  const renderUsers = async (isStaff = true) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
    const view = render(page(client, isStaff));
    await screen.findByText(mapping.user_sis_name);
    return { ...view, client };
  };

  beforeEach(() => {
    useIntegrationUserMappings.mockImplementation(jest.requireActual('../../services/api').useIntegrationUserMappings);
    const otherGet = get.getMockImplementation();
    get.mockImplementation(async (url, options) => {
      if (!url.includes('/mappings/users/')) { return otherGet(url, options); }
      const isSecondPage = new URL(url).searchParams.get('page') === '2';
      return {
        data: {
          count: 51,
          results: isSecondPage ? [secondPage] : [mapping, inactive],
          next: isSecondPage ? null : '?page=2',
          previous: isSecondPage ? '?page=1' : null,
        },
      };
    });
    post.mockResolvedValue(receipt);
  });

  it.each(['secondaire', 'superieur'])('confirms and synchronizes the selected SIS user only once in %s', async (variant) => {
    window.history.replaceState({}, '', `/admin/integration-lms?sis=${variant}`);
    const pending = deferred();
    post.mockReturnValue(pending.promise);
    await renderUsers();
    const row = screen.getByText(mapping.user_sis_name).closest('tr');
    expect(within(row).getByText('-')).toBeInTheDocument();
    expect(within(row).getByText('Jamais')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Synchroniser tous' })).toBeDisabled();
    openIdentity();
    expect(screen.getByRole('dialog')).toHaveTextContent(`Identité LMS : ${mapping.username_edx}`);
    expect(screen.getByRole('dialog')).toHaveTextContent('n’accorde aucun droit d’enseignement ou d’administration');
    expect(screen.getByRole('button', { name: 'Synchroniser cette identité' })).toBeDisabled();
    synchronize();
    expect(post).not.toHaveBeenCalled();
    confirmIdentity();
    synchronize();
    synchronize();
    expect(post.mock.calls).toEqual([[`${endpoint(variant)}/sync/user/41/`, {}]]);
    expect(screen.getByRole('button', { name: 'Synchroniser cette identité' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Fermer' })).toBeDisabled();
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.queryByText(/Synchronisation de l’identité confirmée/)).not.toBeInTheDocument();
    await act(async () => pending.resolve(receipt));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      `Synchronisation de l’identité confirmée par le serveur : ${mapping.username_edx}. ID LMS : 83.`,
    );
    await waitFor(() => expect(userUrls()).toHaveLength(2));
    expect(userUrls()).toEqual(Array(2).fill(`${endpoint(variant)}/mappings/users/?page=1`));
    expect(statsRefresh).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Fermer' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    openIdentity();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Synchroniser cette identité' })).toBeDisabled();
  });

  it('cancels without posting and does not preserve a discarded confirmation', async () => {
    await renderUsers();
    openIdentity();
    confirmIdentity();
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(post).not.toHaveBeenCalled();
    expect(statsRefresh).not.toHaveBeenCalled();
    openIdentity();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    synchronize();
    expect(post).not.toHaveBeenCalled();
  });

  it('blocks non-staff and inactive mappings, including staff permission lost after confirmation', async () => {
    const view = await renderUsers(false);
    openIdentity();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    view.rerender(page(view.client));
    openIdentity(inactive);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    openIdentity();
    confirmIdentity();
    view.rerender(page(view.client, false));
    expect(screen.getByRole('button', { name: 'Synchroniser cette identité' })).toBeDisabled();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    synchronize();
    view.rerender(page(view.client));
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(post).not.toHaveBeenCalled();
  });

  it('invalidates confirmation if a refreshed mapping is revoked', async () => {
    const view = await renderUsers();
    openIdentity();
    confirmIdentity();
    act(() => view.client.setQueryData(['integration', 'user-mappings', 1, endpoint('secondaire')], {
      results: [{ ...mapping, actif: false }], count: 1, next: null, previous: null,
    }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Synchroniser cette identité' })).toBeDisabled());
    synchronize();
    expect(post).not.toHaveBeenCalled();
  });

  it.each([
    ['missing native ID', { status: 200, data: { status: 'ok', username_edx: mapping.username_edx } }],
    ['invalid native ID', { ...receipt, data: { ...receipt.data, user_id_edx: '83' } }],
    ['different identity', { ...receipt, data: { ...receipt.data, username_edx: 'other_identity' } }],
    ['missing status', { ...receipt, data: { ...receipt.data, status: undefined } }],
  ])('reports %s as uncertainty and requires another confirmation for the same identity', async (label, response) => {
    post.mockResolvedValueOnce(response);
    await renderUsers();
    openIdentity();
    confirmIdentity();
    synchronize();
    expect(await screen.findByText(/Synchronisation non confirmée/)).toBeInTheDocument();
    expect(screen.getByText(/n’a pas confirmé l’identité LMS/)).toBeInTheDocument();
    expect(screen.queryByText(/Synchronisation de l’identité confirmée/)).not.toBeInTheDocument();
    await waitFor(() => expect(userUrls()).toHaveLength(2));
    expect(statsRefresh).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    const retry = screen.getByRole('button', { name: 'Réessayer la même identité' });
    expect(retry).toBeDisabled();
    fireEvent.click(retry);
    expect(post).toHaveBeenCalledTimes(1);
    confirmIdentity();
    fireEvent.click(retry);
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    expect(post.mock.calls).toEqual(Array(2).fill([`${endpoint('secondaire')}/sync/user/41/`, {}]));
  });

  it.each([
    new Error('Réponse perdue'),
    { response: { status: 500, data: { error: 'Un compte SIS désactivé ne peut pas être provisionné.' } } },
  ])('retains uncertainty after a transport/backend error and retries the same identity after reopening', async (error) => {
    post.mockRejectedValueOnce(error);
    await renderUsers();
    openIdentity();
    confirmIdentity();
    synchronize();
    await screen.findByText(/Synchronisation non confirmée/);
    expect(screen.getByText(error.message || error.response.data.error)).toBeInTheDocument();
    await waitFor(() => expect(userUrls()).toHaveLength(2));
    expect(statsRefresh).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Fermer' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    openIdentity();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Réessayer la même identité' })).toBeDisabled();
    confirmIdentity();
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer la même identité' }));
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    expect(post.mock.calls).toEqual(Array(2).fill([`${endpoint('secondaire')}/sync/user/41/`, {}]));
  });

  it('does not confirm replacement of an already known native ID and retries the original identity', async () => {
    const view = await renderUsers();
    act(() => view.client.setQueryData(['integration', 'user-mappings', 1, endpoint('secondaire')], {
      results: [{ ...mapping, user_id_edx: 83 }], count: 1, next: null, previous: null,
    }));
    await screen.findByText('83');
    post.mockResolvedValue({ ...receipt, data: { ...receipt.data, user_id_edx: 84 } });
    openIdentity();
    confirmIdentity();
    synchronize();
    await screen.findByText(/Synchronisation non confirmée/);
    expect(screen.queryByText(/Synchronisation de l’identité confirmée/)).not.toBeInTheDocument();
    await waitFor(() => expect(userUrls()).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: 'Fermer' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    openIdentity();
    confirmIdentity();
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer la même identité' }));
    await screen.findByText(/Synchronisation non confirmée/);
    expect(screen.queryByText(/Synchronisation de l’identité confirmée/)).not.toBeInTheDocument();
    post.mockResolvedValue(receipt);
    confirmIdentity();
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer la même identité' }));
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    expect(post.mock.calls).toEqual(Array(3).fill([`${endpoint('secondaire')}/sync/user/41/`, {}]));
  });

  it('refuses demo mode rather than using simulated provisioning', async () => {
    await renderUsers();
    getConfig.mockReturnValue({ ...getConfig(), USE_MOCK_API: true });
    openIdentity();
    expect(screen.getByRole('alert')).toHaveTextContent('mode démonstration');
    expect(screen.getByRole('checkbox')).toBeDisabled();
    synchronize();
    expect(post).not.toHaveBeenCalled();
  });

  it('clears unsubmitted confirmation on a SIS switch and isolates pending results and refetches', async () => {
    const pending = deferred();
    const view = await renderUsers();
    openIdentity();
    confirmIdentity();
    window.history.replaceState({}, '', '/admin/integration-lms?sis=superieur');
    view.rerender(page(view.client));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() => expect(userUrls()).toContain(`${endpoint('superieur')}/mappings/users/?page=1`));
    await screen.findByText(mapping.user_sis_name);
    openIdentity();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(post).not.toHaveBeenCalled();
    post.mockReturnValueOnce(pending.promise);
    confirmIdentity();
    synchronize();
    window.history.replaceState({}, '', '/admin/integration-lms?sis=secondaire');
    view.rerender(page(view.client));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await screen.findByText(mapping.user_sis_name);
    openIdentity();
    confirmIdentity();
    const readsBefore = userUrls().length;
    await act(async () => pending.resolve(receipt));
    expect(screen.getByRole('checkbox')).toBeChecked();
    expect(screen.queryByText(/Synchronisation de l’identité confirmée/)).not.toBeInTheDocument();
    expect(statsRefresh).not.toHaveBeenCalled();
    expect(userUrls()).toHaveLength(readsBefore);
    synchronize();
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    expect(post.mock.calls).toEqual([
      [`${endpoint('superieur')}/sync/user/41/`, {}],
      [`${endpoint('secondaire')}/sync/user/41/`, {}],
    ]);
  });

  it('keeps an in-flight identity locked after leaving and returning to its SIS scope', async () => {
    const pending = deferred();
    post.mockReturnValue(pending.promise);
    const view = await renderUsers();
    openIdentity();
    confirmIdentity();
    synchronize();
    window.history.replaceState({}, '', '/admin/integration-lms?sis=superieur');
    view.rerender(page(view.client));
    await waitFor(() => expect(userUrls()).toContain(`${endpoint('superieur')}/mappings/users/?page=1`));
    window.history.replaceState({}, '', '/admin/integration-lms?sis=secondaire');
    view.rerender(page(view.client));
    await screen.findByText(mapping.user_sis_name);
    openIdentity();
    expect(screen.getByRole('button', { name: 'Synchroniser cette identité' })).toBeDisabled();
    synchronize();
    expect(post).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(receipt));
    await screen.findByText(/Synchronisation de l’identité confirmée/);
  });

  it('loads actual API pages, refreshes the selected page after synchronization, and resets scope to page one', async () => {
    const view = await renderUsers();
    expect(screen.getByRole('button', { name: 'Précédent' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
    await screen.findByText(secondPage.user_sis_name);
    expect(userUrls()).toContain(`${endpoint('secondaire')}/mappings/users/?page=2`);
    expect(screen.queryByText(mapping.user_sis_name)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Suivant' })).toBeDisabled();
    expect(screen.getByText(/51 résultat\(s\) — page 2/)).toBeInTheDocument();
    post.mockResolvedValue({ ...receipt, data: { ...receipt.data, username_edx: secondPage.username_edx } });
    openIdentity(secondPage);
    confirmIdentity();
    synchronize();
    await screen.findByText(/Synchronisation de l’identité confirmée/);
    expect(post).toHaveBeenCalledWith(`${endpoint('secondaire')}/sync/user/91/`, {});
    await waitFor(() => expect(userUrls().filter(url => url.endsWith('?page=2'))).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: 'Fermer' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Précédent' }));
    await screen.findByText(mapping.user_sis_name);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Suivant' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
    await screen.findByText(secondPage.user_sis_name);
    window.history.replaceState({}, '', '/admin/integration-lms?sis=superieur');
    view.rerender(page(view.client));
    await screen.findByText(mapping.user_sis_name);
    expect(screen.getByText(/51 résultat\(s\) — page 1/)).toBeInTheDocument();
    expect(userUrls()).toContain(`${endpoint('superieur')}/mappings/users/?page=1`);
    expect(userUrls()).not.toContain(`${endpoint('superieur')}/mappings/users/?page=2`);
  });

  it('disables repeated pagination and ignores an obsolete page response after switching SIS', async () => {
    const pending = deferred();
    const currentGet = get.getMockImplementation();
    get.mockImplementation((url, options) => (
      url === `${endpoint('secondaire')}/mappings/users/?page=2` ? pending.promise : currentGet(url, options)
    ));
    const view = await renderUsers();
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
    expect(screen.getByRole('button', { name: 'Suivant' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
    expect(userUrls().filter(url => url.endsWith('?page=2'))).toHaveLength(1);
    const [, { signal }] = get.mock.calls.find(([url]) => url.endsWith('/mappings/users/?page=2'));
    window.history.replaceState({}, '', '/admin/integration-lms?sis=superieur');
    view.rerender(page(view.client));
    await screen.findByText(mapping.user_sis_name);
    expect(signal.aborted).toBe(true);
    await act(async () => pending.resolve({
      data: {
        count: 51, results: [secondPage], next: null, previous: '?page=1',
      },
    }));
    expect(screen.queryByText(secondPage.user_sis_name)).not.toBeInTheDocument();
    expect(screen.getByText(/51 résultat\(s\) — page 1/)).toBeInTheDocument();
    expect(userUrls()).not.toContain(`${endpoint('superieur')}/mappings/users/?page=2`);
    expect(post).not.toHaveBeenCalled();
  });

  it.each(['confirmed', 'uncertain'])('invalidates all own cached pages after %s completion, not another SIS', async (status) => {
    const view = await renderUsers();
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
    await screen.findByText(secondPage.user_sis_name);
    fireEvent.click(screen.getByRole('button', { name: 'Précédent' }));
    await screen.findByText(mapping.user_sis_name);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Suivant' })).toBeEnabled());
    const ownPageKey = ['integration', 'user-mappings', 2, endpoint('secondaire')];
    const otherPageKey = ['integration', 'user-mappings', 2, endpoint('superieur')];
    view.client.setQueryData(otherPageKey, { results: [secondPage], count: 1 });
    expect(view.client.getQueryState(ownPageKey).isInvalidated).toBe(false);
    let moved = false;
    const currentGet = get.getMockImplementation();
    get.mockImplementation((url, options) => {
      if (!moved || !url.includes('/mappings/users/')) { return currentGet(url, options); }
      const isSecondPage = url.endsWith('?page=2');
      return Promise.resolve({
        data: {
          count: 51,
          results: isSecondPage ? [{ ...mapping, user_id_edx: 83 }] : [inactive],
          next: isSecondPage ? null : '?page=2',
          previous: isSecondPage ? '?page=1' : null,
        },
      });
    });
    post.mockImplementationOnce(async () => {
      moved = true;
      if (status === 'uncertain') { throw new Error('Réponse perdue'); }
      return receipt;
    });
    openIdentity();
    confirmIdentity();
    synchronize();
    await screen.findByText(status === 'uncertain'
      ? /Synchronisation non confirmée/ : /Synchronisation de l’identité confirmée/);
    await waitFor(() => expect(view.client.getQueryState(ownPageKey).isInvalidated).toBe(true));
    expect(view.client.getQueryState(otherPageKey).isInvalidated).toBe(false);
    expect(statsRefresh).toHaveBeenCalledTimes(1);
    if (status === 'uncertain') {
      confirmIdentity();
      expect(screen.getByRole('button', { name: 'Réessayer la même identité' })).toBeEnabled();
    }
    fireEvent.click(screen.getByRole('button', { name: 'Fermer' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole('button', { name: 'Suivant' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
    await screen.findByText(mapping.user_sis_name);
    expect(screen.getByText('83')).toBeInTheDocument();
    expect(userUrls().filter(url => url.endsWith('?page=2'))).toHaveLength(2);
    expect(view.client.getQueryState(otherPageKey).isInvalidated).toBe(false);
    expect(userUrls().every(url => url.startsWith(endpoint('secondaire')))).toBe(true);
    expect(post.mock.calls).toEqual([[`${endpoint('secondaire')}/sync/user/41/`, {}]]);
  });
});
