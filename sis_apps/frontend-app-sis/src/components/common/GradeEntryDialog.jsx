import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, postApi } from '../../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../../services/resources';

const GradeEntryDialog = ({
  variant, evaluation, onClose, onSaved,
}) => {
  const [changes, setChanges] = useState({});
  const client = useQueryClient();
  const url = resourceUrl(variant, `notes/evaluations/${evaluation.id}`);
  const learnerField = variant === 'secondaire' ? 'eleve' : 'etudiant';
  const query = useQuery({
    queryKey: ['grade-entry', url],
    queryFn: async ({ signal }) => {
      const [learners, notes] = await Promise.all([
        fetchAllResourcePages(`${url}apprenants/`, { page_size: 100 }, { signal }),
        fetchApi(`${url}notes/`, { signal }),
      ]);
      return { learners, notes };
    },
    refetchOnWindowFocus: false,
  });
  const existing = Object.fromEntries((query.data?.notes || []).map(note => [note[learnerField], note]));
  const initial = id => ({
    valeur: existing[id]?.valeur ?? '',
    statut: existing[id]?.statut || 'presente',
    appreciation: existing[id]?.appreciation || '',
  });
  const update = (id, field, value) => setChanges(previous => ({
    ...previous, [id]: { ...(previous[id] || initial(id)), [field]: value },
  }));
  const saving = useMutation({
    mutationFn: () => postApi(`${url}saisir_notes/`, Object.entries(changes).map(([id, row]) => ({
      [`${learnerField}_id`]: Number(id),
      valeur: row.valeur === '' ? null : row.valeur,
      statut: row.statut,
      appreciation: row.appreciation,
    }))),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['resource'] });
      client.removeQueries({ queryKey: ['grade-entry', url] });
      onSaved();
    },
  });
  const busy = saving.isPending || query.isFetching;
  const statuses = [
    ['presente', 'Présentée'], ['absente', 'Absent'],
    [variant === 'secondaire' ? 'dispensee' : 'dispense', 'Dispensé'],
    ['non_rendue', 'Non rendue'], ['triche', 'Triche'],
    ...(variant === 'superieur' ? [['absent_justifie', 'Absent justifié'], ['en_attente', 'En attente']] : []),
  ];
  return (
    <Dialog open fullWidth maxWidth="md" onClose={() => !saving.isPending && onClose()}>
      <Box component="form" onSubmit={(event) => { event.preventDefault(); saving.mutate(); }}>
        <DialogTitle>Saisir les notes — {evaluation.titre}</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 2 }}>
            Barème : {evaluation.bareme}. Seules les lignes modifiées seront enregistrées.
          </Typography>
          {query.isFetching && <Typography>Chargement des apprenants autorisés…</Typography>}
          {query.error && <Alert severity="error">{apiErrorMessage(query.error)}</Alert>}
          {saving.error && <Alert severity="error">{apiErrorMessage(saving.error)}</Alert>}
          {query.data?.learners.length === 0 && (
            <Alert severity="info">Aucun apprenant inscrit pour cette évaluation.</Alert>
          )}
          {query.data?.learners.map((learner) => {
            const row = changes[learner.id] || initial(learner.id);
            return (
              <Box component="fieldset" key={learner.id} disabled={busy} sx={{ my: 2, borderColor: 'divider' }}>
                <legend>{learner.nom} — {learner.matricule}</legend>
                <Stack spacing={2} sx={{ py: 1 }}>
                  <TextField
                    label={`Note ${learner.matricule}`}
                    disabled={busy}
                    type="number"
                    value={row.valeur}
                    slotProps={{ htmlInput: { min: 0, max: evaluation.bareme, step: '0.01' } }}
                    onChange={event => update(learner.id, 'valeur', event.target.value)}
                  />
                  <TextField
                    label={`Statut ${learner.matricule}`}
                    disabled={busy}
                    select
                    value={row.statut}
                    onChange={event => update(learner.id, 'statut', event.target.value)}
                  >
                    {statuses.map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
                  </TextField>
                  <TextField
                    label={`Appréciation ${learner.matricule}`}
                    disabled={busy}
                    value={row.appreciation}
                    onChange={event => update(learner.id, 'appreciation', event.target.value)}
                  />
                </Stack>
              </Box>
            );
          })}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={saving.isPending}>Annuler</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={busy || !query.data || Boolean(query.error) || Object.keys(changes).length === 0}
          >
            {saving.isPending ? 'Enregistrement…' : 'Enregistrer les notes'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};

GradeEntryDialog.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  evaluation: PropTypes.shape({
    id: PropTypes.number.isRequired,
    titre: PropTypes.string.isRequired,
    bareme: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  }).isRequired,
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
};

export default GradeEntryDialog;
