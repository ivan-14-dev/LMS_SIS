import React from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Print, Download } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable } from '../../components/common';
import { getSuperieurApiUrl, useReleves } from '../../services/api';

const RelevesPage = () => {
  const { data: releves = [], isLoading } = useReleves();

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
        </>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Relevés de notes" subtitle="Documents officiels semestriels" />
      <SISDataTable title="Relevés de notes" data={releves} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default RelevesPage;
