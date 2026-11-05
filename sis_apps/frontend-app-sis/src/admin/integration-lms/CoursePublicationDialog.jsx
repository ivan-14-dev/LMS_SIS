import React, {
  useCallback, useEffect, useRef, useState,
} from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Stack, Typography,
} from '@mui/material';
import { fetchApi, getIntegrationApiUrl, postApi } from '../../services/api';
import { isMockMode } from '../../services/mockApi';
import { apiErrorMessage } from '../../services/resources';

const isRevision = value => typeof value === 'string' && /^[a-f0-9]{24}$/.test(value);
const initialState = { status: 'loading' };
const mappingType = PropTypes.shape({
  id: PropTypes.number.isRequired,
  course_id: PropTypes.string.isRequired,
  course_name: PropTypes.string.isRequired,
  actif: PropTypes.bool.isRequired,
});

const PublicationReview = ({
  mapping, url, state, updateAttempt, attemptKey, canPublish, onClose,
}) => {
  const [confirmed, setConfirmed] = useState(false);
  const current = useRef(state);
  current.current = state;
  const setState = useCallback((value) => {
    current.current = value;
    updateAttempt(attemptKey, value);
  }, [attemptKey, updateAttempt]);
  const permitted = canPublish && mapping.actif && !isMockMode();
  const busy = state.status === 'publishing';
  const finished = state.status === 'success';
  const uncertain = state.status === 'uncertain';
  const canSubmit = permitted && confirmed && ['review', 'uncertain'].includes(state.status);

  useEffect(() => {
    if (!permitted || current.current.status !== 'loading') { return undefined; }
    let active = true;
    const controller = new AbortController();
    const load = async () => {
      try {
        const review = await fetchApi(url, { signal: controller.signal });
        if (review?.id !== mapping.course_id || !isRevision(review?.revision)) {
          throw new Error('Studio n’a pas confirmé l’identité et la révision du cours.');
        }
        if (active) {
          setState({ status: 'review', review });
        }
      } catch (error) {
        if (active) {
          setState({ status: 'review-error', error: apiErrorMessage(error) });
        }
      }
    };
    load();
    return () => {
      active = false;
      controller.abort();
    };
  }, [mapping.course_id, permitted, state.status, setState, url]);

  const publish = async () => {
    if (!canSubmit || !['review', 'uncertain'].includes(current.current.status)) { return; }
    let attempt;
    try {
      attempt = {
        ...current.current,
        operationId: current.current.operationId || crypto.randomUUID(),
        status: 'publishing',
        error: null,
      };
    } catch {
      setState({
        ...current.current, error: 'Impossible de créer un identifiant sécurisé. Utilisez une connexion HTTPS.',
      });
      return;
    }
    setState(attempt);
    try {
      const result = await postApi(url, {
        operation_id: attempt.operationId,
        expected_revision: attempt.review.revision,
        confirm: true,
      });
      if (result?.id !== attempt.review.id
        || result?.operation_id !== attempt.operationId
        || result?.revision !== attempt.review.revision
        || !isRevision(result?.published_version)) {
        throw new Error('Studio n’a pas confirmé l’identité, l’opération et la révision publiées.');
      }
      attempt = { ...attempt, status: 'success', result };
    } catch (error) {
      const status = error?.response?.status;
      attempt = {
        ...attempt,
        status: [400, 401, 403, 404, 409].includes(status) ? 'rejected' : 'uncertain',
        error: apiErrorMessage(error),
      };
    }
    // Keep an uncertain operation across closing/reopening; never replace it with a newer draft.
    setState(attempt);
  };

  const reviewAgain = () => {
    if (current.current.status === 'publishing' || current.current.status === 'uncertain') { return; }
    setConfirmed(false);
    setState(initialState);
  };
  const close = () => {
    if (current.current.status !== 'publishing') { onClose(); }
  };

  return (
    <Dialog open fullWidth maxWidth="sm" onClose={close} aria-labelledby="course-publication-title">
      <DialogTitle id="course-publication-title">Examiner et publier le cours</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <Typography>{mapping.course_name}</Typography>
          <Typography variant="body2">Cours LMS : {state.review?.id || mapping.course_id}</Typography>
          {!canPublish && <Alert severity="error">Publication réservée aux administrateurs.</Alert>}
          {!mapping.actif && <Alert severity="error">Cette association de cours est désactivée.</Alert>}
          {isMockMode() && <Alert severity="error">Publication indisponible en mode démonstration.</Alert>}
          {permitted && state.status === 'loading' && <Typography>Lecture de la révision dans Studio…</Typography>}
          {state.review && <Typography variant="body2">Révision examinée : {state.review.revision}</Typography>}
          {state.operationId && <Typography variant="body2">Opération : {state.operationId}</Typography>}
          {state.error && <Alert severity="error">{state.error}</Alert>}
          {uncertain && (
            <Alert severity="warning">
              Publication non confirmée. Elle peut avoir été effectuée dans Studio.
              Réessayez la même opération et la même révision, sans charger un nouveau brouillon.
              Fermer ne l’annule pas ; conservez cette page pour réessayer.
            </Alert>
          )}
          {state.status === 'rejected' && (
            <Alert severity="warning">
              Demande refusée. Vérifiez les droits, l’association et le contenu dans Studio avant un nouvel examen.
            </Alert>
          )}
          {finished ? (
            <Alert severity="success">
              Publication confirmée par Studio. Version publiée : {state.result.published_version}
            </Alert>
          ) : (
            <FormControlLabel
              control={(
                <Checkbox
                  checked={confirmed}
                  onChange={event => setConfirmed(event.target.checked)}
                  disabled={!permitted || !['review', 'uncertain'].includes(state.status)}
                />
              )}
              label="J’ai examiné ce cours dans Studio et je confirme la publication de cette révision."
            />
          )}
          {busy && <Typography role="status">Publication en cours. Attendez la confirmation avant de fermer.</Typography>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={close} disabled={busy}>{state.operationId ? 'Fermer' : 'Annuler'}</Button>
        {permitted && ['review-error', 'rejected', 'success'].includes(state.status) && (
          <Button onClick={reviewAgain}>Examiner à nouveau</Button>
        )}
        {!finished && (
          <Button variant="contained" disabled={!canSubmit} onClick={publish}>
            {uncertain ? 'Réessayer la même publication' : 'Publier cette révision'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

PublicationReview.propTypes = {
  mapping: mappingType.isRequired,
  url: PropTypes.string.isRequired,
  state: PropTypes.shape({
    status: PropTypes.string.isRequired,
    review: PropTypes.shape({ id: PropTypes.string, revision: PropTypes.string }),
    operationId: PropTypes.string,
    error: PropTypes.string,
    result: PropTypes.shape({ published_version: PropTypes.string }),
  }).isRequired,
  updateAttempt: PropTypes.func.isRequired,
  attemptKey: PropTypes.string.isRequired,
  canPublish: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

const CoursePublicationDialog = ({ mapping, canPublish, onClose }) => {
  const [attempts, setAttempts] = useState(() => new Map());
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const updateAttempt = useCallback((key, value) => {
    if (mounted.current) { setAttempts(previous => new Map(previous).set(key, value)); }
  }, []);
  if (!mapping) { return null; }
  const url = `${getIntegrationApiUrl()}/sync/course/${mapping.id}/publication/`;
  const attemptKey = `${url}:${mapping.course_id}`;
  return (
    <PublicationReview
      key={`${attemptKey}:${mapping.actif}:${canPublish}`}
      mapping={mapping}
      url={url}
      state={attempts.get(attemptKey) || initialState}
      updateAttempt={updateAttempt}
      attemptKey={attemptKey}
      canPublish={canPublish}
      onClose={onClose}
    />
  );
};

CoursePublicationDialog.propTypes = {
  mapping: mappingType,
  canPublish: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

CoursePublicationDialog.defaultProps = { mapping: null };

export default CoursePublicationDialog;
