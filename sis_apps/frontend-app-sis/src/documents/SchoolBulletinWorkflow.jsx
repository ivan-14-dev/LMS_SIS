import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import {
  useMutation, useQueries, useQuery, useQueryClient,
} from '@tanstack/react-query';
import { fetchApi, postApi } from '../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../services/resources';

const references = [
  {
    field: 'eleve', label: 'Élève', resource: 'eleves', name: item => item.full_name,
  },
  {
    field: 'classe', label: 'Classe', resource: 'classes/classes', name: item => `${item.nom} — ${item.annee_libelle}`,
  },
  {
    field: 'periode',
    label: 'Période',
    resource: 'etablissement/periodes',
    name: item => item.libelle || `${item.type_display} ${item.numero} — ${item.annee_libelle}`,
  },
];

const SchoolBulletinWorkflow = ({
  selectedId, onSelect, onClose, canPrepare, canManage,
}) => {
  const [creating, setCreating] = useState(false);
  const [values, setValues] = useState({ eleve: '', classe: '', periode: '' });
  const [appreciation, setAppreciation] = useState('');
  const [decision, setDecision] = useState('');
  const [reason, setReason] = useState('');
  const rectification = useRef(null);
  const url = resourceUrl('secondaire', 'bulletins');
  const client = useQueryClient();
  const detail = useQuery({
    queryKey: ['bulletin-calculation', url, selectedId],
    queryFn: () => fetchApi(`${url}${selectedId}/`),
    enabled: Boolean(selectedId),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const choices = useQueries({
    queries: references.map(reference => ({
      queryKey: ['reference', resourceUrl('secondaire', reference.resource), {}],
      queryFn: ({ signal }) => fetchAllResourcePages(resourceUrl('secondaire', reference.resource), {}, { signal }),
      enabled: creating,
    })),
  });
  const bulletin = detail.data;
  useEffect(() => {
    setReason('');
    rectification.current = null;
  }, [selectedId]);
  useEffect(() => {
    setAppreciation(bulletin?.appreciation_conseil || '');
    setDecision(bulletin?.decision || '');
  }, [bulletin]);
  const mutation = useMutation({
    mutationFn: ({ action, payload }) => postApi(`${url}${action === 'preparer' ? '' : `${selectedId}/`}${action}/`, payload),
    onSuccess: async (result, { action }) => {
      await client.invalidateQueries({ queryKey: ['documents'] });
      if (action === 'preparer' || action === 'rectifier') {
        setCreating(false);
        rectification.current = null;
        setReason('');
        onSelect(result.id);
      } else {
        await client.invalidateQueries({ queryKey: ['bulletin-calculation', url] });
      }
    },
  });
  const close = () => {
    if (mutation.isPending) { return; }
    setCreating(false);
    mutation.reset();
    onClose();
  };
  const referenceError = choices.find(query => query.error)?.error;
  const error = mutation.error || (creating ? referenceError : detail.error);
  const busy = mutation.isPending || (creating ? choices.some(query => query.isFetching) : detail.isFetching);
  const change = action => mutation.mutate({
    action,
    payload: {
      version: bulletin.updated_at,
      ...(action === 'valider' ? {
        confirmer: true, appreciation_conseil: appreciation, decision,
      } : {}),
    },
  });
  const rectify = () => {
    if (!rectification.current) {
      rectification.current = {
        version: bulletin.updated_at, motif: reason.trim(), cle_idempotence: crypto.randomUUID(),
      };
    }
    mutation.mutate({ action: 'rectifier', payload: rectification.current });
  };
  return (
    <>
      {canPrepare && (
        <Button
          variant="contained"
          sx={{ mb: 2 }}
          onClick={() => { mutation.reset(); setCreating(true); onClose(); }}
        >Préparer un bulletin
        </Button>
      )}
      <Dialog open={creating || Boolean(selectedId)} onClose={close} fullWidth maxWidth="md">
        <DialogTitle>{creating ? 'Préparer un brouillon de bulletin' : 'Vérifier le bulletin'}</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            Protocole numérique sur 20 : coefficient × pondération pour chaque évaluation,
            puis coefficients des matières. Arrondi final à deux décimales, demi supérieur.
            Absences, travaux non rendus, compétences et parcours individualisés nécessitent un traitement dédié.
            Aucun rang, passage ou diplôme n’est attribué automatiquement.
          </Alert>
          {error && <Alert severity="error">{apiErrorMessage(error)}</Alert>}
          {mutation.isSuccess && !creating && <Alert severity="success">Opération effectuée.</Alert>}
          {busy && <Typography role="status">Chargement ou enregistrement…</Typography>}
          {creating ? (
            <Box
              component="form"
              id="prepare-school-bulletin"
              onSubmit={(event) => {
                event.preventDefault();
                mutation.mutate({
                  action: 'preparer',
                  payload: {
                    ...Object.fromEntries(Object.entries(values).map(([field, value]) => [field, Number(value)])),
                    methode: 'moyenne_ponderee_20_v1',
                  },
                });
              }}
            >
              {references.map((reference, index) => (
                <TextField
                  key={reference.field}
                  label={reference.label}
                  select
                  required
                  fullWidth
                  margin="normal"
                  disabled={busy || Boolean(referenceError)}
                  value={values[reference.field]}
                  onChange={event => setValues({ ...values, [reference.field]: event.target.value })}
                >
                  {(choices[index].data || []).map(item => (
                    <MenuItem key={item.id} value={item.id}>{reference.name(item)}</MenuItem>
                  ))}
                </TextField>
              ))}
            </Box>
          ) : bulletin && !detail.error && (
            <Stack spacing={2}>
              <Typography>{bulletin.eleve_nom} — {bulletin.classe_nom}</Typography>
              <Typography>Bulletin BUL-{bulletin.id} — révision {bulletin.revision || 1}</Typography>
              {bulletin.rectifie && (
                <Alert severity="info">
                  Rectifie BUL-{bulletin.rectifie}. Motif : {bulletin.motif_rectification}.
                  L’original est conservé ; cette version exige sa propre validation et publication.
                  <Button disabled={busy} onClick={() => onSelect(bulletin.rectifie)}>
                    Voir la version précédente
                  </Button>
                </Alert>
              )}
              {bulletin.rectification_publiee && (
                <Alert severity="warning">
                  Une rectification publiée est disponible : BUL-{bulletin.rectification_publiee}.
                  <Button disabled={busy} onClick={() => onSelect(bulletin.rectification_publiee)}>
                    Voir la rectification publiée
                  </Button>
                </Alert>
              )}
              <Typography>Moyenne calculée : {bulletin.moyenne_generale}/20</Typography>
              <Typography>{bulletin.calcul_detail?.formule}</Typography>
              {bulletin.calcul_detail?.matieres?.map(matiere => (
                <Box component="section" key={matiere.id} aria-label={matiere.nom}>
                  <Typography component="h3" variant="h6">
                    {matiere.nom} : {matiere.moyenne}/20 — coefficient {matiere.coefficient}
                  </Typography>
                  {matiere.notes.map(note => (
                    <Typography key={note.id}>
                      {note.titre} : {note.valeur}/{note.bareme},
                      coefficient {note.coefficient}, pondération {note.ponderation} %.
                    </Typography>
                  ))}
                </Box>
              ))}
              {Boolean(bulletin.calcul_detail?.exclusions?.length) && (
                <Alert severity="warning">
                  Évaluations exclues : {bulletin.calcul_detail.exclusions.map(item => `${item.evaluation} (${item.motif})`).join(', ')}.
                </Alert>
              )}
              {bulletin.publie ? (
                <Alert severity="success">Bulletin publié : le calcul conservé n’est plus modifiable.</Alert>
              ) : (
                <Alert severity="warning">
                  Vérifiez les sources avant validation.
                  Recalculer annule la validation et les appréciations précédentes.
                </Alert>
              )}
              {bulletin.date_validation && (
                <Typography>Validation enregistrée le {bulletin.date_validation}.</Typography>
              )}
              {bulletin.publie && canPrepare && !bulletin.rectification_publiee && (
                <TextField
                  label="Motif de rectification"
                  helperText="Crée un nouveau brouillon à partir des notes actuelles, sans modifier l’original."
                  required
                  multiline
                  value={reason}
                  onChange={event => {
                    setReason(event.target.value);
                    rectification.current = null;
                  }}
                  slotProps={{ htmlInput: { maxLength: 4000 } }}
                  disabled={busy}
                />
              )}
              <TextField
                label="Appréciation du conseil"
                multiline
                value={appreciation}
                onChange={event => setAppreciation(event.target.value)}
                disabled={!canManage || busy || bulletin.publie || Boolean(bulletin.date_validation)}
              />
              <TextField
                label="Décision humaine (facultative)"
                value={decision}
                onChange={event => setDecision(event.target.value)}
                slotProps={{ htmlInput: { maxLength: 50 } }}
                disabled={!canManage || busy || bulletin.publie || Boolean(bulletin.date_validation)}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={close} disabled={mutation.isPending}>Fermer</Button>
          {!creating && selectedId && (
            <Button disabled={busy} onClick={() => detail.refetch()}>Recharger le bulletin</Button>
          )}
          {creating ? (
            <Button
              type="submit"
              form="prepare-school-bulletin"
              disabled={busy || Boolean(referenceError) || !canPrepare}
            >Calculer le brouillon
            </Button>
          ) : bulletin?.calcul_detail?.methode && !bulletin.publie && canManage && !detail.error && (
            <>
              <Button disabled={busy} onClick={() => change('recalculer')}>Recalculer</Button>
              <Button disabled={busy || Boolean(bulletin.date_validation)} onClick={() => change('valider')}>Valider après vérification</Button>
              <Button disabled={busy || !bulletin.date_validation} onClick={() => change('publier')}>Publier le bulletin</Button>
            </>
          )}
          {!creating && bulletin?.calcul_detail?.methode && bulletin.publie
            && !bulletin.rectification_publiee && canPrepare && !detail.error && (
              <Button disabled={busy || !reason.trim()} onClick={rectify}>Créer une rectification</Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
};

SchoolBulletinWorkflow.propTypes = {
  selectedId: PropTypes.number,
  onSelect: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  canPrepare: PropTypes.bool.isRequired,
  canManage: PropTypes.bool.isRequired,
};
SchoolBulletinWorkflow.defaultProps = { selectedId: null };
export default SchoolBulletinWorkflow;
