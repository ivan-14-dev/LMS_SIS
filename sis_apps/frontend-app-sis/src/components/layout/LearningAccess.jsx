import React from 'react';
import PropTypes from 'prop-types';
import { getConfig } from '@edx/frontend-platform';
import { Link, useOutletContext } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Box, Button, Stack, Typography,
} from '@mui/material';
import { fetchApi } from '../../services/api';
import { apiErrorMessage, resourceUrl } from '../../services/resources';
import { canUseLearning } from './navigation';

const externalUrl = (base, path) => {
  try {
    const url = new URL(base);
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
      return null;
    }
    return `${url.href.replace(/\/$/, '')}${path}`;
  } catch (error) {
    if (!(error instanceof TypeError)) { throw error; }
    return null;
  }
};

const LearningAccess = ({ compact }) => {
  const {
    variant, capabilities, searchContext,
  } = useOutletContext();
  const eligible = canUseLearning(capabilities);
  const access = useQuery({
    queryKey: ['my-learning', variant, searchContext],
    queryFn: () => fetchApi(resourceUrl(variant, 'integration/my-learning')),
    enabled: eligible && Boolean(searchContext),
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });
  if (!eligible) {
    return compact ? null : <Alert severity="error">Cet espace est réservé aux apprenants et enseignants autorisés.</Alert>;
  }
  if (!searchContext || access.isLoading || access.isFetching) {
    return <Typography role="status">Vérification de vos accès aux cours…</Typography>;
  }
  if (access.isError) {
    return (
      <Alert severity="error" action={<Button onClick={() => access.refetch()}>Réessayer les accès</Button>}>
        Impossible de vérifier vos accès LMS. {apiErrorMessage(access.error)}
      </Alert>
    );
  }
  if (access.data?.state === 'not_configured') {
    return <Alert severity="info">Les cours en ligne ne sont pas raccordés. Vos services SIS restent disponibles.</Alert>;
  }
  if (access.data?.state === 'unmapped') {
    return <Alert severity="info">Votre compte Open edX doit être associé par l’établissement avant d’ouvrir les cours.</Alert>;
  }
  if (access.data?.state !== 'ready' || !Array.isArray(access.data.courses)) {
    return <Alert severity="error">La réponse des accès LMS est invalide.</Alert>;
  }
  const config = getConfig();
  const lms = externalUrl(config.LMS_BASE_URL, '/dashboard');
  const studio = externalUrl(config.STUDIO_BASE_URL, '/home/');
  if (!lms || (access.data.can_open_studio && !studio)) {
    return <Alert severity="error">Les adresses publiques du LMS ou de Studio sont invalides. Contactez l’administration.</Alert>;
  }
  return (
    <Box component="section" aria-label="Cours en ligne" className="sis-panel" sx={{ p: 2, mb: 3 }}>
      {!compact && <Typography component="h1" variant="h4" sx={{ mb: 2 }}>Mes cours en ligne</Typography>}
      <Stack direction="row" flexWrap="wrap" gap={1}>
        <Button component="a" href={lms} target="_blank" rel="noopener noreferrer" variant="contained">Mes cours</Button>
        {access.data.can_open_studio && (
          <Button component="a" href={studio} target="_blank" rel="noopener noreferrer" variant="outlined">Créer/modifier un cours</Button>
        )}
        {compact && <Button component={Link} to={`/${variant}/cours-lms`}>Cours associés à cet établissement</Button>}
      </Stack>
      <Typography variant="body2" sx={{ mt: 1 }}>
        Ouverture dans un nouvel onglet : votre espace SIS reste disponible.
        {config.SIS_AUTH_MODE === 'local' ? ' La connexion au LMS utilise votre compte Open edX associé, distinct du compte local.' : ' La connexion commune Open edX est utilisée.'}
        {access.data.can_open_studio && ' La création et la publication restent soumises aux autorisations de Studio.'}
      </Typography>
      {!compact && (
        <Stack spacing={2} sx={{ mt: 2 }}>
          {!access.data.courses.length && <Alert severity="info">Aucun accès à un cours n’est actuellement confirmé pour cet établissement.</Alert>}
          {access.data.courses.map(course => (
            <Box component="article" key={course.course_id}>
              <Typography component="h2" variant="h6">{course.name}</Typography>
              <Stack direction="row" gap={1} flexWrap="wrap">
                <Button component="a" href={externalUrl(config.LMS_BASE_URL, `/courses/${encodeURIComponent(course.course_id)}/course/`)} target="_blank" rel="noopener noreferrer">Suivre ce cours</Button>
                {course.can_edit && access.data.can_open_studio && (
                  <Button component="a" href={externalUrl(config.STUDIO_BASE_URL, `/course/${encodeURIComponent(course.course_id)}`)} target="_blank" rel="noopener noreferrer">Modifier dans Studio</Button>
                )}
              </Stack>
            </Box>
          ))}
        </Stack>
      )}
    </Box>
  );
};
LearningAccess.propTypes = { compact: PropTypes.bool };
LearningAccess.defaultProps = { compact: false };
export default LearningAccess;
