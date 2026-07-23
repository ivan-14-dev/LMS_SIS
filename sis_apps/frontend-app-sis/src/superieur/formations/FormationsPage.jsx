import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge, Button } from '@openedx/paragon';
import { Add } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable } from '../../components/common';
import { useFormations } from '../../services/api';

const FormationsPage = () => {
  const navigate = useNavigate();
  const { data: formations = [], isLoading } = useFormations();

  const columns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Département', accessor: 'departement_nom' },
    { Header: 'Niveau', accessor: 'niveau_display' },
    { Header: 'Durée', accessor: 'duree_semestres', Cell: ({ value }) => `${value} semestres` },
    { Header: 'Crédits ECTS', accessor: 'credits_ects' },
    {
      Header: 'Statut',
      accessor: 'active',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'secondary'}>
          {value ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Gestion des formations"
        subtitle={`${formations.length} formations`}
        actions={
          <Button variant="primary" iconBefore={Add}>
            Nouvelle formation
          </Button>
        }
      />
      <SISDataTable
        title="Liste des formations"
        data={formations}
        columns={columns}
        loading={isLoading}
        onRowClick={(row) => navigate(`/superieur/formations/${row.original.id}`)}
        searchable
        exportable
      />
    </div>
  );
};

export default FormationsPage;
