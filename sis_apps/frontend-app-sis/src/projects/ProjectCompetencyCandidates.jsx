import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Checkbox, FormControlLabel, Stack,
} from '@mui/material';
import { fetchApi } from '../services/api';
import { apiErrorMessage } from '../services/resources';
import { criterionType, isDenied, queryOptions } from './projectUi';

const ProjectCompetencyCandidates = ({
  url, projectId, courseId, ownerId, value, onChange, onDenied, onReadyChange, disabled,
}) => {
  const [page, setPage] = useState(1);
  const candidates = useQuery({
    ...queryOptions,
    queryKey: ['projects', url, 'competencies', projectId, courseId, ownerId, page],
    queryFn: ({ signal }) => fetchApi(`${url}competences-candidates/?${new URLSearchParams({
      cours: courseId,
      responsable: ownerId,
      page,
      page_size: 20,
      ...(projectId ? { projet: projectId } : {}),
    })}`, { signal }),
    enabled: !disabled,
  });
  useEffect(() => {
    if (isDenied(candidates.error)) { onDenied(candidates.error); }
  }, [candidates.error, onDenied]);
  const ready = !disabled && candidates.isSuccess && !candidates.isFetching;
  useEffect(() => {
    onReadyChange(ready);
  }, [ready, onReadyChange]);
  const changePage = offset => {
    onReadyChange(false);
    setPage(current => current + offset);
  };
  return (
    <Stack spacing={1}>
      {candidates.isFetching && <Alert severity="info">Chargement des compétences de l’offre liée…</Alert>}
      {candidates.error && (
        <Alert severity="error">
          Compétences indisponibles. {apiErrorMessage(candidates.error)}
          <Button disabled={disabled} onClick={() => { onReadyChange(false); candidates.refetch(); }}>
            Réessayer les compétences
          </Button>
        </Alert>
      )}
      {ready && candidates.data?.count === 0 && (
        <Alert severity="info">Aucune compétence disponible : offre absente ou sans critères de compétences.</Alert>
      )}
      {ready && candidates.data?.results.map(criterion => {
        const checked = value.some(item => item.code === criterion.code);
        return (
          <FormControlLabel
            key={criterion.code}
            label={`${criterion.label} (${criterion.code})`}
            control={(
              <Checkbox
                checked={checked}
                disabled={!checked && value.length >= 100}
                onChange={event => onChange(event.target.checked
                  ? [...value, criterion] : value.filter(item => item.code !== criterion.code))}
              />
            )}
          />
        );
      })}
      <Stack direction="row" spacing={1}>
        <Button disabled={!ready || !candidates.data?.previous} onClick={() => changePage(-1)}>
          Compétences précédentes
        </Button>
        <Button disabled={!ready || !candidates.data?.next} onClick={() => changePage(1)}>
          Compétences suivantes
        </Button>
      </Stack>
    </Stack>
  );
};
ProjectCompetencyCandidates.propTypes = {
  url: PropTypes.string.isRequired,
  projectId: PropTypes.string,
  courseId: PropTypes.number.isRequired,
  ownerId: PropTypes.number.isRequired,
  value: PropTypes.arrayOf(criterionType).isRequired,
  onChange: PropTypes.func.isRequired,
  onDenied: PropTypes.func.isRequired,
  onReadyChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
export default ProjectCompetencyCandidates;
