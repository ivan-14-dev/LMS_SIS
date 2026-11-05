import React, {
  useCallback, useEffect, useRef, useState,
} from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Stack, Typography,
} from '@mui/material';
import { getIntegrationApiUrl, requestIntegrationUserSynchronization } from '../../services/api';
import { isMockMode } from '../../services/mockApi';

const mappingType = PropTypes.shape({
  id: PropTypes.number,
  user_sis: PropTypes.number.isRequired,
  user_sis_name: PropTypes.string,
  user_sis_username: PropTypes.string,
  username_edx: PropTypes.string.isRequired,
  user_id_edx: PropTypes.number,
  actif: PropTypes.bool.isRequired,
});
const initialState = { status: 'review' };

const SynchronizationReview = ({
  mapping, integrationUrl, canSynchronize, state, attemptKey, updateAttempt, onClose, onComplete,
}) => {
  const [confirmed, setConfirmed] = useState(false);
  const current = useRef(state);
  current.current = state;
  const permitted = canSynchronize && mapping.actif && !isMockMode();
  const firstAssociation = mapping.id == null;
  const submitLabel = firstAssociation ? 'Associer cette identité' : 'Synchroniser cette identité';
  const busy = state.status === 'pending';
  const finished = state.status === 'success';
  const canSubmit = permitted && confirmed && !busy && !finished;
  const close = () => {
    if (current.current.status !== 'pending') { onClose(); }
  };
  const synchronize = async () => {
    if (!canSubmit || current.current.status === 'pending'
      || getIntegrationApiUrl() !== integrationUrl) { return; }
    const expectedNativeId = current.current.expectedNativeId ?? mapping.user_id_edx;
    current.current = { status: 'pending', expectedNativeId };
    updateAttempt(attemptKey, current.current);
    setConfirmed(false);
    let outcome;
    try {
      const result = await requestIntegrationUserSynchronization(
        integrationUrl,
        mapping.user_sis,
        mapping.username_edx,
        expectedNativeId,
      );
      outcome = { status: 'success', result, expectedNativeId };
    } catch (error) {
      const detail = error.response?.data?.error || error.response?.data?.detail;
      outcome = {
        status: 'uncertain',
        expectedNativeId,
        error: typeof detail === 'string' ? detail : error.message || 'Réponse du serveur indisponible.',
      };
    }
    // Keep the original identity's attempt, even if another SIS is now selected.
    if (updateAttempt(attemptKey, outcome) && getIntegrationApiUrl() === integrationUrl) {
      await onComplete(integrationUrl);
    }
  };

  return (
    <Dialog open fullWidth maxWidth="sm" onClose={close} aria-labelledby="user-synchronization-title">
      <DialogTitle id="user-synchronization-title">
        {firstAssociation ? 'Associer un utilisateur au LMS' : 'Synchroniser l’identité LMS'}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <Typography>{mapping.user_sis_name || mapping.user_sis_username || mapping.user_sis}</Typography>
          <Typography variant="body2">Utilisateur SIS : {mapping.user_sis}</Typography>
          <Typography variant="body2">Identité LMS : {mapping.username_edx}</Typography>
          {firstAssociation && (
            <Typography variant="body2">
              Première association de cet utilisateur SIS : l’identifiant LMS ci-dessus est calculé par le serveur.
              Aucune association n’est créée avant votre confirmation et l’envoi de la demande.
            </Typography>
          )}
          <Typography variant="body2">
            Cette action crée ou met à jour l’identité LMS associée avec le nom et l’adresse courriel du SIS.
            Elle n’inscrit à aucun cours et n’accorde aucun droit d’enseignement ou d’administration.
          </Typography>
          {!canSynchronize && (
            <Alert severity="error">
              Synchronisation réservée au personnel autorisé, avec une identité active et inchangée.
            </Alert>
          )}
          {!mapping.actif && <Alert severity="error">Cette association LMS est désactivée.</Alert>}
          {isMockMode() && <Alert severity="error">Synchronisation indisponible en mode démonstration.</Alert>}
          {state.error && <Alert severity="error">{state.error}</Alert>}
          {state.status === 'uncertain' && (
            <Alert severity="warning">
              Synchronisation non confirmée. Le LMS peut avoir été modifié, même si la réponse a été perdue.
              Vérifiez la liste actualisée, puis réessayez uniquement cette même identité.
              Fermer ne signifie pas annuler la demande.
            </Alert>
          )}
          {finished ? (
            <Alert severity="success">
              Synchronisation de l’identité confirmée par le serveur : {state.result.username_edx}.
              {' '}ID LMS : {state.result.user_id_edx}.
            </Alert>
          ) : (
            <FormControlLabel
              control={(
                <Checkbox
                  checked={confirmed}
                  onChange={event => setConfirmed(event.target.checked)}
                  disabled={!permitted || busy}
                />
              )}
              label="Je confirme la création ou la mise à jour de cette identité LMS, sans attribution d’accès."
            />
          )}
          {busy && <Typography role="status">Synchronisation en cours. Attendez la réponse avant de fermer.</Typography>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={close} disabled={busy}>{state.status === 'review' ? 'Annuler' : 'Fermer'}</Button>
        {!finished && (
          <Button variant="contained" disabled={!canSubmit} onClick={synchronize}>
            {state.status === 'uncertain' ? 'Réessayer la même identité' : submitLabel}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

SynchronizationReview.propTypes = {
  mapping: mappingType.isRequired,
  integrationUrl: PropTypes.string.isRequired,
  canSynchronize: PropTypes.bool.isRequired,
  state: PropTypes.shape({
    status: PropTypes.string.isRequired,
    expectedNativeId: PropTypes.number,
    error: PropTypes.string,
    result: PropTypes.shape({ username_edx: PropTypes.string, user_id_edx: PropTypes.number }),
  }).isRequired,
  attemptKey: PropTypes.string.isRequired,
  updateAttempt: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
};

const UserSynchronizationDialog = ({
  mapping, integrationUrl, canSynchronize, onClose, onComplete,
}) => {
  const [attempts, setAttempts] = useState(() => new Map());
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const updateAttempt = useCallback((key, value) => {
    if (!mounted.current) { return false; }
    setAttempts(previous => new Map(previous).set(key, value));
    return true;
  }, []);
  if (!mapping) { return null; }
  const attemptKey = `${integrationUrl}:${mapping.user_sis}:${mapping.username_edx}`;
  const state = attempts.get(attemptKey) || initialState;
  const close = () => {
    if (state.status === 'pending') { return; }
    if (state.status === 'success') { updateAttempt(attemptKey, initialState); }
    onClose();
  };
  return (
    <SynchronizationReview
      key={`${attemptKey}:${canSynchronize}:${mapping.actif}`}
      mapping={mapping}
      integrationUrl={integrationUrl}
      canSynchronize={canSynchronize}
      state={state}
      attemptKey={attemptKey}
      updateAttempt={updateAttempt}
      onClose={close}
      onComplete={onComplete}
    />
  );
};

UserSynchronizationDialog.propTypes = {
  mapping: mappingType,
  integrationUrl: PropTypes.string.isRequired,
  canSynchronize: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
};
UserSynchronizationDialog.defaultProps = { mapping: null };

export default UserSynchronizationDialog;
