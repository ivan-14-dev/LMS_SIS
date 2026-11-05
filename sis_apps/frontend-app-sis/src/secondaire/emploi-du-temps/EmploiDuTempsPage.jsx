import React from 'react';
import ResourceManager from '../../components/common/ResourceManager';
import ResourceWorkspace from '../../components/common/ResourceWorkspace';

const EmploiDuTempsPage = () => (
  <ResourceWorkspace title="Emploi du temps">
    <ResourceManager
      variant="secondaire"
      resource="edt/creneaux"
      title="Emploi du temps"
      searchable={false}
      columns={[
        { Header: 'Classe', accessor: 'classe_nom' },
        { Header: 'Matière', accessor: 'matiere_nom' },
        { Header: 'Enseignant', accessor: 'enseignant_nom' },
        { Header: 'Salle', accessor: 'salle_nom' },
        { Header: 'Jour', accessor: 'jour_display' },
        { Header: 'Début', accessor: 'heure_debut' },
        { Header: 'Fin', accessor: 'heure_fin' },
      ]}
      fields={[
        {
          name: 'classe', label: 'Classe', resource: 'classes/classes', required: true,
        },
        {
          name: 'matiere', label: 'Matière', resource: 'classes/matieres', required: true,
        },
        {
          name: 'enseignant',
          label: 'Enseignant',
          resource: 'enseignants/personnel',
          labelField: 'full_name',
          required: true,
        },
        { name: 'salle', label: 'Salle', resource: 'salles' },
        {
          name: 'jour',
          label: 'Jour',
          required: true,
          type: 'number',
          choices: ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            .map((label, index) => ({ value: index + 1, label })),
        },
        {
          name: 'heure_debut', label: 'Heure de début', type: 'time', required: true,
        },
        {
          name: 'heure_fin', label: 'Heure de fin', type: 'time', required: true,
        },
        {
          name: 'semaine', label: 'Semaine (0 = toutes)', type: 'number', defaultValue: 0,
        },
        { name: 'notes', label: 'Notes' },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="enseignants/personnel"
      title="Personnel enseignant"
      columns={[
        { Header: 'Matricule', accessor: 'matricule' },
        { Header: 'Nom', accessor: 'full_name' },
        { Header: 'Email', accessor: 'email' },
        { Header: 'Embauche', accessor: 'date_embauche' },
      ]}
      fields={[
        {
          name: 'username', label: 'Identifiant', required: true, createOnly: true,
        },
        {
          name: 'email', label: 'Email', type: 'email', required: true, createOnly: true,
        },
        {
          name: 'first_name', label: 'Prénom', required: true, createOnly: true,
        },
        {
          name: 'last_name', label: 'Nom', required: true, createOnly: true,
        },
        {
          name: 'password', label: 'Mot de passe initial', type: 'password', required: true, createOnly: true,
        },
        {
          name: 'date_embauche', label: 'Date d’embauche', type: 'date', required: true,
        },
        { name: 'corps', label: 'Corps' },
        {
          name: 'heures_contractuelles', label: 'Heures contractuelles', type: 'number', defaultValue: 0,
        },
      ]}
    />
  </ResourceWorkspace>
);

export default EmploiDuTempsPage;
