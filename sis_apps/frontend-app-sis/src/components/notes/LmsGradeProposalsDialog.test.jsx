import React from 'react';
import {
  act, fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { fetchApi, postApi } from '../../services/api';
import { resourceUrl } from '../../services/resources';
import LmsGradeProposalsDialog from './LmsGradeProposalsDialog';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_SECONDAIRE_API_URL: 'https://secondary.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superior.example/api/v1',
  }),
}));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  postApi: jest.fn(),
}));

const proposal = {
  id: 8,
  learner_id: 31,
  event_id: 'lms-event-8',
  score: '70.00',
  max_score: '100.00',
  proposed_value: '14.00',
  proposed_scale: '20.00',
  review_status: 'pending',
  reviewed_by: null,
  reviewed_at: null,
  review_reason: '',
  note_id: null,
  timestamp_lms: '2026-11-06T09:00:00Z',
};
const page = (results = [proposal], extra = {}) => ({
  count: results.length, next: null, previous: null, results, ...extra,
});
const makeClient = () => new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
});
const show = (variant = 'secondaire', client = makeClient()) => render(
  <QueryClientProvider client={client}>
    <LmsGradeProposalsDialog
      variant={variant}
      evaluation={{ id: 7, titre: 'Contrôle' }}
      onClose={jest.fn()}
    />
  </QueryClientProvider>,
);
const examine = async () => fireEvent.click(await screen.findByRole('button', { name: 'Examiner la proposition 8' }));

beforeEach(() => {
  jest.clearAllMocks();
  fetchApi.mockResolvedValue(page());
  postApi.mockResolvedValue({ id: 8, review_status: 'approved', note_id: 42 });
});

it.each(['secondaire', 'superieur'])('requires explicit approval and refreshes the official grade queries for %s', async (variant) => {
  const client = makeClient();
  const url = resourceUrl(variant, 'notes/evaluations/7');
  const officialKey = ['resource', resourceUrl(variant, 'notes/notes')];
  const gradeKey = ['grade-entry', url];
  client.setQueryData(gradeKey, { notes: [] });
  const officialFetch = jest.fn().mockResolvedValueOnce([]).mockResolvedValue([{ id: 42, valeur: '14.00' }]);
  const OfficialGrades = () => {
    const official = useQuery({ queryKey: officialKey, queryFn: officialFetch });
    return <span data-testid="official-count">{official.data?.length ?? 0}</span>;
  };
  render(
    <QueryClientProvider client={client}>
      <OfficialGrades />
      <LmsGradeProposalsDialog variant={variant} evaluation={{ id: 7, titre: 'Contrôle' }} onClose={jest.fn()} />
    </QueryClientProvider>,
  );
  await examine();
  expect(screen.getByText('70.00 / 100.00')).toBeInTheDocument();
  expect(screen.getByText('14.00 / 20.00')).toBeInTheDocument();
  expect(postApi).not.toHaveBeenCalled();
  expect(screen.getByTestId('official-count')).toHaveTextContent('0');
  fetchApi.mockResolvedValue(page([{ ...proposal, review_status: 'approved', note_id: 42 }]));
  fireEvent.click(screen.getByRole('button', { name: 'Approuver et créer la note' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${url}examiner_proposition_lms/`, {
    proposal_id: 8, decision: 'approve',
  }));
  expect(await screen.findByText('Proposition approuvée : note officielle n° 42 créée.')).toBeInTheDocument();
  await waitFor(() => expect(screen.getByTestId('official-count')).toHaveTextContent('1'));
  expect(client.getQueryState(gradeKey).isInvalidated).toBe(true);
  expect(await screen.findByText('Approuvée')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Examiner la proposition 8' })).not.toBeInTheDocument();
});

it('requires a nonblank rejection reason and never refreshes official grades for a rejection', async () => {
  const client = makeClient();
  const officialKey = ['resource', resourceUrl('secondaire', 'notes/notes')];
  client.setQueryData(officialKey, []);
  show('secondaire', client);
  await examine();
  const reject = screen.getByRole('button', { name: 'Rejeter la proposition' });
  expect(reject).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Motif de la décision'), { target: { value: '   ' } });
  expect(reject).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Motif de la décision'), { target: { value: '  Mauvais apprenant.  ' } });
  postApi.mockResolvedValue({ id: 8, review_status: 'rejected', note_id: null });
  fetchApi.mockResolvedValue(page([{ ...proposal, review_status: 'rejected', review_reason: 'Mauvais apprenant.' }]));
  fireEvent.click(reject);
  expect(await screen.findByText('Proposition rejetée. Aucune note officielle créée.')).toBeInTheDocument();
  expect(postApi).toHaveBeenCalledWith(expect.any(String), {
    proposal_id: 8, decision: 'reject', reason: 'Mauvais apprenant.',
  });
  expect(client.getQueryState(officialKey).isInvalidated).toBe(false);
  expect(await screen.findByText('Rejetée')).toBeInTheDocument();
});

it.each([409, 403])('keeps a failed decision and its reason visible without success for HTTP %s', async (status) => {
  const client = makeClient();
  const officialKey = ['resource', resourceUrl('secondaire', 'notes/notes')];
  client.setQueryData(officialKey, []);
  postApi.mockRejectedValue({ response: { status, data: { detail: 'Validation refusée par le serveur.' } } });
  show('secondaire', client);
  await examine();
  fireEvent.change(screen.getByLabelText('Motif de la décision'), { target: { value: 'Vérifié en séance.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Approuver et créer la note' }));
  expect(await screen.findByText(/Validation refusée par le serveur/)).toBeInTheDocument();
  expect(screen.getByLabelText('Motif de la décision')).toHaveValue('Vérifié en séance.');
  expect(screen.queryByText(/Proposition approuvée :/)).not.toBeInTheDocument();
  expect(client.getQueryState(officialKey).isInvalidated).toBe(false);
  if (status === 409) {
    expect(screen.getByRole('button', { name: 'Approuver et créer la note' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Examiner la proposition 8' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Actualiser les propositions' }));
    await waitFor(() => expect(fetchApi).toHaveBeenCalledTimes(2));
    expect(screen.queryByLabelText('Motif de la décision')).not.toBeInTheDocument();
  }
});

it('shows pending state and prevents duplicate decisions or closing while saving', async () => {
  let finish;
  postApi.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  show();
  await examine();
  fireEvent.click(screen.getByRole('button', { name: 'Approuver et créer la note' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Enregistrement de la décision');
  expect(screen.getByRole('button', { name: 'Approuver et créer la note' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Fermer' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Actualiser les propositions' })).toBeDisabled();
  expect(screen.queryByText(/Proposition approuvée :/)).not.toBeInTheDocument();
  await act(async () => finish({ id: 8, review_status: 'approved', note_id: 42 }));
  expect(postApi).toHaveBeenCalledTimes(1);
});

it('loads one visible page at a time and shows pagination errors with a retry', async () => {
  fetchApi.mockResolvedValue(page([proposal], { count: 26, next: '?page=2' }));
  show();
  await screen.findByRole('button', { name: 'Examiner la proposition 8' });
  expect(screen.getByText('1–25 sur 26')).toBeInTheDocument();
  expect(fetchApi).toHaveBeenCalledTimes(1);
  fetchApi.mockRejectedValue(new Error('Page indisponible.'));
  fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }));
  expect(await screen.findByText('Page indisponible.')).toBeInTheDocument();
  expect(fetchApi).toHaveBeenLastCalledWith(
    expect.stringContaining('/notes/evaluations/7/propositions_lms/?page=2&page_size=25'),
    expect.any(Object),
  );
  expect(screen.queryByRole('button', { name: /Examiner la proposition/ })).not.toBeInTheDocument();
  fetchApi.mockResolvedValue(page([{ ...proposal, id: 9 }], { count: 26, previous: '?page=1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser les propositions' }));
  expect(await screen.findByRole('button', { name: 'Examiner la proposition 9' })).toBeEnabled();
  expect(screen.queryByText('Page indisponible.')).not.toBeInTheDocument();
});

it('shows a forbidden evaluation access error without retrying or leaving the dialog loading', async () => {
  fetchApi.mockRejectedValue({
    response: { status: 403, data: { detail: 'La permission notes.view_evaluation est requise.' } },
  });
  const client = makeClient();
  show('secondaire', client);
  expect(await screen.findByText(/La permission notes.view_evaluation est requise/)).toBeInTheDocument();
  await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(fetchApi).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Examiner la proposition/ })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Fermer' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser les propositions' }));
  await waitFor(() => expect(fetchApi).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(screen.getByText(/La permission notes.view_evaluation est requise/)).toBeInTheDocument();
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  expect(postApi).not.toHaveBeenCalled();
});

it('does not offer review actions for retained, approved or rejected historical events', async () => {
  fetchApi.mockResolvedValue(page([
    {
      ...proposal, id: 1, review_status: 'retained', proposed_value: null, proposed_scale: null,
    },
    {
      ...proposal, id: 2, review_status: 'approved', note_id: 42,
    },
    {
      ...proposal, id: 3, review_status: 'rejected', review_reason: 'Ancien résultat.',
    },
  ]));
  show();
  expect(await screen.findByText('Conservée sans proposition')).toBeInTheDocument();
  expect(screen.getByText('Ancien résultat.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Examiner la proposition/ })).not.toBeInTheDocument();
  expect(postApi).not.toHaveBeenCalled();
});
