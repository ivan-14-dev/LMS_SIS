import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Chip, Dialog, DialogContent, DialogTitle, Paper, Stack, Typography,
} from '@mui/material';
import { apiErrorMessage, downloadPdf, fetchAllResourcePages } from '../services/resources';
import {
  dateLabel, isDenied, milestoneType, queryOptions, teamType,
} from './projectUi';

const ProjectTeamPanel = ({
  url, projectId, team, milestone, disabled, onCommand, onDenied, onBusy,
}) => {
  const teamUrl = `${url}${projectId}/equipes/${team.id}/`;
  const records = useQuery({
    ...queryOptions,
    queryKey: ['projects', url, projectId, 'team', team.id, milestone.id],
    queryFn: async ({ signal }) => {
      const [deliveries, evaluations] = await Promise.all([
        fetchAllResourcePages(`${teamUrl}livrables/`, { jalon: milestone.id, page_size: 100 }, { signal }),
        fetchAllResourcePages(`${teamUrl}evaluations/`, { jalon: milestone.id, page_size: 100 }, { signal }),
      ]);
      return { deliveries, evaluations };
    },
  });
  const download = useMutation({
    retry: false,
    mutationFn: delivery => downloadPdf(`${teamUrl}livrables/${delivery.id}/telecharger/`, delivery.nom),
    onError: error => { if (isDenied(error)) { onDenied(error); } },
    onSettled: () => onBusy(false),
  });
  useEffect(() => {
    if (isDenied(records.error)) { onDenied(records.error); }
  }, [records.error, onDenied]);
  if (records.error) {
    return <Alert severity="error">Données de l’équipe indisponibles. {apiErrorMessage(records.error)}<Button onClick={() => records.refetch()}>Réessayer</Button></Alert>;
  }
  if (!records.data) { return <Alert severity="info">Chargement des livrables et évaluations…</Alert>; }
  const { deliveries, evaluations } = records.data;
  const locked = disabled || records.isFetching || download.isPending;
  const latestRevision = Math.max(0, ...evaluations.map(item => item.revision));
  return (
    <Stack spacing={2}>
      <Typography variant="h6" component="h3">Livrables privés · {team.nom} · {milestone.titre}</Typography>
      <Typography variant="body2">Chaque révision est conservée. Téléchargements réservés aux personnes autorisées.</Typography>
      {download.error && <Alert severity="error">Téléchargement impossible. {apiErrorMessage(download.error)}</Alert>}
      {!deliveries.length && <Alert severity="info">Aucun livrable pour ce jalon.</Alert>}
      {deliveries.map(delivery => (
        <Paper key={delivery.id} variant="outlined" sx={{ p: 2 }}>
          <Typography>{delivery.nom} · Révision {delivery.revision} · {dateLabel(delivery.created_at)}</Typography>
          <Chip size="small" color={delivery.en_retard ? 'warning' : 'success'} label={delivery.en_retard ? 'En retard' : 'Dans les délais'} />
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{delivery.commentaire}</Typography>
          <Button
            disabled={locked}
            onClick={() => { onBusy(true); download.mutate(delivery); }}
          >
            Télécharger {delivery.nom} (révision {delivery.revision})
          </Button>
        </Paper>
      ))}
      {team.actions.can_submit && team.membres.length > 0 && (
        <Button variant="outlined" disabled={locked} onClick={() => onCommand({ kind: 'delivery', teamId: team.id, milestoneId: milestone.id })}>Déposer un PDF</Button>
      )}
      <Typography variant="h6" component="h3">Évaluations pédagogiques</Typography>
      <Typography variant="body2">Les apprenants ne voient que les évaluations publiées et leur contribution personnelle. Une note absente n’est pas une note zéro.</Typography>
      {!evaluations.length && <Alert severity="info">Aucune évaluation accessible pour ce jalon.</Alert>}
      {evaluations.map(evaluation => (
        <Paper key={evaluation.id} variant="outlined" component="section" aria-label={`Évaluation révision ${evaluation.revision}`} sx={{ p: 2 }}>
          <Stack spacing={1}>
            <Typography>Révision {evaluation.revision} · {dateLabel(evaluation.created_at)}</Typography>
            <Chip sx={{ alignSelf: 'flex-start' }} label={evaluation.statut === 'publiee' ? 'Publiée' : 'Brouillon non publié'} color={evaluation.statut === 'publiee' ? 'success' : 'default'} />
            <Typography>Note du groupe : {evaluation.note_groupe ?? 'Non renseignée'} / {evaluation.bareme}</Typography>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{evaluation.commentaire}</Typography>
            {evaluation.contributions.map(contribution => (
              <Paper key={contribution.membre} variant="outlined" sx={{ p: 1 }}>
                <Typography>{team.membres.find(member => member.membre === contribution.membre)?.nom || 'Ancien membre'} : {contribution.note ?? 'Non renseignée'} / {evaluation.bareme}</Typography>
                <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{contribution.commentaire}</Typography>
              </Paper>
            ))}
            {evaluation.statut === 'publiee' && <Typography variant="body2">Publiée le {dateLabel(evaluation.published_at)}</Typography>}
            {team.actions.can_evaluate && team.membres.length > 0 && evaluation.statut === 'brouillon' && evaluation.revision === latestRevision && (
              <Button
                disabled={locked}
                onClick={() => onCommand({
                  kind: 'publish', teamId: team.id, milestoneId: milestone.id, evaluationId: evaluation.id,
                })}
              >
                Publier cette évaluation
              </Button>
            )}
          </Stack>
        </Paper>
      ))}
      {team.actions.can_evaluate && (
        <Button variant="outlined" disabled={locked} onClick={() => onCommand({ kind: 'evaluation', teamId: team.id, milestoneId: milestone.id })}>Nouveau brouillon d’évaluation</Button>
      )}
      <Dialog open={download.isPending} disableEscapeKeyDown>
        <DialogTitle>Téléchargement privé en cours</DialogTitle>
        <DialogContent>Veuillez patienter avant de changer de projet ou d’équipe.</DialogContent>
      </Dialog>
    </Stack>
  );
};
ProjectTeamPanel.propTypes = {
  url: PropTypes.string.isRequired,
  projectId: PropTypes.string.isRequired,
  team: teamType.isRequired,
  milestone: milestoneType.isRequired,
  disabled: PropTypes.bool.isRequired,
  onCommand: PropTypes.func.isRequired,
  onDenied: PropTypes.func.isRequired,
  onBusy: PropTypes.func.isRequired,
};
export default ProjectTeamPanel;
