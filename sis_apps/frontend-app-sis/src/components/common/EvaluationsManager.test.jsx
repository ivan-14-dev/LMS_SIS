import React from 'react';
import {
  act, fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import EvaluationsPage from '../../secondaire/evaluations/EvaluationsPage';
import NotesPage from '../../superieur/notes/NotesPage';
import { useCapabilities } from '../auth/PermissionGuard';
import LmsGradeProposalsDialog from '../notes/LmsGradeProposalsDialog';
import {
  fetchApi, fetchCollection, patchApi, postApi,
} from '../../services/api';
import ResourceManager from './ResourceManager';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_SECONDAIRE_API_URL: 'https://secondary.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superior.example/api/v1',
  }),
}));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  fetchCollection: jest.fn(),
  patchApi: jest.fn(),
  postApi: jest.fn(),
}));
jest.mock('../auth/PermissionGuard', () => ({ useCapabilities: jest.fn() }));
jest.mock('./GradeEntryDialog', () => () => null);
jest.mock('./WorkflowHistoryPanel', () => () => null);
jest.mock('../notes/LmsGradeProposalsDialog', () => ({
  __esModule: true,
  default: jest.fn(() => <div>Examen des propositions de l’évaluation sélectionnée</div>),
}));
jest.mock('./ResourceManager', () => ({
  __esModule: true,
  default: jest.fn(({ columns }) => (
    <div>
      {columns.map(column => column.Cell && (
        <div key={column.accessor}>
          {column.Cell({
            row: {
              original: {
                id: 7, titre: 'Contrôle', bareme: 20, type: 'ds', modalite: 'cc',
              },
            },
          })}
        </div>
      ))}
    </div>
  )),
}));

const staff = {
  role: 'enseignant',
  permissions: ['notes.change_note'],
  affiliations: [{ kind: 'staff', active: true }],
  portals: { staff: true },
};
const resourceStub = ResourceManager.getMockImplementation();
const proposalsStub = LmsGradeProposalsDialog.getMockImplementation();
const realResources = props => React.createElement(jest.requireActual('./ResourceManager').default, props);
const evaluation = {
  id: 7, titre: 'Contrôle', bareme: 20, type: 'ds', modalite: 'cc',
};
const makeClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1, retryDelay: 0, staleTime: 5 * 60 * 1000, refetchOnWindowFocus: false,
    },
  },
});
const showPage = (Page, client) => (
  <QueryClientProvider client={client}><MemoryRouter><Page /></MemoryRouter></QueryClientProvider>
);

beforeEach(() => {
  jest.clearAllMocks();
  useCapabilities.mockReset();
  useCapabilities.mockReturnValue({ data: staff });
  ResourceManager.mockImplementation(resourceStub);
  LmsGradeProposalsDialog.mockImplementation(proposalsStub);
  fetchApi.mockResolvedValue({ count: 1, results: [evaluation] });
});

it.each([
  ['secondaire', EvaluationsPage],
  ['superieur', NotesPage],
])('opens the review flow from the existing %s evaluation page', (variant, Page) => {
  render(<MemoryRouter><Page /></MemoryRouter>);
  expect(screen.queryByText('Examen des propositions de l’évaluation sélectionnée')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Propositions LMS' }));
  expect(screen.getByText('Examen des propositions de l’évaluation sélectionnée')).toBeInTheDocument();
  expect(useCapabilities).toHaveBeenCalledWith(variant, { refetchOnMount: false });
});

it('allows a grade reviewer without granting evaluation editing rights', () => {
  useCapabilities.mockReturnValue({ data: { ...staff, role: 'gestionnaire' } });
  render(<EvaluationsPage />);
  expect(screen.getByRole('button', { name: 'Propositions LMS' })).toBeEnabled();
  expect(ResourceManager).toHaveBeenCalledWith(
    expect.objectContaining({ allowCreate: false, allowEdit: false }),
    expect.anything(),
  );
});

it('keeps the actual evaluation table read-only for a grade reviewer and surfaces export failures', async () => {
  useCapabilities.mockReturnValue({ data: { ...staff, role: 'gestionnaire' } });
  ResourceManager.mockImplementation(realResources);
  fetchCollection.mockRejectedValue({
    response: { status: 403, data: { detail: 'Export des évaluations interdit.' } },
  });
  render(showPage(EvaluationsPage, makeClient()));
  await screen.findByRole('button', { name: 'Propositions LMS' });
  expect(screen.queryByRole('button', { name: 'Ajouter' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Modifier' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Supprimer|Effacer/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Exporter tous les résultats' }));
  expect(await screen.findByText(/Export des évaluations interdit/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Exporter tous les résultats' })).toBeEnabled();
  expect(fetchCollection).toHaveBeenCalledTimes(1);
  expect(postApi).not.toHaveBeenCalled();
  expect(patchApi).not.toHaveBeenCalled();
});

it.each([
  ['secondaire', EvaluationsPage],
  ['superieur', NotesPage],
])('removes an open review dialog and its decisions when grade permission is revoked for %s', async (variant, Page) => {
  ResourceManager.mockImplementation(realResources);
  LmsGradeProposalsDialog.mockImplementation(jest.requireActual('../notes/LmsGradeProposalsDialog').default);
  fetchApi.mockImplementation(async url => ({
    count: 1,
    results: url.includes('/propositions_lms/') ? [{
      id: 8,
      learner_id: 31,
      score: '70.00',
      max_score: '100.00',
      proposed_value: '14.00',
      proposed_scale: '20.00',
      review_status: 'pending',
    }] : [evaluation],
  }));
  const client = makeClient();
  const { rerender } = render(showPage(Page, client));
  fireEvent.click(await screen.findByRole('button', { name: 'Propositions LMS' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Examiner la proposition 8' }));
  fireEvent.change(screen.getByLabelText('Motif de la décision'), { target: { value: 'À vérifier.' } });
  expect(screen.getByRole('button', { name: 'Approuver et créer la note' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Rejeter la proposition' })).toBeEnabled();

  useCapabilities.mockReturnValue({ data: { ...staff, permissions: ['notes.view_note'] } });
  rerender(showPage(Page, client));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Propositions LMS' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Approuver et créer la note' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Rejeter la proposition' })).not.toBeInTheDocument();
  expect(postApi).not.toHaveBeenCalled();
  expect(useCapabilities).toHaveBeenCalledWith(variant, { refetchOnMount: false });
});

it.each([
  ['secondaire', EvaluationsPage, 'notes.view_evaluation'],
  ['superieur', NotesPage, 'notes.view_note'],
])('settles guarded %s capability loading and still removes revoked access', async (variant, Page, permission) => {
  const actual = jest.requireActual('../auth/PermissionGuard');
  useCapabilities.mockImplementation(actual.useCapabilities);
  fetchApi.mockResolvedValue({ ...staff, permissions: [...staff.permissions, permission] });
  const client = makeClient();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <actual.default type={variant} permission={permission}><Page /></actual.default>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByRole('button', { name: 'Propositions LMS' });
  await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(fetchApi).toHaveBeenCalledTimes(1);
  fetchApi.mockResolvedValue({ ...staff, permissions: [] });
  await act(async () => { await client.invalidateQueries({ queryKey: ['capabilities', variant] }); });
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Propositions LMS' })).not.toBeInTheDocument());
  expect(await screen.findByText(/permission d’accéder/)).toBeInTheDocument();
  expect(fetchApi).toHaveBeenCalledTimes(2);
}, 15000);

it('settles a forbidden evaluation listing visibly after the application retry policy, including manual refresh', async () => {
  useCapabilities.mockReturnValue({ data: { ...staff, role: 'gestionnaire' } });
  ResourceManager.mockImplementation(realResources);
  fetchApi.mockRejectedValue({
    response: { status: 403, data: { detail: 'La permission notes.view_evaluation est requise.' } },
  });
  const client = makeClient();
  render(showPage(EvaluationsPage, client));
  expect(await screen.findByText(/La permission notes.view_evaluation est requise/)).toBeInTheDocument();
  await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(fetchApi).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Propositions LMS' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser' }));
  await waitFor(() => expect(fetchApi).toHaveBeenCalledTimes(4));
  await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(screen.getByText(/La permission notes.view_evaluation est requise/)).toBeInTheDocument();
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  expect(postApi).not.toHaveBeenCalled();
});

it.each([
  { ...staff, permissions: ['notes.view_note'] },
  { ...staff, role: 'eleve', permissions: ['*'] },
  { ...staff, role: 'etudiant', permissions: ['*'] },
  { ...staff, role: 'parent', permissions: ['*'] },
  { ...staff, affiliations: [{ kind: 'staff', active: false }] },
])('does not expose LMS review without active staff access and grade permission: %j', (capabilities) => {
  useCapabilities.mockReturnValue({ data: capabilities });
  render(<EvaluationsPage />);
  expect(screen.queryByRole('button', { name: 'Propositions LMS' })).not.toBeInTheDocument();
  expect(screen.queryByText('Examen des propositions de l’évaluation sélectionnée')).not.toBeInTheDocument();
});
