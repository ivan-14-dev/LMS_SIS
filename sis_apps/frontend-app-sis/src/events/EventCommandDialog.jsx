import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, Stack, TextField, Typography,
} from '@mui/material';
import { apiErrorMessage } from '../services/resources';
import EventDates from './EventDates';
import EventSelectors from './EventSelectors';
import EventSummary from './EventSummary';
import {
  choiceType, dateFields, eventType, intervalPayload, isDenied,
} from './eventUi';

const titles = { create: 'Nouvel événement institutionnel', edit: 'Modifier l’événement', cancel: 'Annuler l’événement' };
const EventCommandDialog = ({
  url, scope, kind, event, types, statuses, onClose, onCommand, onReload, onDenied, onBusy, accessChecking,
}) => {
  const [values, setValues] = useState({
    titre: event?.titre || '', description: event?.description || '',
    type: event?.type || types[0]?.value || '', effectif: String(event?.effectif || 1),
  });
  const [start, setStart] = useState(() => dateFields(event?.debut || new Date()));
  const [end, setEnd] = useState(() => dateFields(event?.fin || new Date(Date.now() + 3600000)));
  const [room, setRoom] = useState(event?.salle || null);
  const [participants, setParticipants] = useState(event?.participants || []);
  const [selectorsReady, setSelectorsReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState(null);
  const [reviewed, setReviewed] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const sending = useRef(false);
  const mounted = useRef(true);
  const cancel = kind === 'cancel';
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const setPending = value => {
    sending.current = value;
    if (mounted.current) { setBusy(value); onBusy(value); }
  };
  const submit = async formEvent => {
    formEvent.preventDefault();
    if (sending.current || accessChecking || uncertain || (conflict && (!latest || !reviewed || latest.statut !== 'planifie'))) { return; }
    setError(null);
    let payload;
    try {
      const version = conflict ? latest.version : event?.version;
      if (cancel) {
        payload = { version };
      } else {
        const dates = intervalPayload(start, end, 7);
        // Preserve the exact saved instant (including fractional seconds) when a date was not edited.
        if (event && JSON.stringify(start) === JSON.stringify(dateFields(event.debut))) { dates.debut = event.debut; }
        if (event && JSON.stringify(end) === JSON.stringify(dateFields(event.fin))) { dates.fin = event.fin; }
        const duration = new Date(dates.fin) - new Date(dates.debut);
        if (duration <= 0 || duration > 7 * 86400000) { throw new Error('L’intervalle doit être positif et limité à 7 jours.'); }
        const effectif = Number(values.effectif);
        if (!values.titre.trim() || values.titre.trim().length > 200 || values.description.length > 5000) {
          throw new Error('Le titre est obligatoire (200 caractères maximum) et la description est limitée à 5 000 caractères.');
        }
        if (!room || !selectorsReady) { throw new Error('Sélectionnez une salle existante après chargement des sélecteurs.'); }
        if (!Number.isInteger(effectif) || effectif <= 0 || effectif < participants.length) {
          throw new Error('L’effectif total doit être positif et inclure tous les participants invités.');
        }
        if (effectif > room.capacite) { throw new Error('L’effectif dépasse la capacité de la salle sélectionnée.'); }
        payload = {
          titre: values.titre.trim(), description: values.description, type: values.type,
          salle: room.id, ...dates, effectif, participants: participants.map(person => person.id),
          ...(kind === 'edit' ? { version } : {}),
        };
      }
    } catch (validationError) {
      setError(validationError);
      return;
    }
    setPending(true);
    try {
      await onCommand(kind, event?.id, payload);
    } catch (commandError) {
      if (!mounted.current) { return; }
      if (isDenied(commandError)) { onDenied(commandError); return; }
      setError(commandError);
      if (commandError.response?.status === 409) {
        setConflict(true); setLatest(null); setReviewed(false);
      } else if (commandError.response?.status !== 400) {
        setUncertain(true);
      }
    } finally {
      setPending(false);
    }
  };
  const reload = async () => {
    if (sending.current) { return; }
    setPending(true);
    setReviewed(false);
    setLatest(null);
    try {
      const current = await onReload(event.id);
      if (!mounted.current) { return; }
      if (!current.can_manage) {
        onDenied(new Error('Votre habilitation de gestion a été retirée. Les données privées ont été purgées.'));
        return;
      }
      setLatest(current);
      setError(null);
    } catch (reloadError) {
      if (isDenied(reloadError)) { onDenied(reloadError); } else if (mounted.current) { setError(reloadError); }
    } finally {
      setPending(false);
    }
  };
  const field = (name, maxLength) => ({
    value: values[name], disabled: busy || uncertain || accessChecking,
    onChange: change => { setValues(previous => ({ ...previous, [name]: change.target.value })); setReviewed(false); },
    slotProps: { htmlInput: { maxLength } },
  });
  const locked = busy || uncertain || accessChecking;
  return (
    <Dialog open fullWidth maxWidth="md" onClose={busy ? undefined : onClose} aria-labelledby="event-command-title">
      <form onSubmit={submit}>
        <DialogTitle id="event-command-title">{titles[kind]}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2}>
            {error && <Alert severity="error">{apiErrorMessage(error)}</Alert>}
            {uncertain && (
              <Alert severity="error">
                Résultat non confirmé : aucune nouvelle commande ne sera envoyée depuis ce formulaire.
                Fermez-le puis rechargez l’agenda pour vérifier l’état enregistré avant toute nouvelle opération.
              </Alert>
            )}
            {conflict && (
              <Alert severity="warning">
                La version a changé ou l’événement est annulé. Votre brouillon est conservé, sans rejeu automatique.
                Relisez l’état serveur, comparez les horaires et la liste complète des invitations avant de confirmer.
                <Button disabled={busy} onClick={reload}>Relire la version serveur</Button>
              </Alert>
            )}
            {latest && (
              <Stack component="section" aria-label="Version serveur relue" spacing={2}>
                <Typography variant="h6" component="h2">État actuel du serveur</Typography>
                <EventSummary event={latest} types={types} statuses={statuses} />
                {latest.statut === 'annule' ? <Alert severity="warning">Cet événement est annulé définitivement. Aucune modification ni réactivation possible.</Alert> : (
                  <FormControlLabel
                      control={<Checkbox checked={reviewed} disabled={busy} onChange={change => setReviewed(change.target.checked)} />}
                      label={cancel
                        ? 'J’ai relu cette version et confirme son annulation définitive.'
                        : 'J’ai comparé cette version et confirme le remplacement par mon brouillon, y compris toute la liste des invitations.'}
                  />
                )}
              </Stack>
            )}
            {cancel ? (
              <>
                <Typography>Confirmez l’annulation définitive de « {event.titre} ». La salle sera libérée et les participants recevront une notification interne. L’historique est conservé.</Typography>
                {!latest && <EventSummary event={event} types={types} statuses={statuses} />}
              </>
            ) : (
              <>
                <TextField label="Titre" required {...field('titre', 200)} />
                <TextField label="Description" multiline minRows={2} {...field('description', 5000)} />
                <TextField
                    label="Type d’événement"
                    select
                    required
                    value={values.type}
                    disabled={locked}
                    onChange={change => { setValues(previous => ({ ...previous, type: change.target.value })); setReviewed(false); }}
                    slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}
                >
                  {types.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
                </TextField>
                <EventDates
                    start={start}
                    end={end}
                    onStart={value => { setStart(value); setReviewed(false); }}
                    onEnd={value => { setEnd(value); setReviewed(false); }}
                    disabled={locked}
                />
                <TextField label="Effectif total" type="number" required {...field('effectif')} helperText="Invités et personnes sans compte ; l’organisateur n’est pas ajouté automatiquement." />
                <EventSelectors
                    url={url}
                    scope={scope}
                    eventId={event?.id}
                    room={room}
                    participants={participants}
                    onRoom={value => { setRoom(value); setReviewed(false); }}
                    onParticipants={value => { setParticipants(value); setReviewed(false); }}
                    onReady={setSelectorsReady}
                    onDenied={onDenied}
                    disabled={locked}
                />
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ flexWrap: 'wrap' }}>
          <Button disabled={busy} onClick={onClose}>Fermer sans envoyer</Button>
          <Button
              type="submit"
              variant="contained"
              color={cancel ? 'error' : 'primary'}
              disabled={locked || (!cancel && !selectorsReady) || (conflict && (!latest || !reviewed || latest.statut !== 'planifie'))}
          >
            {cancel ? 'Confirmer l’annulation définitive' : 'Enregistrer l’événement'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};
EventCommandDialog.propTypes = {
  url: PropTypes.string.isRequired, scope: PropTypes.string.isRequired,
  kind: PropTypes.oneOf(['create', 'edit', 'cancel']).isRequired, event: eventType,
  types: PropTypes.arrayOf(choiceType).isRequired, statuses: PropTypes.arrayOf(choiceType).isRequired,
  onClose: PropTypes.func.isRequired, onCommand: PropTypes.func.isRequired,
  onReload: PropTypes.func.isRequired, onDenied: PropTypes.func.isRequired, onBusy: PropTypes.func.isRequired,
  accessChecking: PropTypes.bool,
};
export default EventCommandDialog;
