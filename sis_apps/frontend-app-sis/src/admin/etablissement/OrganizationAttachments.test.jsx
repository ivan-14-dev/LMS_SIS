import React from 'react';
import {
  fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import OrganizationAttachments from './OrganizationAttachments';
import HierarchyEditor from './HierarchyEditor';
import { fetchApi, patchApi, postApi } from '../../services/api';
import { fetchAllResourcePages, fetchResourcePage } from '../../services/resources';

jest.mock('../../services/api', () => ({ fetchApi: jest.fn(), patchApi: jest.fn(), postApi: jest.fn() }));
jest.mock('../../services/resources', () => ({
  ...jest.requireActual('../../services/resources'),
  resourceUrl: (_variant, resource) => `https://sis.example/api/v1/${resource}/`,
  fetchAllResourcePages: jest.fn(),
  fetchResourcePage: jest.fn(),
}));
const base = 'https://sis.example/api/v1/etablissement/';
const targets = [
  { kind: 'user', label: 'Utilisateurs' }, { kind: 'course', label: 'Formations' },
  { kind: 'book', label: 'Ressources — livres et documents' }, { kind: 'activity', label: 'Activités — créneaux de cours' },
];
const catalogue = {
  targets, kinds: [{ value: 'campus', label: 'Campus' }, { value: 'service', label: 'Service' }],
};
const unit = {
  id: 2,
  code: 'CENTRE',
  nom: 'Centre existant',
  label: 'CENTRE - Centre existant',
  kind: 'campus',
  topology_version: 1,
  parent: null,
};
const candidate = { id: 71, label: 'Personne existante', unit: null };
const result = {
  id: 45, label: 'Objet conservé', kind: 'user', unit: 2,
};
const rows = results => ({
  results, count: results.length, next: null, previous: null,
});
const mount = (element) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
};
const select = (name, option) => {
  fireEvent.mouseDown(screen.getByRole('combobox', { name }));
  fireEvent.click(screen.getByRole('option', { name: option }));
};
const openAttachment = async () => {
  mount(<OrganizationAttachments base={base} unit="2" targets={targets} onUnitChange={jest.fn()} />);
  await screen.findByText('Objet conservé');
  fireEvent.click(screen.getByRole('button', { name: 'Rattacher un objet existant' }));
  await screen.findByText('1 objet(s) · page 1');
  select('Objet existant à rattacher', 'Personne existante');
};
beforeEach(() => {
  jest.clearAllMocks();
  fetchApi.mockImplementation(url => Promise.resolve(url.includes('/catalogue/') ? catalogue : unit));
  fetchAllResourcePages.mockResolvedValue([unit]);
  fetchResourcePage.mockImplementation((url) => {
    if (url.includes('/references/')) { return Promise.resolve(rows([candidate])); }
    return Promise.resolve(rows(url.includes('/attachments/') ? [result] : [unit]));
  });
  postApi.mockResolvedValue(result);
  patchApi.mockResolvedValue(unit);
});

it.each(['secondaire', 'superieur'])('creates a free unit with a real parent and keeps one workspace activity (%s)', async (variant) => {
  mount(<HierarchyEditor endpoint={`${base}current/`} variant={variant} />);
  await screen.findByRole('table', { name: 'Unités d’organisation' });
  expect(screen.queryByLabelText('Motif de publication')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
  fireEvent.change(screen.getByLabelText('Code de l’unité', { exact: false }), { target: { value: 'QUALITY' } });
  fireEvent.change(screen.getByLabelText('Nom de l’unité', { exact: false }), { target: { value: 'Service qualité' } });
  select(/Type d’unité/, 'Service');
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Unité parente' })).not.toBeDisabled());
  select('Unité parente', unit.label);
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await screen.findByText('Enregistrement effectué.');
  expect(postApi).toHaveBeenCalledWith(`${base}unites/`, {
    topology_version: 2, code: 'QUALITY', nom: 'Service qualité', kind: 'service', parent: 2,
  });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole('button', { name: 'Rattachements' }));
  expect(screen.queryByRole('table', { name: 'Unités d’organisation' })).not.toBeInTheDocument();
  select('Unité consultée', unit.label);
  await screen.findByRole('table', { name: 'Rattachements de l’unité' });
  expect(screen.getAllByRole('table')).toHaveLength(1);
});

it('renames a legacy unit without silently converting its topology', async () => {
  mount(<HierarchyEditor endpoint={`${base}current/`} variant="secondaire" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
  await screen.findByRole('dialog');
  expect(screen.queryByLabelText('Mode de création')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Nom de l’unité', { exact: false }), { target: { value: 'Campus renommé' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  await screen.findByText('Enregistrement effectué.');
  expect(patchApi).toHaveBeenCalledWith(`${base}unites/2/`, { nom: 'Campus renommé', category_label: '' });
});

it('keeps server validation failure visible in the unit form', async () => {
  postApi.mockRejectedValue({ response: { data: { parent: ['Parent interdit.'] } } });
  mount(<HierarchyEditor endpoint={`${base}current/`} variant="superieur" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Ajouter' }));
  fireEvent.change(screen.getByLabelText('Code de l’unité', { exact: false }), { target: { value: 'BAD' } });
  fireEvent.change(screen.getByLabelText('Nom de l’unité', { exact: false }), { target: { value: 'Bad unit' } });
  select(/Type d’unité/, 'Service');
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
  expect(await within(screen.getByRole('dialog')).findByText(/Parent interdit/)).toBeVisible();
  expect(screen.queryByText('Enregistrement effectué.')).not.toBeInTheDocument();
});

it('requires consent and refreshes only after the server accepts the attachment', async () => {
  await openAttachment();
  expect(screen.getByRole('button', { name: 'Confirmer le rattachement' })).toBeDisabled();
  expect(postApi).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('checkbox', { name: /Je confirme/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer le rattachement' }));
  await screen.findByText(/Rattachement enregistré par le serveur/);
  expect(postApi).toHaveBeenCalledWith(`${base}unites/2/attachments/`, { kind: 'user', object_id: 71, confirm: true });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});

it('does not hide a refused attachment or report success', async () => {
  postApi.mockRejectedValue({ response: { data: { object_id: ['Objet déjà rattaché.'] } } });
  await openAttachment();
  fireEvent.click(screen.getByRole('checkbox', { name: /Je confirme/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer le rattachement' }));
  expect(await within(screen.getByRole('dialog')).findByText(/Objet déjà rattaché/)).toBeVisible();
  expect(screen.queryByText(/Rattachement enregistré par le serveur/)).not.toBeInTheDocument();
  expect(screen.getByRole('combobox', { name: 'Objet existant à rattacher' })).toHaveTextContent(candidate.label);
});

it('paginates references on the server, clears reviewed selections and reports lookup errors', async () => {
  fetchResourcePage.mockImplementation((url, params) => {
    if (!url.includes('/references/')) { return Promise.resolve(rows([result])); }
    if (params.search) { return Promise.reject(new Error('Recherche indisponible')); }
    return Promise.resolve({
      ...rows([candidate]), count: 26, next: params.page === 1 ? 'next' : null, previous: params.page > 1 ? 'previous' : null,
    });
  });
  mount(<OrganizationAttachments base={base} unit="2" targets={targets} onUnitChange={jest.fn()} />);
  await screen.findByText('Objet conservé');
  fireEvent.click(screen.getByRole('button', { name: 'Rattacher un objet existant' }));
  await screen.findByText('26 objet(s) · page 1');
  select('Objet existant à rattacher', candidate.label);
  fireEvent.click(screen.getByRole('checkbox', { name: /Je confirme/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Références suivantes' }));
  await screen.findByText('26 objet(s) · page 2');
  expect(fetchResourcePage).toHaveBeenCalledWith(`${base}unites/references/`, {
    kind: 'user', page: 2, page_size: 25, search: '',
  }, expect.anything());
  expect(screen.getByRole('checkbox', { name: /Je confirme/ })).not.toBeChecked();
  expect(screen.getByRole('button', { name: 'Confirmer le rattachement' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Rechercher un objet'), { target: { value: 'missing' } });
  expect(await screen.findByText(/Recherche indisponible/)).toBeVisible();
  expect(screen.getByRole('combobox', { name: 'Objet existant à rattacher' })).toHaveAttribute('aria-disabled', 'true');
});

it('consults server details and follows a linked academic unit without changing data', async () => {
  const onUnitChange = jest.fn();
  fetchApi.mockResolvedValue({
    ...result,
    details: { titre: 'Livre existant', resume: 'Résumé conservé' },
    relations: [{
      id: 9, kind: 'course', label: 'Formation liée', unit: 8,
    }],
  });
  mount(<OrganizationAttachments base={base} unit="2" targets={targets} onUnitChange={onUnitChange} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Consulter' }));
  await screen.findByText(/Résumé conservé/);
  expect(fetchApi).toHaveBeenCalledWith(`${base}unites/2/attached-object/?kind=user&object_id=45&page=1&page_size=25`);
  fireEvent.click(screen.getByRole('button', { name: 'Consulter l’unité 8' }));
  expect(onUnitChange).toHaveBeenCalledWith('8');
  expect(postApi).not.toHaveBeenCalled();
  expect(patchApi).not.toHaveBeenCalled();
});

it('reports consultation errors without a fabricated detail or success', async () => {
  fetchApi.mockRejectedValue({ response: { data: { detail: 'Objet inaccessible.' } } });
  mount(<OrganizationAttachments base={base} unit="2" targets={targets} onUnitChange={jest.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Consulter' }));
  expect(await screen.findByText(/Objet inaccessible/)).toBeVisible();
  expect(screen.queryByText('Relations académiques existantes')).not.toBeInTheDocument();
});

it('paginates real academic relations without truncating their consultation', async () => {
  fetchApi.mockImplementation(url => Promise.resolve({
    ...result,
    details: {},
    relations: [{
      id: url.includes('page=2') ? 99 : 98, kind: 'course', label: url.includes('page=2') ? 'Classe suivante' : 'Première classe', unit: null,
    }],
    relation_pages: [{ count: 26, next: url.includes('page=2') ? null : 'next', previous: null }],
  }));
  mount(<OrganizationAttachments base={base} unit="2" targets={targets} onUnitChange={jest.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Consulter' }));
  await screen.findByText(/Première classe/);
  fireEvent.click(screen.getByRole('button', { name: 'Relations suivantes' }));
  await screen.findByText(/Classe suivante/);
  expect(fetchApi.mock.lastCall[0]).toContain('page=2&page_size=25');
  expect(screen.queryByText(/Première classe/)).not.toBeInTheDocument();
});
