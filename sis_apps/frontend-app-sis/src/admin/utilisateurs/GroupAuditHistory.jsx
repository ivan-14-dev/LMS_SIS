import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Paper, Stack, Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { apiErrorMessage, fetchResourcePage, resourceUrl } from '../../services/resources';
import CollectionPagination from '../../components/common/CollectionPagination';

const snapshotText = (snapshot) => {
  if (snapshot === null) { return 'Groupe absent'; }
  if (!snapshot || !Array.isArray(snapshot.permissions)) { return 'Instantané non disponible'; }
  return `${snapshot.name} — ${snapshot.permissions.map(permission => permission.code).join(', ') || 'Aucune permission'}`;
};

const GroupAuditHistory = ({ variant, groupId }) => {
  const [page, setPage] = useState(1);
  const history = useQuery({
    queryKey: ['institutional-group-history', resourceUrl(variant, 'utilisateurs/groupes'), groupId, page],
    queryFn: ({ signal }) => fetchResourcePage(resourceUrl(variant, 'core/workflow-events'), {
      app_label: 'auth', model: 'group', object_id: groupId, page,
    }, { signal }),
    gcTime: 0,
    staleTime: 0,
    retry: false,
    refetchOnMount: 'always',
  });

  const renderEvents = () => {
    if (history.isPending) { return <Typography role="status">Chargement de l’historique…</Typography>; }
    if (history.isError) {
      return (
        <Alert severity="error">
          {[401, 403].includes(history.error?.response?.status)
            ? 'Historique non autorisé.' : apiErrorMessage(history.error)}
          <Button type="button" onClick={() => history.refetch()}>Réessayer</Button>
        </Alert>
      );
    }
    return (
      <>
        {!history.data.results.length && <Typography>Aucun événement enregistré pour ce groupe.</Typography>}
        {history.data.results.map((event) => {
          const metadata = event.metadata || {};
          const targets = metadata.user_ids || (metadata.user_id ? [metadata.user_id] : null);
          return (
            <Paper key={event.id} variant="outlined" sx={{ p: 2, mb: 1 }}>
              <Typography component="h4" variant="subtitle2">{event.title}</Typography>
              <Typography variant="body2">{event.actor_nom || 'Acteur non renseigné'} · {event.created_at}</Typography>
              <Typography variant="body2">{event.action} · {event.object_repr}</Typography>
              <Box component="details" sx={{ mt: 1 }}>
                <Typography component="summary" variant="body2">Voir les changements</Typography>
                {metadata.before !== undefined && <Typography variant="body2">Avant : {snapshotText(metadata.before)}</Typography>}
                {metadata.after !== undefined && <Typography variant="body2">Après : {snapshotText(metadata.after)}</Typography>}
                {typeof metadata.before?.actif === 'boolean' && (
                  <Typography variant="body2">Statut avant : {metadata.before.actif ? 'Actif' : 'Désactivé'}</Typography>
                )}
                {typeof metadata.after?.actif === 'boolean' && (
                  <Typography variant="body2">Statut après : {metadata.after.actif ? 'Actif' : 'Désactivé'}</Typography>
                )}
                {targets && <Typography variant="body2">Comptes demandés : {targets.join(', ')}</Typography>}
                {Array.isArray(metadata.added_user_ids) && (
                  <Typography variant="body2">Ajouts effectifs : {metadata.added_user_ids.join(', ') || 'Aucun'}</Typography>
                )}
                {Array.isArray(metadata.removed_user_ids) && (
                  <Typography variant="body2">Retraits effectifs : {metadata.removed_user_ids.join(', ') || 'Aucun'}</Typography>
                )}
                {event.request_id && <Typography variant="body2">Requête : {event.request_id}</Typography>}
              </Box>
            </Paper>
          );
        })}
        <CollectionPagination
          data={history.data}
          page={page}
          setPage={setPage}
          disabled={history.isFetching}
          label="Historique des habilitations"
          previousLabel="Historique précédent"
          nextLabel="Historique suivant"
        />
      </>
    );
  };

  return (
    <Box component="section" aria-label="Historique des habilitations" sx={{ mt: 3 }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ xs: 'stretch', sm: 'center' }} sx={{ mb: 2 }}>
        <Typography component="h3" variant="subtitle1">Historique des habilitations</Typography>
        <Button type="button" disabled={history.isFetching} onClick={() => history.refetch()}>Actualiser l’historique</Button>
      </Stack>
      {renderEvents()}
    </Box>
  );
};

GroupAuditHistory.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  groupId: PropTypes.number.isRequired,
};

export default GroupAuditHistory;
