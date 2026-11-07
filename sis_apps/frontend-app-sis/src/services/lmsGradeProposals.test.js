import { fetchApi, postApi } from './api';
import { fetchLmsGradeProposals, reviewLmsGradeProposal } from './lmsGradeProposals';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_SECONDAIRE_API_URL: 'https://secondary.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superior.example/api/v1',
  }),
}));
jest.mock('./api', () => ({
  ...jest.requireActual('./api'),
  fetchApi: jest.fn(),
  postApi: jest.fn(),
}));

beforeEach(() => jest.clearAllMocks());

it.each([
  ['secondaire', 'https://secondary.example/api/v1'],
  ['superieur', 'https://superior.example/api/v1'],
])('uses the evaluation review endpoints and fetches only the requested page for %s', async (variant, base) => {
  const page = {
    count: 51, next: `${base}/notes/evaluations/7/propositions_lms/?page=3`, previous: '?page=1', results: [{ id: 8 }],
  };
  const options = { signal: new AbortController().signal };
  fetchApi.mockResolvedValue(page);
  expect(await fetchLmsGradeProposals(variant, 7, { page: 2, page_size: 25 }, options)).toEqual(page);
  expect(fetchApi).toHaveBeenCalledTimes(1);
  expect(fetchApi).toHaveBeenCalledWith(`${base}/notes/evaluations/7/propositions_lms/?page=2&page_size=25`, options);
  postApi.mockResolvedValue({ id: 8, review_status: 'rejected', note_id: null });
  await reviewLmsGradeProposal(variant, 7, { proposalId: 8, decision: 'reject', reason: '  Erreur de correspondance.  ' });
  expect(postApi).toHaveBeenCalledWith(`${base}/notes/evaluations/7/examiner_proposition_lms/`, {
    proposal_id: 8, decision: 'reject', reason: 'Erreur de correspondance.',
  });
});

it('preserves conflicts from the API and never adds an empty approval reason', async () => {
  const error = { response: { status: 409, data: { detail: 'Une note existe déjà.' } } };
  postApi.mockRejectedValue(error);
  await expect(reviewLmsGradeProposal('secondaire', 7, {
    proposalId: 8, decision: 'approve', reason: '  ',
  })).rejects.toBe(error);
  expect(postApi).toHaveBeenCalledWith(expect.any(String), { proposal_id: 8, decision: 'approve' });
});
