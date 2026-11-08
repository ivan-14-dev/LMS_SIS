import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Button, Stack, Typography,
} from '@mui/material';
import { useCapabilities } from '../components/auth/PermissionGuard';
import { fetchApi, postApi } from '../services/api';
import { apiErrorMessage, fetchResourcePage, resourceUrl } from '../services/resources';
import SurveyDetail from './SurveyDetail';
import SurveyEditor from './SurveyEditor';

const queryOptions = {
  retry: false, gcTime: 0, staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: 'always',
};
const information = 'Enquêtes nominatives : votre identité et vos réponses sont visibles par les gestionnaires habilités. Aucun anonymat, aucun lien public ni envoi de courriel. Une seule réponse définitive par destinataire.';

const SurveysWorkspace = ({ variant }) => {
  const client = useQueryClient();
  const [parameters, setParameters] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [commandError, setCommandError] = useState(null);
  const [success, setSuccess] = useState(false);
  const portal = resourceUrl(variant, 'portail/enquetes');
  const management = resourceUrl(variant, 'core/enquetes');
  const managing = parameters.get('gestion') === '1';
  const id = parameters.get('enquete');
  const url = managing ? management : portal;
  const capabilities = useQuery({
    ...queryOptions,
    queryKey: ['surveys', portal, 'capabilities'],
    queryFn: ({ signal }) => fetchApi(`${portal}capacites/`, { signal }),
    enabled: !commandError,
  });
  const allowed = Boolean(capabilities.data && !capabilities.error && (!managing || capabilities.data.can_manage));
  const list = useQuery({
    ...queryOptions,
    queryKey: ['surveys', url, 'list', page],
    queryFn: ({ signal }) => fetchResourcePage(url, { page, page_size: 20 }, { signal }),
    enabled: allowed && !id && !creating && !commandError,
  });
  const detail = useQuery({
    ...queryOptions,
    queryKey: ['surveys', url, 'detail', id],
    queryFn: ({ signal }) => fetchApi(`${url}${id}/`, { signal }),
    enabled: allowed && Boolean(id) && !commandError,
  });
  const results = useQuery({
    ...queryOptions,
    queryKey: ['surveys', management, 'results', id],
    queryFn: ({ signal }) => fetchApi(`${management}${id}/resultats/`, { signal }),
    enabled: allowed && managing && Boolean(id) && !commandError,
  });
  useEffect(() => () => {
    [portal, management].forEach(base => {
      client.cancelQueries({ queryKey: ['surveys', base] });
      client.removeQueries({ queryKey: ['surveys', base] });
    });
  }, [client, portal, management]);
  const select = (value, manager = managing) => {
    if (busy) { return; }
    setCreating(false);
    setSuccess(false);
    setCommandError(null);
    const next = new URLSearchParams();
    if (value) { next.set('enquete', value); }
    if (manager) { next.set('gestion', '1'); }
    setParameters(next);
    setPage(1);
  };
  const command = async (tail, payload) => {
    if (busy) { return; }
    setBusy(true);
    setSuccess(false);
    try {
      const data = await postApi(`${url}${id ? `${id}/` : ''}${tail}`, payload);
      await Promise.all([portal, management].map(base => client.invalidateQueries({ queryKey: ['surveys', base] })));
      setSuccess(true);
      if (creating) {
        setCreating(false);
        setParameters({ gestion: '1', enquete: data.id });
      }
    } catch (error) {
      setCommandError(error);
      [portal, management].forEach(base => {
        client.cancelQueries({ queryKey: ['surveys', base] });
        client.removeQueries({ queryKey: ['surveys', base] });
      });
    } finally {
      setBusy(false);
    }
  };
  const error = commandError || capabilities.error || (id ? detail.error || (managing && results.error) : list.error);
  if (error) {
    return (
      <Alert severity="error">
        Enquêtes indisponibles. Aucune donnée précédemment chargée n’est affichée. {apiErrorMessage(error)}
        <Button onClick={() => { setCommandError(null); client.resetQueries({ queryKey: ['surveys'] }); }}>
          Recharger
        </Button>
        <Button onClick={() => select(null, false)}>Mes enquêtes</Button>
      </Alert>
    );
  }
  if (!capabilities.data || capabilities.isFetching) { return <Alert severity="info">Vérification des accès…</Alert>; }
  if (!allowed) { return <Alert severity="error">La gestion des enquêtes exige une habilitation explicite.<Button onClick={() => select(null, false)}>Mes enquêtes</Button></Alert>; }
  const loading = id ? detail.isFetching || !detail.data || (managing && (results.isFetching || !results.data))
    : !creating && list.isFetching;
  return (
    <Stack spacing={2}>
      <Typography variant="h1">{managing ? 'Gestion des enquêtes institutionnelles' : 'Mes enquêtes institutionnelles'}</Typography>
      <Alert severity="info">{information}</Alert>
      <Stack direction="row" spacing={1}>
        <Button disabled={busy} onClick={() => select(null, false)}>Mes enquêtes</Button>
        {capabilities.data.can_manage && (
          <Button disabled={busy} onClick={() => select(null, true)}>Gérer les enquêtes</Button>
        )}
        <Button disabled={busy} onClick={() => client.invalidateQueries({ queryKey: ['surveys'] })}>Actualiser</Button>
      </Stack>
      {success && <Alert severity="success">Enregistrement confirmé par le serveur.</Alert>}
      {loading ? <Typography>Chargement…</Typography> : (
        <>
          {creating && (
            <SurveyEditor
              url={management}
              busy={busy}
              onSave={payload => command('', payload)}
              onCancel={() => setCreating(false)}
            />
          )}
          {id && detail.data && (
            <SurveyDetail
              key={`${url}${id}:${detail.data.version || ''}:${Boolean(detail.data.ma_reponse)}`}
              url={url}
              survey={detail.data}
              results={managing ? results.data : undefined}
              managing={managing}
              busy={busy}
              onCommand={command}
            />
          )}
          {!id && !creating && (
            <>
              {managing && <Button disabled={busy} variant="contained" onClick={() => setCreating(true)}>Nouvelle enquête</Button>}
              {(list.data?.results || []).map(survey => (
                <Button key={survey.id} disabled={busy} onClick={() => select(survey.id)}>
                  {survey.titre} · {survey.statut}
                </Button>
              ))}
              {!list.data?.count && <Typography>Aucune enquête accessible.</Typography>}
              <Stack direction="row" spacing={1}>
                <Button disabled={busy || page === 1} onClick={() => setPage(current => current - 1)}>
                  Page précédente
                </Button>
                <Button disabled={busy || !list.data?.next} onClick={() => setPage(current => current + 1)}>
                  Page suivante
                </Button>
              </Stack>
            </>
          )}
        </>
      )}
    </Stack>
  );
};
SurveysWorkspace.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };

const SurveysPage = ({ variant }) => {
  const capabilities = useCapabilities(variant, { retry: false });
  if (capabilities.error) { return <Alert severity="error">Impossible de vérifier le module enquêtes. {apiErrorMessage(capabilities.error)}</Alert>; }
  if (!capabilities.data || capabilities.isFetching) { return <Alert severity="info">Vérification du module enquêtes…</Alert>; }
  if (capabilities.data.modules?.['sis.surveys'] !== true) { return <Alert severity="warning">Le module Enquêtes institutionnelles est désactivé ou indisponible.</Alert>; }
  return <SurveysWorkspace key={variant} variant={variant} />;
};
SurveysPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default SurveysPage;
