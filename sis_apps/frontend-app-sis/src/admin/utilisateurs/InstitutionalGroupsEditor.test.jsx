import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  MemoryRouter, Outlet, Route, Routes,
} from 'react-router-dom';
import { patchApi, postApi } from '../../services/api';
import { fetchAllResourcePages, fetchResourcePage } from '../../services/resources';
import InstitutionalGroupsEditor from './InstitutionalGroupsEditor';
import UtilisateursPage from './UtilisateursPage';

jest.mock('../../services/api', () => ({
  patchApi: jest.fn(), postApi: jest.fn(),
}));
jest.mock('../../services/resources', () => ({
  resourceUrl: (_variant, resource) => `https://sis.example/api/v1/${resource}/`,
  fetchAllResourcePages: jest.fn(),
  fetchResourcePage: jest.fn(),
  getEnabledVariants: () => ['secondaire'],
  apiErrorMessage: error => error?.response?.data?.detail || error?.message || 'Échec.',
}));
jest.mock('../../components/common/ResourceManager', () => function ResourceManagerMock() {
  return <div>Liste des comptes</div>;
});

const groupsUrl = 'https://sis.example/api/v1/utilisateurs/groupes/';
const permissionsUrl = 'https://sis.example/api/v1/utilisateurs/permissions/';
const usersUrl = 'https://sis.example/api/v1/utilisateurs/comptes/';
const historyUrl = 'https://sis.example/api/v1/core/workflow-events/';
const permissions = [
  {
    id: 11, app_label: 'notes', codename: 'view_note', name: 'Voir les notes',
  },
  {
    id: 12, app_label: 'notes', codename: 'change_note', name: 'Modifier les notes',
  },
];
let groups;
let users;
const allowed = [
  'auth.view_group', 'auth.add_group', 'auth.change_group',
  'utilisateurs.view_utilisateur', 'utilisateurs.change_utilisateur',
];
const renderEditor = (grants = allowed, attributes = {}) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <InstitutionalGroupsEditor variant="secondaire" capabilities={{ permissions: grants, attributes }} />
  </QueryClientProvider>,
);
const renderPage = (context) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/admin/utilisateurs?sis=secondaire']}>
      <Routes>
        <Route element={<Outlet context={context} />}>
          <Route path="/admin/utilisateurs" element={<UtilisateursPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  </QueryClientProvider>,
);

beforeEach(() => {
  jest.clearAllMocks();
  fetchResourcePage.mockReset();
  fetchResourcePage.mockResolvedValue({
    count: 0, results: [], next: null, previous: null,
  });
  groups = [{ id: 7, name: 'Équipe examens', permissions: [11] }];
  users = [{
    id: 5, username: 'jane', full_name: 'Jane Doe', groups: [3],
  }];
  fetchAllResourcePages.mockImplementation(async url => {
    if (url === groupsUrl) { return groups; }
    if (url === permissionsUrl) { return permissions; }
    if (url === usersUrl) { return users; }
    throw new Error(`URL inattendue : ${url}`);
  });
  patchApi.mockImplementation(async (_url, data) => {
    groups = [{ ...groups[0], ...data }];
    return data;
  });
  postApi.mockImplementation(async (url, data) => {
    if (url === `${groupsUrl}7/assign/`) {
      users = [{ ...users[0], groups: [...users[0].groups, 7] }];
    } else if (url === `${groupsUrl}7/unassign/`) {
      users = [{ ...users[0], groups: users[0].groups.filter(group => group !== 7) }];
    } else if ([`${groupsUrl}7/assign_many/`, `${groupsUrl}7/unassign_many/`].includes(url)) {
      users = users.map(user => (
        !data.user_ids.includes(user.id) ? user : {
          ...user,
          groups: url.endsWith('/assign_many/')
            ? [...new Set([...user.groups, 7])] : user.groups.filter(group => group !== 7),
        }
      ));
    }
    return url === groupsUrl
      ? { id: 8, name: 'Nouveau groupe', permissions: [12] } : data;
  });
});

it('loads the API catalogue, edits a group and creates one without preset role names', async () => {
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.getByRole('checkbox', { name: /Voir les notes/ })).toBeChecked();
  fireEvent.click(screen.getByRole('checkbox', { name: /Modifier les notes/ }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Nom du groupe' }), { target: { value: 'Équipe concours' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le groupe' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith(`${groupsUrl}7/`, { name: 'Équipe concours', permissions: [11, 12] }));
  await screen.findByText('Groupe enregistré.');
  fireEvent.click(screen.getByRole('button', { name: 'Créer un groupe' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Nom du groupe' }), { target: { value: 'Nouveau groupe' } });
  fireEvent.click(screen.getByRole('checkbox', { name: /Modifier les notes/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le groupe' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(groupsUrl, {
    name: 'Nouveau groupe', permissions: [12],
  }));
  expect(screen.getByText(/L’API ne permet pas de désactiver un groupe/)).toBeVisible();
});

it('adds and removes a user through the group assignment endpoints without PATCHing accounts', async () => {
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  fireEvent.mouseDown(await screen.findByRole('combobox', { name: 'Compte' }));
  fireEvent.click(screen.getByRole('option', { name: 'Jane Doe (jane)' }));
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter au groupe' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${groupsUrl}7/assign/`, { user_id: 5 }));
  await screen.findByRole('button', { name: 'Retirer du groupe' });
  fireEvent.click(screen.getByRole('button', { name: 'Retirer du groupe' }));
  await waitFor(() => expect(postApi).toHaveBeenLastCalledWith(`${groupsUrl}7/unassign/`, { user_id: 5 }));
  expect(users[0].groups).toEqual([3]);
  expect(patchApi).not.toHaveBeenCalled();
});

it('reads paginated audit snapshots for the selected group and resets on group changes', async () => {
  groups.push({ id: 8, name: 'Autre équipe', permissions: [] });
  const created = {
    id: 91,
    title: 'Création de groupe',
    actor_nom: 'Auditeur local',
    action: 'group_created',
    created_at: '2026-11-07T10:00:00Z',
    object_repr: 'Lecteurs',
    metadata: {
      before: null, after: { name: 'Lecteurs', permissions: [{ id: 11, code: 'notes.view_note' }] },
    },
  };
  const assigned = {
    ...created,
    id: 92,
    title: 'Affectation de groupe',
    action: 'assign_many',
    metadata: { user_ids: [5, 6], added_user_ids: [] },
  };
  fetchResourcePage.mockImplementation(async (_url, params) => ({
    count: 2,
    next: params.page === 1 ? '?page=2' : null,
    results: [params.page === 1 ? created : assigned],
  }));
  renderEditor([...allowed, 'core.view_workflowevent']);
  expect(fetchResourcePage).not.toHaveBeenCalled();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  await screen.findByRole('heading', { name: 'Création de groupe' });
  expect(fetchResourcePage).toHaveBeenLastCalledWith(historyUrl, {
    app_label: 'auth', model: 'group', object_id: 7, page: 1,
  }, expect.objectContaining({ signal: expect.anything() }));
  fireEvent.click(screen.getByText('Voir les changements'));
  expect(screen.getByText('Avant : Groupe absent')).toBeVisible();
  expect(screen.getByText('Après : Lecteurs — notes.view_note')).toBeVisible();
  expect(screen.getByText(/Auditeur local/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Historique suivant' }));
  await screen.findByRole('heading', { name: 'Affectation de groupe' });
  expect(screen.queryByRole('heading', { name: 'Création de groupe' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Voir les changements'));
  expect(screen.getByText('Comptes demandés : 5, 6')).toBeVisible();
  expect(screen.getByText('Ajouts effectifs : Aucun')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Historique suivant' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Autre équipe' }));
  await screen.findByRole('heading', { name: 'Création de groupe' });
  expect(fetchResourcePage).toHaveBeenLastCalledWith(historyUrl, {
    app_label: 'auth', model: 'group', object_id: 8, page: 1,
  }, expect.anything());
});

it.each([
  [allowed, {}],
  [[...allowed, 'core.view_workflowevent'], { permission_scopes: { 'core.view_workflowevent': { groupes: [7] } } }],
])('does not request audit data without an unrestricted audit permission (%j)', async (grants, attributes) => {
  renderEditor(grants, attributes);
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.queryByRole('region', { name: 'Historique des habilitations' })).not.toBeInTheDocument();
  expect(fetchResourcePage).not.toHaveBeenCalled();
});

it('refreshes history after membership changes and hides its data on a server refusal', async () => {
  renderEditor([...allowed, 'core.view_workflowevent']);
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  await screen.findByText('Aucun événement enregistré pour ce groupe.');
  fetchResourcePage.mockResolvedValue({
    count: 1,
    next: null,
    results: [{
      id: 93,
      title: 'Affectation auditée',
      actor_nom: 'Auditeur local',
      action: 'assign',
      created_at: '2026-11-07T10:00:00Z',
      object_repr: 'Équipe examens',
      metadata: { user_id: 5, added_user_ids: [5] },
    }],
  });
  fireEvent.mouseDown(await screen.findByRole('combobox', { name: 'Compte' }));
  fireEvent.click(screen.getByRole('option', { name: 'Jane Doe (jane)' }));
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter au groupe' }));
  await screen.findByRole('heading', { name: 'Affectation auditée' });
  expect(fetchResourcePage).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByText('Voir les changements'));
  expect(screen.getByText('Ajouts effectifs : 5')).toBeVisible();
  fetchResourcePage.mockRejectedValueOnce({ response: { status: 403 } });
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser l’historique' }));
  await screen.findByText('Historique non autorisé.');
  expect(screen.queryByText(/Auditeur local/)).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Affectation auditée' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }));
  await screen.findByRole('heading', { name: 'Affectation auditée' });
});

it('removes the audit panel and its cache when audit permission is withdrawn', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const tree = grants => (
    <QueryClientProvider client={client}>
      <InstitutionalGroupsEditor variant="secondaire" capabilities={{ permissions: grants }} />
    </QueryClientProvider>
  );
  const view = render(tree([...allowed, 'core.view_workflowevent']));
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  await screen.findByText('Aucun événement enregistré pour ce groupe.');
  expect(client.getQueriesData({ queryKey: ['institutional-group-history'] })).toHaveLength(1);
  view.rerender(tree(allowed));
  expect(screen.queryByRole('region', { name: 'Historique des habilitations' })).not.toBeInTheDocument();
  await waitFor(() => expect(client.getQueriesData({ queryKey: ['institutional-group-history'] })).toHaveLength(0));
  expect(fetchResourcePage).toHaveBeenCalledTimes(1);
});

const selectBatch = async () => {
  const input = await screen.findByRole('combobox', { name: 'Comptes du lot' });
  ['Jane Doe (jane)', 'John Roe (john)'].forEach(label => {
    fireEvent.change(input, { target: { value: label } });
    fireEvent.click(screen.getByRole('option', { name: label }));
  });
  fireEvent.keyDown(input, { key: 'Escape' });
};

it('adds and removes a selected batch through one atomic request and preserves unrelated memberships', async () => {
  users.push({
    id: 6, username: 'john', full_name: 'John Roe', groups: [4],
  });
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(await screen.findByRole('button', { name: 'Ajouter la sélection au groupe' })).toBeDisabled();
  await selectBatch();
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter la sélection au groupe' }));
  await screen.findByText('Affectation en lot enregistrée.');
  expect(postApi).toHaveBeenCalledTimes(1);
  expect(postApi).toHaveBeenCalledWith(`${groupsUrl}7/assign_many/`, { user_ids: [5, 6] });
  expect(users.map(user => user.groups)).toEqual([[3, 7], [4, 7]]);
  expect(screen.getByRole('button', { name: 'Retirer la sélection du groupe' })).toBeDisabled();
  await selectBatch();
  fireEvent.click(screen.getByRole('button', { name: 'Retirer la sélection du groupe' }));
  await screen.findByText('Affectation en lot enregistrée.');
  expect(postApi).toHaveBeenCalledTimes(2);
  expect(postApi).toHaveBeenLastCalledWith(`${groupsUrl}7/unassign_many/`, { user_ids: [5, 6] });
  expect(users.map(user => user.groups)).toEqual([[3], [4]]);
  expect(patchApi).not.toHaveBeenCalled();
});

it('keeps the selection and shows an explicit refused batch without a success notice', async () => {
  users.push({
    id: 6, username: 'john', full_name: 'John Roe', groups: [4],
  });
  postApi.mockRejectedValueOnce({ response: { status: 403 } });
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  await selectBatch();
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter la sélection au groupe' }));
  expect(await screen.findByText('Affectation en lot non autorisée.')).toBeVisible();
  expect(screen.queryByText('Affectation en lot enregistrée.')).not.toBeInTheDocument();
  expect(users.map(user => user.groups)).toEqual([[3], [4]]);
  expect(screen.getByText('Jane Doe (jane)')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Ajouter la sélection au groupe' })).toBeEnabled();
});

it('clears a batch when switching groups instead of silently assigning the prior selection', async () => {
  users.push({
    id: 6, username: 'john', full_name: 'John Roe', groups: [4],
  });
  groups.push({ id: 8, name: 'Autre équipe', permissions: [11] });
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  await selectBatch();
  fireEvent.click(screen.getByRole('button', { name: 'Autre équipe' }));
  expect(screen.getByRole('button', { name: 'Ajouter la sélection au groupe' })).toBeDisabled();
  expect(postApi).not.toHaveBeenCalled();
});

it('prevents switching the destination group while a batch request is pending', async () => {
  users.push({
    id: 6, username: 'john', full_name: 'John Roe', groups: [4],
  });
  groups.push({ id: 8, name: 'Autre équipe', permissions: [11] });
  let finish;
  postApi.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  await selectBatch();
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter la sélection au groupe' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Autre équipe' })).toBeDisabled());
  expect(screen.getByRole('button', { name: 'Créer un groupe' })).toBeDisabled();
  finish({ group_id: 7, user_ids: [5, 6] });
  await screen.findByText('Affectation en lot enregistrée.');
  expect(screen.getByRole('button', { name: 'Autre équipe' })).toBeEnabled();
});

it('keeps individual assignment but hides batches when an explicit empty scope is configured', async () => {
  renderEditor(allowed, { permission_scopes: { 'auth.change_group': {} } });
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(await screen.findByRole('combobox', { name: 'Compte' })).toBeVisible();
  expect(screen.queryByRole('combobox', { name: 'Comptes du lot' })).not.toBeInTheDocument();
  expect(screen.getByText('L’affectation en lot exige des permissions sans périmètre configuré.')).toBeVisible();
});

it('duplicates readable permissions into a new editable group without modifying the source or copying members', async () => {
  renderEditor(['auth.view_group', 'auth.add_group']);
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.getByRole('textbox', { name: 'Nom du groupe' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Dupliquer le groupe' }));
  expect(screen.getByRole('textbox', { name: 'Nom du groupe' })).toHaveValue('Équipe examens (copie)');
  expect(screen.getByRole('checkbox', { name: /Voir les notes/ })).toBeChecked();
  expect(screen.queryByRole('region', { name: 'Affectation des comptes' })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole('textbox', { name: 'Nom du groupe' }), { target: { value: 'Équipe corrections' } });
  fireEvent.click(screen.getByRole('checkbox', { name: /Modifier les notes/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le groupe' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(groupsUrl, {
    name: 'Équipe corrections', permissions: [11, 12],
  }));
  expect(patchApi).not.toHaveBeenCalled();
  expect(groups).toEqual([{ id: 7, name: 'Équipe examens', permissions: [11] }]);
  expect(fetchAllResourcePages).not.toHaveBeenCalledWith(usersUrl);
});

it.each([
  [['auth.view_group'], {}],
  [allowed, { permission_scopes: { 'auth.add_group': { etablissement: [1] } } }],
])('does not offer duplication without an unrestricted group creation grant', async (grants, attributes) => {
  renderEditor(grants, attributes);
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.queryByRole('button', { name: 'Dupliquer le groupe' })).not.toBeInTheDocument();
});

it('refuses to duplicate a group whose permission list was not supplied by the server', async () => {
  groups = [{ id: 7, name: 'Équipe examens' }];
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.getByText(/Les permissions de ce groupe ne sont pas disponibles/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Dupliquer le groupe' })).not.toBeInTheDocument();
});

it('preserves the accounts tab and refuses unauthorized group and membership changes', async () => {
  renderPage({ capabilities: { permissions: ['auth.view_group'] } });
  fireEvent.click(screen.getByRole('tab', { name: 'Comptes' }));
  expect(screen.getByText('Liste des comptes')).toBeVisible();
  expect(fetchAllResourcePages).not.toHaveBeenCalledWith(usersUrl);
  fireEvent.click(screen.getByRole('tab', { name: 'Groupes et permissions' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.getByText('Modification non autorisée pour ce compte.')).toBeVisible();
  expect(screen.getByText(/Affectation non autorisée/)).toBeVisible();
  expect(fetchAllResourcePages).not.toHaveBeenCalledWith(usersUrl);
});

it('requires change_group even when the account permissions permit modifications', async () => {
  renderEditor(['auth.view_group', 'utilisateurs.view_utilisateur', 'utilisateurs.change_utilisateur']);
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.getByText(/Affectation non autorisée/)).toBeVisible();
  expect(fetchAllResourcePages).not.toHaveBeenCalledWith(usersUrl);
  expect(postApi).not.toHaveBeenCalled();
});

it('does not offer group writes or assignments when group write grants are scoped', async () => {
  renderEditor(allowed, {
    permission_scopes: {
      'auth.add_group': { etablissement: [1] },
      'auth.change_group': { etablissement: [1] },
    },
  });
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.queryByRole('button', { name: 'Créer un groupe' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Enregistrer le groupe' })).not.toBeInTheDocument();
  expect(screen.getByText('Modification non autorisée pour ce compte.')).toBeVisible();
  expect(screen.getByText(/Affectation non autorisée/)).toBeVisible();
  expect(fetchAllResourcePages).not.toHaveBeenCalledWith(usersUrl);
});

it('does not fetch groups when the group view grant is scoped', () => {
  renderEditor(['auth.view_group'], { permission_scopes: { 'auth.view_group': { etablissement: [1] } } });
  expect(screen.getByText(/Accès non autorisé : permission de consultation/)).toBeVisible();
  expect(fetchAllResourcePages).not.toHaveBeenCalled();
});

it('keeps group editing available but prevents assignment when account write is scoped', async () => {
  renderEditor(allowed, { permission_scopes: { 'utilisateurs.change_utilisateur': { etablissement: [1] } } });
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(screen.getByRole('button', { name: 'Enregistrer le groupe' })).toBeVisible();
  expect(screen.getByText(/Affectation non autorisée/)).toBeVisible();
  expect(fetchAllResourcePages).not.toHaveBeenCalledWith(usersUrl);
});

it('does not fetch data for a user without group view permission', () => {
  renderEditor([]);
  expect(screen.getByText(/Accès non autorisé : permission de consultation/)).toBeVisible();
  expect(fetchAllResourcePages).not.toHaveBeenCalled();
});

it('allows retrying a failed permissions catalogue without enabling unsafe edits', async () => {
  const load = fetchAllResourcePages.getMockImplementation();
  fetchAllResourcePages.mockImplementationOnce(async () => groups);
  fetchAllResourcePages.mockRejectedValueOnce(new Error('Catalogue indisponible.'));
  fetchAllResourcePages.mockImplementation(load);
  renderEditor();
  expect(await screen.findByText('Catalogue indisponible.')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Créer un groupe' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }));
  expect(await screen.findByRole('button', { name: 'Équipe examens' })).toBeVisible();
});

it('shows a forbidden account list without offering membership changes', async () => {
  const load = fetchAllResourcePages.getMockImplementation();
  fetchAllResourcePages.mockImplementation(async url => {
    if (url === usersUrl) {
      const forbidden = new Error('Forbidden');
      forbidden.response = { status: 403 };
      throw forbidden;
    }
    return load(url);
  });
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  expect(await screen.findByText('Accès non autorisé aux comptes.')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Ajouter au groupe' })).not.toBeInTheDocument();
  expect(patchApi).not.toHaveBeenCalled();
});

it('keeps the editor closed during capability loading or failure and on a forbidden group response', async () => {
  const { rerender } = renderPage({ loading: true });
  expect(screen.getByRole('status')).toHaveTextContent('Chargement des autorisations');
  expect(fetchAllResourcePages).not.toHaveBeenCalled();
  rerender(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/admin/utilisateurs']}>
        <Routes>
          <Route element={<Outlet context={{ error: new Error('inaccessible') }} />}>
            <Route path="/admin/utilisateurs" element={<UtilisateursPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByText(/Impossible de vérifier les autorisations/)).toBeVisible();
  fetchAllResourcePages.mockRejectedValueOnce({ response: { status: 403 } });
  renderEditor();
  expect(await screen.findByText('Accès non autorisé aux groupes ou aux permissions.')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Créer un groupe' })).not.toBeInTheDocument();
});

it('reports denied group edits and denied assignments without falsely claiming success', async () => {
  patchApi.mockRejectedValueOnce({ response: { status: 403 } });
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Équipe examens' }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le groupe' }));
  expect(await screen.findByText('Enregistrement non autorisé.')).toBeVisible();
  fireEvent.mouseDown(await screen.findByRole('combobox', { name: 'Compte' }));
  fireEvent.click(screen.getByRole('option', { name: 'Jane Doe (jane)' }));
  postApi.mockRejectedValueOnce({ response: { status: 403 } });
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter au groupe' }));
  expect(await screen.findByText('Affectation non autorisée.')).toBeVisible();
  expect(postApi).toHaveBeenCalledWith(`${groupsUrl}7/assign/`, { user_id: 5 });
  expect(patchApi).toHaveBeenCalledTimes(1);
  expect(screen.queryByText('Affectation du compte enregistrée.')).not.toBeInTheDocument();
});
