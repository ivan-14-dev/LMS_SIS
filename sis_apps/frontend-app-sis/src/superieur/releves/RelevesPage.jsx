import React from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Print } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable } from '../../components/common';
import { useReleves } from '../../services/api';

const RelevesPage = () => {
  const { data: releves = [], isLoading } = useReleves();

  const columns = [
    { Header: 'Numéro', accessor: 'numero' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Semestre', accessor: 'semestre' },
    { Header: 'Moyenne', accessor: 'moyenne', Cell: ({ value }) => `${value}/20` },
    { Header: 'Date édition', accessor: 'date_edition' },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: () => (
        <Button size="sm" variant="outline-primary" iconBefore={Print}>
          Imprimer
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Relevés de notes" subtitle="Édition et historique des relevés" />
      <SISDataTable title="Relevés de notes" data={releves} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default RelevesPage;
