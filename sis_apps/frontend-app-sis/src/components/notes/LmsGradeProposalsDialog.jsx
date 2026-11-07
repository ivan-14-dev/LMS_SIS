import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import SISDataTable from '../common/SISDataTable';
import { apiErrorMessage, resourceUrl } from '../../services/resources';
import { fetchLmsGradeProposals, reviewLmsGradeProposal } from '../../services/lmsGradeProposals';

const reviewLabels = {
  retained: 'Conservée sans proposition',
  pending: 'En attente de validation',
  approved: 'Approuvée',
  rejected: 'Rejetée',
};

const reviewButton = (select, disabled, cell) => (
  cell.row.original.review_status === 'pending' ? (
    <Button
      disabled={disabled}
      onClick={() => select(cell.row.original)}
      aria-label={`Examiner la proposition ${cell.row.original.id}`}
    >
      Examiner
    </Button>
  ) : null
);

const LmsGradeProposalsDialog = ({ variant, evaluation, onClose }) => {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState(null);
  const [reason, setReason] = useState('');
  const [notice, setNotice] = useState('');
  const client = useQueryClient();
  const evaluationUrl = resourceUrl(variant, `notes/evaluations/${evaluation.id}`);
  const queryKey = ['lms-grade-proposals', evaluationUrl];
  const query = useQuery({
    queryKey: [...queryKey, page, pageSize],
    queryFn: ({ signal }) => fetchLmsGradeProposals(
      variant,
      evaluation.id,
      { page: page + 1, page_size: pageSize },
      { signal },
    ),
    refetchOnWindowFocus: false,
    retry: false,
  });
  const saving = useMutation({
    retry: false,
    mutationFn: decision => reviewLmsGradeProposal(variant, evaluation.id, {
      proposalId: selected.id, decision, reason,
    }),
    onMutate: () => setNotice(''),
    onSuccess: async (result) => {
      setSelected(null);
      setReason('');
      setNotice(result.review_status === 'approved'
        ? `Proposition approuvée : note officielle n° ${result.note_id} créée.`
        : 'Proposition rejetée. Aucune note officielle créée.');
      await Promise.all([
        client.invalidateQueries({ queryKey }),
        ...(result.review_status === 'approved' ? [
          client.invalidateQueries({ queryKey: ['resource'] }),
          client.invalidateQueries({ queryKey: ['grade-entry', evaluationUrl] }),
        ] : []),
      ]);
    },
  });
  const conflict = saving.error?.response?.status === 409;
  const busy = saving.isPending || query.isFetching;
  const cannotReview = busy || Boolean(query.error) || conflict;
  const select = (proposal) => {
    saving.reset();
    setNotice('');
    setReason('');
    setSelected(proposal);
  };
  const refresh = () => {
    if (busy) { return; }
    select(null);
    query.refetch();
  };
  const columns = [
    { Header: 'Proposition', accessor: 'id' },
    { Header: variant === 'secondaire' ? 'Élève (identifiant)' : 'Étudiant (identifiant)', accessor: 'learner_id' },
    { Header: 'Score LMS', accessor: 'lms_score' },
    { Header: 'Note proposée', accessor: 'proposed_grade' },
    { Header: 'Reçue du LMS', accessor: 'timestamp_lms' },
    { Header: 'Décision', accessor: 'review_label' },
    { Header: 'Motif', accessor: 'review_reason' },
    { Header: 'Note officielle', accessor: 'note_id' },
    { Header: 'Actions', accessor: 'actions', Cell: reviewButton.bind(null, select, cannotReview) },
  ];
  const rows = (query.data?.results || []).map(proposal => ({
    ...proposal,
    lms_score: `${proposal.score ?? '—'} / ${proposal.max_score ?? '—'}`,
    proposed_grade: proposal.proposed_value == null ? '—' : `${proposal.proposed_value} / ${proposal.proposed_scale}`,
    review_label: reviewLabels[proposal.review_status] || proposal.review_status,
  }));
  return (
    <Dialog open fullWidth maxWidth="lg" onClose={() => !saving.isPending && onClose()}>
      <DialogTitle>Propositions LMS — {evaluation.titre}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Alert severity="info">
            Les scores LMS ne sont pas des notes officielles. Une approbation explicite crée une note
            uniquement si aucune note n’existe déjà ; elle ne remplace jamais une note enregistrée.
          </Alert>
          {notice && <Alert severity="success">{notice}</Alert>}
          {query.error && <Alert severity="error">{apiErrorMessage(query.error)}</Alert>}
          {saving.error && (
            <Alert severity="error">
              {conflict && 'Conflit : actualisez les propositions avant de réexaminer cette décision. '}
              {apiErrorMessage(saving.error)}
            </Alert>
          )}
          {selected && (
            <Stack spacing={2} component="section" aria-label="Examiner une proposition LMS">
              <Typography variant="h6" component="h2">
                Proposition n° {selected.id} — apprenant n° {selected.learner_id}
              </Typography>
              <Typography>
                Score LMS : {selected.score} / {selected.max_score}.
                Note proposée : {selected.proposed_value ?? '—'} / {selected.proposed_scale ?? '—'}.
              </Typography>
              <TextField
                label="Motif de la décision"
                helperText="Obligatoire pour rejeter la proposition."
                multiline
                minRows={2}
                value={reason}
                disabled={cannotReview}
                onChange={event => setReason(event.target.value)}
              />
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <Button
                  variant="contained"
                  disabled={cannotReview || selected.proposed_value == null || selected.proposed_scale == null}
                  onClick={() => saving.mutate('approve')}
                >
                  Approuver et créer la note
                </Button>
                <Button
                  color="error"
                  disabled={cannotReview || !reason.trim()}
                  onClick={() => saving.mutate('reject')}
                >
                  Rejeter la proposition
                </Button>
                <Button disabled={saving.isPending} onClick={() => select(null)}>Annuler l’examen</Button>
              </Stack>
            </Stack>
          )}
          {saving.isPending && <Typography role="status">Enregistrement de la décision…</Typography>}
          <SISDataTable
            title="Propositions LMS"
            columns={columns}
            data={rows}
            loading={query.isFetching}
            searchable={false}
            exportable={false}
            emptyMessage={query.error ? 'Les propositions ne sont pas disponibles.' : 'Aucune proposition LMS pour cette évaluation.'}
            serverPagination={{
              page: query.data ? page : 0,
              pageSize,
              count: query.data?.count || 0,
              search: '',
              onSearchChange: () => {},
              onPageChange: (value) => {
                if (!busy) { select(null); setPage(value); }
              },
              onPageSizeChange: (value) => {
                if (!busy) { select(null); setPageSize(value); setPage(0); }
              },
            }}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={refresh} disabled={busy}>Actualiser les propositions</Button>
        <Button onClick={onClose} disabled={saving.isPending}>Fermer</Button>
      </DialogActions>
    </Dialog>
  );
};

LmsGradeProposalsDialog.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  evaluation: PropTypes.shape({
    id: PropTypes.number.isRequired,
    titre: PropTypes.string.isRequired,
  }).isRequired,
  onClose: PropTypes.func.isRequired,
};

export default LmsGradeProposalsDialog;
