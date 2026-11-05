import React from 'react';
import ResourceManager from '../../components/common/ResourceManager';
import ResourceWorkspace from '../../components/common/ResourceWorkspace';

const regimes = [
  { value: 'standard', label: 'Standard' },
  { value: 'vegetarien', label: 'Végétarien' },
  { value: 'sans_porc', label: 'Sans porc' },
  { value: 'sans_gluten', label: 'Sans gluten' },
];

const CantinePage = () => (
  <ResourceWorkspace title="Cantine">
    <ResourceManager
      variant="secondaire"
      resource="cantine/menus"
      title="Menus de la cantine"
      searchable={false}
      columns={[
        { Header: 'Date', accessor: 'date' },
        { Header: 'Entrée', accessor: 'entree' },
        { Header: 'Plat', accessor: 'plat' },
        { Header: 'Accompagnement', accessor: 'accompagnement' },
        { Header: 'Dessert', accessor: 'dessert' },
        { Header: 'Régime', accessor: 'regime_display' },
        { Header: 'Prix', accessor: 'prix' },
      ]}
      fields={[
        {
          name: 'date', label: 'Date', type: 'date', required: true,
        },
        { name: 'entree', label: 'Entrée' },
        { name: 'plat', label: 'Plat', required: true },
        { name: 'accompagnement', label: 'Accompagnement' },
        { name: 'dessert', label: 'Dessert' },
        {
          name: 'regime',
          label: 'Régime',
          defaultValue: 'standard',
          required: true,
          choices: [...regimes, { value: 'autre', label: 'Autre' }],
        },
        {
          name: 'prix', label: 'Prix', type: 'number', defaultValue: 0, required: true,
        },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="cantine/inscriptions-cantine"
      title="Inscriptions à la cantine"
      searchable={false}
      columns={[
        { Header: 'Matricule', accessor: 'eleve_matricule' },
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Classe', accessor: 'eleve_classe' },
        { Header: 'Forfait', accessor: 'forfait_display' },
        { Header: 'Régime', accessor: 'regime_display' },
        { Header: 'Début', accessor: 'date_debut' },
        { Header: 'Fin', accessor: 'date_fin' },
      ]}
      fields={[
        {
          name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'matricule', required: true,
        },
        {
          name: 'forfait',
          label: 'Forfait',
          defaultValue: 'annuel',
          required: true,
          choices: ['annuel', 'trimestriel', 'mensuel', 'unitaire'].map(value => ({ value, label: value })),
        },
        {
          name: 'regime', label: 'Régime', choices: regimes, defaultValue: 'standard', required: true,
        },
        {
          name: 'date_debut', label: 'Début', type: 'date', required: true,
        },
        { name: 'date_fin', label: 'Fin', type: 'date' },
        {
          name: 'actif', label: 'Actif', type: 'checkbox', defaultValue: true,
        },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="cantine/presences-cantine"
      title="Présences à la cantine"
      searchable={false}
      columns={[
        { Header: 'Date', accessor: 'menu_date' },
        { Header: 'Plat', accessor: 'menu_plat' },
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Pointage', accessor: 'heure_pointage' },
      ]}
      fields={[
        {
          name: 'menu', label: 'Menu', resource: 'cantine/menus', labelField: 'date', required: true,
        },
        {
          name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'matricule', required: true,
        },
        {
          name: 'present', label: 'Présent', type: 'checkbox', defaultValue: true,
        },
        { name: 'heure_pointage', label: 'Pointage', type: 'time' },
      ]}
    />
  </ResourceWorkspace>
);

export default CantinePage;
