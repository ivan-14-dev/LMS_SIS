import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Checkbox, FormControlLabel, Stack, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, putApi } from '../../services/api';
import { apiErrorMessage, getEnabledVariants, resourceUrl } from '../../services/resources';
import { accountsLinked, institutionsLinked, otherVariant } from '../../services/institutionWorkspace';

const InstitutionWorkspaceEditor = ({ variant, administration = false }) => {
  const client = useQueryClient();
  const other = otherVariant(variant);
  const [discovered, setDiscovered] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [identityConfirmed, setIdentityConfirmed] = useState(false);
  const url = source => resourceUrl(source, 'etablissement/current/workspace');
  const current = useQuery({ queryKey: ['institution-workspace', variant], queryFn: () => fetchApi(url(variant)) });
  const peer = useQuery({
    queryKey: ['institution-workspace', other],
    queryFn: () => fetchApi(url(other)),
    enabled: discovered && getEnabledVariants().includes(other),
    retry: false,
  });
  useEffect(() => {
    setConfirmed(false);
    setIdentityConfirmed(false);
  }, [current.data?.id, current.data?.user, peer.data?.id, peer.data?.user]);
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ['institution-workspace'] });
    await client.invalidateQueries({ queryKey: ['capabilities'] });
  };
  const declare = (source, workspace, target, home) => putApi(url(source), {
    version: workspace.version, peer: target, home,
  });
  const institution = useMutation({
    mutationFn: async () => {
      await declare(variant, current.data, peer.data.id, current.data.id);
      await declare(other, peer.data, current.data.id, current.data.id);
    },
    onSettled: refresh,
  });
  const detach = useMutation({
    mutationFn: () => declare(variant, current.data, null, null),
    onSettled: refresh,
  });
  const account = useMutation({
    mutationFn: async (remove) => {
      await putApi(resourceUrl(variant, 'utilisateurs/comptes/workspace-link'), {
        peer: remove ? null : peer.data.id, user: remove ? null : peer.data.user,
      });
      if (!remove) {
        await putApi(resourceUrl(other, 'utilisateurs/comptes/workspace-link'), {
          peer: current.data.id, user: current.data.user,
        });
      }
    },
    onSettled: refresh,
  });
  if (!getEnabledVariants().includes(other)) {
    return <Alert severity="info">Le second moteur doit être installé en mode dual pour réunir ses fonctionnalités.</Alert>;
  }
  const busy = institution.isPending || detach.isPending || account.isPending || current.isFetching || peer.isFetching;
  const linked = !current.isError && !peer.isError && institutionsLinked(current.data, peer.data);
  const joined = linked && accountsLinked(current.data, peer.data);
  const error = current.error || institution.error || detach.error || account.error;
  return (
    <Stack spacing={2} sx={{ my: 3 }}>
      <Typography component="h2" variant="h6">Espace institutionnel commun</Typography>
      <Alert severity="info">
        Réunissez les fonctions dans un seul menu, sans déplacer ni fusionner les dossiers.
        Le siège choisit le type d’établissement dans Identité : secondaire, supérieur ou mixte.
        Les autorisations restent vérifiées séparément par chaque service.
      </Alert>
      {current.data && <Typography>Espace courant : {current.data.name} — compte : {current.data.account}</Typography>}
      {error && <Alert severity="error">{apiErrorMessage(error)} Rechargez avant de réessayer ; une confirmation partielle ne suffit pas.</Alert>}
      <Button onClick={() => { setDiscovered(true); peer.refetch(); current.refetch(); }} disabled={busy}>
        Vérifier le second espace
      </Button>
      <Button component="a" href={`/${other}/compte`} target="_blank" rel="noopener noreferrer">
        Connecter mon compte dans l’autre espace
      </Button>
      {discovered && peer.isError && <Alert severity="warning">Le second espace est inaccessible. Connectez-vous dans l’autre onglet, puis vérifiez à nouveau.</Alert>}
      {discovered && !current.isError && !peer.isError && peer.data && (
        <>
          <Typography>Second espace : {peer.data.name} — compte : {peer.data.account}</Typography>
          {administration && linked && current.data.home !== current.data.id && (
            <Alert severity="info">
              Le type de l’établissement commun se règle au siège, dans l’autre espace.
            </Alert>
          )}
          {administration && (
            <Button component="a" href={`/admin/etablissement?sis=${other}`}>
              Paramètres métier de l’autre espace
            </Button>
          )}
          {administration && current.data?.can_configure && peer.data.can_configure && !linked && (
            <>
              <FormControlLabel
                label={'Je confirme que ces deux espaces appartiennent au même établissement ; '
                  + 'cet espace sera le siège.'}
                control={<Checkbox checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />}
              />
              <Button variant="contained" disabled={busy || !confirmed} onClick={() => institution.mutate()}>
                Réunir les fonctions de ces deux espaces
              </Button>
            </>
          )}
          {linked ? <Alert severity="success">Rattachement institutionnel confirmé des deux côtés.</Alert>
            : <Alert severity="warning">Les administrateurs doivent confirmer le rattachement dans les deux espaces.</Alert>}
          {linked && !joined && (
            <>
              <FormControlLabel
                label="Je confirme que les deux comptes affichés sont les miens et souhaite réunir mes accès."
                control={(
                  <Checkbox
                    checked={identityConfirmed}
                    onChange={event => setIdentityConfirmed(event.target.checked)}
                  />
                )}
              />
              <Button variant="contained" disabled={busy || !identityConfirmed} onClick={() => account.mutate(false)}>
                Réunir mes accès autorisés
              </Button>
            </>
          )}
          {joined && <Alert severity="success">Navigation commune activée pour vos deux comptes.</Alert>}
        </>
      )}
      {current.data?.account_link && (
        <Button disabled={busy} onClick={() => account.mutate(true)}>Dissocier mes accès</Button>
      )}
      {administration && current.data?.can_configure && current.data.peer && (
        <Button color="warning" disabled={busy} onClick={() => detach.mutate()}>Détacher cet espace institutionnel</Button>
      )}
    </Stack>
  );
};
InstitutionWorkspaceEditor.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  administration: PropTypes.bool,
};
export default InstitutionWorkspaceEditor;
