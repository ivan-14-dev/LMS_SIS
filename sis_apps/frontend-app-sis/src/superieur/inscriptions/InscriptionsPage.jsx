import React, { useState } from 'react';
import ResourceManager from '../../components/common/ResourceManager';
import { WorkflowHistoryPanel, WorkflowNotificationsPanel } from '../../components/common';

const InscriptionsPage = () => {
  const [selected, setSelected] = useState(null);
  return (
    <>
      <WorkflowNotificationsPanel apiType="superieur" />
      <ResourceManager
        variant="superieur"
        resource="inscriptions"
        title="Inscriptions administratives"
        searchable={false}
        onSelect={setSelected}
        columns={[
          { Header: 'Matricule', accessor: 'etudiant_matricule' },
          { Header: 'Étudiant', accessor: 'etudiant_nom' },
          { Header: 'Formation', accessor: 'formation_nom' },
          { Header: 'Offre', accessor: 'offre_configuration.label' },
          { Header: 'Année', accessor: 'annee_universitaire_libelle' },
          { Header: 'Statut', accessor: 'statut_display' },
        ]}
        fields={[
          {
            name: 'etudiant', label: 'Étudiant', resource: 'etudiants', labelField: 'full_name', required: true,
          },
          {
            name: 'formation', label: 'Formation', resource: 'formations/formations', required: true,
          },
          {
            name: 'annee_universitaire',
            label: 'Année universitaire',
            required: true,
            resource: 'etablissement/annees',
            labelField: 'libelle',
          },
          {
            name: 'date_inscription', label: 'Date d’inscription', type: 'date', required: true,
          },
        ]}
        actions={[{ label: 'Valider', endpoint: 'valider' }]}
      />
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={selected ? `inscriptions/${selected.id}/historique/` : ''}
        title="Historique de l'inscription"
      />
    </>
  );
};

export default InscriptionsPage;
