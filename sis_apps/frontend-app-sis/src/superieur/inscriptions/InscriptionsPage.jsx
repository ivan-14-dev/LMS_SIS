import React, { useState } from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Add } from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, WorkflowHistoryPanel, WorkflowNotificationsPanel,
} from '../../components/common';
import { useInscriptions } from '../../services/api';

const InscriptionsPage = () => {
  const { data: inscriptions = [], isLoading } = useInscriptions();
  const [selectedInscriptionId, setSelectedInscriptionId] = useState(null);

  const columns = [
    { Header: 'Matricule', accessor: 'etudiant_matricule' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Année', accessor: 'annee_universitaire_libelle' },
    { Header: 'Date inscription', accessor: 'date_inscription' },
    {
      Header: 'Statut',
      accessor: 'statut_display',
      Cell: ({ value }) => {
        const variants = {
          Validée: 'success',
          Provisoire: 'warning',
          Refusée: 'danger',
          Annulée: 'secondary',
        };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
    {
      Header: 'Workflow',
      accessor: 'id',
      Cell: ({ value }) => (
        <Button size="sm" variant="outline-info" onClick={() => setSelectedInscriptionId(value)}>
          Historique
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Inscriptions administratives"
        subtitle={`${inscriptions.length} inscriptions`}
        actions={<Button variant="primary" iconBefore={Add}>Nouvelle inscription</Button>}
      />
      <WorkflowNotificationsPanel apiType="superieur" />
      <SISDataTable
        title="Liste des inscriptions"
        data={inscriptions}
        columns={columns}
        loading={isLoading}
        searchable
        exportable
      />
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={selectedInscriptionId ? `inscriptions/${selectedInscriptionId}/historique/` : ''}
        title="Historique de l'inscription"
      />
    </div>
  );
};

export default InscriptionsPage;
