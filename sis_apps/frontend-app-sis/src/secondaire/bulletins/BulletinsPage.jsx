import React from 'react';
import { Badge, Button, Row, Col } from '@openedx/paragon';
import { Print, Download } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useBulletins } from '../../services/api';

const BulletinsPage = () => {
  const { data: bulletins = [], isLoading } = useBulletins();

  const columns = [
    { Header: 'Élève', accessor: 'eleve_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Trimestre', accessor: 'trimestre' },
    { Header: 'Moyenne', accessor: 'moyenne', Cell: ({ value }) => value ? `${value}/20` : '—' },
    { Header: 'Rang', accessor: 'rang' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => (
        <Badge variant={value === 'valide' ? 'success' : value === 'genere' ? 'info' : 'warning'}>
          {value}
        </Badge>
      ),
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: () => (
        <>
          <Button size="sm" variant="outline-primary" iconBefore={Print} className="me-1">Imprimer</Button>
          <Button size="sm" variant="outline-secondary" iconBefore={Download}>PDF</Button>
        </>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Bulletins"
        subtitle="Génération et impression des bulletins de notes"
        actions={[
          { label: 'Générer bulletins', variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Bulletins générés" value={bulletins.filter(b => b.statut !== 'en_attente').length} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Validés" value={bulletins.filter(b => b.statut === 'valide').length} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="En attente" value={bulletins.filter(b => b.statut === 'en_attente').length} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Trimestre actif" value="T1" variant="info" />
        </Col>
      </Row>
      <SISDataTable title="Bulletins de notes" data={bulletins} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default BulletinsPage;
