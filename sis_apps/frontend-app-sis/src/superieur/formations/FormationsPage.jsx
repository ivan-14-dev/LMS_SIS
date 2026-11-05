import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@mui/material';
import { WorkflowHistoryPanel } from '../../components/common';
import ResourceManager from '../../components/common/ResourceManager';

const historyButton = (select, cell) => (
  <Button onClick={(event) => { event.stopPropagation(); select(cell.row.original.id); }}>Historique</Button>
);

const FormationsPage = () => {
  const navigate = useNavigate();
  const [selectedFormationId, setSelectedFormationId] = useState(null);
  return (
    <div>
      <ResourceManager
        variant="superieur"
        resource="formations/formations"
        title="Formations"
        onSelect={formation => navigate(`/superieur/formations/${formation.id}`)}
        columns={[
          { Header: 'Code', accessor: 'code' },
          { Header: 'Nom', accessor: 'nom' },
          { Header: 'Offre', accessor: 'offre_code' },
          { Header: 'Origine des règles', accessor: 'configuration_origine.source.label' },
          { Header: 'Département', accessor: 'departement_nom' },
          { Header: 'Niveau', accessor: 'niveau_display' },
          { Header: 'Durée (années)', accessor: 'duree_annees' },
          { Header: 'Crédits du cursus', accessor: 'credits_total' },
          { Header: 'Statut', accessor: 'actif', Cell: cell => (cell.value ? 'Active' : 'Inactive') },
          { Header: 'Historique', accessor: 'historique', Cell: historyButton.bind(null, setSelectedFormationId) },
        ]}
        fields={[
          { name: 'code', label: 'Code', required: true },
          { name: 'nom', label: 'Nom de la formation', required: true },
          {
            name: 'organisation_unit',
            label: 'Unité d’organisation',
            resource: 'etablissement/unites',
            createOnly: true,
            labelField: 'label',
          },
          {
            name: 'type', label: 'Type', defaultValue: 'licence', required: true,
          },
          { name: 'niveau', label: 'Niveau' },
          {
            name: 'offre_code',
            label: 'Offre institutionnelle',
            helpText: 'À la création, laissez vide pour hériter des règles de l’unité ou de l’établissement.',
            resource: 'etablissement/learning-offerings',
            valueField: 'code',
            labelField: 'label',
          },
          { name: 'departement', label: 'Département', resource: 'structure/departements' },
          {
            name: 'duree_annees', label: 'Durée (années)', type: 'number', defaultValue: 3, required: true,
          },
          {
            name: 'nb_semestres', label: 'Nombre de semestres', type: 'number', defaultValue: 6, required: true,
          },
          {
            name: 'credits_total', label: 'Crédits du cursus (0 sans crédits)', type: 'number', defaultValue: 180, required: true,
          },
          {
            name: 'actif', label: 'Formation active', type: 'checkbox', defaultValue: true,
          },
        ]}
      />
      {selectedFormationId && (
      <WorkflowHistoryPanel
        apiType="superieur"
        endpoint={`formations/formations/${selectedFormationId}/historique/`}
        title="Historique de la formation"
      />
      )}
    </div>
  );
};

export default FormationsPage;
