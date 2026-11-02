import React from 'react';
import { Stack } from '@mui/material';
import ResourceManager from '../../components/common/ResourceManager';

const ClubsPage = () => (
  <Stack spacing={4}>
    <ResourceManager
      variant="secondaire"
      resource="clubs"
      title="Clubs"
      columns={[
        { Header: 'Nom', accessor: 'nom' },
        { Header: 'Type', accessor: 'type_display' },
        { Header: 'Responsable', accessor: 'responsable_nom' },
        { Header: 'Horaires', accessor: 'horaires' },
        { Header: 'Membres actifs', accessor: 'nb_membres' },
        { Header: 'Capacité', accessor: 'capacite' },
      ]}
      fields={[
        { name: 'nom', label: 'Nom', required: true },
        {
          name: 'type',
          label: 'Type',
          required: true,
          defaultValue: 'culturel',
          choices: ['sportif', 'culturel', 'scientifique', 'artistique', 'citoyen', 'autre']
            .map(value => ({ value, label: value })),
        },
        {
          name: 'description', label: 'Description', required: true, multiline: true,
        },
        {
          name: 'responsable',
          label: 'Responsable',
          resource: 'utilisateurs/comptes',
          labelField: 'full_name',
          required: true,
        },
        { name: 'salle', label: 'Salle' },
        { name: 'horaires', label: 'Horaires', required: true },
        {
          name: 'capacite', label: 'Capacité', type: 'number', defaultValue: 30, required: true,
        },
        {
          name: 'date_creation', label: 'Date de création', type: 'date', required: true,
        },
        {
          name: 'actif', label: 'Actif', type: 'checkbox', defaultValue: true,
        },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="clubs/membres-clubs"
      title="Membres des clubs"
      searchable={false}
      columns={[
        { Header: 'Club', accessor: 'club_nom' },
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Classe', accessor: 'eleve_classe' },
        { Header: 'Inscription', accessor: 'date_inscription' },
        { Header: 'Statut', accessor: 'statut_display' },
      ]}
      fields={[
        {
          name: 'club', label: 'Club', resource: 'clubs', required: true,
        },
        {
          name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'matricule', required: true,
        },
      ]}
      actions={[{ label: 'Suspendre', endpoint: 'suspendre' }, { label: 'Réactiver', endpoint: 'reactiver' }]}
    />
    <ResourceManager
      variant="secondaire"
      resource="clubs/activites-clubs"
      title="Séances des clubs"
      searchable={false}
      columns={[
        { Header: 'Club', accessor: 'club_nom' },
        { Header: 'Date', accessor: 'date' },
        { Header: 'Début', accessor: 'heure_debut' },
        { Header: 'Fin', accessor: 'heure_fin' },
        { Header: 'Activité', accessor: 'activite' },
        { Header: 'Présents', accessor: 'nb_presents' },
      ]}
      fields={[
        {
          name: 'club', label: 'Club', resource: 'clubs', required: true,
        },
        {
          name: 'date', label: 'Date', type: 'date', required: true,
        },
        {
          name: 'heure_debut', label: 'Début', type: 'time', required: true,
        },
        {
          name: 'heure_fin', label: 'Fin', type: 'time', required: true,
        },
        {
          name: 'activite', label: 'Activité', required: true, multiline: true,
        },
      ]}
    />
  </Stack>
);

export default ClubsPage;
