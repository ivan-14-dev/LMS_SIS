import React, {
  useCallback, useEffect, useRef, useState,
} from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Box, Button, Stack,
} from '@mui/material';
import { useCapabilities } from '../components/auth/PermissionGuard';
import { PageHeader, SISDataTable } from '../components/common';
import { fetchApi } from '../services/api';
import { apiErrorMessage, fetchResourcePage, resourceUrl } from '../services/resources';
import ProjectCommandDialog from './ProjectCommandDialog';
import ProjectDetail from './ProjectDetail';
import { isDenied, limitations, queryOptions } from './projectUi';

const ProjectsWorkspace = ({ variant }) => {
  const url = resourceUrl(variant, 'core/projets');
  const client = useQueryClient();
  const [parameters, setParameters] = useSearchParams();
  const [busy, setBusy] = useState(false);
  const selected = useRef(parameters.get('projet'));
  if (!busy) { selected.current = parameters.get('projet'); }
  const id = selected.current;
  const [creating, setCreating] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState('');
  const [denied, setDenied] = useState(null);
  const onDenied = useCallback(error => setDenied(error), []);
  const capabilities = useQuery({
    ...queryOptions,
    queryKey: ['projects', url, 'capabilities'],
    queryFn: ({ signal }) => fetchApi(`${url}capacites/`, { signal }),
    enabled: !denied,
  });
  const list = useQuery({
    ...queryOptions,
    queryKey: ['projects', url, 'list', page, pageSize, search],
    queryFn: ({ signal }) => fetchResourcePage(url, { page: page + 1, page_size: pageSize, q: search }, { signal }),
    enabled: !id && !denied && Boolean(capabilities.data) && !capabilities.error,
  });
  useEffect(() => {
    const error = capabilities.error || list.error;
    if (isDenied(error)) { onDenied(error); }
  }, [capabilities.error, list.error, onDenied]);
  useEffect(() => {
    if (denied) {
      client.cancelQueries({ queryKey: ['projects', url] });
      client.removeQueries({ queryKey: ['projects', url] });
    }
  }, [denied, client, url]);
  useEffect(() => () => {
    client.cancelQueries({ queryKey: ['projects', url] });
    client.removeQueries({ queryKey: ['projects', url] });
  }, [client, url]);
  useEffect(() => {
    if (!busy) { return undefined; }
    const preventLeaving = event => {
      event.preventDefault();
      // Older browsers require returnValue for the native leave-page confirmation.
      // eslint-disable-next-line no-param-reassign
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', preventLeaving);
    return () => window.removeEventListener('beforeunload', preventLeaving);
  }, [busy]);
  const select = value => {
    if (busy) { return; }
    const next = new URLSearchParams(parameters);
    if (value) { next.set('projet', value); } else { next.delete('projet'); }
    setParameters(next);
  };
  const created = async result => {
    await client.invalidateQueries({ queryKey: ['projects', url, 'list'] });
    setCreating(false);
    // The response identifies the newly created project; never infer or guess its identifier.
    const next = new URLSearchParams(parameters);
    next.set('projet', result.id);
    setParameters(next);
  };
  if (denied || capabilities.error) {
    return (
      <Alert severity="error">
        {denied ? 'Accès aux projets refusé.' : 'Erreur de chargement des capacités projets.'}
        {' '}Aucune donnée précédemment chargée n’est affichée. {apiErrorMessage(denied || capabilities.error)}
        {!denied && <Button onClick={() => capabilities.refetch()}>Réessayer</Button>}
      </Alert>
    );
  }
  if (!capabilities.data) { return <Alert severity="info">Chargement des capacités projets…</Alert>; }
  return (
    <Stack spacing={3}>
      <Alert severity="info">{limitations}</Alert>
      {id ? (
        <ProjectDetail
          key={id}
          url={url}
          id={id}
          busy={busy}
          onBusy={setBusy}
          onBack={() => select(null)}
          onDenied={onDenied}
        />
      ) : (
        <>
          <PageHeader title="Projets pédagogiques" subtitle="Projets individuels et collectifs, travaux privés et évaluations publiées explicitement." />
          {list.error ? (
            <Alert severity="error">Liste indisponible. {apiErrorMessage(list.error)}<Button onClick={() => list.refetch()}>Réessayer</Button></Alert>
          ) : (
            <SISDataTable
              title="Projets accessibles"
              columns={[
                { Header: 'Titre', accessor: 'titre' },
                { Header: 'Mode', accessor: 'mode' },
              ]}
              data={list.data?.results || []}
              loading={list.isPending || list.isFetching}
              exportable={false}
              emptyMessage="Aucun projet accessible dans cette sélection."
              onRowClick={busy ? undefined : row => select(row.original.id)}
              onAdd={capabilities.data.can_create && !busy && !capabilities.isFetching
                ? () => setCreating(true) : undefined}
              addButtonLabel="Nouveau projet"
              onRefresh={busy ? undefined : () => { list.refetch(); capabilities.refetch(); }}
              serverPagination={{
                page,
                pageSize,
                count: list.data?.count || 0,
                search,
                onPageChange: value => { if (!busy) { setPage(value); } },
                onPageSizeChange: value => { if (!busy) { setPageSize(value); setPage(0); } },
                onSearchChange: value => { if (!busy) { setSearch(value); setPage(0); } },
              }}
            />
          )}
          {creating && capabilities.data.can_create && (
            <ProjectCommandDialog url={url} kind="create" onClose={() => setCreating(false)} onSuccess={created} onDenied={onDenied} onBusy={setBusy} />
          )}
        </>
      )}
    </Stack>
  );
};
ProjectsWorkspace.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };

const ProjectsPage = ({ variant }) => {
  const capabilities = useCapabilities(variant, { retry: false });
  if (capabilities.error) {
    return <Alert severity="error">Impossible de vérifier l’accès au module projets. {apiErrorMessage(capabilities.error)}</Alert>;
  }
  if (!capabilities.data || !capabilities.isFetchedAfterMount) { return <Alert severity="info">Vérification du module projets…</Alert>; }
  if (capabilities.data.modules?.['sis.projects'] !== true) {
    return <Alert severity="warning">Le module Projets pédagogiques est désactivé ou indisponible pour cet établissement.</Alert>;
  }
  return <Box><ProjectsWorkspace key={variant} variant={variant} /></Box>;
};
ProjectsPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default ProjectsPage;
