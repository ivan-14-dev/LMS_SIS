import React, { useState } from 'react';
import { Badge, Button, Row, Col } from '@openedx/paragon';
import { Add, People } from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, StatCard, WorkflowHistoryPanel, WorkflowNotificationsPanel,
} from '../../components/common';
import { useClasses } from '../../services/api';

const ClassesPage = () => {
  const { data: classes = [], isLoading } = useClasses();
  const [selectedClassId, setSelectedClassId] = useState(null);

  const columns = [
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Niveau', accessor: 'niveau_nom' },
    { Header: 'Année', accessor: 'annee_libelle' },
    { Header: 'Effectif', accessor: 'effectif' },
    { Header: 'Capacité max', accessor: 'effectif_max' },
    { Header: 'Prof. principal', accessor: 'prof_principal_nom' },
    {
      Header: 'Statut',
      accessor: 'effectif',
      Cell: ({ value }) => (
        <Badge variant={value > 0 ? 'success' : 'secondary'}>{value > 0 ? 'Active' : 'Préparation'}</Badge>
      ),
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: ({ value }) => (
        <>
          <Button size="sm" variant="outline-primary" iconBefore={People}>Liste élèves</Button>
          <Button size="sm" variant="outline-info" className="ms-1" onClick={() => setSelectedClassId(value)}>Historique</Button>
        </>
      ),
    },
  ];

  const totalEffectif = classes.reduce((sum, c) => sum + (c.effectif || 0), 0);

  return (
    <div>
      <PageHeader
        title="Classes"
        subtitle="Gestion des classes de l'établissement"
        actions={[
          { label: 'Nouvelle classe', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <WorkflowNotificationsPanel apiType="secondaire" />
      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Total classes" value={classes.length} variant="primary" />
        </Col>
        <Col md={4}>
          <StatCard title="Total élèves" value={totalEffectif} variant="success" />
        </Col>
        <Col md={4}>
          <StatCard title="Moy. élèves/classe" value={classes.length ? Math.round(totalEffectif / classes.length) : 0} variant="info" />
        </Col>
      </Row>
      <SISDataTable title="Liste des classes" data={classes} columns={columns} loading={isLoading} searchable exportable />
      <WorkflowHistoryPanel
        apiType="secondaire"
        endpoint={selectedClassId ? `classes/classes/${selectedClassId}/historique/` : ''}
        title="Historique de la classe"
      />
    </div>
  );
};

export default ClassesPage;
