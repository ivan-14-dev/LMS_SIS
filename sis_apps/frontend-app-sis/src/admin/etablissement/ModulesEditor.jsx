import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Checkbox, Chip, FormControlLabel, Paper, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, patchApi, postApi } from '../../services/api';
import { apiErrorMessage } from '../../services/resources';

const ModulesEditor = ({ endpoint }) => {
  const url = `${endpoint}modules/`;
  const client = useQueryClient();
  const queryKey = ['tenant-modules', url];
  const query = useQuery({ queryKey, queryFn: () => fetchApi(url) });
  const [enabled, setEnabled] = useState({});
  const [reason, setReason] = useState('');
  const preview = useMutation({ mutationFn: payload => postApi(url, payload) });
  const save = useMutation({
    mutationFn: payload => patchApi(url, payload),
    onSuccess: (data) => {
      client.setQueryData(queryKey, data);
      client.invalidateQueries({ queryKey: ['capabilities'] });
      client.invalidateQueries({ queryKey: ['workflow-events'] });
      preview.reset();
      setReason('');
    },
  });
  useEffect(() => {
    if (query.data) {
      setEnabled(query.data.enabled);
      preview.reset();
    }
    // A refreshed catalogue invalidates the previously reviewed activation proposal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data]);
  const resetFeedback = () => { preview.reset(); save.reset(); };
  if (query.isPending) { return <p role="status">Chargement des modules installés…</p>; }
  if (query.isError) {
    return (
      <Alert severity="error">
        {apiErrorMessage(query.error)}
        <Button type="button" onClick={() => query.refetch()}>Recharger les modules</Button>
      </Alert>
    );
  }
  const busy = save.isPending || preview.isPending;
  const dirty = Object.keys(enabled).some(key => enabled[key] !== query.data.enabled[key]);
  const payload = { revision: query.data.revision, enabled, reason };
  return (
    <Paper component="section" variant="outlined" sx={{ mt: 3, p: { xs: 2, sm: 3 } }} aria-label="Modules installés">
      <Typography component="h2" variant="h6" gutterBottom>Modules installés</Typography>
      <Typography sx={{ mb: 3 }}>
        Catalogue privé de cette version. Une désactivation bloque les accès au module,
        sans supprimer ses dossiers ni les notifications déjà engagées.
        Aucun code tiers ne peut être téléversé ici.
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' }, gap: 2 }}>
        {(query.data.modules || []).map(module => (
          <Paper component="article" variant="outlined" sx={{ p: 2, minWidth: 0, overflowWrap: 'anywhere' }} key={module.identifier}>
            <FormControlLabel
              label={module.label}
              control={(
                <Checkbox
                  checked={Boolean(enabled[module.identifier])}
                  disabled={module.required || busy}
                  onChange={(event) => {
                    setEnabled(current => ({ ...current, [module.identifier]: event.target.checked }));
                    resetFeedback();
                  }}
                />
              )}
            />
            <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap', mb: 2 }}>
              <Chip size="small" label="Installé" variant="outlined" />
              <Chip size="small" label={query.data.enabled[module.identifier] ? 'Actif' : 'Désactivé'} color={query.data.enabled[module.identifier] ? 'success' : 'default'} />
              {enabled[module.identifier] !== query.data.enabled[module.identifier] && <Chip size="small" label="Modification non publiée" variant="outlined" />}
            </Stack>
            <Typography sx={{ mb: 2 }}>{module.description}</Typography>
            <Typography variant="body2">
              {module.identifier} · v{module.version} · {module.required ? 'Obligatoire' : 'Activable'}
              {' · '}{module.origin === 'tenant' ? 'Choix de l’établissement' : 'Valeur par défaut'}
            </Typography>
            {module.publisher && <Typography variant="body2">Éditeur : {module.publisher}</Typography>}
            {module.variants && <Typography variant="body2">Compatible : {module.variants.join(', ')} · contrat {module.contract_version}</Typography>}
            {module.dependencies.length > 0 && <Typography variant="body2">Dépendances : {module.dependencies.map(id => query.data.modules.find(item => item.identifier === id)?.label || id).join(', ')}</Typography>}
            <Typography variant="body2">Permissions métier : {module.permissions?.join(', ') || 'Aucune permission supplémentaire déclarée'}. L’activation ne donne aucun droit à un compte.</Typography>
            {module.data_retention === 'preserve' && <Typography variant="body2">Dossiers conservés lors d’une désactivation.</Typography>}
          </Paper>
        ))}
      </Box>
      <TextField
        label="Motif du changement de modules"
        fullWidth
        sx={{ my: 3 }}
        value={reason}
        slotProps={{ htmlInput: { maxLength: 1000 } }}
        disabled={busy}
        onChange={(event) => { setReason(event.target.value); resetFeedback(); }}
      />
      {(preview.isError || save.isError) && (
      <Alert severity="error" sx={{ mb: 2 }}>
        {apiErrorMessage(save.error || preview.error)}
        <Button type="button" onClick={() => { resetFeedback(); query.refetch(); }}>Recharger les modules</Button>
      </Alert>
      )}
      {preview.isSuccess && (
      <Alert severity="info" sx={{ mb: 2 }}>
        Simulation validée : {Object.keys(preview.data.changes).length} modification(s).
        Aucun changement enregistré.
        {Object.entries(preview.data.changes).map(([id, change]) => {
          const module = query.data.modules.find(item => item.identifier === id);
          return (
            <Box key={id} sx={{ mt: 1 }}>
              <Typography>{module.label} : {change.after ? 'réactivation des accès selon les droits existants' : 'accès bloqués pour tous les comptes, y compris les administrateurs'}.</Typography>
              {module.ui?.length > 0 && <Typography>Entrées de navigation {change.after ? 'rétablies' : 'retirées'} : {module.ui.join(', ')}.</Typography>}
              {module.api?.length > 0 && <Typography>API {change.after ? 'rétablies' : 'bloquées'} : {module.api.join(', ')}.</Typography>}
              {module.data_retention === 'preserve' && <Typography>Dossiers et historique conservés. Les notifications déjà engagées continuent.</Typography>}
            </Box>
          );
        })}
      </Alert>
      )}
      {save.isSuccess && <Alert severity="success" sx={{ mb: 2 }}>Configuration des modules enregistrée.</Alert>}
      <Stack direction="row" useFlexGap sx={{ gap: 2, flexWrap: 'wrap' }}>
        <Button
          type="button"
          variant="outlined"
          disabled={!dirty || !reason.trim() || busy}
          onClick={() => preview.mutate(payload)}
        >Simuler les modules
        </Button>
        <Button
          type="button"
          variant="contained"
          disabled={!dirty || !reason.trim() || busy || !preview.isSuccess}
          onClick={() => save.mutate(payload)}
        >Appliquer les modules
        </Button>
      </Stack>
    </Paper>
  );
};

ModulesEditor.propTypes = { endpoint: PropTypes.string.isRequired };
export default ModulesEditor;
