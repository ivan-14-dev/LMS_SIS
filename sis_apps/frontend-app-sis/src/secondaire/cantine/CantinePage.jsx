import React from 'react';
import { Badge, Button, Row, Col, Tabs, Tab } from '@openedx/paragon';
import { Add, Restaurant } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useInscritsCantin, useRepas, useMenus } from '../../services/api';

const CantinePage = () => {
  const { data: inscritsData, isLoading: loadingInscrits } = useInscritsCantin();
  const { data: repasData, isLoading: loadingRepas } = useRepas();
  const { data: menusData } = useMenus();
  
  const inscrits = Array.isArray(inscritsData) ? inscritsData : [];
  const repas = Array.isArray(repasData) ? repasData : [];
  const menus = Array.isArray(menusData) ? menusData : [];

  const inscritsColumns = [
    { Header: 'Matricule', accessor: 'eleve_matricule' },
    { Header: 'Élève', accessor: 'eleve_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Régime', accessor: 'regime' },
    {
      Header: 'Statut paiement',
      accessor: 'paiement_ok',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'danger'}>{value ? 'À jour' : 'Impayé'}</Badge>
      ),
    },
    { Header: 'Allergies', accessor: 'allergies' },
  ];

  const repasColumns = [
    { Header: 'Date', accessor: 'date' },
    { Header: 'Service', accessor: 'service' },
    { Header: 'Élèves servis', accessor: 'nb_eleves' },
    { Header: 'Menu', accessor: 'menu_nom' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => (
        <Badge variant={value === 'termine' ? 'success' : value === 'en_cours' ? 'warning' : 'secondary'}>
          {value}
        </Badge>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Cantine"
        subtitle="Gestion de la restauration scolaire"
        actions={[
          { label: 'Nouvelle inscription', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Inscrits cantine" value={inscrits.length} icon={<Restaurant />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Repas servis (mois)" value={repas.reduce((sum, r) => sum + r.nb_eleves, 0)} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Paiements en retard" value={inscrits.filter(i => !i.paiement_ok).length} variant="danger" />
        </Col>
        <Col md={3}>
          <StatCard title="Menus actifs" value={menus.filter(m => m.actif).length} variant="info" />
        </Col>
      </Row>

      <Tabs defaultActiveKey="inscrits">
        <Tab eventKey="inscrits" title="Élèves inscrits">
          <div className="pt-3">
            <SISDataTable title="" data={inscrits} columns={inscritsColumns} loading={loadingInscrits} searchable exportable />
          </div>
        </Tab>
        <Tab eventKey="repas" title="Historique repas">
          <div className="pt-3">
            <SISDataTable title="" data={repas} columns={repasColumns} loading={loadingRepas} searchable exportable />
          </div>
        </Tab>
      </Tabs>
    </div>
  );
};

export default CantinePage;
