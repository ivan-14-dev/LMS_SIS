import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField,
} from '@mui/material';
import { fetchApi, normalizePageResponse } from '../../services/api';
import { resourceUrl } from '../../services/resources';
import { libraryQueryOptions } from './libraryUi';

const LibraryLoanDialog = ({
  variant, livre, title, reservation, busy, onClose, onError, onSubmit,
}) => {
  const base = resourceUrl(variant, 'bibliotheque');
  const [copy, setCopy] = useState('');
  const [date, setDate] = useState('');
  const copies = useQuery({
    ...libraryQueryOptions,
    queryKey: ['library', base, 'copies', livre],
    queryFn: async ({ signal }) => normalizePageResponse(await fetchApi(`${base}livres/${livre}/exemplaires/`, { signal })),
  });
  useEffect(() => { if (copies.error) { onError(copies.error); } }, [copies.error, onError]);
  const available = copies.data?.results.filter(item => (reservation
    ? !['perdu', 'détérioré', 'deteriore'].includes(item.etat)
    : item.disponible === true)) || [];
  const dateRequired = Boolean(reservation && variant === 'secondaire');
  const ready = !copies.isFetching && !copies.error && available.some(item => String(item.id) === copy);
  return (
    <Dialog open onClose={() => !busy && onClose()} fullWidth>
      <Box
        component="form"
        onSubmit={event => {
          event.preventDefault();
          if (busy || !ready || (dateRequired && !date)) { return; }
          onSubmit({ exemplaire: Number(copy), ...(dateRequired ? { date_retour_prevue: date } : {}) });
        }}
      >
        <DialogTitle>{reservation ? 'Remettre un exemplaire' : 'Emprunter un exemplaire'} — {title}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Alert severity="info">
              {reservation ? 'Le serveur vérifie la priorité de la réservation et la disponibilité réelle de l’exemplaire.'
                : 'Cet emprunt sera enregistré à votre nom. Le serveur applique la durée prévue et vérifie les réservations prioritaires.'}
            </Alert>
            {copies.isFetching ? <Alert severity="info">Chargement des exemplaires…</Alert> : (
              <TextField
                label="Exemplaire"
                select
                required
                value={copy}
                disabled={busy || Boolean(copies.error)}
                onChange={event => setCopy(String(event.target.value))}
                helperText={!available.length ? 'Aucun exemplaire disponible. Vous pouvez demander une réservation depuis le catalogue.' : undefined}
              >
                {available.map(item => <MenuItem key={item.id} value={String(item.id)}>{item.code_barre}</MenuItem>)}
              </TextField>
            )}
            {dateRequired && (
              <TextField
                label="Date de retour prévue"
                type="date"
                required={dateRequired}
                value={date}
                disabled={busy}
                onChange={event => setDate(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                helperText="Date future obligatoire."
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button disabled={busy} onClick={onClose}>Annuler</Button>
          <Button type="submit" variant="contained" disabled={busy || !ready || (dateRequired && !date)}>
            {reservation ? 'Confirmer la remise' : 'Confirmer mon emprunt'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};
LibraryLoanDialog.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  livre: PropTypes.number.isRequired,
  title: PropTypes.string.isRequired,
  reservation: PropTypes.shape({ id: PropTypes.number.isRequired }),
  busy: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onError: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};
LibraryLoanDialog.defaultProps = { reservation: null };
export default LibraryLoanDialog;
