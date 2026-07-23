import React from 'react';
import { Badge, Button, Row, Col, Tabs, Tab } from '@openedx/paragon';
import { Add, LocalHospital } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useVisitesInfirmerie, useDossiersMediaux } from '../../services/api';

const InfirmeriePage = () => {
  const { data: visitesData, isLoading: loadingVisites } = useVisitesInfirmerie();
  const { data: dossiersData, isLoading: loadingDossiers } = useDossiersMediaux();
  
  const visites = Array.isArray(visitesData) ? visitesData : [];
  const dossiers = Array.isArray(dossiersData) ? dossiersData : [];

  const visitesColumns = [
    { Header: 'Date', accessor: 'date' },
    { Header: 'Heure', accessor: 'heure' },
    { Header: 'Élève', accessor: 'eleve_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Motif', accessor: 'motif' },
    { Header: 'Soins', accessor: 'soins_prodigues' },
    {
      Header: 'Suite',
      accessor: 'suite',
      Cell: ({ value }) => {
        const variants = {
          retour_classe: 'success',
          repos_infirmerie: 'warning',
          retour_maison: 'danger',
          urgences: 'danger',
        };
        return <Badge variant={variants[value] || 'secondary'}>{value?.replace('_', ' ')}</Badge>;
      },
    },
  ];

  const dossiersColumns = [
    { Header: 'Matricule', accessor: 'eleve_matricule' },
    { Header: 'Élève', accessor: 'eleve_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Groupe sanguin', accessor: 'groupe_sanguin' },
    { Header: 'Allergies', accessor: 'allergies' },
    { Header: 'Maladies chroniques', accessor: 'maladies_chroniques' },
    {
      Header: 'Vaccins à jour',
      accessor: 'vaccins_a_jour',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'warning'}>{value ? 'Oui' : 'Non'}</Badge>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Infirmerie"
        subtitle="Suivi médical et sanitaire des élèves"
        actions={[
          { label: 'Nouvelle visite', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Visites (mois)" value={visites.length} icon={<LocalHospital />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Retours classe" value={visites.filter(v => v.suite === 'retour_classe').length} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Retours maison" value={visites.filter(v => v.suite === 'retour_maison').length} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Urgences" value={visites.filter(v => v.suite === 'urgences').length} variant="danger" />
        </Col>
      </Row>

      <Tabs defaultActiveKey="visites">
        <Tab eventKey="visites" title="Visites">
          <div className="pt-3">
            <SISDataTable title="" data={visites} columns={visitesColumns} loading={loadingVisites} searchable exportable />
          </div>
        </Tab>
        <Tab eventKey="dossiers" title="Dossiers médicaux">
          <div className="pt-3">
            <SISDataTable title="" data={dossiers} columns={dossiersColumns} loading={loadingDossiers} searchable exportable />
          </div>
        </Tab>
      </Tabs>
    </div>
  );
};

export default InfirmeriePage;
