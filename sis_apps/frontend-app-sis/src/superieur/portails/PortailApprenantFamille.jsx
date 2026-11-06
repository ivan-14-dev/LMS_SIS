import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Box, CircularProgress, Grid,
} from '@mui/material';
import {
  Grade, Money, School,
} from '@mui/icons-material';
import {
  PageHeader, SISDataTable, StatCard,
} from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { canEnterPortal } from '../../components/layout/navigation';
import { fetchApi, getSuperieurApiUrl } from '../../services/api';
import { apiErrorMessage } from '../../services/resources';
import RecordsTabs from '../../components/common/RecordsTabs';

const PortailApprenantFamille = () => {
  const {
    data: capabilities, isLoading: loadingCapabilities, isFetching: checkingCapabilities, isError: capabilitiesError,
  } = useCapabilities('superieur', { refetchOnMount: false });
  const isLearner = canEnterPortal(capabilities, 'learner');

  const {
    data: dashboard, isLoading: loadingDashboard, isFetching: checkingDashboard, error: dashboardError,
  } = useQuery({
    queryKey: ['superieur-portail-apprenant-dashboard'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/apprenant/tableau_bord/`),
    enabled: isLearner && !checkingCapabilities && !capabilitiesError,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });

  const {
    data: releves = [], isLoading: loadingReleves, isFetching: checkingReleves, error: relevesError,
  } = useQuery({
    queryKey: ['superieur-portail-apprenant-releves'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/apprenant/releves/`),
    enabled: isLearner && !checkingCapabilities && !capabilitiesError,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });

  if (loadingCapabilities || checkingCapabilities || loadingDashboard || loadingReleves
      || (isLearner && (checkingDashboard || checkingReleves))) {
    return <CircularProgress aria-label="Chargement du portail apprenant" />;
  }

  if (capabilitiesError || !capabilities) {
    return <Alert severity="error">Impossible de vérifier vos permissions. Rechargez la page pour réessayer.</Alert>;
  }
  if (!isLearner) {
    return <Alert severity="error">Ce portail est réservé aux étudiants affiliés et autorisés.</Alert>;
  }
  if (dashboardError || relevesError) {
    return <Alert severity="error">Impossible de charger votre dossier. {apiErrorMessage(dashboardError || relevesError)}</Alert>;
  }

  const stats = dashboard?.statistiques || {};
  const notes = dashboard?.notes_recentes || [];
  const factures = dashboard?.factures_impayees || [];
  const notesColumns = [
    { Header: 'ECUE', accessor: 'ecue' },
    { Header: 'UE', accessor: 'ue' },
    { Header: 'Note', accessor: 'note' },
    { Header: 'Statut', accessor: 'statut' },
    { Header: 'Date', accessor: 'date' },
  ];
  const relevesColumns = [
    { Header: 'Semestre', accessor: 'semestre' },
    { Header: 'Moyenne', accessor: 'moyenne' },
    { Header: 'Crédits validés', accessor: 'credits_valides' },
    { Header: 'Mention', accessor: 'mention' },
    { Header: 'Date émission', accessor: 'date_emission' },
  ];
  const facturesColumns = [
    { Header: 'Numéro', accessor: 'numero' },
    { Header: 'Montant', accessor: 'montant' },
    { Header: 'Reste à payer', accessor: 'reste_a_payer' },
    { Header: 'Échéance', accessor: 'echeance' },
    { Header: 'Statut', accessor: 'statut' },
  ];

  return (
    <Box>
      <PageHeader
        title="Mon espace étudiant"
        subtitle={dashboard?.etudiant ? `${dashboard.etudiant.nom} · ${dashboard.etudiant.matricule}` : 'Espace étudiant'}
      />
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard title="Moyenne" value={stats.moyenne ?? '—'} icon={<Grade />} variant="primary" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard title="Crédits validés" value={stats.credits_valides ?? 0} icon={<School />} variant="success" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard title="Notes récentes" value={notes.length} icon={<Grade />} variant="info" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard title="Factures impayées" value={factures.length} icon={<Money />} variant="warning" />
        </Grid>
      </Grid>
      <RecordsTabs
        label="Mon dossier universitaire"
        panels={[
          { label: 'Notes récentes', content: <SISDataTable title="Notes récentes" showTitle={false} data={notes} columns={notesColumns} searchable={false} exportable={false} /> },
          { label: 'Relevés de notes', content: <SISDataTable title="Relevés de notes" showTitle={false} data={releves} columns={relevesColumns} searchable={false} exportable={false} /> },
          { label: 'Factures en attente', content: <SISDataTable title="Factures en attente" showTitle={false} data={factures} columns={facturesColumns} searchable={false} exportable={false} /> },
        ]}
      />
    </Box>
  );
};

export default PortailApprenantFamille;
