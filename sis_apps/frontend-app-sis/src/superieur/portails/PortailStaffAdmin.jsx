import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Card, Col, Row, Spinner,
} from '@openedx/paragon';
import {
  Assignment, Grade, People, School,
} from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, StatCard, WorkflowNotificationsPanel,
} from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { fetchApi, getSuperieurApiUrl } from '../../services/api';

const teacherRoles = ['enseignant', 'chercheur'];
const registrarRoles = ['scolarite', 'directeur_etudes', 'chef_departement', 'comptable'];
const leadershipRoles = ['doyen', 'vice_doyen', 'president', 'vice_president'];

const StaffAdminFallback = ({ role, groups = [] }) => {
  const navigate = useNavigate();
  return (
    <Card>
      <Card.Header><Card.Title>Accès staff / admin</Card.Title></Card.Header>
      <Card.Body>
        <p className="mb-3">
          Rôle détecté : <strong>{role || 'admin'}</strong>
        </p>
        <p className="small text-muted mb-3">Groupes résolus : {groups.join(', ') || 'aucun'}</p>
        <div className="d-grid gap-2">
          <Button variant="primary" onClick={() => navigate('/superieur/workflows')}>Centre workflow</Button>
          <Button variant="outline-primary" onClick={() => navigate('/superieur/inscriptions')}>Inscriptions</Button>
          <Button variant="outline-primary" onClick={() => navigate('/superieur/notes')}>Notes</Button>
          <Button variant="outline-primary" onClick={() => navigate('/admin/etablissement')}>Administration</Button>
        </div>
      </Card.Body>
    </Card>
  );
};

const PortailStaffAdmin = () => {
  const navigate = useNavigate();
  const { data: capabilities, isLoading: loadingCapabilities, isError: capabilitiesError } = useCapabilities('superieur');
  const role = capabilities?.role || '';
  const groups = capabilities?.groups || [];
  const permissions = capabilities?.permissions || [];
  const isLearner = ['etudiant', 'doctorant'].includes(role);
  const viewMode = teacherRoles.includes(role)
    ? 'teacher'
    : leadershipRoles.includes(role)
      ? 'leadership'
      : (registrarRoles.includes(role) || permissions.includes('*') || groups.includes('academic_admin_superieur'))
        ? 'registrar'
        : 'generic';

  const { data: teacherDashboard, isLoading: loadingTeacher, isError: teacherError } = useQuery({
    queryKey: ['superieur-portail-staff-teacher-dashboard'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/tableau_bord/`),
    enabled: viewMode === 'teacher',
  });
  const { data: notesASaisir = [] } = useQuery({
    queryKey: ['superieur-portail-staff-teacher-notes'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/notes_a_saisir/`),
    enabled: viewMode === 'teacher',
  });

  const { data: registrarDashboard, isLoading: loadingRegistrar, isError: registrarError } = useQuery({
    queryKey: ['superieur-portail-staff-registrar-dashboard'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/tableau_bord/`),
    enabled: viewMode === 'registrar',
  });
  const { data: registrarAlerts = [] } = useQuery({
    queryKey: ['superieur-portail-staff-registrar-alerts'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/alertes/`),
    enabled: viewMode === 'registrar',
  });

  const { data: leadershipDashboard, isLoading: loadingLeadership, isError: leadershipError } = useQuery({
    queryKey: ['superieur-portail-staff-leadership-dashboard'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/tableau_bord/`),
    enabled: viewMode === 'leadership',
  });
  const { data: formationStats = [] } = useQuery({
    queryKey: ['superieur-portail-staff-leadership-formations'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/staff/statistiques_formations/`),
    enabled: viewMode === 'leadership',
  });

  if (
    loadingCapabilities
    || loadingTeacher
    || loadingRegistrar
    || loadingLeadership
  ) {
    return <Spinner animation="border" screenReaderText="Chargement du portail staff" />;
  }

  if (capabilitiesError || isLearner) {
    return <Alert variant="danger">Ce portail est réservé au staff et aux administrateurs autorisés.</Alert>;
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
      if (teacherError || !teacherDashboard) {
        return <StaffAdminFallback role={role} groups={groups} />;
      }
      return (
        <>
          <Row className="mb-4">
            <Col md={4}>
              <StatCard title="Cours" value={teacherDashboard?.statistiques?.nb_cours ?? 0} icon={<School />} variant="primary" />
            </Col>
            <Col md={4}>
              <StatCard title="Heures" value={teacherDashboard?.statistiques?.heures_total ?? 0} icon={<Assignment />} variant="success" />
            </Col>
            <Col md={4}>
              <StatCard title="Notes à saisir" value={notesASaisir.length} icon={<Grade />} variant="warning" />
            </Col>
          </Row>
          <SISDataTable title="Notes à saisir" data={notesASaisir} columns={teacherColumns} searchable={false} exportable />
        </>
      );
    }
    if (viewMode === 'leadership') {
      if (leadershipError || !leadershipDashboard) {
        return <StaffAdminFallback role={role} groups={groups} />;
      }
      return (
        <>
          <Row className="mb-4">
            <Col md={3}>
              <StatCard title="Formations" value={leadershipDashboard?.statistiques?.nb_formations ?? 0} icon={<School />} variant="primary" />
            </Col>
            <Col md={3}>
              <StatCard title="Départements" value={leadershipDashboard?.statistiques?.nb_departements ?? 0} icon={<Assignment />} variant="success" />
            </Col>
            <Col md={3}>
              <StatCard title="Étudiants" value={leadershipDashboard?.statistiques?.nb_etudiants ?? 0} icon={<People />} variant="info" />
            </Col>
            <Col md={3}>
              <StatCard title="Enseignants" value={leadershipDashboard?.statistiques?.nb_enseignants ?? 0} icon={<School />} variant="warning" />
            </Col>
          </Row>
          <SISDataTable title="Statistiques des formations" data={formationStats} columns={formationColumns} searchable exportable />
        </>
      );
    }
    if (viewMode === 'registrar') {
      if (registrarError || !registrarDashboard) {
        return <StaffAdminFallback role={role} groups={groups} />;
      }
      const stats = registrarDashboard?.statistiques || {};
      return (
        <>
          <Row className="mb-4">
            <Col md={3}>
              <StatCard title="Étudiants actifs" value={stats.total_etudiants ?? 0} icon={<People />} variant="primary" />
            </Col>
            <Col md={3}>
              <StatCard title="Inscriptions année" value={stats.inscriptions_annee ?? 0} icon={<Assignment />} variant="success" />
            </Col>
            <Col md={3}>
              <StatCard title="Factures impayées" value={stats.factures_impayees ?? 0} icon={<Grade />} variant="warning" />
            </Col>
            <Col md={3}>
              <StatCard title="Montant impayé" value={stats.montant_impaye ?? 0} icon={<Grade />} variant="info" />
            </Col>
          </Row>
          <Row>
            <Col md={8}>
              <SISDataTable title="Inscriptions récentes" data={registrarDashboard?.inscriptions_recentes || []} columns={inscriptionColumns} searchable={false} exportable />
            </Col>
            <Col md={4}>
              <Card>
                <Card.Header><Card.Title>Alertes</Card.Title></Card.Header>
                <Card.Body>
                  {registrarAlerts.length ? registrarAlerts.map((alert, index) => (
                    <Alert key={index} variant={alert.niveau === 'warning' ? 'warning' : 'info'}>{alert.message}</Alert>
                  )) : <p className="text-muted mb-0">Aucune alerte.</p>}
                </Card.Body>
              </Card>
            </Col>
          </Row>
        </>
      );
    }
    return <StaffAdminFallback role={role} groups={groups} />;
  };

  return (
    <div>
      <PageHeader
        title="Portail staff / admin"
        subtitle={`Données affichées selon les permissions de ${role || 'staff'}`}
        actions={[
          { label: 'Workflows', variant: 'primary', onClick: () => navigate('/superieur/workflows') },
          { label: 'Inscriptions', variant: 'secondary', onClick: () => navigate('/superieur/inscriptions') },
        ]}
      />
      <WorkflowNotificationsPanel apiType="superieur" title="Notifications workflow staff / admin" />
      {renderContent()}
    </div>
  );
};

export default PortailStaffAdmin;
