import React from 'react';
import { Row, Col, Card, Tabs, Tab } from '@openedx/paragon';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useLaboratoires, useProjetsRecherche } from '../../services/api';
import { Science, Group, Article } from '@openedx/paragon/icons';

const RecherchePage = () => {
  const { data: laboratoires = [] } = useLaboratoires();
  const { data: projets = [] } = useProjetsRecherche();

  const labColumns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Directeur', accessor: 'directeur_nom' },
    { Header: 'Membres', accessor: 'nb_membres' },
    { Header: 'Thèmes', accessor: 'themes_recherche' },
  ];

  const projetColumns = [
    { Header: 'Titre', accessor: 'titre' },
    { Header: 'Responsable', accessor: 'responsable_nom' },
    { Header: 'Budget', accessor: 'budget', Cell: ({ value }) => `${value} €` },
    { Header: 'Date début', accessor: 'date_debut' },
    { Header: 'Date fin', accessor: 'date_fin' },
    { Header: 'Statut', accessor: 'statut' },
  ];

  return (
    <div>
      <PageHeader title="Recherche" subtitle="Laboratoires et projets de recherche" />

      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Laboratoires" value={laboratoires.length} icon={<Science />} variant="primary" />
        </Col>
        <Col md={4}>
          <StatCard title="Projets en cours" value={projets.filter(p => p.statut === 'en_cours').length} icon={<Article />} variant="success" />
        </Col>
        <Col md={4}>
          <StatCard title="Chercheurs" value="—" icon={<Group />} variant="warning" />
        </Col>
      </Row>

      <Card>
        <Card.Body>
          <Tabs defaultActiveKey="laboratoires">
            <Tab eventKey="laboratoires" title="Laboratoires">
              <div className="pt-3">
                <SISDataTable title="Laboratoires de recherche" data={laboratoires} columns={labColumns} searchable />
              </div>
            </Tab>
            <Tab eventKey="projets" title="Projets">
              <div className="pt-3">
                <SISDataTable title="Projets de recherche" data={projets} columns={projetColumns} searchable />
              </div>
            </Tab>
            <Tab eventKey="publications" title="Publications">
              <div className="pt-3">
                <p className="text-muted">Liste des publications scientifiques...</p>
              </div>
            </Tab>
          </Tabs>
        </Card.Body>
      </Card>
    </div>
  );
};

export default RecherchePage;
