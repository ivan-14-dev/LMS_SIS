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
          { Header: 'Niveau', accessor: 'niveau_nom' },
          { Header: 'Année', accessor: 'annee_libelle' },
          { Header: 'Effectif', accessor: 'effectif' },
          { Header: 'Capacité', accessor: 'effectif_max' },
        ]}
        fields={[
          { name: 'nom', label: 'Nom de la classe', required: true },
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
