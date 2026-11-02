import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Stack, Typography,
} from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi, postApi } from '../../services/api';
import { apiErrorMessage, resourceUrl } from '../../services/resources';

const LearnerImport = ({ variant, resource }) => {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [downloadError, setDownloadError] = useState('');
  const client = useQueryClient();
  const url = resourceUrl(variant, resource);
  const mutation = useMutation({
    mutationFn: (apply) => {
      const payload = new FormData();
      payload.append('file', file);
      payload.append('apply', String(apply));
      if (apply) { payload.append('digest', preview.digest); }
      return postApi(`${url}importer/`, payload);
    },
    onSuccess: (result) => {
      setPreview(result);
      if (result.applied) { client.invalidateQueries({ queryKey: ['resource', url] }); }
    },
  });
  const download = async () => {
    setDownloadError('');
    try {
      const blob = await fetchApi(`${url}modele-import/`, { responseType: 'blob' });
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = 'modele_apprenants.xlsx';
      link.click();
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      setDownloadError(apiErrorMessage(error));
    }
  };
  return (
    <Box sx={{ my: 3 }}>
      <Typography variant="h6">Importer des apprenants</Typography>
      <Typography sx={{ my: 1 }}>
        CSV UTF-8 ou XLSX, 1 000 lignes et 5 Mo maximum.
        Les dossiers identiques sont ignorés ; aucun dossier existant n’est écrasé.
      </Typography>
      <Stack direction="row" spacing={2} sx={{ my: 2 }}>
        <Button onClick={download}>Télécharger le modèle</Button>
        <Button component="label">
          Choisir un fichier
          <input
            type="file"
            aria-label="Fichier des apprenants"
            accept=".csv,.xlsx"
            hidden
            onChange={(event) => {
              setFile(event.target.files[0] || null);
              setPreview(null);
              mutation.reset();
            }}
          />
        </Button>
        <Button onClick={() => mutation.mutate(false)} disabled={!file || mutation.isPending}>Prévisualiser</Button>
      </Stack>
      {file && <Typography>{file.name}</Typography>}
      {(mutation.error || downloadError) && <Alert severity="error">{downloadError || apiErrorMessage(mutation.error)}</Alert>}
      {preview && (
        <Box>
          <Typography>
            {preview.total} lignes : {preview.to_create} à créer,
            {' '}{preview.skipped} déjà présentes, {preview.errors.length} erreurs.
          </Typography>
          {preview.errors.map(row => <Alert key={row.line} severity="error">Ligne {row.line} : {JSON.stringify(row.errors)}</Alert>)}
          {preview.applied
            ? <Alert severity="success">{preview.created} dossiers créés. Les comptes locaux doivent être activés via « Mot de passe oublié » ; les comptes Open edX nécessitent une association explicite.</Alert>
            : <Button variant="contained" onClick={() => mutation.mutate(true)} disabled={Boolean(preview.errors.length) || !preview.to_create || mutation.isPending}>Confirmer l’import</Button>}
        </Box>
      )}
    </Box>
  );
};
LearnerImport.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  resource: PropTypes.string.isRequired,
};
export default LearnerImport;
