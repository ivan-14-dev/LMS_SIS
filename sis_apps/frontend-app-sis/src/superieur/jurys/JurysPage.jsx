import React from 'react';
import PropTypes from 'prop-types';
import { Badge } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useJurys } from '../../services/api';

const StatusCell = ({ value }) => {
  const variants = { planifie: 'warning', en_cours: 'info', cloture: 'success' };
  return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
};

StatusCell.propTypes = { value: PropTypes.string };

const JurysPage = () => {
  const { data: jurys = [], isLoading } = useJurys();

  const columns = [
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Année', accessor: 'annee_universitaire' },
    { Header: 'Session', accessor: 'session' },
    { Header: 'Date', accessor: 'date_jury' },
    { Header: 'Président', accessor: 'president_nom' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: StatusCell,
    },
  ];

  return (
    <div>
      <PageHeader title="Jurys de délibération" subtitle="Organisation et procès-verbaux" />
      <SISDataTable title="Liste des jurys" data={jurys} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default JurysPage;
