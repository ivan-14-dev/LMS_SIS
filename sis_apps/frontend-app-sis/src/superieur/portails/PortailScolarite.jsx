import React from 'react';
import { Row, Col, Card, Button } from '@openedx/paragon';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  PageHeader, StatCard, SISDataTable, WorkflowNotificationsPanel,
} from '../../components/common';
import { fetchApi, getSuperieurApiUrl } from '../../services/api';
import { People, Assignment, Money, School } from '@openedx/paragon/icons';

const PortailScolarite = () => {
  const navigate = useNavigate();
  const { data: stats } = useQuery({
    queryKey: ['portail-scolarite-stats'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-scolarite/statistiques/`),
  });

  const { data: inscriptionsRecentes = [] } = useQuery({
    queryKey: ['portail-scolarite-inscriptions'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-scolarite/inscriptions-recentes/`),
  });

  const inscriptionColumns = [
    { Header: 'Matricule', accessor: 'etudiant_matricule' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Date', accessor: 'date_inscription' },
    { Header: 'Statut', accessor: 'statut' },
  ];

  return (
    <div>
      <PageHeader
        title="Portail Scolarité"
        subtitle="Gestion administrative des étudiants"
        actions={[
          { label: 'Inscriptions', variant: 'primary', onClick: () => navigate('/superieur/inscriptions') },
          { label: 'Paiements', variant: 'secondary', onClick: () => navigate('/superieur/paiements') },
          { label: 'Workflows', variant: 'secondary', onClick: () => navigate('/superieur/workflows') },
        ]}
      />
      <WorkflowNotificationsPanel apiType="superieur" title="Notifications workflow de la scolarité" />

      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Étudiants inscrits" value={stats?.total_etudiants || 0} icon={<People />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Inscriptions en attente" value={stats?.inscriptions_en_attente || 0} icon={<Assignment />} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Paiements en attente" value={stats?.paiements_en_attente || 0} icon={<Money />} variant="danger" />
        </Col>
        <Col md={3}>
          <StatCard title="Formations actives" value={stats?.formations_actives || 0} icon={<School />} variant="success" />
        </Col>
      </Row>

      <Row>
        <Col md={8}>
          <Card className="mb-4">
            <Card.Header><Card.Title>Inscriptions récentes</Card.Title></Card.Header>
            <Card.Body>
              <SISDataTable
                title=""
                data={inscriptionsRecentes}
                columns={inscriptionColumns}
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
                <Button variant="primary" onClick={() => navigate('/superieur/inscriptions')}>Nouvelle inscription</Button>
                <Button variant="outline-primary" onClick={() => navigate('/superieur/paiements')}>Valider les paiements</Button>
                <Button variant="outline-primary" onClick={() => navigate('/superieur/diplomes')}>Éditer certificats</Button>
                <Button variant="outline-primary" onClick={() => navigate('/superieur/releves')}>Relevés de notes</Button>
              </div>
            </Card.Body>
          </Card>

          <Card>
            <Card.Header><Card.Title>Raccourcis workflow</Card.Title></Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                <Button variant="outline-primary" onClick={() => navigate('/superieur/workflows')}>Centre workflow</Button>
                <Button variant="outline-primary" onClick={() => navigate('/superieur/examens')}>Suivre les examens</Button>
                <Button variant="outline-primary" onClick={() => navigate('/superieur/notes')}>Suivre les notes</Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PortailScolarite;
