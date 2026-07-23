import React from 'react';
import { Badge } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useEnseignants } from '../../services/api';

const EnseignantsPage = () => {
  const { data: enseignants = [], isLoading } = useEnseignants();

  const columns = [
    { Header: 'Matricule', accessor: 'matricule' },
    { Header: 'Nom', accessor: 'nom_complet', Cell: ({ row }) => `${row.original.nom} ${row.original.prenom}` },
    { Header: 'Grade', accessor: 'grade' },
    { Header: 'Département', accessor: 'departement_nom' },
    { Header: 'Spécialité', accessor: 'specialite' },
    { Header: 'Email', accessor: 'email' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => <Badge variant={value === 'actif' ? 'success' : 'secondary'}>{value}</Badge>,
    },
  ];

  return (
    <div>
      <PageHeader title="Enseignants-Chercheurs" subtitle={`${enseignants.length} enseignants`} />
      <SISDataTable title="Liste des enseignants" data={enseignants} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default EnseignantsPage;
