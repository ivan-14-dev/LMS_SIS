import React from 'react';
import PropTypes from 'prop-types';
import { Stack, Typography } from '@mui/material';
import {
  choiceLabel, choiceType, eventDateLabel, eventType, roomLabel,
} from './eventUi';

const EventSummary = ({ event, types, statuses }) => (
  <Stack spacing={1}>
    <Typography variant="h6" component="h2">{event.titre}</Typography>
    <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{event.description}</Typography>
    <Typography>{choiceLabel(types, event.type)} · {choiceLabel(statuses, event.statut)} · version {event.version}</Typography>
    <Typography>Du {eventDateLabel(event.debut)} au {eventDateLabel(event.fin)}</Typography>
    <Typography>Salle : {roomLabel(event.salle)}</Typography>
    <Typography>Effectif total : {event.effectif}</Typography>
    {event.can_manage && (
      <>
        <Typography>Invitations actives : {event.participants.length}</Typography>
        {event.participants.map(person => <Typography key={person.id}>{person.nom}</Typography>)}
      </>
    )}
    {!event.can_manage && <Typography>Événement accessible dans le périmètre de votre invitation active.</Typography>}
  </Stack>
);
EventSummary.propTypes = {
  event: eventType.isRequired, types: PropTypes.arrayOf(choiceType).isRequired,
  statuses: PropTypes.arrayOf(choiceType).isRequired,
};
export default EventSummary;
