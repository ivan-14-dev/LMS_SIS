import React from 'react';
import { Row, Col, Card, Tabs, Tab } from '@openedx/paragon';
import { useQuery } from '@tanstack/react-query';
import { PageHeader, StatCard, SISDataTable } from '../../components/common';
import { fetchApi, getSuperieurApiUrl } from '../../services/api';
import { People, School, Science, Grade } from '@openedx/paragon/icons';

const PortailDoyen = () => {
  const { data: stats } = useQuery({
    queryKey: ['portail-doyen-stats'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-doyen/statistiques/`),
  });

  const { data: formations = [] } = useQuery({
    queryKey: ['portail-doyen-formations'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-doyen/formations/`),
  });

  const formationColumns = [
    { Header: 'Formation', accessor: 'nom' },
    { Header: 'Étudiants', accessor: 'nb_etudiants' },
    { Header: 'Enseignants', accessor: 'nb_enseignants' },
    { Header: 'Taux réussite', accessor: 'taux_reussite', Cell: ({ value }) => `${value}%` },
    { Header: 'Moyenne', accessor: 'moyenne_generale', Cell: ({ value }) => `${value}/20` },
  ];

  return (
    <div>
      <PageHeader title="Portail Doyen" subtitle="Pilotage de la faculté" />

      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Total étudiants" value={stats?.total_etudiants || 0} icon={<People />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Enseignants" value={stats?.total_enseignants || 0} icon={<School />} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Laboratoires" value={stats?.total_laboratoires || 0} icon={<Science />} variant="info" />
        </Col>
        <Col md={3}>
          <StatCard title="Taux de réussite" value={`${stats?.taux_reussite_global || 0}%`} icon={<Grade />} variant="warning" />
        </Col>
      </Row>

      <Card>
        <Card.Body>
          <Tabs defaultActiveKey="formations">
            <Tab eventKey="formations" title="Vue par formation">
              <div className="pt-3">
                <SISDataTable
                  title="Performance des formations"
                  data={formations}
                  columns={formationColumns}
                  searchable
                  exportable
                />
              </div>
            </Tab>
            <Tab eventKey="departements" title="Vue par département">
              <div className="pt-3">
                <p className="text-muted">Statistiques par département...</p>
              </div>
            </Tab>
            <Tab eventKey="recherche" title="Recherche">
              <div className="pt-3">
                <p className="text-muted">Indicateurs recherche...</p>
              </div>
            </Tab>
          </Tabs>
        </Card.Body>
      </Card>
    </div>
  );
};

export default PortailDoyen;
