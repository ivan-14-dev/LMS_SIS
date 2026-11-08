import React from 'react';
import {
  fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  MemoryRouter, Outlet, Route, Routes,
} from 'react-router-dom';
import { fetchApi, patchApi, postApi } from '../../services/api';
import ResourceManager from './ResourceManager';
import ResourceWorkspace from './ResourceWorkspace';
import { fetchAllResourcePages } from '../../services/resources';
import UtilisateursPage from '../../admin/utilisateurs/UtilisateursPage';

jest.mock('../../services/resources', () => ({
  ...jest.requireActual('../../services/resources'),
  fetchAllResourcePages: jest.fn(),
  exportRecords: jest.fn(),
}));

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_SECONDAIRE_API_URL: 'https://secondary.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superior.example/api/v1',
  }),
}));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  patchApi: jest.fn(),
  postApi: jest.fn(),
}));

const show = (fields = [], props = {}) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ResourceManager
      variant="secondaire"
      resource="classes/classes"
      title="Classes"
      columns={[{ Header: 'Nom', accessor: 'nom' }]}
      fields={fields}
      {...props}
    />
  </QueryClientProvider>,
);

beforeEach(() => {
  jest.clearAllMocks();
});

it.each([
  ['secondaire', 'secondary'],
  ['superieur', 'superior'],
])('creates and displays a real %s partner through the existing account form', async (variant, host) => {
  const account = {
    id: 35, username: 'partner-35', full_name: 'Compte Partenaire', role: 'partenaire', role_display: 'Partenaire', is_active: true,
  };
  let created = false;
  fetchApi.mockImplementation(async () => ({ count: created ? 1 : 0, results: created ? [account] : [] }));
  postApi.mockImplementation(async () => { created = true; return account; });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[`/admin/utilisateurs?sis=${variant}`]}>
        <Routes>
          <Route element={<Outlet context={{ capabilities: { permissions: ['*'] }, loading: false }} />}>
            <Route path="/admin/utilisateurs" element={<UtilisateursPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole('button', { name: 'Ajouter' }));
  const payload = {
    username: 'partner-35',
    first_name: 'Compte',
    last_name: 'Partenaire',
    email: 'partner@example.test',
    password: 'Synthetic-partner-test-35!',
    password_confirm: 'Synthetic-partner-test-35!',
    role: 'partenaire',
  };
  for (const [label, field] of [
    [/Identifiant/, 'username'], [/Prénom/, 'first_name'], [/^Nom/, 'last_name'], [/Email/, 'email'],
    [/Mot de passe initial/, 'password'], [/Confirmation du mot de passe/, 'password_confirm'],
  ]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value: payload[field] } });
  }
  fireEvent.mouseDown(screen.getByRole('combobox', { name: /Rôle/ }));
  fireEvent.click(screen.getByRole('option', { name: 'Partenaire', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`https://${host}.example/api/v1/utilisateurs/comptes/`, payload));
  expect(await screen.findByRole('cell', { name: 'Partenaire', exact: true })).toBeVisible();
});

it('keeps one page heading and loads only the selected service without losing its actions', async () => {
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  postApi.mockResolvedValue({ id: 1 });
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ResourceWorkspace title="Vie scolaire">
          <ResourceManager variant="secondaire" resource="clubs" title="Clubs" columns={[{ Header: 'Nom', accessor: 'nom' }]} />
          <ResourceManager
            variant="secondaire"
            resource="cantine/menus"
            title="Menus"
            columns={[{ Header: 'Plat', accessor: 'plat' }]}
            fields={[{ name: 'plat', label: 'Plat', required: true }]}
          />
        </ResourceWorkspace>
      </QueryClientProvider>
    </MemoryRouter>,
  );
  expect(fetchApi).not.toHaveBeenCalled();
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: 'Clubs', exact: true }));
  await waitFor(() => expect(fetchApi).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole('region', { name: 'Menus', exact: true })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: 'Toutes les rubriques' }));
  fireEvent.click(screen.getByRole('link', { name: 'Menus', exact: true }));
  await waitFor(() => expect(fetchApi).toHaveBeenCalledTimes(2));
  fireEvent.click(within(screen.getByRole('region', { name: 'Menus', exact: true })).getByRole('button', { name: 'Ajouter' }));
  fireEvent.change(screen.getByLabelText(/^Plat/), { target: { value: 'Riz' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith('https://secondary.example/api/v1/cantine/menus/', { plat: 'Riz' }));
  expect(screen.queryByRole('region', { name: 'Clubs', exact: true })).not.toBeInTheDocument();
});

it('requests server pages and server search rather than filtering only page one', async () => {
  fetchApi.mockImplementation(async (request) => {
    const params = new URL(request).searchParams;
    return {
      count: 51,
      results: [{ id: 1, nom: params.get('search') || (params.get('page') === '2' ? 'Classe tardive' : 'Classe initiale') }],
    };
  });
  show();
  await screen.findByText('Classe initiale');
  fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }));
  await screen.findByText('Classe tardive');
  fireEvent.change(screen.getByPlaceholderText('Rechercher...'), { target: { value: 'Recherche distante' } });
  await screen.findByText('Recherche distante');
  const finalRequest = new URL(fetchApi.mock.calls.at(-1)[0]);
  expect(finalRequest.searchParams.get('page')).toBe('1');
  expect(finalRequest.searchParams.get('search')).toBe('Recherche distante');
});

it('posts real form values and reports backend validation errors', async () => {
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  postApi.mockRejectedValue({ response: { data: { nom: ['Ce nom existe déjà.'] } } });
  show([{ name: 'nom', label: 'Nom', required: true }]);
  expect(screen.getAllByRole('heading', { name: 'Classes', exact: true })).toHaveLength(1);
  const toolbar = screen.getByRole('button', { name: 'Ajouter' }).closest('.sis-data-table');
  expect(within(toolbar).getByRole('button', { name: 'Exporter tous les résultats' })).toBeVisible();
  expect(within(toolbar).getByRole('textbox', { name: 'Rechercher' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
  fireEvent.change(screen.getByLabelText(/Nom/), { target: { value: '6e A' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/', { nom: '6e A' }));
  expect(await screen.findAllByText(/Ce nom existe déjà/)).not.toHaveLength(0);
});

it('does not submit its enclosing settings form when a dialog is saved', async () => {
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  postApi.mockResolvedValue({ id: 1 });
  const outerSubmit = jest.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <form onSubmit={outerSubmit}>
        <ResourceManager
          variant="secondaire"
          resource="etablissement/unites"
          title="Unités"
          columns={[{ Header: 'Nom', accessor: 'nom' }]}
          fields={[{ name: 'nom', label: 'Nom', required: true }]}
        />
      </form>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
  fireEvent.change(screen.getByLabelText(/Nom/), { target: { value: 'Campus' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await screen.findByText('Enregistrement effectué.');
  expect(postApi).toHaveBeenCalledTimes(1);
  expect(outerSubmit).not.toHaveBeenCalled();
});

it('loads details before editing and clears an optional number with null', async () => {
  fetchApi.mockImplementation(async request => (request.endsWith('/1/')
    ? { id: 1, nom: 'Classe', retard_minutes: 5 }
    : { count: 1, results: [{ id: 1, nom: 'Classe' }] }));
  patchApi.mockResolvedValue({ id: 1 });
  show([
    { name: 'nom', label: 'Nom', required: true },
    { name: 'retard_minutes', label: 'Retard', type: 'number' },
  ]);
  fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
  fireEvent.change(await screen.findByLabelText('Retard'), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/1/', { nom: 'Classe', retard_minutes: null }));
});

it.each(['2026-11-02T08:17:31.125Z', '2026-10-25T01:17:31.125Z'])(
  'roundtrips %s without losing precision or DST offset and clears optional dates and times',
  async (instant) => {
    fetchApi.mockImplementation(async request => (request.endsWith('/1/')
      ? {
        id: 1, nom: 'Visite', date: instant, fin: '2026-11-03', sortie: '09:00:00',
      }
      : { count: 1, results: [{ id: 1, nom: 'Visite' }] }));
    patchApi.mockResolvedValue({ id: 1 });
    show([
      {
        name: 'date', label: 'Date et heure', type: 'datetime-local', required: true,
      },
      { name: 'fin', label: 'Fin', type: 'date' },
      { name: 'sortie', label: 'Sortie', type: 'time' },
    ]);
    fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
    const input = await screen.findByLabelText(/Date et heure/);
    expect(Number(input.value.slice(11, 13))).toBe(new Date(instant).getHours());
    fireEvent.change(screen.getByLabelText('Fin'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Sortie'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
    await waitFor(() => expect(patchApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/1/', { date: instant, fin: null, sortie: null }));
  },
);

it('sends an offering reference as a code rather than coercing it to a number', async () => {
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  fetchAllResourcePages.mockResolvedValue([{ code: 'vocational-1', label: 'Formation courte' }]);
  postApi.mockResolvedValue({ id: 1 });
  show([{
    name: 'offre_code',
    label: 'Offre institutionnelle',
    resource: 'etablissement/learning-offerings',
    valueField: 'code',
    labelField: 'label',
  }]);
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
  const select = await screen.findByRole('combobox', { name: 'Offre institutionnelle' });
  await waitFor(() => expect(select).not.toHaveAttribute('aria-disabled', 'true'));
  fireEvent.mouseDown(select);
  fireEvent.click(await screen.findByRole('option', { name: 'Formation courte' }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/', { offre_code: 'vocational-1' }));
});

it('preserves UUID references and acknowledges a successful creation only after the server responds', async () => {
  const id = '1025238e-6cab-4b6b-8694-f1a270ca988a';
  const saved = jest.fn();
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  fetchAllResourcePages.mockResolvedValue([{ id, label: 'Signature approuvée' }]);
  postApi.mockResolvedValue({ id: 21 });
  show([{
    name: 'signature', label: 'Signature', resource: 'core/signatures', valueType: 'string', labelField: 'label',
  }], { onSaved: saved });
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
  const select = await screen.findByRole('combobox', { name: 'Signature' });
  await waitFor(() => expect(select).not.toHaveAttribute('aria-disabled', 'true'));
  fireEvent.mouseDown(select);
  fireEvent.click(await screen.findByRole('option', { name: 'Signature approuvée' }));
  expect(saved).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/', { signature: id }));
  await waitFor(() => expect(saved).toHaveBeenCalledWith({ id: 21 }));
});

it('keeps a historical offering selectable after catalogue removal and clears it with an empty code', async () => {
  fetchApi.mockImplementation(async request => (request.endsWith('/1/')
    ? { id: 1, nom: 'Classe', offre_code: 'retired-1' }
    : { count: 1, results: [{ id: 1, nom: 'Classe' }] }));
  fetchAllResourcePages.mockResolvedValue([]);
  patchApi.mockResolvedValue({ id: 1 });
  show([{
    name: 'offre_code',
    label: 'Offre institutionnelle',
    resource: 'etablissement/learning-offerings',
    valueField: 'code',
    labelField: 'label',
  }]);
  fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
  const select = await screen.findByRole('combobox', { name: 'Offre institutionnelle' });
  await waitFor(() => expect(select).not.toHaveAttribute('aria-disabled', 'true'));
  expect(select).toHaveTextContent('retired-1 (configuration conservée)');
  fireEvent.mouseDown(select);
  fireEvent.click(screen.getByRole('option', { name: '—', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/1/', { offre_code: '' }));
});

it('keeps collection filters for loading and export and binds new records to their parent', async () => {
  fetchApi.mockResolvedValue({ count: 0, results: [] });
  fetchAllResourcePages.mockResolvedValue([]);
  postApi.mockResolvedValue({ id: 2 });
  show([{ name: 'nom', label: 'Nom', required: true }], {
    filters: { formation: 12 }, fixedValues: { formation: 12 },
  });
  await waitFor(() => expect(fetchApi).toHaveBeenCalled());
  expect(new URL(fetchApi.mock.calls[0][0]).searchParams.get('formation')).toBe('12');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Exporter tous les résultats' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Exporter tous les résultats' }));
  await waitFor(() => expect(fetchAllResourcePages).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/', { formation: 12 }));
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
  fireEvent.change(await screen.findByLabelText(/Nom/), { target: { value: 'Parcours' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/', { nom: 'Parcours', formation: 12 }));
});

it('submits a motivated action without PATCHing the record and retains errors', async () => {
  fetchApi.mockResolvedValue({ count: 1, results: [{ id: 5, nom: 'Dossier', statut: 'validee' }] });
  postApi.mockRejectedValue({ response: { data: { detail: 'Des acquis doivent être conservés.' } } });
  show([], {
    actions: [{
      label: 'Transférer',
      endpoint: 'transferer',
      statuses: ['validee'],
      fields: [{ name: 'motif', label: 'Motif', required: true }],
    }],
  });
  fireEvent.click(await screen.findByRole('button', { name: 'Transférer' }));
  fireEvent.change(await screen.findByLabelText(/Motif/), { target: { value: 'Réorientation' } });
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Transférer' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/5/transferer/', { motif: 'Réorientation' }));
  expect(patchApi).not.toHaveBeenCalled();
  expect(await within(screen.getByRole('dialog')).findByText(/Des acquis/)).toBeVisible();
});

it('normalizes nested references and preserves multiple class IDs during edition', async () => {
  fetchApi.mockImplementation(async request => (request.endsWith('/1/')
    ? {
      id: 1, nom: 'Épreuve', classes: [{ id: 3 }, { id: 4 }], salle: { id: 3 },
    }
    : { count: 1, results: [{ id: 1, nom: 'Épreuve' }] }));
  fetchAllResourcePages.mockResolvedValue([{ id: 3, nom: 'A' }, { id: 4, nom: 'B' }]);
  patchApi.mockResolvedValue({ id: 1 });
  show([
    {
      name: 'classes', label: 'Classes', resource: 'classes/classes', multiple: true,
    },
    { name: 'salle', label: 'Salle', resource: 'salles' },
  ]);
  fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
  await screen.findByRole('dialog');
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith('https://secondary.example/api/v1/classes/classes/1/', { classes: [3, 4], salle: 3 }));
});
