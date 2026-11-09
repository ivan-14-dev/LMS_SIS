import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Chip, Stack, Tab, Tabs,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  PageHeader, SISDataTable, WorkflowHistoryPanel,
} from '../components/common';
import { useCapabilities } from '../components/auth/PermissionGuard';
import {
  apiErrorMessage, downloadPdf, exportRecords, fetchAllResourcePages, fetchResourcePage, resourceUrl,
} from '../services/resources';
import ArchivedDocuments from './ArchivedDocuments';
import SchoolBulletinWorkflow from './SchoolBulletinWorkflow';
import { hasCapability } from '../components/layout/navigation';

const categories = {
  secondaire: [{
    resource: 'bulletins',
    title: 'Bulletins',
    filename: 'bulletin',
    columns: [
      { Header: 'Élève', accessor: 'eleve_nom' }, { Header: 'Matricule', accessor: 'eleve_matricule' },
      { Header: 'Classe', accessor: 'classe_nom' }, { Header: 'Période', accessor: 'periode_libelle' },
      { Header: 'Moyenne', accessor: 'moyenne_generale' }, { Header: 'Décision', accessor: 'decision' },
    ],
  }],
  superieur: [{
    resource: 'releves',
    title: 'Relevés de notes',
    filename: 'releve',
    columns: [
      { Header: 'Série', accessor: 'numero_serie' }, { Header: 'Étudiant', accessor: 'etudiant_nom' },
      { Header: 'Semestre', accessor: 'semestre_nom' }, { Header: 'Moyenne', accessor: 'moyenne_generale' },
      { Header: 'Crédits validés', accessor: 'credits_valides' }, { Header: 'Date', accessor: 'date_emission' },
    ],
  }, {
    resource: 'releves/transcripts',
    title: 'Transcripts',
    filename: 'transcript',
    columns: [
      { Header: 'Série', accessor: 'numero_serie' }, { Header: 'Étudiant', accessor: 'etudiant_nom' },
      { Header: 'Diplôme préparé', accessor: 'diplome_prepare' }, { Header: 'Années couvertes', accessor: 'nb_annees' },
      { Header: 'Moyenne pondérée', accessor: 'moyenne_ponderee' },
      { Header: 'Crédits validés', accessor: 'credits_valides' }, { Header: 'Date', accessor: 'date_emission' },
    ],
  }, {
    resource: 'releves/attestations',
    title: 'Attestations',
    filename: 'attestation',
    columns: [
      { Header: 'Numéro', accessor: 'numero' }, { Header: 'Étudiant', accessor: 'etudiant_nom' },
      { Header: 'Type', accessor: 'type_display' }, { Header: 'Date', accessor: 'date_emission' },
      { Header: 'Validité', accessor: 'date_validite' },
    ],
  }],
};

const validationCell = (variant, cell) => {
  const { original } = cell.row;
  const available = variant === 'secondaire' ? original.publie : original.signe || original.signe_par;
  return <Chip size="small" label={available ? 'Disponible' : 'Brouillon'} color={available ? 'success' : 'default'} />;
};

const documentActions = (download, personal, setSelected, review, cell) => (
  <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap' }}>
    <Button disabled={download.isPending} onClick={() => download.mutate(cell.value)}>Télécharger le PDF</Button>
    {!personal && <Button onClick={() => setSelected(cell.value)}>Historique</Button>}
    {!personal && review && cell.row.original.calcule && (
      <Button onClick={() => review(cell.value)}>Vérifier le bulletin</Button>
    )}
  </Stack>
);

const DocumentList = ({
  category, variant, personal, capabilities,
}) => {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [review, setReview] = useState(null);
  const schoolManagement = variant === 'secondaire' && !personal;
  const canManage = hasCapability(capabilities, 'notes.view_bulletin') && hasCapability(capabilities, 'notes.change_bulletin');
  const canPrepare = canManage && hasCapability(capabilities, 'notes.add_bulletin');
  const url = resourceUrl(variant, category.resource);
  const query = useQuery({
    queryKey: ['documents', url, page, pageSize, search],
    queryFn: ({ signal }) => fetchResourcePage(url, { page: page + 1, page_size: pageSize, search }, { signal }),
  });
  const download = useMutation({
    mutationFn: id => downloadPdf(`${url}${id}/pdf_officiel/`, `${category.filename}-${id}.pdf`),
  });
  const exportList = useMutation({
    mutationFn: async () => {
      const records = await fetchAllResourcePages(url, { search });
      exportRecords(category.title, category.columns, records);
    },
  });
  const columns = [...category.columns];
  if (!personal) {
    columns.push({
      Header: 'Validation',
      accessor: 'signe',
      Cell: validationCell.bind(null, variant),
    });
  }
  columns.push({
    Header: 'Actions',
    accessor: 'id',
    Cell: documentActions.bind(null, download, personal, setSelected, schoolManagement ? setReview : null),
  });
  return (
    <Box role="tabpanel" aria-label={category.title} sx={{ mt: 2, minWidth: 0 }}>
      {schoolManagement && (
        <SchoolBulletinWorkflow
          key={review || 'new'}
          selectedId={review}
          onSelect={setReview}
          onClose={() => setReview(null)}
          canPrepare={canPrepare}
          canManage={canManage}
        />
      )}
      {(download.error || exportList.error) && <Alert severity="error" sx={{ mb: 2 }}>{apiErrorMessage(download.error || exportList.error)}</Alert>}
      {download.isPending && <Alert severity="info" sx={{ mb: 2 }}>Préparation du PDF…</Alert>}
      {download.isSuccess && <Alert severity="success" sx={{ mb: 2 }}>Téléchargement du PDF lancé.</Alert>}
      {query.error ? (
        <Alert severity="error" action={<Button onClick={() => query.refetch()}>Réessayer</Button>}>
          Impossible de charger les documents. {apiErrorMessage(query.error)}
        </Alert>
      ) : (
        <>
          <Button sx={{ mb: 2 }} disabled={query.isPending || exportList.isPending} onClick={() => exportList.mutate()}>
            {exportList.isPending ? 'Export en cours…' : 'Exporter la liste filtrée (CSV)'}
          </Button>
          <SISDataTable
            title={category.title}
            columns={columns}
            data={query.data?.results || []}
            loading={query.isPending}
            exportable={false}
            emptyMessage={search ? 'Aucun document ne correspond à la recherche.' : 'Aucun document disponible pour le moment.'}
            onRefresh={() => query.refetch()}
            serverPagination={{
              page,
              pageSize,
              search,
              count: query.data?.count || 0,
              onPageChange: setPage,
              onPageSizeChange: size => { setPageSize(size); setPage(0); },
              onSearchChange: value => { setSearch(value); setPage(0); },
            }}
          />
        </>
      )}
      {!personal && selected && (
        <WorkflowHistoryPanel
          apiType={variant}
          endpoint={selected ? `${category.resource}/${selected}/historique/` : ''}
          title="Historique du document"
        />
      )}
    </Box>
  );
};
DocumentList.propTypes = {
  category: PropTypes.shape({
    resource: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    filename: PropTypes.string.isRequired,
    columns: PropTypes.arrayOf(PropTypes.shape({
      Header: PropTypes.string.isRequired, accessor: PropTypes.string.isRequired,
    })).isRequired,
  }).isRequired,
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  personal: PropTypes.bool.isRequired,
  capabilities: PropTypes.shape({ permissions: PropTypes.arrayOf(PropTypes.string) }),
};
DocumentList.defaultProps = { capabilities: undefined };

const DocumentsPage = ({ variant, personal = true }) => {
  const [tab, setTab] = useState(0);
  const capabilities = useCapabilities(variant);
  const allowedRoles = variant === 'secondaire' ? ['eleve', 'parent'] : ['etudiant', 'doctorant'];
  const accessNotice = personal
    ? 'Seuls les documents publiés ou validés vous concernant sont accessibles.'
    : 'Les brouillons restent réservés aux gestionnaires habilités.';
  if (personal && capabilities.isLoading) { return <Alert severity="info">Chargement de votre espace documentaire…</Alert>; }
  if (personal && capabilities.isError) {
    return <Alert severity="error" action={<Button onClick={() => capabilities.refetch()}>Réessayer</Button>}>Impossible de vérifier vos accès.</Alert>;
  }
  if (personal && !allowedRoles.includes(capabilities.data?.role)) {
    return <Alert severity="warning">Cet espace est réservé aux apprenants et aux familles autorisées.</Alert>;
  }
  return (
    <>
      <PageHeader title={personal ? 'Mes documents' : 'Documents académiques'} subtitle="Documents établis par votre établissement, sans nouveau dossier à créer." />
      <Alert severity="info" sx={{ mb: 2 }}>
        {accessNotice}{' '}
        Les PDF sont générés à la demande.
        La validation administrative existante n’est pas une signature numérique vérifiable.
      </Alert>
      <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" scrollButtons="auto" aria-label="Catégories de documents">
        {categories[variant].map(category => <Tab key={category.resource} label={category.title} />)}
        <Tab label="Versions signées" />
      </Tabs>
      {tab === categories[variant].length ? <ArchivedDocuments variant={variant} /> : (
        <DocumentList key={`${variant}-${tab}`} category={categories[variant][tab]} variant={variant} personal={personal} capabilities={capabilities.data} />
      )}
    </>
  );
};
DocumentsPage.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  personal: PropTypes.bool,
};
export default DocumentsPage;
