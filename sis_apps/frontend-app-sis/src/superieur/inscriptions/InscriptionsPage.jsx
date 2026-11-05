import React, { useState } from 'react';
import { Alert } from '@mui/material';
import ResourceManager from '../../components/common/ResourceManager';
import { WorkflowHistoryPanel } from '../../components/common';
import admissionActions from '../../components/common/admissionActions';

const InscriptionsPage = () => {
  const [selected, setSelected] = useState(null);
  return (
    <>
      <Alert severity="info" sx={{ mb: 3 }}>
        Une réinscription ouvre une nouvelle demande sur une année postérieure.
        Les notes, choix pédagogiques et règles antérieurs ne sont pas transférés ni convertis automatiquement.
      </Alert>
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
            name: 'etudiant', label: 'Étudiant', resource: 'etudiants', labelField: 'full_name', required: true, createOnly: true,
          },
          {
            name: 'formation', label: 'Formation', resource: 'formations/formations', required: true, createOnly: true,
          },
          {
            name: 'annee_universitaire',
            label: 'Année universitaire',
            required: true,
            createOnly: true,
            resource: 'etablissement/annees',
            labelField: 'libelle',
          },
          {
            name: 'date_inscription', label: 'Date d’inscription', type: 'date', required: true,
          },
        ]}
        actions={[
          ...admissionActions('superieur'),
          {
            label: 'Transférer',
            endpoint: 'transferer',
            statuses: ['validee'],
            fields: [
              {
                name: 'formation', label: 'Formation de destination', resource: 'formations/formations', required: true,
              },
              { name: 'parcours', label: 'Parcours de destination', resource: 'formations/parcours' },
              {
                name: 'motif', label: 'Motif du transfert', required: true, multiline: true,
              },
            ],
          },
        ]}
      />
      {selected && (
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={`inscriptions/${selected.id}/historique/`}
        title="Historique de l'inscription"
      />
      )}
    </>
  );
};

export default InscriptionsPage;
