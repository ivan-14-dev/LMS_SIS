import React, { useState } from 'react';
import { Badge, Button, Row, Col } from '@openedx/paragon';
import { Add, Grade } from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, StatCard, WorkflowHistoryPanel, WorkflowNotificationsPanel,
} from '../../components/common';
import { useEvaluations } from '../../services/api';

const EvaluationsPage = () => {
  const { data: evaluations = [], isLoading } = useEvaluations();
  const [selectedEvaluationId, setSelectedEvaluationId] = useState(null);

  const columns = [
    { Header: 'Titre', accessor: 'titre' },
    { Header: 'Matière', accessor: 'matiere_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Type', accessor: 'type_display' },
    { Header: 'Coefficient', accessor: 'coefficient' },
    { Header: 'Date', accessor: 'date' },
    {
      Header: 'Cible',
      accessor: 'individualisee',
      Cell: ({ row }) => (
        row.original.individualisee
          ? `Individuelle (${row.original.eleve_cible_nom || row.original.eleve_cible_matricule || 'élève ciblé'})`
          : 'Classe entière'
      ),
    },
    {
      Header: 'Statut',
      accessor: 'notes_saisies',
      Cell: ({ row }) => (
        <Badge variant={row.original.notes_saisies ? 'success' : 'warning'}>
          {row.original.notes_saisies ? `${row.original.nb_notes || 0} note(s)` : 'En attente'}
        </Badge>
      ),
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: ({ value }) => (
        <div className="d-flex gap-2">
          <Button size="sm" variant="outline-primary" iconBefore={Grade}>Saisir notes</Button>
          <Button size="sm" variant="outline-info" onClick={() => setSelectedEvaluationId(value)}>Historique</Button>
        </div>
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
      <WorkflowNotificationsPanel apiType="secondaire" />
      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Total évaluations" value={evaluations.length} variant="primary" />
        </Col>
        <Col md={4}>
          <StatCard title="Notes saisies" value={evaluations.filter(e => e.notes_saisies).length} variant="success" />
        </Col>
        <Col md={4}>
          <StatCard title="Évaluations individuelles" value={evaluations.filter(e => e.individualisee).length} variant="warning" />
        </Col>
      </Row>
      <SISDataTable title="Liste des évaluations" data={evaluations} columns={columns} loading={isLoading} searchable exportable />
      <WorkflowHistoryPanel
        apiType="secondaire"
        endpoint={selectedEvaluationId ? `notes/evaluations/${selectedEvaluationId}/historique/` : ''}
        title="Historique de l'évaluation"
      />
    </div>
  );
};

export default EvaluationsPage;
