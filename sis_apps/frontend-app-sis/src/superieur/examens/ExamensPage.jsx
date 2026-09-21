import React, { useState } from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Add } from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, WorkflowHistoryPanel, WorkflowNotificationsPanel,
} from '../../components/common';
import { useExamens } from '../../services/api';

const ExamensPage = () => {
  const { data: examens = [], isLoading } = useExamens();
  const [selectedExamenId, setSelectedExamenId] = useState(null);

  const columns = [
    { Header: 'ECUE', accessor: 'ecue_nom' },
    { Header: 'Type', accessor: 'session_numero' },
    { Header: 'Date', accessor: 'date' },
    { Header: 'Heure', accessor: 'heure_debut' },
    { Header: 'Lieu', accessor: 'lieu' },
    { Header: 'Durée', accessor: 'duree_minutes', Cell: ({ value }) => `${value} min` },
    { Header: 'Fin soumission', accessor: 'fin_soumission' },
    {
      Header: 'Statut',
      accessor: 'soumission_statut',
      Cell: ({ row }) => {
        const variants = {
          ouverte: row.original.soumission_alerte ? 'warning' : 'success',
          a_venir: 'info',
          fermee: 'danger',
          non_planifiee: 'light',
        };
        return <Badge variant={variants[row.original.soumission_statut] || 'secondary'}>{row.original.soumission_alerte?.message || row.original.soumission_statut}</Badge>;
      },
    },
    {
      Header: 'Workflow',
      accessor: 'id',
      Cell: ({ value }) => (
        <Button size="sm" variant="outline-info" onClick={() => setSelectedExamenId(value)}>
          Historique
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Gestion des examens"
        subtitle="Planning et organisation des examens"
        actions={<Button variant="primary" iconBefore={Add}>Planifier un examen</Button>}
      />
      <WorkflowNotificationsPanel apiType="superieur" />
      <SISDataTable title="Liste des examens" data={examens} columns={columns} loading={isLoading} searchable exportable />
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={selectedExamenId ? `examens/epreuves/${selectedExamenId}/historique/` : ''}
        title="Historique de l'épreuve"
      />
    </div>
  );
};

export default ExamensPage;
