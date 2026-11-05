import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteApi, fetchApi, postApi } from '../../services/api';
import { apiErrorMessage, resourceUrl } from '../../services/resources';
import { usesLocalSession } from '../../services/localSession';

const AccountPage = ({ variant }) => {
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [enrollment, setEnrollment] = useState(null);
  const [notice, setNotice] = useState('');
  const client = useQueryClient();
  const url = resourceUrl(variant, 'utilisateurs/comptes');
  const profile = useQuery({ queryKey: ['profile', url], queryFn: () => fetchApi(`${url}me/`) });
  const action = useMutation({
    mutationFn: ({ name, payload }) => postApi(`${url}${name}/`, payload),
    onSuccess: (result) => {
      setNotice(result.detail || 'Opération effectuée.');
      if (result.provisioning_uri) { setEnrollment(result); } else { setEnrollment(null); }
      setCode('');
      setPassword('');
      client.invalidateQueries({ queryKey: ['profile', url] });
    },
  });
  const logout = useMutation({
    mutationFn: () => deleteApi(resourceUrl(variant, 'auth/session')),
    onSuccess: () => {
      client.clear();
      window.location.reload();
    },
  });
  return (
    <Box className="sis-panel" sx={{ maxWidth: 640 }}>
      <Typography variant="h4" component="h1">Sécurité du compte</Typography>
      <Alert severity="info" sx={{ my: 2 }}>
        Le MFA configuré ici protège les connexions SIS locales.
        Pour Open edX, configurez également le MFA de votre fournisseur d’identité.
      </Alert>
      {(profile.error || action.error || logout.error) && <Alert severity="error">{apiErrorMessage(profile.error || action.error || logout.error)}</Alert>}
      {notice && <Alert severity="success">{notice}</Alert>}
      <Typography sx={{ my: 2 }}>{profile.data?.full_name || profile.data?.username}</Typography>
      <Stack spacing={2}>
        <Typography>MFA local : {profile.data?.mfa_active ? 'activé' : 'désactivé'}</Typography>
        {!profile.data?.mfa_active && (
          <Button disabled={action.isPending} onClick={() => action.mutate({ name: 'mfa_enroll', payload: {} })}>Configurer le MFA</Button>
        )}
        {enrollment && (
          <Alert severity="warning">
            Ajoutez cette clé dans votre application d’authentification, puis confirmez avec un code.
            Ne partagez pas cette clé.
            <Typography component="code" display="block">{enrollment.secret}</Typography>
          </Alert>
        )}
        {(enrollment || profile.data?.mfa_active) && (
          <TextField label="Code MFA" autoComplete="one-time-code" value={code} onChange={event => setCode(event.target.value)} />
        )}
        {enrollment && (
          <Button variant="contained" disabled={action.isPending || !code} onClick={() => action.mutate({ name: 'mfa_activate', payload: { code } })}>Activer le MFA</Button>
        )}
        {profile.data?.mfa_active && (
          <>
            <TextField
              label="Mot de passe local"
              type="password"
              value={password}
              onChange={event => setPassword(event.target.value)}
            />
            <Button disabled={action.isPending || !code || !password} onClick={() => action.mutate({ name: 'mfa_disable', payload: { code, password } })}>Désactiver le MFA local</Button>
          </>
        )}
        {usesLocalSession() && (
          <Button onClick={() => logout.mutate()} disabled={logout.isPending}>Se déconnecter</Button>
        )}
      </Stack>
    </Box>
  );
};

AccountPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default AccountPage;
