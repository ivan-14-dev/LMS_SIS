import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Row, Col, Badge, Button,
} from '@openedx/paragon';
import { Money } from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, StatCard, WorkflowHistoryPanel, WorkflowNotificationsPanel,
} from '../../components/common';
import { usePaiements } from '../../services/api';

const StatusCell = ({ value }) => {
  const variants = {
    en_attente: 'warning', valide: 'success', rejete: 'danger', rembourse: 'info',
  };
  return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
};

StatusCell.propTypes = { value: PropTypes.string };

const createActionCell = (onSelect) => {
  const ActionCell = ({ value }) => (
    <Button size="sm" variant="outline-info" onClick={() => onSelect(value)}>
      Historique
    </Button>
  );
  ActionCell.propTypes = { value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]) };
  return ActionCell;
};

const PaiementsPage = () => {
  const { data: paiements = [], isLoading } = usePaiements();
  const [selectedPaiementId, setSelectedPaiementId] = useState(null);
  const actionCell = useMemo(() => createActionCell(setSelectedPaiementId), [setSelectedPaiementId]);

  const columns = [
    { Header: 'Référence', accessor: 'numero' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Facture', accessor: 'facture_numero' },
    { Header: 'Montant', accessor: 'montant', Cell: ({ value }) => `${value} €` },
    { Header: 'Date', accessor: 'date_paiement' },
    { Header: 'Mode', accessor: 'mode_display' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: StatusCell,
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: actionCell,
    },
  ];

  const totalPaiements = paiements.filter(p => p.statut === 'valide').reduce((sum, p) => sum + p.montant, 0);

  return (
    <div>
      <PageHeader title="Paiements" subtitle="Gestion des frais de scolarité" />
      <WorkflowNotificationsPanel apiType="superieur" />
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
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={selectedPaiementId ? `paiements/transactions/${selectedPaiementId}/historique/` : ''}
        title="Historique du paiement"
      />
    </div>
  );
};

export default PaiementsPage;
