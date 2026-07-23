import React from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Add } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable } from '../../components/common';
import { useExamens } from '../../services/api';

const ExamensPage = () => {
  const { data: examens = [], isLoading } = useExamens();

  const columns = [
    { Header: 'ECUE', accessor: 'ecue_nom' },
    { Header: 'Type', accessor: 'type_examen' },
    { Header: 'Date', accessor: 'date_examen' },
    { Header: 'Heure', accessor: 'heure_debut' },
    { Header: 'Salle', accessor: 'salle_nom' },
    { Header: 'Durée', accessor: 'duree', Cell: ({ value }) => `${value} min` },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = { planifie: 'warning', en_cours: 'info', termine: 'success', annule: 'danger' };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
  ];

  return (
    <div>
      <PageHeader
        title="Gestion des examens"
        subtitle="Planning et organisation des examens"
        actions={<Button variant="primary" iconBefore={Add}>Planifier un examen</Button>}
      />
      <SISDataTable title="Liste des examens" data={examens} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default ExamensPage;
