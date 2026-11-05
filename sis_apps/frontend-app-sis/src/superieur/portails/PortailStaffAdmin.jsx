import React from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Box, Button, Card, CardContent, CardHeader, CircularProgress, Grid, Stack, Typography,
} from '@mui/material';
import {
  Assignment, Grade, People, School,
} from '@mui/icons-material';
import {
  PageHeader, SectionNavigator, SISDataTable, StatCard, WorkflowNotificationsPanel,
} from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { canEnterPortal, hasCapability } from '../../components/layout/navigation';
import { fetchApi, getSuperieurApiUrl } from '../../services/api';

const StaffAdminFallback = ({ role, groups = [], capabilities }) => {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader title={<Typography component="h2" variant="h3" className="sis-card-title">Accès staff / admin</Typography>} />
      <CardContent>
        <Typography sx={{ mb: 2 }}>
          Rôle détecté : <strong>{role || 'admin'}</strong>
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Groupes résolus : {groups.join(', ') || 'aucun'}</Typography>
        <Stack spacing={1}>
          <Button variant="contained" onClick={() => navigate('/superieur/workflows')}>Centre workflow</Button>
          {hasCapability(capabilities, 'etudiants.view_inscriptionadministrative') && <Button variant="outlined" onClick={() => navigate('/superieur/inscriptions')}>Inscriptions</Button>}
          {hasCapability(capabilities, 'notes.view_note') && <Button variant="outlined" onClick={() => navigate('/superieur/notes')}>Notes</Button>}
          {hasCapability(capabilities, 'etablissement.change_universite') && <Button variant="outlined" onClick={() => navigate('/admin/etablissement?sis=superieur')}>Administration</Button>}
        </Stack>
      </CardContent>
    </Card>
  );
};
StaffAdminFallback.propTypes = {
  role: PropTypes.string,
  groups: PropTypes.arrayOf(PropTypes.string),
  capabilities: PropTypes.shape({ permissions: PropTypes.arrayOf(PropTypes.string) }),
};
StaffAdminFallback.defaultProps = { role: '', groups: [], capabilities: null };

const PortailStaffAdmin = () => {
  const navigate = useNavigate();
  const {
    data: capabilities, isLoading: loadingCapabilities, isFetching: checkingCapabilities, isError: capabilitiesError,
  } = useCapabilities('superieur', { refetchOnMount: false });
  const role = capabilities?.role || '';
  const groups = capabilities?.groups || [];
  const isStaff = canEnterPortal(capabilities, 'staff');
  const canViewNotes = hasCapability(capabilities, 'notes.view_note');
  const canViewStudents = hasCapability(capabilities, 'etudiants.view_etudiant');
  const canViewFormations = hasCapability(capabilities, 'formations.view_formation');
  const canViewInscriptions = hasCapability(capabilities, 'etudiants.view_inscriptionadministrative');
  const enabled = isStaff && !checkingCapabilities && !capabilitiesError;
  let viewMode = 'generic';
  if (['enseignant', 'chercheur'].includes(role) && canViewNotes) {
    viewMode = 'teacher';
  } else if (['doyen', 'vice_doyen', 'president', 'vice_president'].includes(role) && canViewFormations) {
    viewMode = 'leadership';
  } else if (canViewStudents) {
    viewMode = 'registrar';
  } else if (canViewFormations) {
    viewMode = 'leadership';
  }
  const secondaryActions = [];
  if (viewMode === 'teacher' && canViewNotes) {
    secondaryActions.push({ label: 'Saisir des notes', variant: 'secondary', onClick: () => navigate('/superieur/notes') });
  } else if (canViewInscriptions) {
    secondaryActions.push({ label: 'Inscriptions', variant: 'secondary', onClick: () => navigate('/superieur/inscriptions') });
  }

  const { data: teacherDashboard, isLoading: loadingTeacher, isError: teacherError } = useQuery({
    queryKey: ['superieur-portail-staff-teacher-dashboard'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/tableau_bord/`),
    enabled: enabled && viewMode === 'teacher',
  });
  const { data: notesASaisir = [], isLoading: loadingNotes, isError: notesError } = useQuery({
    queryKey: ['superieur-portail-staff-teacher-notes'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/notes_a_saisir/`),
    enabled: enabled && viewMode === 'teacher' && canViewNotes,
  });

  const { data: registrarDashboard, isLoading: loadingRegistrar, isError: registrarError } = useQuery({
    queryKey: ['superieur-portail-staff-registrar-dashboard'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/tableau_bord/`),
    enabled: enabled && viewMode === 'registrar',
  });
  const { data: registrarAlerts = [], isLoading: loadingAlerts, isError: alertsError } = useQuery({
    queryKey: ['superieur-portail-staff-registrar-alerts'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/alertes/`),
    enabled: enabled && viewMode === 'registrar' && canViewStudents,
  });

  const { data: leadershipDashboard, isLoading: loadingLeadership, isError: leadershipError } = useQuery({
    queryKey: ['superieur-portail-staff-leadership-dashboard'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/tableau_bord/`),
    enabled: enabled && viewMode === 'leadership',
  });
  const { data: formationStats = [], isLoading: loadingFormations, isError: formationsError } = useQuery({
    queryKey: ['superieur-portail-staff-leadership-formations'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/statistiques_formations/`),
    enabled: enabled && viewMode === 'leadership' && canViewFormations,
  });

  if (
    loadingCapabilities
    || checkingCapabilities
    || loadingTeacher
    || loadingRegistrar
    || loadingLeadership
    || loadingNotes
    || loadingAlerts
    || loadingFormations
  ) {
    return <CircularProgress aria-label="Chargement du portail staff" />;
  }

  if (capabilitiesError || !capabilities) {
    return <Alert severity="error">Impossible de vérifier vos permissions. Rechargez la page pour réessayer.</Alert>;
  }
  if (!isStaff) {
    return <Alert severity="error">Ce portail est réservé au staff affilié et autorisé.</Alert>;
  }
  if (teacherError || registrarError || leadershipError || notesError || alertsError || formationsError) {
    return <Alert severity="error">Impossible de charger votre activité. Rechargez la page pour réessayer.</Alert>;
  }

  const teacherColumns = [
    { Header: 'Titre', accessor: 'titre' },
    { Header: 'ECUE', accessor: 'ecue_nom' },
    { Header: 'Semestre', accessor: 'semestre' },
    { Header: 'Modalité', accessor: 'modalite' },
    { Header: 'Notes saisies', accessor: 'notes_saisies' },
  ];
  const inscriptionColumns = [
    { Header: 'Étudiant', accessor: 'etudiant' },
    { Header: 'Matricule', accessor: 'matricule' },
    { Header: 'Formation', accessor: 'formation' },
    { Header: 'Date', accessor: 'date' },
    { Header: 'Statut', accessor: 'statut' },
  ];
  const formationColumns = [
    { Header: 'Formation', accessor: 'nom' },
    { Header: 'Département', accessor: 'departement' },
    { Header: 'Inscrits', accessor: 'nb_inscrits' },
    { Header: 'Niveau', accessor: 'niveau' },
  ];

  const renderContent = () => {
    if (viewMode === 'teacher') {
      if (!teacherDashboard) {
        return <StaffAdminFallback role={role} groups={groups} capabilities={capabilities} />;
      }
      return (
        <>
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, md: 4 }}>
              <StatCard title="Cours" value={teacherDashboard?.statistiques?.nb_cours ?? 0} icon={<School />} variant="primary" />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <StatCard title="Heures" value={teacherDashboard?.statistiques?.heures_total ?? 0} icon={<Assignment />} variant="success" />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <StatCard title="Notes à saisir" value={notesASaisir.length} icon={<Grade />} variant="warning" />
            </Grid>
          </Grid>
          <SISDataTable
            title="Notes à saisir"
            data={notesASaisir}
            columns={teacherColumns}
            searchable={false}
            exportable={hasCapability(capabilities, 'portail.export_staff')}
          />
        </>
      );
    }
    if (viewMode === 'leadership') {
      if (!leadershipDashboard) {
        return <StaffAdminFallback role={role} groups={groups} capabilities={capabilities} />;
      }
      return (
        <>
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard title="Formations" value={leadershipDashboard?.statistiques?.nb_formations ?? 0} icon={<School />} variant="primary" />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard title="Départements" value={leadershipDashboard?.statistiques?.nb_departements ?? 0} icon={<Assignment />} variant="success" />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard title="Étudiants" value={leadershipDashboard?.statistiques?.nb_etudiants ?? 0} icon={<People />} variant="info" />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard title="Enseignants" value={leadershipDashboard?.statistiques?.nb_enseignants ?? 0} icon={<School />} variant="warning" />
            </Grid>
          </Grid>
          <SISDataTable
            title="Statistiques des formations"
            data={formationStats}
            columns={formationColumns}
            searchable
            exportable={hasCapability(capabilities, 'portail.export_staff')}
          />
        </>
      );
    }
    if (viewMode === 'registrar') {
      if (!registrarDashboard) {
        return <StaffAdminFallback role={role} groups={groups} capabilities={capabilities} />;
      }
      const stats = registrarDashboard?.statistiques || {};
      return (
        <>
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard title="Étudiants actifs" value={stats.total_etudiants ?? 0} icon={<People />} variant="primary" />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard title="Inscriptions année" value={stats.inscriptions_annee ?? 0} icon={<Assignment />} variant="success" />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard title="Factures impayées" value={stats.factures_impayees ?? 0} icon={<Grade />} variant="warning" />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
              <StatCard title="Montant impayé" value={stats.montant_impaye ?? 0} icon={<Grade />} variant="info" />
            </Grid>
          </Grid>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, lg: 8 }}>
              <SISDataTable
                title="Inscriptions récentes"
                data={registrarDashboard?.inscriptions_recentes || []}
                columns={inscriptionColumns}
                searchable={false}
                exportable={hasCapability(capabilities, 'portail.export_staff')}
              />
            </Grid>
            <Grid size={{ xs: 12, lg: 4 }}>
              <Card>
                <CardHeader title={<Typography component="h2" variant="h3" className="sis-card-title">Alertes</Typography>} />
                <CardContent>
                  {registrarAlerts.length ? registrarAlerts.map(alert => (
                    <Alert key={`${alert.niveau}-${alert.message}`} severity={alert.niveau === 'warning' ? 'warning' : 'info'} sx={{ mb: 1 }}>{alert.message}</Alert>
                  )) : <Typography color="text.secondary">Aucune alerte.</Typography>}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </>
      );
    }
    return <StaffAdminFallback role={role} groups={groups} capabilities={capabilities} />;
  };

  return (
    <Box>
      <PageHeader
        title={viewMode === 'teacher' ? 'Mon activité pédagogique' : 'Mon espace administratif'}
        subtitle={`Données affichées selon les permissions de ${role || 'staff'}`}
        actions={[
          { label: 'Workflows', variant: 'primary', onClick: () => navigate('/superieur/workflows') },
          ...secondaryActions,
        ]}
      />
      <SectionNavigator
        label="Rubriques de mon activité"
        sections={[
          { id: 'activite', label: 'Mon activité', content: renderContent() },
          { id: 'notifications', label: 'Notifications', content: <WorkflowNotificationsPanel apiType="superieur" title="Notifications workflow staff / admin" /> },
        ]}
      />
    </Box>
  );
};

export default PortailStaffAdmin;
