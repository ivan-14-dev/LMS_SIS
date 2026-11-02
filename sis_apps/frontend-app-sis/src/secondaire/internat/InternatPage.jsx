import React from 'react';
import { Alert, Stack } from '@mui/material';
import ResourceManager from '../../components/common/ResourceManager';

const InternatPage = () => (
  <Stack spacing={4}>
    <Alert severity="info">Les capacités et les chevauchements de séjour doivent être contrôlés par le gestionnaire.</Alert>
    <ResourceManager
      variant="secondaire"
      resource="internat/batiments"
      title="Bâtiments"
      columns={[
        { Header: 'Nom', accessor: 'nom' },
        { Header: 'Adresse', accessor: 'adresse' },
        { Header: 'Étages', accessor: 'nb_etages' },
      ]}
      fields={[
        { name: 'nom', label: 'Nom', required: true },
        { name: 'adresse', label: 'Adresse' },
        {
          name: 'nb_etages', label: 'Étages', type: 'number', defaultValue: 1, required: true,
        },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="internat/chambres"
      title="Chambres"
      searchable={false}
      columns={[
        { Header: 'Bâtiment', accessor: 'batiment_nom' },
        { Header: 'Numéro', accessor: 'numero' },
        { Header: 'Étage', accessor: 'etage' },
        { Header: 'Type', accessor: 'type_display' },
        { Header: 'Capacité', accessor: 'capacite' },
        { Header: 'Occupants', accessor: 'nb_occupants' },
      ]}
      fields={[
        {
          name: 'batiment', label: 'Bâtiment', resource: 'internat/batiments', required: true,
        },
        { name: 'numero', label: 'Numéro', required: true },
        {
          name: 'etage', label: 'Étage', type: 'number', defaultValue: 0, required: true,
        },
        {
          name: 'type',
          label: 'Type',
          defaultValue: 'double',
          required: true,
          choices: ['simple', 'double', 'triple', 'quadruple'].map(value => ({ value, label: value })),
        },
        {
          name: 'capacite', label: 'Capacité', type: 'number', defaultValue: 2, required: true,
        },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="internat/occupants-chambres"
      title="Séjours à l'internat"
      searchable={false}
      columns={[
        { Header: 'Bâtiment', accessor: 'batiment_nom' },
        { Header: 'Chambre', accessor: 'chambre_numero' },
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Classe', accessor: 'eleve_classe' },
        { Header: 'Début', accessor: 'date_debut' },
        { Header: 'Fin', accessor: 'date_fin' },
      ]}
      fields={[
        {
          name: 'chambre', label: 'Chambre', resource: 'internat/chambres', labelField: 'libelle', required: true,
        },
        {
          name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'matricule', required: true,
        },
        {
          name: 'date_debut', label: 'Début', type: 'date', required: true,
        },
        { name: 'date_fin', label: 'Fin', type: 'date' },
        { name: 'motif_fin', label: 'Motif de fin', multiline: true },
      ]}
    />
  </Stack>
);

export default InternatPage;
