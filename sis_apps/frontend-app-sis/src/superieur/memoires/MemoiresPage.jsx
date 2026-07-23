import React from 'react';
import { Badge } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useMemoires } from '../../services/api';

const MemoiresPage = () => {
  const { data: memoires = [], isLoading } = useMemoires();

  const columns = [
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Titre', accessor: 'titre' },
    { Header: 'Directeur', accessor: 'directeur_nom' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Date soutenance', accessor: 'date_soutenance' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = { en_redaction: 'warning', soumis: 'info', soutenu: 'success', valide: 'success' };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
  ];

  return (
    <div>
      <PageHeader title="Mémoires et Thèses" subtitle="Suivi des travaux de recherche" />
      <SISDataTable title="Liste des mémoires" data={memoires} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default MemoiresPage;
