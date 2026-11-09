import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Box, CircularProgress, Grid,
} from '@mui/material';
import {
  EventNote, Grade, Money, Person,
} from '@mui/icons-material';
import {
  PageHeader, SISDataTable, StatCard,
} from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { canEnterPortal } from '../../components/layout/navigation';
import { fetchApi, getSecondaireApiUrl } from '../../services/api';
import { apiErrorMessage } from '../../services/resources';
import RecordsTabs from '../../components/common/RecordsTabs';
import ChildFamilyRecord from './ChildFamilyRecord';
import AdmissionRequestPanel from '../../components/common/AdmissionRequestPanel';

const PortailApprenantFamille = () => {
  const {
    data: capabilities, isLoading: loadingCapabilities, isFetching: checkingCapabilities, isError: capabilitiesError,
  } = useCapabilities('secondaire', { refetchOnMount: false });
  const isEleve = canEnterPortal(capabilities, 'learner');
  const isParent = !isEleve && canEnterPortal(capabilities, 'parent');

  const {
    data: eleveDashboard, isLoading: loadingEleve, isFetching: checkingEleve, error: eleveError,
  } = useQuery({
    queryKey: ['secondaire-portail-apprenant-eleve-dashboard'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/apprenant/tableau_bord/`),
    enabled: isEleve && !checkingCapabilities && !capabilitiesError,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });

  const {
    data: bulletins = [], error: bulletinsError, isLoading: loadingBulletins, isFetching: checkingBulletins,
  } = useQuery({
    queryKey: ['secondaire-portail-apprenant-eleve-bulletins'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/apprenant/bulletins/`),
    enabled: isEleve && !checkingCapabilities && !capabilitiesError,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });

  const {
    data: parentDashboard, isLoading: loadingParent, isFetching: checkingParent, error: parentError,
  } = useQuery({
    queryKey: ['secondaire-portail-apprenant-parent-dashboard'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/apprenant/tableau_bord/`),
    enabled: isParent && !checkingCapabilities && !capabilitiesError,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });

  if (loadingCapabilities || checkingCapabilities
      || (isEleve && (loadingEleve || checkingEleve || loadingBulletins || checkingBulletins))
      || (isParent && (loadingParent || checkingParent))) {
    return <CircularProgress aria-label="Chargement du portail" />;
  }

  if (capabilitiesError || !capabilities) {
    return <Alert severity="error">Impossible de vérifier vos permissions. Rechargez la page pour réessayer.</Alert>;
  }
  if (!isEleve && !isParent) {
    return <Alert severity="error">Ce portail est réservé aux élèves et parents affiliés et autorisés.</Alert>;
  }
  if (eleveError || bulletinsError || parentError) {
    return <Alert severity="error">Impossible de charger votre dossier. {apiErrorMessage(eleveError || bulletinsError || parentError)}</Alert>;
  }

  if (isEleve) {
    const stats = eleveDashboard?.statistiques || {};
    const notes = eleveDashboard?.notes_recentes || [];
    const notesColumns = [
      { Header: 'Évaluation', accessor: 'evaluation' },
      { Header: 'Matière', accessor: 'matiere' },
      { Header: 'Note', accessor: 'note' },
      { Header: 'Période', accessor: 'periode' },
      { Header: 'Date', accessor: 'date' },
    ];
    const bulletinColumns = [
      { Header: 'Période', accessor: 'periode' },
      { Header: 'Classe', accessor: 'classe' },
      { Header: 'Moyenne', accessor: 'moyenne' },
      { Header: 'Rang', accessor: 'rang' },
      { Header: 'Décision', accessor: 'decision' },
      { Header: 'Publié le', accessor: 'publie_le' },
    ];

    return (
      <Box>
        <PageHeader
          title="Mon espace élève"
          subtitle={eleveDashboard?.eleve ? `${eleveDashboard.eleve.nom} · ${eleveDashboard?.classe?.nom || 'Sans classe'}` : 'Espace élève'}
        />
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard title="Moyenne" value={stats.moyenne ?? '—'} icon={<Grade />} variant="primary" />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard title="Rang" value={stats.rang ?? '—'} icon={<Person />} variant="success" />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard title="Absences" value={stats.absences ?? 0} icon={<EventNote />} variant="warning" />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard title="Retards" value={stats.retards ?? 0} icon={<EventNote />} variant="info" />
          </Grid>
        </Grid>
        <RecordsTabs
          label="Mon dossier scolaire"
          panels={[
            { label: 'Notes récentes', content: <SISDataTable title="Notes récentes" showTitle={false} data={notes} columns={notesColumns} searchable={false} exportable={false} /> },
            { label: 'Bulletins publiés', content: <SISDataTable title="Bulletins publiés" showTitle={false} data={bulletins} columns={bulletinColumns} searchable={false} exportable={false} /> },
            { label: 'Admissions et inscriptions', content: <AdmissionRequestPanel variant="secondaire" /> },
          ]}
        />
      </Box>
    );
  }

  const enfants = parentDashboard?.enfants || [];
  const factures = parentDashboard?.factures_impayees || [];
  const enfantsColumns = [
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Classe', accessor: 'classe' },
    { Header: 'Niveau', accessor: 'niveau' },
    { Header: 'Moyenne', accessor: 'moyenne' },
    { Header: 'Rang', accessor: 'rang' },
    { Header: 'Absences', accessor: 'absences' },
    { Header: 'Retards', accessor: 'retards' },
  ];
  const facturesColumns = [
    { Header: 'Élève', accessor: 'eleve' },
    { Header: 'Numéro', accessor: 'numero' },
    { Header: 'Montant', accessor: 'montant' },
    { Header: 'Reste à payer', accessor: 'reste_a_payer' },
    { Header: 'Échéance', accessor: 'echeance' },
    { Header: 'Statut', accessor: 'statut' },
  ];

  return (
    <Box>
      <PageHeader
        title="Mon espace famille"
        subtitle="Vue parent avec données limitées aux enfants autorisés"
      />
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard title="Enfants suivis" value={enfants.length} icon={<Person />} variant="primary" />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard title="Factures impayées" value={factures.length} icon={<Money />} variant="warning" />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard title="Absences cumulées" value={enfants.reduce((total, enfant) => total + (enfant.absences || 0), 0)} icon={<EventNote />} variant="info" />
        </Grid>
      </Grid>
      <RecordsTabs
        label="Dossiers de ma famille"
        panels={[
          { label: 'Enfants autorisés', content: <SISDataTable title="Enfants autorisés" showTitle={false} data={enfants} columns={enfantsColumns} searchable={false} exportable={false} /> },
          { label: 'Factures en attente', content: <SISDataTable title="Factures en attente" showTitle={false} data={factures} columns={facturesColumns} searchable={false} exportable={false} /> },
        ]}
      />
      <ChildFamilyRecord pupils={enfants} />
    </Box>
  );
};

export default PortailApprenantFamille;
