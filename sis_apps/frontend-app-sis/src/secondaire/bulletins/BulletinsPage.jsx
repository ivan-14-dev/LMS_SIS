import React, { useState } from 'react';
import { Badge, Button, Row, Col } from '@openedx/paragon';
import { Print, Download } from '@openedx/paragon/icons';
import {
 PageHeader, SISDataTable, StatCard, WorkflowHistoryPanel, WorkflowNotificationsPanel,
} from '../../components/common';
import { getSecondaireApiUrl, useBulletins } from '../../services/api';

const BulletinsPage = () => {
 const { data: bulletins = [], isLoading } = useBulletins();
 const [selectedBulletinId, setSelectedBulletinId] = useState(null);

 const downloadPdf = (id) => window.open(`${getSecondaireApiUrl()}/bulletins/${id}/pdf_officiel/`, '_blank', 'noopener,noreferrer');

  const columns = [
    { Header: 'Élève', accessor: 'eleve_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Période', accessor: 'periode_libelle' },
    { Header: 'Moyenne', accessor: 'moyenne_generale', Cell: ({ value }) => (value ? `${value}/20` : '—') },
    { Header: 'Rang', accessor: 'rang' },
    { Header: 'Matières individualisées', accessor: 'nb_matieres_individualisees' },
    {
      Header: 'Statut',
      accessor: 'publie',
      Cell: ({ row }) => {
        if (row.original.signe) {
          return <Badge variant="success">Signé</Badge>;
        }
        if (row.original.publie) {
          return <Badge variant="info">Publié</Badge>;
        }
        return <Badge variant="warning">Brouillon</Badge>;
      },
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
          <Button size="sm" variant="outline-info" className="ms-1" onClick={() => setSelectedBulletinId(value)}>
            Historique
          </Button>
        </>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Bulletins"
        subtitle="Bulletins officiels et publication"
      />
      <WorkflowNotificationsPanel apiType="secondaire" />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Total bulletins" value={bulletins.length} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Publiés" value={bulletins.filter((b) => b.publie).length} variant="info" />
        </Col>
        <Col md={3}>
          <StatCard title="Signés" value={bulletins.filter((b) => b.signe).length} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard
            title="Avec individualisation"
            value={bulletins.filter((b) => (b.nb_matieres_individualisees || 0) > 0).length}
            variant="warning"
          />
        </Col>
      </Row>
      <SISDataTable title="Bulletins de notes" data={bulletins} columns={columns} loading={isLoading} searchable exportable />
      <WorkflowHistoryPanel
        apiType="secondaire"
        endpoint={selectedBulletinId ? `bulletins/${selectedBulletinId}/historique/` : ''}
        title="Historique du bulletin"
      />
    </div>
  );
};

export default BulletinsPage;
