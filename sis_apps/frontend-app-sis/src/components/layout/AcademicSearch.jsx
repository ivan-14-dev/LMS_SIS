import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import {
  Alert, Box, Button, List, ListItemButton, ListItemText, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import {
  academicResultPath, academicSearchUrl, usePrivateResource, validSearchTerm,
} from '../../services/academicSearch';
import { apiErrorMessage } from '../../services/resources';
import CollectionPagination from '../common/CollectionPagination';

const AcademicSearch = ({ variant, resources, onNavigate }) => {
  const [resource, setResource] = useState(resources[0]?.value || '');
  const [term, setTerm] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [page, setPage] = useState(1);
  const valid = validSearchTerm(term);
  const url = submitted ? academicSearchUrl(variant, resource, submitted, page) : null;
  const request = usePrivateResource(url);
  const results = request.data?.results;
  const invalidResponse = request.data && (!Array.isArray(results) || !Number.isInteger(request.data.count));
  const clear = () => { setSubmitted(''); setPage(1); };
  if (!resources.length) { return <Alert severity="info">Aucune recherche de dossiers autorisée dans ce contexte.</Alert>; }
  return (
    <Box>
      <Box
        component="form"
        onSubmit={event => {
          event.preventDefault();
          if (valid) {
            if (submitted === term && page === 1) { request.retry(); } else {
              setSubmitted(term);
              setPage(1);
            }
          }
        }}
      >
        <Stack spacing={2}>
          <TextField select label="Type de dossier" value={resource} onChange={event => { clear(); setResource(event.target.value); }}>
            {resources.map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
          </TextField>
          <TextField
            autoFocus
            label="Rechercher un dossier"
            value={term}
            onChange={event => { clear(); setTerm(event.target.value); }}
            error={Boolean(term) && !valid}
            helperText="Entre 2 et 100 caractères, sans caractères de contrôle. Factures et documents : numéro ou référence."
          />
          <Button type="submit" disabled={!valid || request.loading}>Rechercher les dossiers</Button>
        </Stack>
      </Box>
      <Typography variant="body2" sx={{ mt: 2 }}>Résultats limités à votre établissement et à vos droits actuels.</Typography>
      {request.loading && <Typography role="status">Recherche en cours…</Typography>}
      {request.error && (
        <Alert severity="error" action={<Button onClick={request.retry}>Réessayer la recherche</Button>}>
          {request.error.response?.status === 403
            ? 'Accès refusé (403) : vos droits ne permettent plus cette recherche.'
            : `Impossible de rechercher les dossiers. ${apiErrorMessage(request.error)}`}
        </Alert>
      )}
      {invalidResponse && <Alert severity="error">Réponse de recherche invalide reçue du serveur.</Alert>}
      {!invalidResponse && results && (
        <>
          {!results.length && <Typography>Aucun dossier autorisé ne correspond.</Typography>}
          <List aria-label="Résultats de la recherche">
            {results.map(result => {
              const path = academicResultPath(variant, resource, result.id);
              return path && (
                <ListItemButton key={result.id} component={Link} to={path} onClick={onNavigate}>
                  <ListItemText primary={result.nom} secondary={result.code} />
                </ListItemButton>
              );
            })}
          </List>
          <CollectionPagination
            data={request.data}
            page={page}
            setPage={setPage}
            disabled={request.loading}
            label="Recherche de dossiers"
            previousLabel="Résultats précédents"
            nextLabel="Résultats suivants"
          />
        </>
      )}
    </Box>
  );
};
AcademicSearch.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  resources: PropTypes.arrayOf(PropTypes.shape({
    value: PropTypes.string.isRequired, label: PropTypes.string.isRequired,
  })).isRequired,
  onNavigate: PropTypes.func.isRequired,
};
export default AcademicSearch;
