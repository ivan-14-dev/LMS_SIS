import React from 'react';
import { Badge } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useDiplomes } from '../../services/api';

const DiplomesPage = () => {
  const { data: diplomes = [], isLoading } = useDiplomes();

  const columns = [
    { Header: 'Numéro', accessor: 'numero_diplome' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Mention', accessor: 'mention' },
    { Header: 'Date délivrance', accessor: 'date_delivrance' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = { en_preparation: 'warning', imprime: 'info', delivre: 'success', retire: 'success' };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
  ];

  return (
    <div>
      <PageHeader title="Diplômes" subtitle="Gestion et délivrance des diplômes" />
      <SISDataTable title="Liste des diplômes" data={diplomes} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default DiplomesPage;
