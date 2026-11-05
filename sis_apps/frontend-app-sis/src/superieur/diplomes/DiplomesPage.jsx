import React, { useState } from 'react';
import { Button } from '@openedx/paragon';
import { Download } from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, StatusBadge, WorkflowHistoryPanel, WorkflowNotificationsPanel,
} from '../../components/common';
import { getSuperieurApiUrl, useDiplomes } from '../../services/api';

const diplomaStatus = cell => <StatusBadge value={cell.value ? 'signe' : 'prepare'} />;
const diplomaActions = (id, onDownload, onHistory) => (
  <>
    <Button size="sm" variant="outline-secondary" iconBefore={Download} onClick={() => onDownload(id)}>
      PDF officiel
    </Button>
    <Button size="sm" variant="outline-info" className="ms-1" onClick={() => onHistory(id)}>
      Historique
    </Button>
  </>
);

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
      Cell: diplomaStatus,
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: cell => diplomaActions(cell.value, downloadPdf, setSelectedDiplomeId),
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
