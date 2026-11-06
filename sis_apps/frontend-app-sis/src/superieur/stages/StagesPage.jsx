import React from 'react';
import PropTypes from 'prop-types';
import { Badge } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useStages } from '../../services/api';

const StatusCell = ({ value }) => {
  const variants = {
    en_cours: 'info', termine: 'success', valide: 'success', annule: 'danger',
  };
  return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
};

StatusCell.propTypes = { value: PropTypes.string };

const StagesPage = () => {
  const { data: stages = [], isLoading } = useStages();

  const columns = [
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Entreprise', accessor: 'entreprise_nom' },
    { Header: 'Sujet', accessor: 'sujet' },
    { Header: 'Date début', accessor: 'date_debut' },
    { Header: 'Date fin', accessor: 'date_fin' },
    { Header: 'Tuteur', accessor: 'tuteur_nom' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: StatusCell,
    },
  ];

  return (
    <div>
      <PageHeader title="Gestion des stages" subtitle="Conventions et suivi" />
      <SISDataTable title="Liste des stages" data={stages} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default StagesPage;
