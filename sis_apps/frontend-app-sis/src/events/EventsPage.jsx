import React, {
  useCallback, useEffect, useRef, useState,
} from 'react';
import PropTypes from 'prop-types';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Box, Button, Stack, Typography,
} from '@mui/material';
import { useCapabilities } from '../components/auth/PermissionGuard';
import PageHeader from '../components/common/PageHeader';
import SISDataTable from '../components/common/SISDataTable';
import { fetchApi, postApi } from '../services/api';
import { apiErrorMessage, fetchResourcePage, resourceUrl } from '../services/resources';
import EventCommandDialog from './EventCommandDialog';
import EventDates from './EventDates';
import EventSummary from './EventSummary';
import {
  checkedCapabilities, checkedEvent, choiceLabel, eventAccess, eventDateLabel,
  initialInterval, intervalPayload, isDenied, queryOptions, roomLabel, uuidPattern,
} from './eventUi';

const accessError = () => Object.assign(new Error('Votre accès aux événements a été retiré.'), { response: { status: 403 } });
const eventLink = (select, disabled, { row }) => <Button disabled={disabled} onClick={() => select(row.original.id)}>Ouvrir {row.original.titre}</Button>;

const EventsWorkspace = ({ variant, scope, accessChecking }) => {
  const url = resourceUrl(variant, 'core/evenements');
  const client = useQueryClient();
  const [parameters, setParameters] = useSearchParams();
  const id = parameters.get('evenement');
  const [bounds, setBounds] = useState(initialInterval);
  const [interval, setInterval] = useState(() => intervalPayload(bounds.start, bounds.end, 93));
  const [boundsError, setBoundsError] = useState(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [dialog, setDialog] = useState(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState(null);
  const [notice, setNotice] = useState('');
  const [readError, setReadError] = useState(null);
  const mounted = useRef(true);
  const sending = useRef(false);
  const postController = useRef(null);
  const previousAccess = useRef(null);
  const capabilities = useQuery({
    ...queryOptions,
    queryKey: ['events', scope, 'capabilities'],
    queryFn: async ({ signal }) => checkedCapabilities(await fetchApi(`${url}capacites/`, { signal })),
    enabled: !failure,
  });
  const allowed = !failure && !capabilities.error && eventAccess(capabilities.data);
  const list = useQuery({
    ...queryOptions,
    queryKey: ['events', scope, 'list', interval, page, pageSize],
    queryFn: async ({ signal }) => {
      const data = await fetchResourcePage(url, { ...interval, page: page + 1, page_size: pageSize }, { signal });
      return { ...data, results: data.results.map(item => checkedEvent(item, null, false)) };
    },
    enabled: allowed,
  });
  const detail = useQuery({
    ...queryOptions,
    queryKey: ['events', scope, 'detail', id],
    queryFn: async ({ signal }) => checkedEvent(await fetchApi(`${url}${id}/`, { signal }), id),
    enabled: allowed && Boolean(id) && uuidPattern.test(id),
  });
  const purge = useCallback(() => {
    client.cancelQueries({ queryKey: ['events', scope] });
    client.removeQueries({ queryKey: ['events', scope] });
  }, [client, scope]);
  const deny = useCallback(error => {
    setFailure(error);
    setNotice('');
    setDialog(null);
    setBusy(false);
    purge();
  }, [purge]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      postController.current?.abort();
      purge();
    };
  }, [purge]);
  const queryError = capabilities.error || detail.error || list.error;
  const accessWithdrawn = previousAccess.current && capabilities.data
    && ['can_create', 'can_manage', 'can_consult'].some(
      key => previousAccess.current[key] && !capabilities.data[key],
    );
  useEffect(() => {
    if (isDenied(queryError)) { deny(queryError); }
  }, [queryError, deny]);
  useEffect(() => {
    if (capabilities.data && !capabilities.isFetching && !eventAccess(capabilities.data)) { deny(accessError()); }
  }, [capabilities.data, capabilities.isFetching, deny]);
  useEffect(() => {
    if (capabilities.data) {
      previousAccess.current = capabilities.data;
      if (accessWithdrawn) { deny(accessError()); }
    }
  }, [accessWithdrawn, capabilities.data, deny]);
  const canEdit = detail.data?.can_manage && detail.data.statut === 'planifie';
  const dialogAllowed = dialog?.kind === 'create' ? capabilities.data?.can_create : detail.data?.can_manage;
  useEffect(() => {
    if (dialog && !dialogAllowed) {
      setDialog(null);
      setNotice('');
      setBusy(false);
      client.removeQueries({ queryKey: ['events', scope, 'rooms'] });
      client.removeQueries({ queryKey: ['events', scope, 'participants'] });
    }
  }, [dialog, dialogAllowed, client, scope]);
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
  const checking = accessChecking || capabilities.isFetching;
  const select = value => {
    if (busy) { return; }
    setDialog(null); setNotice(''); setReadError(null);
    const next = new URLSearchParams(parameters);
    if (value) { next.set('evenement', value); } else { next.delete('evenement'); }
    setParameters(next);
  };
  const readEvent = async eventId => {
    const result = await client.fetchQuery({
      ...queryOptions,
      queryKey: ['events', scope, 'detail', eventId],
      queryFn: async ({ signal }) => checkedEvent(await fetchApi(`${url}${eventId}/`, { signal }), eventId),
    });
    if (!mounted.current) { throw new Error('Le contexte de session a changé.'); }
    return result;
  };
  const openCommand = async kind => {
    if (busy || checking) { return; }
    setReadError(null); setNotice('');
    if (kind === 'create') { setDialog({ kind }); return; }
    setBusy(true);
    try {
      // The list has no invitations. Always reread authoritative detail before replacing participants.
      const current = await readEvent(id);
      if (!current.can_manage) { deny(accessError()); return; }
      if (current.statut !== 'planifie') { throw new Error('Cet événement est déjà annulé.'); }
      setDialog({ kind, event: current });
    } catch (error) {
      if (isDenied(error)) { deny(error); } else if (mounted.current) { setReadError(error); }
    } finally {
      if (mounted.current) { setBusy(false); }
    }
  };
  const refresh = async () => {
    setNotice(''); setReadError(null);
    try {
      await client.invalidateQueries({ queryKey: ['events', scope] }, { throwOnError: true });
    } catch (error) {
      if (isDenied(error)) { deny(error); } else if (mounted.current) { setReadError(error); }
    }
  };
  const command = async (kind, eventId, payload) => {
    if (sending.current || checking || !allowed) { throw new Error('Veuillez attendre la vérification des accès.'); }
    sending.current = true;
    setNotice('');
    let responseReceived = false;
    try {
      postController.current = new AbortController();
      const endpoint = kind === 'create' ? url : `${url}${eventId}/${kind === 'edit' ? 'modifier' : 'annuler'}/`;
      const result = checkedEvent(await postApi(endpoint, payload, { signal: postController.current.signal }), eventId);
      responseReceived = true;
      if (result.version !== (kind === 'create' ? 1 : payload.version + 1)
          || result.statut !== (kind === 'cancel' ? 'annule' : 'planifie')) {
        throw new Error('La réponse ne confirme pas la commande demandée.');
      }
      if (!mounted.current) { throw new Error('Le contexte de session a changé.'); }
      const authoritative = await readEvent(result.id);
      if (authoritative.version < result.version) { throw new Error('La relecture ne confirme pas la version enregistrée.'); }
      await client.invalidateQueries({ queryKey: ['events', scope, 'list'] }, { throwOnError: true });
      const caps = await capabilities.refetch({ throwOnError: true });
      if (!eventAccess(caps.data)) { throw accessError(); }
      if (!mounted.current) { return; }
      setDialog(null);
      const next = new URLSearchParams(parameters);
      next.set('evenement', result.id);
      setParameters(next);
      setNotice('Opération confirmée par le serveur et état relu.');
    } catch (error) {
      if (isDenied(error) && mounted.current) { deny(error); }
      if (responseReceived && !isDenied(error)) {
        const unconfirmed = new Error(`La commande a reçu une réponse, mais sa relecture a échoué. ${apiErrorMessage(error)}`);
        if (mounted.current) { setReadError(unconfirmed); }
        throw unconfirmed;
      }
      throw error;
    } finally {
      sending.current = false;
      postController.current = null;
      if (mounted.current) { setBusy(false); }
    }
  };
  if (failure || isDenied(queryError) || accessWithdrawn) {
    return (
      <Alert severity="error">
        Accès aux événements refusé ou retiré. Les anciennes données privées ont été purgées. {apiErrorMessage(failure || queryError || accessError())}
        <Button onClick={() => { setFailure(null); select(null); }}>Revérifier les accès</Button>
      </Alert>
    );
  }
  if (capabilities.error) {
    return <Alert severity="error">Capacités indisponibles. {apiErrorMessage(capabilities.error)}<Button onClick={() => capabilities.refetch()}>Réessayer</Button></Alert>;
  }
  if (!capabilities.data) { return <Alert severity="info">Vérification des capacités événementielles…</Alert>; }
  if (!allowed) { return <Alert severity="warning">Une habilitation explicite est nécessaire pour consulter ou organiser des événements.</Alert>; }
  const types = capabilities.data.types;
  const statuses = capabilities.data.statuts;
  const columns = [
    { Header: 'Titre', accessor: 'titre' },
    { Header: 'Type', accessor: 'type_label' },
    { Header: 'Début', accessor: 'debut_label' },
    { Header: 'Fin', accessor: 'fin_label' },
    { Header: 'Salle', accessor: 'salle_label' },
    { Header: 'Statut', accessor: 'statut_display' },
    { Header: 'Actions', accessor: 'id', Cell: eventLink.bind(null, select, busy || checking) },
  ];
  return (
    <Stack spacing={3}>
      <PageHeader title="Événements institutionnels" subtitle="Conférences, examens, réunions, cérémonies et activités institutionnelles." />
      <Alert severity="info">
        Seuls les événements autorisés sont visibles. La consultation d’une invitation exige une habilitation explicite.
        Notifications internes uniquement, sans courriel ni SMS.
      </Alert>
      <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap' }}>
        <Button disabled={busy} onClick={() => select(null)}>Agenda autorisé</Button>
        <Button disabled={busy || checking} onClick={refresh}>Actualiser l’agenda</Button>
        <Button component={Link} to={`/${variant}/workflows`} disabled={busy}>Notifications internes</Button>
        {capabilities.data.can_create && <Button variant="contained" disabled={busy || checking} onClick={() => openCommand('create')}>Nouvel événement</Button>}
      </Stack>
      {notice && !queryError && !checking && <Alert severity="success">{notice}</Alert>}
      {readError && <Alert severity="error">{apiErrorMessage(readError)}</Alert>}
      {id ? (
        <Box component="section" aria-label="Détail de l’événement">
          {!uuidPattern.test(id) && <Alert severity="error">Identifiant d’événement invalide.</Alert>}
          {detail.error && <Alert severity="error">Détail indisponible. {apiErrorMessage(detail.error)}<Button disabled={busy} onClick={() => detail.refetch()}>Recharger le détail</Button></Alert>}
          {uuidPattern.test(id) && !detail.error && (!detail.data || detail.isFetching) && <Typography role="status">Relecture de l’événement…</Typography>}
          {!detail.error && detail.data && !detail.isFetching && (
            <Stack spacing={2}>
              <EventSummary event={detail.data} types={types} statuses={statuses} />
              {canEdit && (
                <Stack direction="row" spacing={1}>
                  <Button disabled={busy || checking} onClick={() => openCommand('edit')}>Modifier l’horaire, la salle ou les invitations</Button>
                  <Button color="error" disabled={busy || checking} onClick={() => openCommand('cancel')}>Annuler l’événement</Button>
                </Stack>
              )}
            </Stack>
          )}
        </Box>
      ) : (
        <>
          <Box component="form" onSubmit={formEvent => {
            formEvent.preventDefault();
            try {
              const next = intervalPayload(bounds.start, bounds.end, 93);
              setInterval(next); setPage(0); setBoundsError(null); setNotice('');
            } catch (error) { setBoundsError(error); }
          }}
          >
            <Stack spacing={2}>
              <EventDates
                  calendar
                  start={bounds.start}
                  end={bounds.end}
                  onStart={start => setBounds(value => ({ ...value, start }))}
                  onEnd={end => setBounds(value => ({ ...value, end }))}
                  disabled={busy}
              />
              {boundsError && <Alert severity="error">{apiErrorMessage(boundsError)}</Alert>}
              <Button type="submit" disabled={busy || checking}>Afficher cette période</Button>
              <Typography>Période affichée : {eventDateLabel(interval.debut)} — {eventDateLabel(interval.fin)} (fin exclue).</Typography>
            </Stack>
          </Box>
          {list.error ? (
            <Alert severity="error">Agenda indisponible. {apiErrorMessage(list.error)}<Button onClick={() => list.refetch()}>Réessayer</Button></Alert>
          ) : (
            <SISDataTable
                title="Agenda autorisé"
                columns={columns}
                data={!list.isFetching ? (list.data?.results || []).map(item => ({
                  ...item, type_label: choiceLabel(types, item.type),
                  debut_label: eventDateLabel(item.debut), fin_label: eventDateLabel(item.fin),
                  salle_label: roomLabel(item.salle), statut_display: choiceLabel(statuses, item.statut),
                })) : []}
                loading={list.isPending || list.isFetching}
                searchable={false}
                exportable={false}
                emptyMessage="Aucun événement accessible pendant cette période."
                serverPagination={{
                  page, pageSize, count: list.data?.count || 0, search: '', onSearchChange: () => {},
                  onPageChange: value => { if (!busy) { setPage(value); } },
                  onPageSizeChange: value => { if (!busy) { setPageSize(Math.min(value, 100)); setPage(0); } },
                }}
            />
          )}
        </>
      )}
      {dialog && dialogAllowed && !isDenied(queryError) && (
        <EventCommandDialog
            url={url}
            scope={scope}
            kind={dialog.kind}
            event={dialog.event}
            types={types}
            statuses={statuses}
            onClose={() => { setDialog(null); setBusy(false); }}
            onCommand={command}
            onReload={readEvent}
            onDenied={deny}
            onBusy={setBusy}
            accessChecking={checking || Boolean(queryError) || (dialog.event && detail.data?.statut !== 'planifie')}
        />
      )}
    </Stack>
  );
};
EventsWorkspace.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired, scope: PropTypes.string.isRequired,
  accessChecking: PropTypes.bool,
};

const EventsPage = ({ variant }) => {
  const capabilities = useCapabilities(variant, { retry: false });
  const profileUrl = resourceUrl(variant, 'utilisateurs/comptes');
  const profile = useQuery({
    ...queryOptions,
    queryKey: ['profile', profileUrl],
    queryFn: ({ signal }) => fetchApi(`${profileUrl}me/`, { signal }),
    enabled: capabilities.data?.modules?.['sis.events'] === true && !capabilities.error,
  });
  if (capabilities.error || profile.error) {
    return <Alert severity="error">Impossible de vérifier l’accès aux événements. Les données privées sont masquées. {apiErrorMessage(capabilities.error || profile.error)}</Alert>;
  }
  if (!capabilities.data || !capabilities.isFetchedAfterMount) { return <Alert severity="info">Vérification du module événements…</Alert>; }
  if (capabilities.data.modules?.['sis.events'] !== true) { return <Alert severity="warning">Le module Événements institutionnels est désactivé ou indisponible.</Alert>; }
  if (!profile.isFetchedAfterMount) { return <Alert severity="info">Vérification du compte et de l’établissement…</Alert>; }
  if (!profile.data?.id || !profile.data?.etablissement) { return <Alert severity="error">Compte ou établissement indisponible. Aucun événement n’est affiché.</Alert>; }
  const scope = JSON.stringify([variant, profileUrl, profile.data.id, profile.data.etablissement, capabilities.data]);
  return <EventsWorkspace key={scope} scope={scope} variant={variant} accessChecking={capabilities.isFetching || profile.isFetching} />;
};
EventsPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default EventsPage;
