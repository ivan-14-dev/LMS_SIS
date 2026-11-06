import React from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Box, Button, Card, CardContent, CardHeader, CircularProgress, Grid, Stack, Typography,
} from '@mui/material';
import {
  Class, Grade, Person,
} from '@mui/icons-material';
import {
  PageHeader, SectionNavigator, SISDataTable, StatCard, WorkflowNotificationsPanel,
} from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { canEnterPortal, hasCapability } from '../../components/layout/navigation';
import { fetchApi, getSecondaireApiUrl } from '../../services/api';

const StaffAdminFallback = ({ role, groups = [], capabilities }) => {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader title={<Typography component="h2" variant="h3" className="sis-card-title">Accès staff / admin</Typography>} />
      <CardContent>
        <Typography sx={{ mb: 2 }}>
          Rôle détecté : <strong>{role || 'non défini'}</strong>
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Les données détaillées ne sont affichées que pour les profils disposant d&apos;un périmètre métier compatible.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Groupes résolus : {groups.join(', ') || 'aucun'}</Typography>
        <Stack spacing={1}>
          <Button variant="contained" onClick={() => navigate('/secondaire/workflows')}>Centre workflow</Button>
          {hasCapability(capabilities, 'classes.view_classe') && <Button variant="outlined" onClick={() => navigate('/secondaire/classes')}>Classes</Button>}
          {hasCapability(capabilities, 'notes.view_evaluation') && <Button variant="outlined" onClick={() => navigate('/secondaire/evaluations')}>Évaluations</Button>}
          {hasCapability(capabilities, 'etablissement.change_etablissement') && <Button variant="outlined" onClick={() => navigate('/admin/etablissement?sis=secondaire')}>Administration</Button>}
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
  } = useCapabilities('secondaire', { refetchOnMount: false });
  const role = capabilities?.role || '';
  const isStaffPortalCandidate = canEnterPortal(capabilities, 'staff');
  const canViewClasses = hasCapability(capabilities, 'classes.view_classe');
  const canViewAbsences = hasCapability(capabilities, 'presences.view_presence');
  const canViewEvaluations = hasCapability(capabilities, 'notes.view_evaluation');
  const enabled = isStaffPortalCandidate && !checkingCapabilities && !capabilitiesError;

  const {
    data: dashboard, isLoading: loadingDashboard, isFetching: checkingDashboard, isError: dashboardError,
  } = useQuery({
    queryKey: ['secondaire-portail-staff-dashboard'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/staff/tableau_bord/`),
    enabled,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });

  const {
    data: classes = [], isLoading: loadingClasses, isFetching: checkingClasses, isError: classesError,
  } = useQuery({
    queryKey: ['secondaire-portail-staff-classes'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/staff/mes_classes/`),
    enabled: enabled && canViewClasses,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });

  const {
    data: absences = [], isLoading: loadingAbsences, isFetching: checkingAbsences, isError: absencesError,
  } = useQuery({
    queryKey: ['secondaire-portail-staff-absences'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/staff/absences_a_saisir/`),
    enabled: enabled && canViewAbsences,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });

  if (loadingCapabilities || checkingCapabilities || loadingDashboard || loadingClasses || loadingAbsences
      || (enabled && (checkingDashboard || (canViewClasses && checkingClasses)
        || (canViewAbsences && checkingAbsences)))) {
    return <CircularProgress aria-label="Chargement du portail staff" />;
  }

  if (capabilitiesError || !capabilities) {
    return <Alert severity="error">Impossible de vérifier vos permissions. Rechargez la page pour réessayer.</Alert>;
  }
  if (!isStaffPortalCandidate) {
    return <Alert severity="error">Ce portail est réservé au staff affilié et autorisé.</Alert>;
  }
  if (dashboardError || classesError || absencesError) {
    return <Alert severity="error">Impossible de charger votre activité pédagogique. Rechargez la page pour réessayer.</Alert>;
  }

  const stats = dashboard?.statistiques || {};
  const classColumns = [
    { Header: 'Classe', accessor: 'nom' },
    { Header: 'Niveau', accessor: 'niveau' },
    { Header: 'Matière', accessor: 'matiere' },
    { Header: 'Élèves', accessor: 'nb_eleves' },
    { Header: 'Heures/semaine', accessor: 'heures_semaine' },
  ];
  const absencesColumns = [
    { Header: 'Classe', accessor: 'classe' },
    { Header: 'Matière', accessor: 'matiere' },
    { Header: 'Heure', accessor: 'heure' },
  ];

  return (
    <Box>
      <PageHeader
        title="Mon activité pédagogique"
        subtitle={dashboard?.enseignant?.nom || `Rôle ${role || 'staff'}`}
        actions={[
          { label: 'Workflows', variant: 'primary', onClick: () => navigate('/secondaire/workflows') },
          ...(canViewAbsences ? [{ label: 'Présences', variant: 'secondary', onClick: () => navigate('/secondaire/presences') }] : []),
        ]}
      />
      {!dashboard ? (
        <StaffAdminFallback role={role} groups={capabilities?.groups} capabilities={capabilities} />
      ) : (
        <SectionNavigator
          label="Rubriques de mon activité pédagogique"
          sections={[
            {
              id: 'synthese',
              label: 'Synthèse de mon activité',
              content: (
                <Grid container spacing={3} sx={{ mb: 3 }}>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <StatCard title="Affectations" value={stats.nb_affectations ?? 0} icon={<Person />} variant="primary" />
                  </Grid>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <StatCard title="Classes" value={stats.nb_classes ?? 0} icon={<Class />} variant="success" />
                  </Grid>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <StatCard title="Élèves suivis" value={stats.nb_eleves_total ?? 0} icon={<Grade />} variant="info" />
                  </Grid>
                </Grid>
              ),
            },
            ...(canViewClasses ? [{
              id: 'classes',
              label: 'Classes accessibles',
              content: (
                <SISDataTable
                  title="Classes accessibles"
                  data={classes}
                  columns={classColumns}
                  searchable={false}
                  exportable={hasCapability(capabilities, 'portail.export_staff')}
                />
              ),
            }] : []),
            ...(canViewAbsences ? [{
              id: 'absences',
              label: 'Absences à saisir',
              content: (
                <>
                  <SISDataTable title="Absences à saisir" data={absences} columns={absencesColumns} searchable={false} exportable={false} />
                  <Stack spacing={1} sx={{ mt: 2 }}>
                    {canViewEvaluations && <Button variant="outlined" onClick={() => navigate('/secondaire/evaluations')}>Saisir des notes</Button>}
                    {canViewClasses && <Button variant="outlined" onClick={() => navigate('/secondaire/classes')}>Voir les classes</Button>}
                  </Stack>
                </>
              ),
            }] : []),
            { id: 'notifications', label: 'Notifications', content: <WorkflowNotificationsPanel apiType="secondaire" title="Notifications workflow staff / admin" /> },
          ]}
        />
      )}
    </Box>
  );
};

export default PortailStaffAdmin;
