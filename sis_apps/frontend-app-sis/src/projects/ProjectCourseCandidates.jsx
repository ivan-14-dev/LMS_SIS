import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Autocomplete, Button, Stack, TextField,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../services/api';
import { apiErrorMessage } from '../services/resources';
import {
  courseLabel, courseType, isDenied, queryOptions,
} from './projectUi';

const ProjectCourseCandidates = ({
  url, projectId, ownerId, value, onChange, onDenied, disabled,
}) => {
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => setTerm(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);
  const valid = term.length >= 2 && term.length <= 100 && term === search.trim();
  const candidates = useQuery({
    ...queryOptions,
    queryKey: ['projects', url, 'courses', projectId, ownerId, term, page],
    queryFn: ({ signal }) => fetchApi(`${url}cours-candidats/?${new URLSearchParams({
      q: term,
      page,
      page_size: 20,
      ...(projectId ? { projet: projectId } : {}),
      ...(ownerId ? { responsable: ownerId } : {}),
    })}`, { signal }),
    enabled: valid && !disabled && Boolean(ownerId),
  });
  useEffect(() => {
    if (isDenied(candidates.error)) { onDenied(candidates.error); }
  }, [candidates.error, onDenied]);
  const ready = valid && !disabled && !candidates.error && !candidates.isFetching;
  return (
    <Stack spacing={1}>
      <Autocomplete
        disabled={disabled || !ownerId}
        value={value}
        options={ready ? candidates.data?.results || [] : []}
        filterOptions={options => options}
        getOptionLabel={courseLabel}
        isOptionEqualToValue={(option, selected) => option.id === selected.id}
        onChange={(_, selected) => onChange(selected)}
        onInputChange={(_, text, reason) => {
          if (reason === 'input' || reason === 'clear') { setSearch(text); setPage(1); }
        }}
        loading={valid && candidates.isFetching}
        noOptionsText={valid ? 'Aucun cours compatible disponible' : 'Saisir de 2 à 100 caractères'}
        renderInput={params => (
          <TextField
            {...params}
            label="Cours existant (facultatif)"
            helperText="Recherche paginée dans les accès communs au gestionnaire et au responsable. Aucun cours créé."
            slotProps={{ htmlInput: { ...params.inputProps, maxLength: 100 } }}
          />
        )}
      />
      <Stack direction="row" spacing={1}>
        <Button disabled={!ready || !candidates.data?.previous} onClick={() => setPage(current => current - 1)}>
          Cours précédents
        </Button>
        <Button disabled={!ready || !candidates.data?.next} onClick={() => setPage(current => current + 1)}>
          Cours suivants
        </Button>
      </Stack>
      {candidates.error && <Alert severity="error">Recherche de cours indisponible. {apiErrorMessage(candidates.error)}</Alert>}
    </Stack>
  );
};
ProjectCourseCandidates.propTypes = {
  url: PropTypes.string.isRequired,
  projectId: PropTypes.string,
  ownerId: PropTypes.number,
  value: courseType,
  onChange: PropTypes.func.isRequired,
  onDenied: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
export default ProjectCourseCandidates;
