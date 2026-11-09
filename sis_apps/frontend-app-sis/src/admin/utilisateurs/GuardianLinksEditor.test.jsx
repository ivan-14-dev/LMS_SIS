import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { deleteApi, patchApi, postApi } from '../../services/api';
import { fetchAllResourcePages } from '../../services/resources';
import GuardianLinksEditor from './GuardianLinksEditor';

jest.mock('../../services/api', () => ({ deleteApi: jest.fn(), patchApi: jest.fn(), postApi: jest.fn() }));
jest.mock('../../services/resources', () => ({
  resourceUrl: (_variant, resource) => `https://sis.test/api/v1/${resource}/`,
  fetchAllResourcePages: jest.fn(),
  apiErrorMessage: error => error?.message || 'Échec.',
}));
jest.mock('../../components/common/ResourceManager', () => function ResourceManagerMock() {
  return <div>Profils parents</div>;
});

const url = 'https://sis.test/api/v1/utilisateurs/liens-parent/';
const grants = [
  'eleves.view_tuteur', 'eleves.view_eleve', 'eleves.view_elevetuteur',
  'eleves.add_elevetuteur', 'eleves.change_elevetuteur', 'eleves.delete_elevetuteur',
];
let links;
const renderEditor = (permissions = grants) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><GuardianLinksEditor capabilities={{ permissions }} /></QueryClientProvider>);
};

beforeEach(() => {
  jest.clearAllMocks();
  links = [{ id: 8, tuteur_nom: 'Parent A', eleve_nom: 'Enfant A', autorise_acces_portail: true }];
  fetchAllResourcePages.mockImplementation(async (path) => {
    if (path === url) { return links; }
    if (path.endsWith('/utilisateurs/parents/')) { return [{ id: 3, prenom: 'Parent', nom: 'A', compte: 'parent-a' }]; }
    if (path.endsWith('/eleves/')) { return [{ id: 4, matricule: 'E-004', full_name: 'Enfant A' }]; }
    throw new Error(`Unexpected ${path}`);
  });
  postApi.mockResolvedValue({ id: 9 });
  patchApi.mockImplementation(async (_path, data) => {
    links = [{ ...links[0], ...data }];
    return links[0];
  });
  deleteApi.mockImplementation(async () => { links = []; });
});

it('creates an explicitly authorized child link through its dedicated API', async () => {
  renderEditor();
  await screen.findByText('Parent A → Enfant A · Accès autorisé');
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Parent' }));
  fireEvent.click(await screen.findByRole('option', { name: 'Parent A (parent-a)' }));
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Enfant' }));
  fireEvent.click(await screen.findByRole('option', { name: 'Enfant A' }));
  expect(screen.getByRole('checkbox', { name: 'Autoriser l’accès au portail' })).not.toBeChecked();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Autoriser l’accès au portail' }));
  fireEvent.click(screen.getByRole('button', { name: 'Créer la liaison' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(url, {
    tuteur: 3, eleve: 4, autorise_acces_portail: true,
  }));
  expect(patchApi).not.toHaveBeenCalled();
});

it('revokes without deleting then removes only after confirmation', async () => {
  renderEditor();
  fireEvent.click(await screen.findByRole('button', { name: 'Révoquer l’accès' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith(`${url}8/`, { autorise_acces_portail: false }));
  await screen.findByText('Parent A → Enfant A · Accès révoqué');
  expect(deleteApi).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Retirer la liaison' }));
  expect(deleteApi).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer le retrait' }));
  await waitFor(() => expect(deleteApi).toHaveBeenCalledWith(`${url}8/`));
  await screen.findByText('Aucune liaison.');
});

it('does not fetch or offer linking on role-less denied capabilities', () => {
  renderEditor([]);
  expect(screen.getByText('Permission de consultation des liaisons requise.')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Créer la liaison' })).not.toBeInTheDocument();
  expect(fetchAllResourcePages).not.toHaveBeenCalled();
});

it('hides cached links when the server refuses a revalidation', async () => {
  renderEditor(['eleves.view_elevetuteur']);
  await screen.findByText('Parent A → Enfant A · Accès autorisé');
  fetchAllResourcePages.mockRejectedValue(new Error('Accès retiré'));
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser les liaisons' }));
  await screen.findByText('Accès retiré');
  expect(screen.queryByText('Parent A → Enfant A · Accès autorisé')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Révoquer l’accès' })).not.toBeInTheDocument();
});
