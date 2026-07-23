import React from 'react';
import { Badge, Button, Row, Col, Tabs, Tab } from '@openedx/paragon';
import { Add, DirectionsBus } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useInscritsTransport, useCircuits, useVehicules } from '../../services/api';

const TransportPage = () => {
  const { data: inscritsData, isLoading: loadingInscrits } = useInscritsTransport();
  const { data: circuitsData, isLoading: loadingCircuits } = useCircuits();
  const { data: vehiculesData } = useVehicules();
  
  const inscrits = Array.isArray(inscritsData) ? inscritsData : [];
  const circuits = Array.isArray(circuitsData) ? circuitsData : [];
  const vehicules = Array.isArray(vehiculesData) ? vehiculesData : [];

  const inscritsColumns = [
    { Header: 'Matricule', accessor: 'eleve_matricule' },
    { Header: 'Élève', accessor: 'eleve_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Circuit', accessor: 'circuit_nom' },
    { Header: 'Arrêt', accessor: 'arret' },
    {
      Header: 'Paiement',
      accessor: 'paiement_ok',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'danger'}>{value ? 'À jour' : 'Impayé'}</Badge>
      ),
    },
  ];

  const circuitsColumns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Véhicule', accessor: 'vehicule_immatriculation' },
    { Header: 'Chauffeur', accessor: 'chauffeur_nom' },
    { Header: 'Élèves', accessor: 'nb_eleves' },
    { Header: 'Arrêts', accessor: 'nb_arrets' },
    {
      Header: 'Statut',
      accessor: 'actif',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'secondary'}>{value ? 'Actif' : 'Inactif'}</Badge>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Transport"
        subtitle="Gestion du transport scolaire"
        actions={[
          { label: 'Nouvelle inscription', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Élèves transportés" value={inscrits.length} icon={<DirectionsBus />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Circuits actifs" value={circuits.filter(c => c.actif).length} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Véhicules" value={vehicules.length} variant="info" />
        </Col>
        <Col md={3}>
          <StatCard title="Paiements en retard" value={inscrits.filter(i => !i.paiement_ok).length} variant="danger" />
        </Col>
      </Row>

      <Tabs defaultActiveKey="inscrits">
        <Tab eventKey="inscrits" title="Élèves inscrits">
          <div className="pt-3">
            <SISDataTable title="" data={inscrits} columns={inscritsColumns} loading={loadingInscrits} searchable exportable />
          </div>
        </Tab>
        <Tab eventKey="circuits" title="Circuits">
          <div className="pt-3">
            <SISDataTable title="" data={circuits} columns={circuitsColumns} loading={loadingCircuits} searchable exportable />
          </div>
        </Tab>
      </Tabs>
    </div>
  );
};

export default TransportPage;
