import React from 'react';
import ResourceManager from '../../components/common/ResourceManager';
import ResourceWorkspace from '../../components/common/ResourceWorkspace';

const PresencesPage = () => (
  <ResourceWorkspace title="Présences et absences">
    <ResourceManager
      variant="secondaire"
      resource="presences/appels"
      title="Appels"
      searchable={false}
      columns={[
        { Header: 'ID', accessor: 'id' },
        { Header: 'Cours', accessor: 'creneau_libelle' },
        { Header: 'Date', accessor: 'date' },
        { Header: 'Enseignant', accessor: 'enseignant_nom' },
        { Header: 'Statut', accessor: 'statut' },
        { Header: 'Présents', accessor: 'nb_presents' },
        { Header: 'Absents', accessor: 'nb_absents' },
      ]}
      fields={[
        {
          name: 'creneau', label: 'Créneau', resource: 'edt/creneaux', labelField: 'matiere_nom', required: true,
        },
        {
          name: 'enseignant', label: 'Enseignant', resource: 'enseignants/personnel', labelField: 'full_name', required: true,
        },
        {
          name: 'date', label: 'Date', type: 'date', required: true,
        },
      ]}
      actions={[{ label: 'Fermer', endpoint: 'fermer' }, { label: 'Valider', endpoint: 'valider' }]}
    />
    <ResourceManager
      variant="secondaire"
      resource="presences"
      title="Présences par appel"
      searchable={false}
      columns={[
        { Header: 'Appel', accessor: 'appel' },
        { Header: 'Matricule', accessor: 'eleve_matricule' },
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Statut', accessor: 'statut_display' },
        { Header: 'Retard (minutes)', accessor: 'retard_minutes' },
        { Header: 'Commentaire', accessor: 'commentaire' },
      ]}
      fields={[
        {
          name: 'appel', label: 'Appel', resource: 'presences/appels', labelField: 'id', required: true, createOnly: true,
        },
        {
          name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'full_name', required: true, createOnly: true,
        },
        {
          name: 'statut',
          label: 'Statut',
          required: true,
          choices: [
            { value: 'present', label: 'Présent' },
            { value: 'absent', label: 'Absent' },
            { value: 'absent_justifie', label: 'Absence justifiée' },
            { value: 'retard', label: 'En retard' },
            { value: 'dispense', label: 'Dispensé' },
          ],
        },
        { name: 'retard_minutes', label: 'Retard en minutes', type: 'number' },
        { name: 'commentaire', label: 'Commentaire' },
      ]}
    />
  </ResourceWorkspace>
);

export default PresencesPage;
