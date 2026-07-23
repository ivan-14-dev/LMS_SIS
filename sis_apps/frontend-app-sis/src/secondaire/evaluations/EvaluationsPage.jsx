import React from 'react';
import { Badge, Button, Row, Col, Card } from '@openedx/paragon';
import { Add, Grade } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useEvaluations } from '../../services/api';

const EvaluationsPage = () => {
  const { data: evaluations = [], isLoading } = useEvaluations();

  const columns = [
    { Header: 'Titre', accessor: 'titre' },
    { Header: 'Matière', accessor: 'matiere_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Type', accessor: 'type' },
    { Header: 'Coefficient', accessor: 'coefficient' },
    { Header: 'Date', accessor: 'date' },
    {
      Header: 'Statut',
      accessor: 'notes_saisies',
      Cell: ({ row }) => (
        <Badge variant={row.original.notes_saisies ? 'success' : 'warning'}>
          {row.original.notes_saisies ? 'Notes saisies' : 'En attente'}
        </Badge>
      ),
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: () => (
        <Button size="sm" variant="outline-primary" iconBefore={Grade}>Saisir notes</Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Évaluations"
        subtitle="Gestion des évaluations et contrôles"
        actions={[
          { label: 'Nouvelle évaluation', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Total évaluations" value={evaluations.length} variant="primary" />
        </Col>
        <Col md={4}>
          <StatCard title="Notes saisies" value={evaluations.filter(e => e.notes_saisies).length} variant="success" />
        </Col>
        <Col md={4}>
          <StatCard title="En attente" value={evaluations.filter(e => !e.notes_saisies).length} variant="warning" />
        </Col>
      </Row>
      <SISDataTable title="Liste des évaluations" data={evaluations} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default EvaluationsPage;
