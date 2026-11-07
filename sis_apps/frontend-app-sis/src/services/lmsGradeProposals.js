import { postApi } from './api';
import { fetchResourcePage, resourceUrl } from './resources';

export const fetchLmsGradeProposals = (variant, evaluationId, params = {}, options = {}) => (
  fetchResourcePage(
    `${resourceUrl(variant, `notes/evaluations/${evaluationId}`)}propositions_lms/`,
    params,
    options,
  )
);

export const reviewLmsGradeProposal = (variant, evaluationId, { proposalId, decision, reason }) => (
  postApi(
    `${resourceUrl(variant, `notes/evaluations/${evaluationId}`)}examiner_proposition_lms/`,
    {
      proposal_id: proposalId,
      decision,
      ...(reason?.trim() ? { reason: reason.trim() } : {}),
    },
  )
);
