import React from 'react';
import { Row, Col, Card, Button } from '@openedx/paragon';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  PageHeader, StatCard, SISDataTable, WorkflowNotificationsPanel,
} from '../../components/common';
import { fetchApi, getSuperieurApiUrl } from '../../services/api';
import { People, CalendarMonth, Grade, Science } from '@openedx/paragon/icons';

const PortailEnseignant = () => {
  const navigate = useNavigate();
  const { data: profil } = useQuery({
    queryKey: ['portail-enseignant-profil'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-enseignant/mon-profil/`),
  });

  const { data: cours = [] } = useQuery({
    queryKey: ['portail-enseignant-cours'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-enseignant/mes-cours/`),
  });

  const coursColumns = [
    { Header: 'ECUE', accessor: 'ecue_nom' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Jour', accessor: 'jour_display' },
    { Header: 'Horaire', accessor: 'horaire' },
    { Header: 'Salle', accessor: 'salle_code' },
  ];

  return (
    <div>
      <PageHeader
        title="Mon espace enseignant"
        subtitle={profil ? `${profil.nom} ${profil.prenom} - ${profil.grade}` : 'Chargement...'}
        actions={[
          { label: 'Notes', variant: 'primary', onClick: () => navigate('/superieur/notes') },
          { label: 'Examens', variant: 'secondary', onClick: () => navigate('/superieur/examens') },
          { label: 'Workflows', variant: 'secondary', onClick: () => navigate('/superieur/workflows') },
        ]}
      />
      <WorkflowNotificationsPanel apiType="superieur" title="Notifications workflow de l’enseignant" />

      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Mes étudiants" value={profil?.nb_etudiants || 0} icon={<People />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Cours cette semaine" value={cours.length} icon={<CalendarMonth />} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Notes à saisir" value={profil?.notes_en_attente || 0} icon={<Grade />} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Encadrements" value={profil?.nb_encadrements || 0} icon={<Science />} variant="info" />
        </Col>
      </Row>

      <Row>
        <Col md={8}>
          <Card className="mb-4">
            <Card.Header><Card.Title>Mon emploi du temps</Card.Title></Card.Header>
            <Card.Body>
              <SISDataTable
                title=""
                data={cours}
                columns={coursColumns}
                searchable={false}
                exportable={false}
              />
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="mb-4">
            <Card.Header><Card.Title>Actions rapides</Card.Title></Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                <Button variant="primary" onClick={() => navigate('/superieur/notes')}>Saisir des notes</Button>
                <Button variant="outline-primary" onClick={() => navigate('/superieur/etudiants')}>Consulter mes étudiants</Button>
                <Button variant="outline-primary" onClick={() => navigate('/superieur/examens')}>Examens</Button>
                <Button variant="outline-primary" onClick={() => navigate('/superieur/workflows')}>Centre workflow</Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PortailEnseignant;
