import React, { useState } from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Print, Download } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, WorkflowHistoryPanel, WorkflowNotificationsPanel } from '../../components/common';
import { getSuperieurApiUrl, useReleves } from '../../services/api';

const RelevesPage = () => {
  const { data: releves = [], isLoading } = useReleves();
  const [selectedReleveId, setSelectedReleveId] = useState(null);

  const downloadPdf = (id) => window.open(`${getSuperieurApiUrl()}/releves/${id}/pdf_officiel/`, '_blank', 'noopener,noreferrer');

  const columns = [
    { Header: 'Série', accessor: 'numero_serie' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Semestre', accessor: 'semestre_nom' },
    { Header: 'Moyenne', accessor: 'moyenne_generale', Cell: ({ value }) => (value ? `${value}/20` : '—') },
    { Header: 'Mention', accessor: 'mention' },
    { Header: 'Crédits validés', accessor: 'credits_valides' },
    { Header: 'Date émission', accessor: 'date_emission' },
    {
      Header: 'Statut',
      accessor: 'signe',
      Cell: ({ value }) => <Badge variant={value ? 'success' : 'warning'}>{value ? 'Signé' : 'À signer'}</Badge>,
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: ({ value }) => (
        <>
          <Button size="sm" variant="outline-primary" iconBefore={Print} className="me-1" onClick={() => downloadPdf(value)}>
            Imprimer
          </Button>
          <Button size="sm" variant="outline-secondary" iconBefore={Download} onClick={() => downloadPdf(value)}>
            PDF
          </Button>
          <Button size="sm" variant="outline-info" className="ms-1" onClick={() => setSelectedReleveId(value)}>
            Historique
          </Button>
        </>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Relevés de notes" subtitle="Documents officiels semestriels" />
      <WorkflowNotificationsPanel apiType="superieur" />
      <SISDataTable title="Relevés de notes" data={releves} columns={columns} loading={isLoading} searchable exportable />
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={selectedReleveId ? `releves/${selectedReleveId}/historique/` : ''}
        title="Historique du relevé"
      />
    </div>
  );
};

export default RelevesPage;
