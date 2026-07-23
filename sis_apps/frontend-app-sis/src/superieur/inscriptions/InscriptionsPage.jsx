import React from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Add } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable } from '../../components/common';
import { useInscriptions } from '../../services/api';

const InscriptionsPage = () => {
  const { data: inscriptions = [], isLoading } = useInscriptions();

  const columns = [
    { Header: 'Matricule', accessor: 'etudiant_matricule' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Année', accessor: 'annee_universitaire' },
    { Header: 'Date inscription', accessor: 'date_inscription' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = { validee: 'success', en_attente: 'warning', refusee: 'danger', annulee: 'secondary' };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
  ];

  return (
    <div>
      <PageHeader
        title="Inscriptions administratives"
        subtitle={`${inscriptions.length} inscriptions`}
        actions={<Button variant="primary" iconBefore={Add}>Nouvelle inscription</Button>}
      />
      <SISDataTable
        title="Liste des inscriptions"
        data={inscriptions}
        columns={columns}
        loading={isLoading}
        searchable
        exportable
      />
    </div>
  );
};

export default InscriptionsPage;
