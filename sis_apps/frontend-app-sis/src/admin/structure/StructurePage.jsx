import React from 'react';
import { Row, Col, Card, Button, Badge, Tabs, Tab } from '@openedx/paragon';
import { Add, Edit, AccountTree } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useDepartements, useNiveaux, useMatieres, useSalles } from '../../services/api';

const StructurePage = () => {
  const { data: departements = [], isLoading: loadingDept } = useDepartements();
  const { data: niveaux = [], isLoading: loadingNiv } = useNiveaux();
  const { data: matieres = [], isLoading: loadingMat } = useMatieres();
  const { data: salles = [], isLoading: loadingSalles } = useSalles();

  const departementColumns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Responsable', accessor: 'responsable_nom' },
    { Header: 'Formations', accessor: 'nb_formations' },
    { Header: 'Enseignants', accessor: 'nb_enseignants' },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: () => <Button size="sm" variant="outline-primary" iconBefore={Edit}>Éditer</Button>,
    },
  ];

  const niveauColumns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Type', accessor: 'type' },
    { Header: 'Ordre', accessor: 'ordre' },
    {
      Header: 'Actif',
      accessor: 'actif',
      Cell: ({ value }) => <Badge variant={value ? 'success' : 'secondary'}>{value ? 'Oui' : 'Non'}</Badge>,
    },
  ];

  const matiereColumns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Coefficient', accessor: 'coefficient' },
    { Header: 'Catégorie', accessor: 'categorie' },
    {
      Header: 'Actif',
      accessor: 'actif',
      Cell: ({ value }) => <Badge variant={value ? 'success' : 'secondary'}>{value ? 'Oui' : 'Non'}</Badge>,
    },
  ];

  const salleColumns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Type', accessor: 'type' },
    { Header: 'Capacité', accessor: 'capacite' },
    { Header: 'Bâtiment', accessor: 'batiment' },
    { Header: 'Équipements', accessor: 'equipements' },
    {
      Header: 'Disponible',
      accessor: 'disponible',
      Cell: ({ value }) => <Badge variant={value ? 'success' : 'danger'}>{value ? 'Oui' : 'Non'}</Badge>,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Structure"
        subtitle="Configuration de la structure pédagogique et administrative"
      />

      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Départements" value={departements.length} icon={<AccountTree />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Niveaux" value={niveaux.length} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Matières" value={matieres.length} variant="info" />
        </Col>
        <Col md={3}>
          <StatCard title="Salles" value={salles.length} variant="warning" />
        </Col>
      </Row>

      <Tabs defaultActiveKey="departements">
        <Tab eventKey="departements" title="Départements">
          <div className="pt-3">
            <div className="mb-3">
              <Button variant="primary" iconBefore={Add}>Nouveau département</Button>
            </div>
            <SISDataTable title="" data={departements} columns={departementColumns} loading={loadingDept} searchable exportable />
          </div>
        </Tab>

        <Tab eventKey="niveaux" title="Niveaux">
          <div className="pt-3">
            <div className="mb-3">
              <Button variant="primary" iconBefore={Add}>Nouveau niveau</Button>
            </div>
            <SISDataTable title="" data={niveaux} columns={niveauColumns} loading={loadingNiv} searchable exportable />
          </div>
        </Tab>

        <Tab eventKey="matieres" title="Matières">
          <div className="pt-3">
            <div className="mb-3">
              <Button variant="primary" iconBefore={Add}>Nouvelle matière</Button>
            </div>
            <SISDataTable title="" data={matieres} columns={matiereColumns} loading={loadingMat} searchable exportable />
          </div>
        </Tab>

        <Tab eventKey="salles" title="Salles">
          <div className="pt-3">
            <div className="mb-3">
              <Button variant="primary" iconBefore={Add}>Nouvelle salle</Button>
            </div>
            <SISDataTable title="" data={salles} columns={salleColumns} loading={loadingSalles} searchable exportable />
          </div>
        </Tab>
      </Tabs>
    </div>
  );
};

export default StructurePage;
