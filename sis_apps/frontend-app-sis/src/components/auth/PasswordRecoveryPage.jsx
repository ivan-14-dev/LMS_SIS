import React, { useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { apiErrorMessage, getEnabledVariants, resourceUrl } from '../../services/resources';
import { localHttpClient } from '../../services/localSession';

const PasswordRecoveryPage = () => {
  const { uid, token } = useParams();
  const [params] = useSearchParams();
  const variants = getEnabledVariants();
  const [variant, setVariant] = useState(variants.includes(params.get('sis')) ? params.get('sis') : variants[0]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const mutation = useMutation({
    mutationFn: () => localHttpClient.post(
      resourceUrl(variant, `auth/password-reset/${token ? 'confirm' : 'request'}`),
      token ? { uid, token, new_password: password } : { email },
    ),
    onSuccess: () => setPassword(''),
  });
  return (
    <Box
      component="form"
      className="sis-panel sis-auth-form"
      sx={{ maxWidth: 460, mx: 'auto', my: 5 }}
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <Typography variant="h4" component="h1">Mot de passe SIS local</Typography>
      <Alert severity="info" sx={{ my: 2 }}>Ce formulaire ne modifie pas votre mot de passe Open edX.</Alert>
      {mutation.error && <Alert severity="error">{apiErrorMessage(mutation.error)}</Alert>}
      {mutation.isSuccess && <Alert severity="success">{mutation.data.data.detail}</Alert>}
      <Stack spacing={2}>
        {variants.length > 1 && (
          <TextField select label="SIS" value={variant} onChange={event => setVariant(event.target.value)}>
            {variants.map(value => <MenuItem value={value} key={value}>{value}</MenuItem>)}
          </TextField>
        )}
        {token
          ? <TextField label="Nouveau mot de passe" type="password" autoComplete="new-password" required value={password} onChange={event => setPassword(event.target.value)} />
          : <TextField label="Email" type="email" required value={email} onChange={event => setEmail(event.target.value)} />}
        <Button type="submit" variant="contained" disabled={mutation.isPending}>{token ? 'Modifier le mot de passe' : 'Envoyer le lien'}</Button>
        <Button href={`/${variant}`}>Retour à la connexion</Button>
      </Stack>
    </Box>
  );
};

export default PasswordRecoveryPage;
