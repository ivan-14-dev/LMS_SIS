import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useLocation } from 'react-router-dom';
import {
  Alert, Box, Button, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, postApi } from '../../services/api';
import { apiErrorMessage, getEnabledVariants, resourceUrl } from '../../services/resources';
import { usesLocalSession } from '../../services/localSession';

const LocalSessionGate = ({ variant, children }) => {
  const location = useLocation();
  const [credentials, setCredentials] = useState({ username: '', password: '', code: '' });
  const client = useQueryClient();
  const url = resourceUrl(variant, 'auth/session');
  const enabled = getEnabledVariants();
  const selected = new URLSearchParams(location.search).get('sis');
  const administrationVariant = enabled.includes(selected) ? selected : enabled[0];
  const recoveryVariant = variant === 'admin' ? administrationVariant : variant;
  const status = useQuery({
    queryKey: ['local-session', url],
    queryFn: () => fetchApi(url),
    enabled: usesLocalSession(),
    retry: false,
  });
  const login = useMutation({
    mutationFn: () => postApi(url, credentials),
    onSuccess: () => {
      setCredentials({ username: '', password: '', code: '' });
      client.clear();
      window.location.reload();
    },
  });
  if (!usesLocalSession()) { return children; }
  if (status.isLoading) { return <Typography>Vérification de la session…</Typography>; }
  if (status.data?.authenticated) { return children; }
  return (
    <div className="sis-auth-layout">
      <section className="sis-auth-intro" aria-label="Votre espace éducatif">
        <strong>LMS SIS</strong>
        <h2>Votre établissement, un seul espace.</h2>
        <p>Retrouvez votre dossier, vos résultats, vos documents et les démarches accessibles à votre profil.</p>
      </section>
      <Box
        component="form"
        className="sis-panel sis-auth-form"
        onSubmit={(event) => {
          event.preventDefault();
          login.mutate();
        }}
      >
        <Typography variant="h4" component="h1">Connexion SIS</Typography>
        <Typography sx={{ my: 2 }}>Compte local — distinct du compte Open edX.</Typography>
        {(login.error || status.error) && <Alert severity="error">{apiErrorMessage(login.error || status.error)}</Alert>}
        <Stack spacing={2} sx={{ my: 2 }}>
          <TextField label="Identifiant" autoComplete="username" required value={credentials.username} onChange={event => setCredentials({ ...credentials, username: event.target.value })} />
          <TextField label="Mot de passe" autoComplete="current-password" type="password" required value={credentials.password} onChange={event => setCredentials({ ...credentials, password: event.target.value })} />
          <TextField label="Code MFA (si activé)" autoComplete="one-time-code" value={credentials.code} onChange={event => setCredentials({ ...credentials, code: event.target.value })} />
          <Button variant="contained" type="submit" disabled={login.isPending}>Se connecter</Button>
          <Button href={`/forgot-password/?sis=${recoveryVariant}`}>Mot de passe oublié</Button>
        </Stack>
      </Box>
    </div>
  );
};

LocalSessionGate.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur', 'admin']).isRequired,
  children: PropTypes.node.isRequired,
};

export default LocalSessionGate;
