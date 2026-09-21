import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Card, Col, Row, Spinner,
} from '@openedx/paragon';
import {
  Class, EventNote, Grade, Person,
} from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, StatCard, WorkflowNotificationsPanel,
} from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { fetchApi, getSecondaireApiUrl } from '../../services/api';

const StaffAdminFallback = ({ role, groups = [] }) => {
  const navigate = useNavigate();
  return (
    <Card>
      <Card.Header><Card.Title>Accès staff / admin</Card.Title></Card.Header>
      <Card.Body>
        <p className="mb-3">
          Rôle détecté : <strong>{role || 'non défini'}</strong>
        </p>
        <p className="text-muted">
          Les données détaillées ne sont affichées que pour les profils disposant d&apos;un périmètre métier compatible.
        </p>
        <p className="small text-muted mb-3">Groupes résolus : {groups.join(', ') || 'aucun'}</p>
        <div className="d-grid gap-2">
          <Button variant="primary" onClick={() => navigate('/secondaire/workflows')}>Centre workflow</Button>
          <Button variant="outline-primary" onClick={() => navigate('/secondaire/classes')}>Classes</Button>
          <Button variant="outline-primary" onClick={() => navigate('/secondaire/evaluations')}>Évaluations</Button>
          <Button variant="outline-primary" onClick={() => navigate('/admin/etablissement')}>Administration</Button>
        </div>
      </Card.Body>
    </Card>
  );
};

const PortailStaffAdmin = () => {
  const navigate = useNavigate();
  const { data: capabilities, isLoading: loadingCapabilities, isError: capabilitiesError } = useCapabilities('secondaire');
  const role = capabilities?.role || '';
  const isLearner = ['eleve', 'parent'].includes(role);
  const isStaffPortalCandidate = !isLearner && Boolean(role || capabilities?.permissions?.length || capabilities?.groups?.length);

  const { data: dashboard, isLoading: loadingDashboard, isError: dashboardError } = useQuery({
    queryKey: ['secondaire-portail-staff-dashboard'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/staff/tableau_bord/`),
    enabled: isStaffPortalCandidate,
  });

  const { data: classes = [] } = useQuery({
    queryKey: ['secondaire-portail-staff-classes'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/staff/mes_classes/`),
    enabled: isStaffPortalCandidate,
  });

  const { data: absences = [] } = useQuery({
    queryKey: ['secondaire-portail-staff-absences'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/staff/absences_a_saisir/`),
    enabled: isStaffPortalCandidate,
  });

  if (loadingCapabilities || loadingDashboard) {
    return <Spinner animation="border" screenReaderText="Chargement du portail staff" />;
  }

  if (capabilitiesError || isLearner) {
    return <Alert variant="danger">Ce portail est réservé au staff et aux administrateurs autorisés.</Alert>;
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
    <div>
      <PageHeader
        title="Portail staff / admin"
        subtitle={dashboard?.enseignant?.nom || `Rôle ${role || 'staff'}`}
        actions={[
          { label: 'Workflows', variant: 'primary', onClick: () => navigate('/secondaire/workflows') },
          { label: 'Présences', variant: 'secondary', onClick: () => navigate('/secondaire/presences') },
        ]}
      />
      <WorkflowNotificationsPanel apiType="secondaire" title="Notifications workflow staff / admin" />
      {dashboardError || !dashboard ? (
        <StaffAdminFallback role={role} groups={capabilities?.groups} />
      ) : (
        <>
          <Row className="mb-4">
            <Col md={4}>
              <StatCard title="Affectations" value={stats.nb_affectations ?? 0} icon={<Person />} variant="primary" />
            </Col>
            <Col md={4}>
              <StatCard title="Classes" value={stats.nb_classes ?? 0} icon={<Class />} variant="success" />
            </Col>
            <Col md={4}>
              <StatCard title="Élèves suivis" value={stats.nb_eleves_total ?? 0} icon={<Grade />} variant="info" />
            </Col>
          </Row>
          <Row>
            <Col md={8}>
              <SISDataTable title="Classes accessibles" data={classes} columns={classColumns} searchable={false} exportable />
            </Col>
            <Col md={4}>
              <SISDataTable title="Absences à saisir" data={absences} columns={absencesColumns} searchable={false} exportable={false} />
              <div className="d-grid gap-2 mt-3">
                <Button variant="outline-primary" onClick={() => navigate('/secondaire/evaluations')}>Saisir des notes</Button>
                <Button variant="outline-primary" onClick={() => navigate('/secondaire/classes')}>Voir les classes</Button>
                <Button variant="outline-primary" onClick={() => navigate('/admin/etablissement')}>Paramétrage établissement</Button>
              </div>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
};

export default PortailStaffAdmin;
