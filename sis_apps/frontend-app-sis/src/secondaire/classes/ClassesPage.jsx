import React, { useState } from 'react';
import ResourceManager from '../../components/common/ResourceManager';
import { WorkflowHistoryPanel, WorkflowNotificationsPanel } from '../../components/common';

const ClassesPage = () => {
  const [selected, setSelected] = useState(null);
  return (
    <>
      <WorkflowNotificationsPanel apiType="secondaire" />
      <ResourceManager
        variant="secondaire"
        resource="classes/classes"
        title="Classes"
        onSelect={setSelected}
        columns={[
          { Header: 'Classe', accessor: 'nom' },
          { Header: 'Offre', accessor: 'offre_code' },
          { Header: 'Niveau', accessor: 'niveau_nom' },
          { Header: 'Année', accessor: 'annee_libelle' },
          { Header: 'Effectif', accessor: 'effectif' },
          { Header: 'Capacité', accessor: 'effectif_max' },
        ]}
        fields={[
          { name: 'nom', label: 'Nom de la classe', required: true },
          {
            name: 'offre_code',
            label: 'Offre institutionnelle',
            resource: 'etablissement/learning-offerings',
            valueField: 'code',
            labelField: 'label',
          },
          {
            name: 'niveau', label: 'Niveau', resource: 'etablissement/niveaux', labelField: 'libelle', required: true,
          },
          {
            name: 'annee_scolaire',
            label: 'Année scolaire',
            resource: 'etablissement/annees',
            labelField: 'libelle',
            required: true,
          },
          {
            name: 'effectif_max', label: 'Capacité maximale', type: 'number', defaultValue: 40, required: true,
          },
          {
            name: 'prof_principal', label: 'Professeur principal', resource: 'utilisateurs/comptes', labelField: 'full_name',
          },
          { name: 'salle_principale', label: 'Salle principale', resource: 'salles' },
        ]}
      />
      <ResourceManager
        variant="secondaire"
        resource="eleves/inscriptions"
        title="Inscriptions annuelles"
        searchable={false}
        columns={[
          { Header: 'Élève', accessor: 'eleve_nom' },
          { Header: 'Classe', accessor: 'classe_nom' },
          { Header: 'Année', accessor: 'annee_libelle' },
          { Header: 'Offre', accessor: 'offre_configuration.label' },
          { Header: 'Statut', accessor: 'statut_display' },
        ]}
        fields={[
          {
            name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'full_name', required: true,
          },
          {
            name: 'classe', label: 'Classe', resource: 'classes/classes', required: true,
          },
          {
            name: 'annee_scolaire',
            label: 'Année scolaire',
            resource: 'etablissement/annees',
            labelField: 'libelle',
            required: true,
          },
          {
            name: 'date_inscription', label: 'Date d’inscription', type: 'date', required: true,
          },
        ]}
        actions={[{ label: 'Valider', endpoint: 'valider' }]}
      />
      {selected && (
        <ResourceManager
          key={selected.id}
          variant="secondaire"
          resource={`classes/classes/${selected.id}/eleves`}
          title={`Élèves — ${selected.nom}`}
          searchable={false}
          columns={[
            { Header: 'Matricule', accessor: 'matricule' },
            { Header: 'Nom', accessor: 'full_name' },
          ]}
        />
      )}
      <WorkflowHistoryPanel
        apiType="secondaire"
        endpoint={selected ? `classes/classes/${selected.id}/historique/` : ''}
        title="Historique de la classe"
      />
    </>
  );
};

export default ClassesPage;
