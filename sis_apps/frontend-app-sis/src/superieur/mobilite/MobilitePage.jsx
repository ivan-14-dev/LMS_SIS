import React from 'react';
import { Badge } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useMobilites } from '../../services/api';

const MobilitePage = () => {
  const { data: mobilites = [], isLoading } = useMobilites();

  const columns = [
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Type', accessor: 'type_mobilite' },
    { Header: 'Destination', accessor: 'etablissement_partenaire' },
    { Header: 'Pays', accessor: 'pays' },
    { Header: 'Date début', accessor: 'date_debut' },
    { Header: 'Date fin', accessor: 'date_fin' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = { en_cours: 'info', termine: 'success', annule: 'danger' };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
  ];

  return (
    <div>
      <PageHeader title="Mobilité internationale" subtitle="Programmes d'échanges et partenariats" />
      <SISDataTable title="Mobilités" data={mobilites} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default MobilitePage;
