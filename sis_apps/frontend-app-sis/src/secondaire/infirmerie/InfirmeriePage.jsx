import React from 'react';
import { Alert } from '@mui/material';
import ResourceManager from '../../components/common/ResourceManager';
import ResourceWorkspace from '../../components/common/ResourceWorkspace';

const InfirmeriePage = () => (
  <ResourceWorkspace
    title="Infirmerie"
    notice={(
      <Alert severity="info">
        Accès réservé aux personnes habilitées. Les dossiers médicaux structurés restent gérés dans l’administration.
      </Alert>
    )}
  >
    <ResourceManager
      variant="secondaire"
      resource="infirmerie/visites-infirmerie"
      title="Visites à l'infirmerie"
      columns={[
        { Header: 'Date', accessor: 'date' },
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Classe', accessor: 'eleve_classe' },
        { Header: 'Arrivée', accessor: 'heure_arrivee' },
        { Header: 'Sortie', accessor: 'heure_sortie' },
        { Header: 'Motif', accessor: 'motif' },
        { Header: 'Orientation', accessor: 'orientation_display' },
        { Header: 'Infirmier', accessor: 'infirmier_nom' },
      ]}
      fields={[
        {
          name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'matricule', required: true,
        },
        {
          name: 'date', label: 'Date et heure', type: 'datetime-local', required: true,
        },
        {
          name: 'heure_arrivee', label: 'Arrivée', type: 'time', required: true,
        },
        { name: 'heure_sortie', label: 'Sortie', type: 'time' },
        {
          name: 'motif', label: 'Motif', required: true, multiline: true,
        },
        { name: 'symptomes', label: 'Symptômes', multiline: true },
        { name: 'soins', label: 'Soins', multiline: true },
        { name: 'traitement_administre', label: 'Traitement administré', multiline: true },
        {
          name: 'orientation',
          label: 'Orientation',
          defaultValue: 'retour_cours',
          required: true,
          choices: [
            { value: 'retour_cours', label: 'Retour en cours' },
            { value: 'sortie', label: 'Sortie' },
            { value: 'urgence', label: 'Urgence' },
            { value: 'parents', label: 'Parents' },
            { value: 'hospitalisation', label: 'Hospitalisation' },
          ],
        },
        { name: 'parents_prevenus', label: 'Parents prévenus', type: 'checkbox' },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="infirmerie/stock-medicaments"
      title="Stock de l'infirmerie"
      columns={[
        { Header: 'Nom', accessor: 'nom' },
        { Header: 'Quantité', accessor: 'quantite' },
        { Header: 'Unité', accessor: 'unite' },
        { Header: 'Seuil', accessor: 'seuil_alerte' },
        { Header: 'Péremption', accessor: 'date_peremption' },
        { Header: 'Lot', accessor: 'numero_lot' },
      ]}
      fields={[
        { name: 'nom', label: 'Nom', required: true },
        { name: 'description', label: 'Description', multiline: true },
        {
          name: 'quantite', label: 'Quantité', type: 'number', defaultValue: 0, required: true,
        },
        {
          name: 'seuil_alerte', label: 'Seuil', type: 'number', defaultValue: 10, required: true,
        },
        {
          name: 'unite', label: 'Unité', defaultValue: 'unité', required: true,
        },
        { name: 'date_peremption', label: 'Péremption', type: 'date' },
        { name: 'numero_lot', label: 'Lot' },
      ]}
    />
  </ResourceWorkspace>
);

export default InfirmeriePage;
