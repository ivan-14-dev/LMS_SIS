import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Autocomplete, TextField } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../services/api';
import { apiErrorMessage } from '../services/resources';
import { candidateType, isDenied, queryOptions } from './projectUi';

const ProjectCandidates = ({
  url, projectId, ownerId, type, label, value, onChange, onDenied, disabled, multiple = false, required = false,
}) => {
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setTerm(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);
  const valid = term.length >= 2 && term.length <= 100 && term === search.trim();
  const candidates = useQuery({
    ...queryOptions,
    queryKey: ['projects', url, 'candidates', projectId, ownerId, type, term],
    queryFn: ({ signal }) => fetchApi(`${url}candidats/?${new URLSearchParams({
      type,
      q: term,
      ...(projectId ? { projet: projectId } : {}),
      ...(!projectId && ownerId ? { responsable: ownerId } : {}),
    })}`, { signal }),
    enabled: valid && !disabled,
  });
  useEffect(() => {
    if (isDenied(candidates.error)) { onDenied(candidates.error); }
  }, [candidates.error, onDenied]);
  return (
    <>
      <Autocomplete
        multiple={multiple}
        disabled={disabled}
        value={value}
        options={valid && !candidates.error && !candidates.isFetching ? candidates.data?.results || [] : []}
        filterOptions={options => options}
        getOptionLabel={option => option.nom}
        isOptionEqualToValue={(option, selected) => option.id === selected.id}
        onChange={(_, selected) => onChange(selected)}
        onInputChange={(_, text, reason) => { if (reason === 'input' || reason === 'clear') { setSearch(text); } }}
        loading={valid && candidates.isFetching}
        noOptionsText={valid ? 'Aucun candidat disponible' : 'Saisir de 2 à 100 caractères'}
        renderInput={params => (
          <TextField
            {...params}
            label={label}
            required={required && (multiple ? !value.length : !value)}
            helperText="Recherche nominative dans le périmètre autorisé · 20 résultats maximum."
          />
        )}
      />
      {candidates.error && <Alert severity="error">Recherche indisponible. {apiErrorMessage(candidates.error)}</Alert>}
    </>
  );
};
ProjectCandidates.propTypes = {
  url: PropTypes.string.isRequired,
  projectId: PropTypes.string,
  ownerId: PropTypes.number,
  type: PropTypes.oneOf(['responsable', 'evaluateur', 'membre']).isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([candidateType, PropTypes.arrayOf(candidateType)]),
  onChange: PropTypes.func.isRequired,
  onDenied: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  multiple: PropTypes.bool,
  required: PropTypes.bool,
};
export default ProjectCandidates;
