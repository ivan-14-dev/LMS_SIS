import React from 'react';
import { Badge, Button } from '@openedx/paragon';
import { Download } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable } from '../../components/common';
import { getSuperieurApiUrl, useDiplomes } from '../../services/api';

const DiplomesPage = () => {
  const { data: diplomes = [], isLoading } = useDiplomes();

  const downloadPdf = (id) => window.open(`${getSuperieurApiUrl()}/diplomes/${id}/pdf_officiel/`, '_blank', 'noopener,noreferrer');

  const columns = [
    { Header: 'Série', accessor: 'numero_serie' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Diplôme', accessor: 'diplome_nom' },
    { Header: 'Année', accessor: 'annee_libelle' },
    { Header: 'Mention', accessor: 'mention' },
    { Header: 'Date obtention', accessor: 'date_obtention' },
    {
      Header: 'Statut',
      accessor: 'date_signature',
      Cell: ({ value }) => <Badge variant={value ? 'success' : 'warning'}>{value ? 'Signé' : 'Préparé'}</Badge>,
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: ({ value }) => (
        <Button size="sm" variant="outline-secondary" iconBefore={Download} onClick={() => downloadPdf(value)}>
          PDF officiel
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Diplômes" subtitle="Délivrances et documents officiels" />
      <SISDataTable title="Liste des délivrances de diplômes" data={diplomes} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default DiplomesPage;
