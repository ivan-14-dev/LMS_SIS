import React from 'react';
import ResourceManager from '../../components/common/ResourceManager';
import ResourceWorkspace from '../../components/common/ResourceWorkspace';

const TransportPage = () => (
  <ResourceWorkspace title="Transport scolaire">
    <ResourceManager
      variant="secondaire"
      resource="transport/lignes-transport"
      title="Lignes de transport"
      columns={[
        { Header: 'Nom', accessor: 'nom' },
        { Header: 'Arrêts', accessor: 'nb_arrets' },
        { Header: 'Distance (km)', accessor: 'distance_km' },
        { Header: 'Durée (minutes)', accessor: 'duree_estimee_min' },
      ]}
      fields={[
        { name: 'nom', label: 'Nom', required: true },
        {
          name: 'itineraire', label: 'Itinéraire', required: true, multiline: true,
        },
        {
          name: 'distance_km', label: 'Distance (km)', type: 'number', defaultValue: 0, required: true,
        },
        {
          name: 'duree_estimee_min', label: 'Durée (minutes)', type: 'number', defaultValue: 0, required: true,
        },
        {
          name: 'actif', label: 'Actif', type: 'checkbox', defaultValue: true,
        },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="transport/arrets"
      title="Arrêts"
      searchable={false}
      columns={[
        { Header: 'Ligne', accessor: 'ligne_nom' },
        { Header: 'Nom', accessor: 'nom' },
        { Header: 'Passage', accessor: 'heure_passage' },
        { Header: 'Ordre', accessor: 'ordre' },
      ]}
      fields={[
        {
          name: 'ligne', label: 'Ligne', resource: 'transport/lignes-transport', required: true,
        },
        { name: 'nom', label: 'Nom', required: true },
        {
          name: 'heure_passage', label: 'Passage', type: 'time', required: true,
        },
        {
          name: 'ordre', label: 'Ordre', type: 'number', defaultValue: 1, required: true,
        },
        { name: 'adresse', label: 'Adresse' },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="transport/vehicules"
      title="Véhicules"
      columns={[
        { Header: 'Immatriculation', accessor: 'immatriculation' },
        { Header: 'Capacité', accessor: 'capacite' },
        { Header: 'Chauffeur', accessor: 'chauffeur' },
        { Header: 'Ligne', accessor: 'ligne_nom' },
      ]}
      fields={[
        { name: 'immatriculation', label: 'Immatriculation', required: true },
        {
          name: 'capacite', label: 'Capacité', type: 'number', required: true,
        },
        { name: 'marque', label: 'Marque' },
        { name: 'modele', label: 'Modèle' },
        { name: 'chauffeur', label: 'Chauffeur' },
        { name: 'telephone_chauffeur', label: 'Téléphone du chauffeur' },
        { name: 'ligne', label: 'Ligne', resource: 'transport/lignes-transport' },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="transport/inscriptions-transport"
      title="Inscriptions au transport"
      searchable={false}
      columns={[
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Classe', accessor: 'eleve_classe' },
        { Header: 'Ligne', accessor: 'ligne_nom' },
        { Header: 'Montée', accessor: 'arret_montee_nom' },
        { Header: 'Descente', accessor: 'arret_descente_nom' },
      ]}
      fields={[
        {
          name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'matricule', required: true,
        },
        {
          name: 'ligne', label: 'Ligne', resource: 'transport/lignes-transport', required: true,
        },
        {
          name: 'arret_montee',
          label: 'Arrêt de montée',
          resource: 'transport/arrets',
          labelField: 'libelle',
          required: true,
        },
        {
          name: 'arret_descente',
          label: 'Arrêt de descente',
          resource: 'transport/arrets',
          labelField: 'libelle',
          required: true,
        },
        {
          name: 'annee_scolaire',
          label: 'Année scolaire',
          resource: 'etablissement/annees',
          labelField: 'libelle',
          required: true,
        },
        {
          name: 'actif', label: 'Actif', type: 'checkbox', defaultValue: true,
        },
      ]}
    />
  </ResourceWorkspace>
);

export default TransportPage;
