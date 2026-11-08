import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Box, Button, Stack, Tab, Tabs, Typography,
} from '@mui/material';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { hasCapability } from '../../components/layout/navigation';
import SISDataTable from '../../components/common/SISDataTable';
import { postApi } from '../../services/api';
import { apiErrorMessage, fetchResourcePage, resourceUrl } from '../../services/resources';
import LibraryBook from './LibraryBook';
import LibraryLoanDialog from './LibraryLoanDialog';
import { libraryQueryOptions, reservationResource } from './libraryUi';

const bookColumns = [
  { Header: 'Titre', accessor: 'titre' },
  { Header: 'Auteurs', accessor: 'auteurs' },
  { Header: 'ISBN', accessor: 'isbn' },
];
const loanColumns = [
  { Header: 'Ouvrage', accessor: 'livre_titre' },
  { Header: 'Emprunteur', accessor: 'emprunteur_nom' },
  { Header: 'Date emprunt', accessor: 'date_emprunt' },
  { Header: 'Retour prévu', accessor: 'date_retour_prevue' },
  { Header: 'Statut', accessor: 'statut_display' },
];
const reservationColumns = [
  { Header: 'Ouvrage', accessor: 'livre_titre' },
  { Header: 'Date de réservation', accessor: 'date_reservation' },
  { Header: 'Statut', accessor: 'statut' },
];

const libraryActions = (settings, cell) => {
  const row = cell.row.original;
  const {
    catalogue, loans, manage, can, busy, base, currentTab, variant, command, select, remit,
  } = settings;
  return (
    <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap' }}>
      {catalogue && <Button disabled={busy} onClick={() => select(row.id)}>Ouvrir {row.titre}</Button>}
      {loans && (manage || can('change_emprunt')) && ['en_cours', 'en_retard', 'renouvele'].includes(row.statut) && (
        <Button disabled={busy} onClick={() => command(`${base}emprunts/${row.id}/${variant === 'secondaire' ? 'retourner' : 'rendre'}/`, {})}>
          Retourner
        </Button>
      )}
      {!catalogue && !loans && ['en_attente', 'disponible'].includes(row.statut) && (
        <>
          <Button disabled={busy} onClick={() => select(row.livre)}>Ouvrir le titre réservé</Button>
          {(can('change_reservation') || can('add_reservation') || manage) && (
            <Button disabled={busy} onClick={() => command(`${base}${currentTab}/${row.id}/${variant === 'secondaire' ? 'cancel' : 'annuler'}/`, {})}>
              Annuler la réservation
            </Button>
          )}
          {manage && <Button disabled={busy} onClick={() => remit(row)}>Remettre un exemplaire</Button>}
        </>
      )}
    </Stack>
  );
};

const LibraryWorkspace = ({ variant, capabilities }) => {
  const can = permission => hasCapability(capabilities, `bibliotheque.${permission}`);
  const manage = can('change_livre');
  const catalogueAccess = [
    'view_livre', 'consulter_ressource_numerique', 'change_livre',
    'view_emprunt', 'add_emprunt', 'change_emprunt',
    'view_reservation', 'add_reservation', 'change_reservation',
  ].some(can);
  const tabs = [
    { value: 'livres', label: 'Catalogue', allowed: catalogueAccess },
    { value: 'emprunts', label: 'Prêts', allowed: can('view_emprunt') || can('add_emprunt') || can('change_emprunt') || manage },
    { value: reservationResource(variant), label: 'Réservations', allowed: can('view_reservation') || can('add_reservation') || can('change_reservation') || manage },
  ].filter(tab => tab.allowed);
  const [tab, setTab] = useState(tabs[0]?.value);
  const [selected, setSelected] = useState(null);
  const [remise, setRemise] = useState(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState('');
  const [failure, setFailure] = useState(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const mounted = useRef(true);
  const client = useQueryClient();
  const base = resourceUrl(variant, 'bibliotheque');
  const queryKey = ['library', base];
  const currentTab = tabs.some(item => item.value === tab) ? tab : tabs[0]?.value;
  const catalogue = currentTab === 'livres';
  const loans = currentTab === 'emprunts';
  const list = useQuery({
    ...libraryQueryOptions,
    queryKey: [...queryKey, currentTab, page, pageSize, search],
    queryFn: ({ signal }) => fetchResourcePage(`${base}${currentTab}/`, {
      page: page + 1, page_size: pageSize, ...(catalogue ? { search } : {}),
    }, { signal }),
    enabled: Boolean(currentTab) && !failure,
  });
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      client.cancelQueries({ queryKey: ['library', base] });
      client.removeQueries({ queryKey: ['library', base] });
    };
  }, [base, client]);
  useEffect(() => {
    if (list.error) {
      setFailure(list.error);
      setNotice('');
      setSelected(null);
      setRemise(null);
      client.cancelQueries({ queryKey: ['library', base] });
      client.removeQueries({ queryKey: ['library', base] });
    }
  }, [base, client, list.error]);
  const fail = error => {
    if (!mounted.current) { return; }
    setNotice('');
    setFailure(error);
    setSelected(null);
    setRemise(null);
    client.cancelQueries({ queryKey });
    client.removeQueries({ queryKey });
  };
  const refresh = async () => {
    setNotice('');
    await client.invalidateQueries({ queryKey }, { throwOnError: true });
  };
  const command = async (endpoint, payload) => {
    if (sending.current) { return; }
    sending.current = true;
    setBusy(true);
    setNotice('');
    try {
      const result = await postApi(endpoint, payload);
      if (!result?.id) { throw new Error('Réponse de commande invalide. Rechargez la bibliothèque.'); }
      await refresh();
      if (mounted.current) {
        setRemise(null);
        setNotice('Opération confirmée par le serveur.');
      }
    } catch (error) {
      fail(error);
    } finally {
      sending.current = false;
      if (mounted.current) { setBusy(false); }
    }
  };
  if (!tabs.length) { return <Alert severity="warning">La bibliothèque nécessite une habilitation explicite.</Alert>; }
  if (failure || list.error) {
    return (
      <Alert severity="error">
        Bibliothèque indisponible. Les données précédemment chargées ont été masquées.
        {' '}{apiErrorMessage(failure || list.error)}
        <Button onClick={() => {
          setFailure(null); setSelected(null); setRemise(null); setNotice('');
          client.resetQueries({ queryKey });
        }}
        >Recharger la bibliothèque
        </Button>
      </Alert>
    );
  }
  let baseColumns = bookColumns;
  if (!catalogue) { baseColumns = loans ? loanColumns : reservationColumns; }
  const columns = [...baseColumns, {
    Header: 'Actions',
    accessor: 'id',
    Cell: libraryActions.bind(null, {
      catalogue,
      loans,
      manage,
      can,
      busy,
      base,
      currentTab,
      variant,
      command,
      select: value => { setTab('livres'); setSelected(value); setNotice(''); },
      remit: row => { setRemise(row); setNotice(''); },
    }),
  }];
  return (
    <Stack spacing={2}>
      <Typography variant="h4" component="h1">Bibliothèque</Typography>
      <Typography>Catalogue, ressources numériques, prêts et réservations de votre établissement.</Typography>
      <Tabs
        value={currentTab}
        onChange={(event, value) => {
          if (busy) { return; }
          setTab(value); setPage(0); setSearch(''); setSelected(null); setNotice(''); setRemise(null);
        }}
      >
        {tabs.map(item => <Tab key={item.value} value={item.value} label={item.label} disabled={busy} />)}
      </Tabs>
      {notice && !list.isFetching && <Alert severity="success">{notice}</Alert>}
      <SISDataTable
        key={currentTab}
        title={tabs.find(item => item.value === currentTab).label}
        columns={columns}
        data={!list.isFetching && !list.error ? list.data?.results || [] : []}
        loading={list.isFetching}
        searchable={catalogue}
        exportable={false}
        pageSize={25}
        onRefresh={busy ? undefined : () => refresh().catch(fail)}
        serverPagination={variant === 'secondaire' && currentTab === 'reservations' ? undefined : {
          page,
          pageSize,
          count: list.data?.count || 0,
          search,
          onPageChange: setPage,
          onPageSizeChange: size => { setPageSize(size); setPage(0); },
          onSearchChange: value => { setSearch(value); setPage(0); setSelected(null); setNotice(''); },
        }}
      />
      {selected && catalogue && (
        <Box component="section" aria-label="Détail du livre">
          <LibraryBook
            key={`${base}${selected}`}
            variant={variant}
            id={selected}
            capabilities={capabilities}
            busy={busy}
            onBusy={setBusy}
            onError={fail}
            onRefresh={async () => {
              await refresh();
              if (mounted.current) { setNotice('Fichier et licence enregistrés ; données actualisées.'); }
            }}
            onCommand={command}
          />
        </Box>
      )}
      {remise && (
        <LibraryLoanDialog
          variant={variant}
          livre={remise.livre}
          title={remise.livre_titre}
          reservation={remise}
          busy={busy}
          onClose={() => setRemise(null)}
          onError={fail}
          onSubmit={payload => command(`${base}${reservationResource(variant)}/${remise.id}/${variant === 'secondaire' ? 'fulfil' : 'recuperer'}/`, payload)}
        />
      )}
    </Stack>
  );
};
LibraryWorkspace.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  capabilities: PropTypes.shape({
    permissions: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
};

const BibliothequePage = ({ variant }) => {
  const capabilities = useCapabilities(variant, { retry: false });
  if (capabilities.error) { return <Alert severity="error">Permissions de bibliothèque indisponibles. {apiErrorMessage(capabilities.error)}</Alert>; }
  if (!capabilities.data || capabilities.isFetching) { return <Alert severity="info">Vérification des habilitations…</Alert>; }
  return <LibraryWorkspace key={`${variant}:${JSON.stringify(capabilities.data)}`} variant={variant} capabilities={capabilities.data} />;
};
BibliothequePage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default BibliothequePage;
