import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Box, Button, Chip, Stack, TextField, Typography,
} from '@mui/material';
import { apiErrorMessage, fetchResourcePage } from '../services/resources';
import {
  accountType, isDenied, queryOptions, roomLabel, roomType,
} from './eventUi';

const EventSelectors = ({
  url, scope, eventId, room, participants, onRoom, onParticipants, onDenied, onReady, disabled,
}) => {
  const [roomPage, setRoomPage] = useState(1);
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const rooms = useQuery({
    ...queryOptions,
    queryKey: ['events', scope, 'rooms', eventId, roomPage],
    queryFn: ({ signal }) => fetchResourcePage(`${url}salles/`, { evenement_id: eventId, page: roomPage }, { signal }),
  });
  const candidates = useQuery({
    ...queryOptions,
    queryKey: ['events', scope, 'participants', eventId, query, page],
    queryFn: ({ signal }) => fetchResourcePage(`${url}participants/`, {
      evenement_id: eventId, q: query, page,
    }, { signal }),
    enabled: query.length >= 2 && query.length <= 100,
  });
  const error = rooms.error || candidates.error;
  const ready = Boolean(rooms.data) && !error && !rooms.isFetching && !candidates.isFetching;
  useEffect(() => { if (isDenied(error)) { onDenied(error); } }, [error, onDenied]);
  useEffect(() => { onReady(ready); }, [ready, onReady]);
  const available = rooms.data?.results || [];
  const options = room && !available.some(item => item.id === room.id) ? [room, ...available] : available;
  return (
    <Stack spacing={2}>
      <Typography variant="h6" component="h3">Salle existante et invitations</Typography>
      <Alert severity="info">
        Choisir une salle ne garantit pas sa disponibilité. Le serveur vérifie les conflits et la capacité lors de l’enregistrement.
        Les invitations et changements d’horaire utilisent uniquement les notifications internes.
        Une invitation ne donne pas le droit de consultation : une habilitation explicite reste nécessaire.
      </Alert>
      {error && <Alert severity="error">{apiErrorMessage(error)}</Alert>}
      <TextField
          select
          label="Salle existante"
          required
          disabled={disabled || rooms.isFetching || Boolean(rooms.error)}
          value={room?.id || ''}
          onChange={event => onRoom(options.find(item => item.id === Number(event.target.value)) || null)}
          slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}
      >
        <option value="">Choisir une salle</option>
        {options.map(item => <option key={item.id} value={item.id}>{roomLabel(item)}</option>)}
      </TextField>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
        <Button disabled={disabled || rooms.isFetching || roomPage === 1} onClick={() => setRoomPage(value => value - 1)}>Salles précédentes</Button>
        <Typography aria-live="polite">Salles : page {roomPage} · {rooms.data?.count || 0} résultats</Typography>
        <Button disabled={disabled || rooms.isFetching || !rooms.data?.next} onClick={() => setRoomPage(value => value + 1)}>Salles suivantes</Button>
        {rooms.error && <Button disabled={disabled} onClick={() => rooms.refetch()}>Recharger les salles</Button>}
      </Stack>
      <Typography>Participants invités : {participants.length}/200. Retirer un participant révoque son invitation à l’enregistrement.</Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {participants.map(person => (
          <Stack key={person.id} direction="row" spacing={1} alignItems="center">
            <Chip label={person.nom} />
            <Button
                disabled={disabled}
                aria-label={`Retirer ${person.nom}`}
                onClick={() => onParticipants(participants.filter(item => item.id !== person.id))}
            >Retirer
            </Button>
          </Stack>
        ))}
      </Box>
      <TextField
          label="Rechercher un participant"
          value={search}
          disabled={disabled}
          onChange={event => {
            setSearch(event.target.value);
            setQuery('');
            setPage(1);
          }}
          helperText="Nom, prénom ou identifiant : 2 à 100 caractères. Aucun droit de gestion des comptes requis."
          slotProps={{ htmlInput: { maxLength: 100 } }}
      />
      <Button
          disabled={disabled || search.trim().length < 2 || search.trim().length > 100}
          onClick={() => { setQuery(search.trim()); setPage(1); }}
      >Rechercher des participants
      </Button>
      {candidates.isFetching && <Typography role="status">Recherche des participants…</Typography>}
      {!candidates.isFetching && !candidates.error && query && (
        <Stack spacing={1}>
          {(candidates.data?.results || []).map(person => (
            <Button
                key={person.id}
                disabled={disabled || participants.length >= 200 || participants.some(item => item.id === person.id)}
                onClick={() => onParticipants([...participants, person])}
            >Ajouter {person.nom}
            </Button>
          ))}
          {candidates.data?.count === 0 && <Typography>Aucun participant trouvé.</Typography>}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <Button disabled={disabled || page === 1} onClick={() => setPage(value => value - 1)}>Participants précédents</Button>
            <Typography aria-live="polite">Participants : page {page} · {candidates.data?.count || 0} résultats</Typography>
            <Button disabled={disabled || !candidates.data?.next} onClick={() => setPage(value => value + 1)}>Participants suivants</Button>
          </Stack>
        </Stack>
      )}
      {candidates.error && <Button disabled={disabled} onClick={() => candidates.refetch()}>Réessayer la recherche</Button>}
    </Stack>
  );
};
EventSelectors.propTypes = {
  url: PropTypes.string.isRequired, scope: PropTypes.string.isRequired, eventId: PropTypes.string,
  room: roomType, participants: PropTypes.arrayOf(accountType).isRequired,
  onRoom: PropTypes.func.isRequired, onParticipants: PropTypes.func.isRequired,
  onDenied: PropTypes.func.isRequired, onReady: PropTypes.func.isRequired, disabled: PropTypes.bool,
};
export default EventSelectors;
