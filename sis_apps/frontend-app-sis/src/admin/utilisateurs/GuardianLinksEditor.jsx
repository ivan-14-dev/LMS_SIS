import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteApi, patchApi, postApi } from '../../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../../services/resources';
import ResourceManager from '../../components/common/ResourceManager';

const GuardianLinksEditor = ({ capabilities }) => {
  const can = permission => capabilities?.permissions?.includes('*')
    || capabilities?.permissions?.includes(permission);
  const canView = can('eleves.view_elevetuteur');
  const canAdd = can('eleves.add_elevetuteur') && can('eleves.view_tuteur') && can('eleves.view_eleve');
  const url = resourceUrl('secondaire', 'utilisateurs/liens-parent');
  const client = useQueryClient();
  const [guardianId, setGuardianId] = useState('');
  const [childId, setChildId] = useState('');
  const [authorized, setAuthorized] = useState(false);
  const [removing, setRemoving] = useState(null);
  const [notice, setNotice] = useState('');
  const links = useQuery({
    queryKey: ['family-links', url],
    queryFn: () => fetchAllResourcePages(url),
    enabled: canView,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
    retry: false,
  });
  const guardians = useQuery({
    queryKey: ['family-guardians'],
    queryFn: () => fetchAllResourcePages(resourceUrl('secondaire', 'utilisateurs/parents')),
    enabled: canAdd,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });
  const children = useQuery({
    queryKey: ['family-pupils'],
    queryFn: () => fetchAllResourcePages(resourceUrl('secondaire', 'eleves')),
    enabled: canAdd,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });
  const mutation = useMutation({
    mutationFn: ({ operation, id, data }) => {
      if (operation === 'delete') { return deleteApi(`${url}${id}/`); }
      if (id) { return patchApi(`${url}${id}/`, data); }
      return postApi(url, data);
    },
    onSuccess: async () => {
      setRemoving(null);
      setGuardianId('');
      setChildId('');
      setAuthorized(false);
      await client.invalidateQueries({ queryKey: ['family-links', url] });
      await client.invalidateQueries({ queryKey: ['secondaire-portail-apprenant-parent-dashboard'] });
      await client.invalidateQueries({ queryKey: ['family-child-record'] });
      setNotice('Liaison enregistrée. Les accès sont réévalués côté serveur à chaque consultation.');
    },
  });
  const submit = (payload) => {
    setNotice('');
    mutation.mutate(payload);
  };
  const referencesError = guardians.error || children.error;
  const busy = mutation.isPending || links.isFetching;

  return (
    <Stack spacing={3}>
      <Alert severity="info">
        Un profil parent ne donne accès à aucun enfant sans liaison autorisée.
        Révoquer conserve la liaison ; retirer la supprime. Aucun accès enseignant ou administrateur n’est ajouté.
      </Alert>
      {can('eleves.view_tuteur') && (
        <ResourceManager
          variant="secondaire"
          resource="utilisateurs/parents"
          title="Profils parents"
          allowCreate={can('eleves.add_tuteur') && can('utilisateurs.view_utilisateur')}
          allowEdit={can('eleves.change_tuteur')}
          onSaved={() => client.invalidateQueries({ queryKey: ['family-guardians'] })}
          columns={[
            { Header: 'Nom', accessor: 'nom' },
            { Header: 'Prénom', accessor: 'prenom' },
            { Header: 'Compte', accessor: 'compte' },
          ]}
          fields={[
            {
              name: 'user',
              label: 'Compte parent',
              resource: 'utilisateurs/comptes',
              filters: { role: 'parent', is_active: true },
              labelField: 'username',
              required: true,
              createOnly: true,
            },
            { name: 'nom', label: 'Nom', required: true },
            { name: 'prenom', label: 'Prénom', required: true },
            {
              name: 'lien_parente',
              label: 'Lien de parenté',
              required: true,
              choices: [
                { value: 'pere', label: 'Père' }, { value: 'mere', label: 'Mère' },
                { value: 'tuteur_legal', label: 'Tuteur légal' },
                { value: 'grand_parent', label: 'Grand-parent' }, { value: 'autre', label: 'Autre' },
              ],
            },
            { name: 'telephone', label: 'Téléphone', required: true },
            {
              name: 'email', label: 'Email', type: 'email', required: true,
            },
          ]}
        />
      )}
      {!canView ? <Alert severity="warning">Permission de consultation des liaisons requise.</Alert> : (
        <Box component="section" aria-label="Liaisons parent-enfant">
          <Typography component="h2" variant="h6">Liaisons parent-enfant</Typography>
          {notice && <Alert severity="success">{notice}</Alert>}
          {mutation.error && <Alert severity="error">{apiErrorMessage(mutation.error)}</Alert>}
          <Button onClick={() => links.refetch()} disabled={busy}>Actualiser les liaisons</Button>
          {(links.isFetching || links.isPending) && <Typography role="status">Vérification des liaisons…</Typography>}
          {!links.isFetching && !links.isPending && links.error && (
            <Alert severity="error">{apiErrorMessage(links.error)}</Alert>
          )}
          {!links.isFetching && !links.isPending && !links.error && (
          <Stack spacing={1}>
            {(links.data || []).map(link => (
              <Box key={link.id}>
                <Typography>{link.tuteur_nom} → {link.eleve_nom} · {link.autorise_acces_portail ? 'Accès autorisé' : 'Accès révoqué'}</Typography>
                {can('eleves.change_elevetuteur') && (
                <Button
                  disabled={busy}
                  onClick={() => submit({
                    id: link.id, data: { autorise_acces_portail: !link.autorise_acces_portail },
                  })}
                >
                  {link.autorise_acces_portail ? 'Révoquer' : 'Autoriser'} l’accès
                </Button>
                )}
                {can('eleves.delete_elevetuteur') && (
                <Button disabled={busy} onClick={() => setRemoving(link)}>Retirer la liaison</Button>
                )}
              </Box>
            ))}
            {links.data?.length === 0 && <Typography>Aucune liaison.</Typography>}
          </Stack>
          )}
          {canAdd && (
            <Box
              component="form"
              onSubmit={(event) => {
                event.preventDefault();
                submit({
                  data: { tuteur: Number(guardianId), eleve: Number(childId), autorise_acces_portail: authorized },
                });
              }}
              sx={{ mt: 2 }}
            >
              <Typography component="h3" variant="subtitle1">Lier un parent à un enfant</Typography>
              {referencesError && <Alert severity="error">{apiErrorMessage(referencesError)}</Alert>}
              <Stack spacing={2}>
                <TextField select label="Parent" value={guardianId} required onChange={event => setGuardianId(event.target.value)}>
                  {(guardians.data || []).map(item => (
                    <MenuItem key={item.id} value={item.id}>{item.prenom} {item.nom} ({item.compte})</MenuItem>
                  ))}
                </TextField>
                <TextField select label="Enfant" value={childId} required onChange={event => setChildId(event.target.value)}>
                  {(children.data || []).map(item => (
                    <MenuItem key={item.id} value={item.id}>
                      {item.full_name || item.nom_complet || item.matricule}
                    </MenuItem>
                  ))}
                </TextField>
                <FormControlLabel
                  label="Autoriser l’accès au portail"
                  control={<Checkbox checked={authorized} onChange={event => setAuthorized(event.target.checked)} />}
                />
                <Button type="submit" disabled={busy || Boolean(referencesError) || !guardianId || !childId}>Créer la liaison</Button>
              </Stack>
            </Box>
          )}
        </Box>
      )}
      <Dialog open={Boolean(removing)} onClose={() => !busy && setRemoving(null)}>
        <DialogTitle>Retirer la liaison parent-enfant ?</DialogTitle>
        <DialogContent>
          Les prochaines consultations du dossier et des bulletins seront refusées pour ce parent.
        </DialogContent>
        <DialogActions>
          <Button disabled={busy} onClick={() => setRemoving(null)}>Annuler</Button>
          <Button disabled={busy} onClick={() => submit({ operation: 'delete', id: removing.id })}>Confirmer le retrait</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
};

GuardianLinksEditor.propTypes = {
  capabilities: PropTypes.shape({ permissions: PropTypes.arrayOf(PropTypes.string) }).isRequired,
};

export default GuardianLinksEditor;
