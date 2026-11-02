import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box } from '@mui/material';
import ResourceManager from '../../components/common/ResourceManager';
import { getEnabledVariants } from '../../services/resources';

const AnneesAcademiquesPage = () => {
  const [params] = useSearchParams();
  const variants = getEnabledVariants();
  const variant = variants.includes(params.get('sis')) ? params.get('sis') : variants[0];
  const secondary = variant === 'secondaire';
  const years = 'etablissement/annees';
  const periods = `etablissement/${secondary ? 'periodes' : 'semestres'}`;
  const yearField = secondary ? 'annee_scolaire' : 'annee_universitaire';
  return (
    <Box key={variant}>
      <ResourceManager
        variant={variant}
        resource={years}
        title={`Années ${secondary ? 'scolaires' : 'universitaires'}`}
        searchable={false}
        columns={[
          { Header: 'Année', accessor: 'libelle' },
          { Header: 'Début', accessor: 'date_debut' },
          { Header: 'Fin', accessor: 'date_fin' },
          { Header: 'En cours', accessor: 'en_cours', Cell: ({ value }) => (value ? 'Oui' : 'Non') },
          { Header: 'Clôturée', accessor: 'cloturee', Cell: ({ value }) => (value ? 'Oui' : 'Non') },
        ]}
        fields={[
          { name: 'libelle', label: 'Année (ex. 2026-2027)', required: true },
          {
            name: 'date_debut', label: 'Date de début', type: 'date', required: true,
          },
          {
            name: 'date_fin', label: 'Date de fin', type: 'date', required: true,
          },
        ]}
        actions={[
          { label: 'Activer', endpoint: 'activer' },
          { label: 'Clôturer', endpoint: 'cloturer' },
        ]}
      />
      <Box sx={{ mt: 4 }}>
        <ResourceManager
          variant={variant}
          resource={periods}
          title={secondary ? 'Périodes' : 'Semestres'}
          searchable={false}
          columns={[
            { Header: 'Année', accessor: 'annee_libelle' },
            { Header: 'Numéro', accessor: 'numero' },
            { Header: 'Type', accessor: 'type_display' },
            { Header: 'Début', accessor: 'date_debut' },
            { Header: 'Fin', accessor: 'date_fin' },
          ]}
          fields={[
            {
              name: yearField, label: 'Année', resource: years, labelField: 'libelle', required: true,
            },
            {
              name: 'numero', label: 'Numéro', type: 'number', required: true,
            },
            {
              name: 'type',
              label: 'Type',
              required: true,
              choices: (secondary ? ['trimestre', 'semestre', 'quadrimestre', 'sequence'] : ['impair', 'pair', 'unique'])
                .map(value => ({ value, label: value })),
            },
            {
              name: 'date_debut', label: 'Date de début', type: 'date', required: true,
            },
            {
              name: 'date_fin', label: 'Date de fin', type: 'date', required: true,
            },
          ]}
          actions={[{ label: 'Clôturer', endpoint: 'cloturer' }]}
        />
      </Box>
    </Box>
  );
};

export default AnneesAcademiquesPage;
