import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  MemoryRouter, Outlet, Route, Routes,
} from 'react-router-dom';
import { patchApi, postApi } from '../../services/api';
import { fetchAllResourcePages } from '../../services/resources';
import InstitutionalGroupsEditor from './InstitutionalGroupsEditor';
import UtilisateursPage from './UtilisateursPage';

jest.mock('../../services/api', () => ({
  patchApi: jest.fn(), postApi: jest.fn(),
}));
jest.mock('../../services/resources', () => ({
  resourceUrl: (_variant, resource) => `https://sis.example/api/v1/${resource}/`,
  fetchAllResourcePages: jest.fn(),
  getEnabledVariants: () => ['secondaire'],
  apiErrorMessage: error => error?.response?.data?.detail || error?.message || 'Échec.',
}));
jest.mock('../../components/common/ResourceManager', () => function ResourceManagerMock() {
  return <div>Liste des comptes</div>;
});

const groupsUrl = 'https://sis.example/api/v1/utilisateurs/groupes/';
const permissionsUrl = 'https://sis.example/api/v1/utilisateurs/permissions/';
const usersUrl = 'https://sis.example/api/v1/utilisateurs/comptes/';
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
