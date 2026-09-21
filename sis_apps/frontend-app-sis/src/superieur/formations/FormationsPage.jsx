import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge, Button } from '@openedx/paragon';
import { Add } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, WorkflowHistoryPanel, WorkflowNotificationsPanel } from '../../components/common';
import { useFormations } from '../../services/api';

const FormationsPage = () => {
  const navigate = useNavigate();
  const { data: formations = [], isLoading } = useFormations();
  const [selectedFormationId, setSelectedFormationId] = useState(null);

  const columns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Département', accessor: 'departement_nom' },
    { Header: 'Niveau', accessor: 'niveau_display' },
    { Header: 'Durée', accessor: 'duree_annees', Cell: ({ value }) => `${value} an(s)` },
    { Header: 'Crédits ECTS', accessor: 'credits_total' },
    {
      Header: 'Statut',
      accessor: 'actif',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'secondary'}>
          {value ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      Header: 'Workflow',
      accessor: 'id',
      Cell: ({ value }) => (
        <Button size="sm" variant="outline-info" onClick={(event) => { event.stopPropagation(); setSelectedFormationId(value); }}>
          Historique
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Gestion des formations"
        subtitle={`${formations.length} formations`}
        actions={
          <Button variant="primary" iconBefore={Add}>
            Nouvelle formation
          </Button>
        }
      />
      <WorkflowNotificationsPanel apiType="superieur" />
      <SISDataTable
        title="Liste des formations"
        data={formations}
        columns={columns}
        loading={isLoading}
        onRowClick={(row) => navigate(`/superieur/formations/${row.original.id}`)}
        searchable
        exportable
      />
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={selectedFormationId ? `formations/formations/${selectedFormationId}/historique/` : ''}
        title="Historique de la formation"
      />
    </div>
  );
};

export default FormationsPage;
