import React from 'react';
import { Row, Col, Badge } from '@openedx/paragon';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { usePaiements } from '../../services/api';
import { Money } from '@openedx/paragon/icons';

const PaiementsPage = () => {
  const { data: paiements = [], isLoading } = usePaiements();

  const columns = [
    { Header: 'Référence', accessor: 'reference' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Type', accessor: 'type_frais' },
    { Header: 'Montant', accessor: 'montant', Cell: ({ value }) => `${value} €` },
    { Header: 'Date', accessor: 'date_paiement' },
    { Header: 'Mode', accessor: 'mode_paiement' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = { en_attente: 'warning', valide: 'success', rejete: 'danger', rembourse: 'info' };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
  ];

  const totalPaiements = paiements.filter(p => p.statut === 'valide').reduce((sum, p) => sum + p.montant, 0);

  return (
    <div>
      <PageHeader title="Paiements" subtitle="Gestion des frais de scolarité" />
      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Total collecté" value={`${totalPaiements} €`} icon={<Money />} variant="success" />
        </Col>
        <Col md={4}>
          <StatCard title="En attente" value={paiements.filter(p => p.statut === 'en_attente').length} icon={<Money />} variant="warning" />
        </Col>
        <Col md={4}>
          <StatCard title="Paiements validés" value={paiements.filter(p => p.statut === 'valide').length} icon={<Money />} variant="primary" />
        </Col>
      </Row>
      <SISDataTable title="Historique des paiements" data={paiements} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default PaiementsPage;
