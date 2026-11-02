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
  const assessment = evaluation.offre_configuration?.assessment;
  const mode = assessment?.mode || 'numeric';
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
    resultat: mode === 'competency' ? {
      criteria: Object.fromEntries(assessment.criteria.map(criterion => [
        criterion.code,
        Object.prototype.hasOwnProperty.call(existing[id]?.resultat?.criteria || {}, criterion.code)
          ? existing[id].resultat.criteria[criterion.code] : null,
      ])),
    } : { passed: existing[id]?.resultat?.passed ?? null },
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
      ...(mode !== 'numeric' ? { resultat: row.resultat } : {}),
    }))),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['resource'] });
      client.removeQueries({ queryKey: ['grade-entry', url] });
      onSaved();
    },
  });
  const busy = saving.isPending || query.isFetching;
  const decisionField = (label, value, onChange) => (
    <TextField
      select
      label={label}
      disabled={busy}
      value={value === null ? '' : String(value)}
      onChange={event => onChange(event.target.value === '' ? null : event.target.value === 'true')}
    >
      <MenuItem value="">Non renseigné</MenuItem>
      <MenuItem value="true">Acquis / validé</MenuItem>
      <MenuItem value="false">Non acquis / non validé</MenuItem>
    </TextField>
  );
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
            {mode === 'numeric' ? `Barème : ${evaluation.bareme}. ` : 'Résultats non chiffrés. '}
            Seules les lignes modifiées seront enregistrées.
          </Typography>
          {evaluation.offre_configuration?.label && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Règles historisées : {evaluation.offre_configuration.label}.
              Cette saisie n’attribue pas automatiquement de crédits ou de diplôme.
            </Alert>
          )}
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
                  {mode === 'numeric' && (
                  <TextField
                    label={`Note ${learner.matricule}`}
                    disabled={busy}
                    type="number"
                    value={row.valeur}
                    slotProps={{ htmlInput: { min: assessment?.minimum ?? 0, max: evaluation.bareme, step: '0.01' } }}
                    onChange={event => update(learner.id, 'valeur', event.target.value)}
                  />
                  )}
                  {mode === 'competency' && assessment.criteria.map(criterion => (
                    <React.Fragment key={criterion.code}>
                      {decisionField(
                        `${criterion.label} ${learner.matricule}`,
                        row.resultat.criteria[criterion.code],
                        value => update(learner.id, 'resultat', {
                          criteria: { ...row.resultat.criteria, [criterion.code]: value },
                        }),
                      )}
                    </React.Fragment>
                  ))}
                  {mode === 'pass_fail' && decisionField(
                    `Résultat ${learner.matricule}`,
                    row.resultat.passed,
                    value => update(learner.id, 'resultat', { passed: value }),
                  )}
                  {existing[learner.id]?.resultat_offre && (
                    <Typography>Résultat enregistré : {existing[learner.id].resultat_offre.detail}</Typography>
                  )}
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
    offre_configuration: PropTypes.shape({
      label: PropTypes.string,
      assessment: PropTypes.shape({
        mode: PropTypes.oneOf(['numeric', 'competency', 'pass_fail']),
        minimum: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        criteria: PropTypes.arrayOf(PropTypes.shape({
          code: PropTypes.string.isRequired, label: PropTypes.string.isRequired,
        })),
      }),
    }),
  }).isRequired,
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
};

export default GradeEntryDialog;
