import React, { useState } from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Download } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, WorkflowHistoryPanel, WorkflowNotificationsPanel } from '../../components/common';
import { getSuperieurApiUrl, useDiplomes } from '../../services/api';

const DiplomesPage = () => {
  const { data: diplomes = [], isLoading } = useDiplomes();
  const [selectedDiplomeId, setSelectedDiplomeId] = useState(null);

  const downloadPdf = (id) => window.open(`${getSuperieurApiUrl()}/diplomes/${id}/pdf_officiel/`, '_blank', 'noopener,noreferrer');

  const columns = [
    { Header: 'Série', accessor: 'numero_serie' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Diplôme', accessor: 'diplome_nom' },
    { Header: 'Année', accessor: 'annee_libelle' },
    { Header: 'Mention', accessor: 'mention' },
    { Header: 'Date obtention', accessor: 'date_obtention' },
    {
      Header: 'Statut',
      accessor: 'date_signature',
      Cell: ({ value }) => <Badge variant={value ? 'success' : 'warning'}>{value ? 'Signé' : 'Préparé'}</Badge>,
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: ({ value }) => (
        <>
          <Button size="sm" variant="outline-secondary" iconBefore={Download} onClick={() => downloadPdf(value)}>
            PDF officiel
          </Button>
          <Button size="sm" variant="outline-info" className="ms-1" onClick={() => setSelectedDiplomeId(value)}>
            Historique
          </Button>
        </>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Diplômes" subtitle="Délivrances et documents officiels" />
      <WorkflowNotificationsPanel apiType="superieur" />
      <SISDataTable title="Liste des délivrances de diplômes" data={diplomes} columns={columns} loading={isLoading} searchable exportable />
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={selectedDiplomeId ? `diplomes/${selectedDiplomeId}/historique/` : ''}
        title="Historique du diplôme"
      />
    </div>
  );
};

export default DiplomesPage;
