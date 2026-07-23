import React from 'react';
import { Badge, Button, Row, Col } from '@openedx/paragon';
import { Add, Warning } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useSanctions } from '../../services/api';

const DisciplinePage = () => {
  const { data: sanctions = [], isLoading } = useSanctions();

  const columns = [
    { Header: 'Date', accessor: 'date' },
    { Header: 'Élève', accessor: 'eleve_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    {
      Header: 'Type',
      accessor: 'type',
      Cell: ({ value }) => {
        const variants = {
          avertissement: 'warning',
          blame: 'danger',
          exclusion_temporaire: 'danger',
          conseil_discipline: 'dark',
        };
        return <Badge variant={variants[value] || 'secondary'}>{value.replace('_', ' ')}</Badge>;
      },
    },
    { Header: 'Motif', accessor: 'motif' },
    { Header: 'Décision', accessor: 'decision' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => (
        <Badge variant={value === 'applique' ? 'success' : value === 'en_cours' ? 'warning' : 'secondary'}>
          {value}
        </Badge>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Discipline"
        subtitle="Gestion des sanctions et incidents disciplinaires"
        actions={[
          { label: 'Nouvelle sanction', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Total sanctions" value={sanctions.length} icon={<Warning />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Avertissements" value={sanctions.filter(s => s.type === 'avertissement').length} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Blâmes" value={sanctions.filter(s => s.type === 'blame').length} variant="danger" />
        </Col>
        <Col md={3}>
          <StatCard title="Exclusions" value={sanctions.filter(s => s.type === 'exclusion_temporaire').length} variant="dark" />
        </Col>
      </Row>
      <SISDataTable title="Sanctions disciplinaires" data={sanctions} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default DisciplinePage;
