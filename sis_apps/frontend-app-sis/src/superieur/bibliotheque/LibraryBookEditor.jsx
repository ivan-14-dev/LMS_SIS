import React, { useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, Stack, TextField,
} from '@mui/material';
import { patchApi } from '../../services/api';
import { bookType } from './libraryUi';

const LibraryBookEditor = ({
  book, url, busy, onBusy, onClose, onSaved, onError,
}) => {
  const [active, setActive] = useState(book.licence_active === true);
  const [reference, setReference] = useState(book.licence_reference || '');
  const [expiry, setExpiry] = useState(book.licence_expire_le || '');
  const [file, setFile] = useState(null);
  const sending = useRef(false);
  const submit = async event => {
    event.preventDefault();
    if (busy || sending.current || (active && !reference.trim())) { return; }
    sending.current = true;
    onBusy(true);
    const body = new FormData();
    body.append('licence_active', String(active));
    body.append('licence_reference', reference.trim());
    body.append('licence_expire_le', expiry);
    if (file) { body.append('ressource_numerique', file); }
    try {
      const result = await patchApi(url, body);
      if (result?.id !== book.id) { throw new Error('Réponse de mise à jour invalide. Rechargez la bibliothèque.'); }
      await onSaved();
      onClose();
    } catch (error) {
      onError(error);
    } finally {
      sending.current = false;
      onBusy(false);
    }
  };
  return (
    <Dialog open onClose={() => !busy && onClose()} fullWidth>
      <Box component="form" onSubmit={submit}>
        <DialogTitle>Fichier et licence — {book.titre}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Alert severity="info">
              Cette déclaration consigne votre autorisation de diffusion. Elle ne constitue ni une
              signature ni une validation juridique. Désactiver la licence bloque les prochains téléchargements.
            </Alert>
            <TextField
              label="Ressource numérique (PDF)"
              type="file"
              disabled={busy}
              onChange={event => setFile(event.target.files[0] || null)}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { accept: '.pdf,application/pdf' } }}
              helperText="Le nouveau PDF remplace le fichier conservé. Sans sélection, le fichier actuel est inchangé. Le serveur valide le PDF et sa taille (25 Mo par défaut)."
            />
            <FormControlLabel
              label="Licence de diffusion active"
              control={(
                <Checkbox checked={active} disabled={busy} onChange={event => setActive(event.target.checked)} />
              )}
            />
            <TextField
              label="Référence ou justificatif de licence"
              required={active}
              multiline
              value={reference}
              disabled={busy}
              onChange={event => setReference(event.target.value)}
              slotProps={{ htmlInput: { maxLength: 1000 } }}
              helperText="Obligatoire pour activer la diffusion ; 1 000 caractères maximum."
            />
            <TextField
              label="Expiration de licence (facultative)"
              type="date"
              value={expiry}
              disabled={busy}
              onChange={event => setExpiry(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button disabled={busy} onClick={onClose}>Annuler</Button>
          <Button type="submit" variant="contained" disabled={busy || (active && !reference.trim())}>Enregistrer le fichier et la licence</Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};
LibraryBookEditor.propTypes = {
  book: bookType.isRequired,
  url: PropTypes.string.isRequired,
  busy: PropTypes.bool.isRequired,
  onBusy: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
  onError: PropTypes.func.isRequired,
};
export default LibraryBookEditor;
