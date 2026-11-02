import React, { useState } from 'react';
import { Stack } from '@mui/material';
import { WorkflowHistoryPanel, WorkflowNotificationsPanel } from '../../components/common';
import ResourceManager from '../../components/common/ResourceManager';

const ConseilClassePage = () => {
  const [selected, setSelected] = useState(null);
  return (
    <Stack spacing={3}>
      <WorkflowNotificationsPanel apiType="secondaire" />
      <ResourceManager
        variant="secondaire"
        resource="conseils/conseils-classe"
        title="Conseils de classe"
        searchable={false}
        onSelect={row => setSelected(row.id)}
        columns={[
          { Header: 'Date', accessor: 'date' },
          { Header: 'Classe', accessor: 'classe_nom' },
          { Header: 'Période', accessor: 'periode_nom' },
          { Header: 'Président', accessor: 'president_nom' },
          { Header: 'Décisions', accessor: 'nb_decisions' },
          { Header: 'Statut', accessor: 'statut_display' },
        ]}
        fields={[
          {
            name: 'classe', label: 'Classe', resource: 'classes/classes', required: true,
          },
          {
            name: 'periode', label: 'Période', resource: 'etablissement/periodes', labelField: 'libelle', required: true,
          },
          {
            name: 'date', label: 'Date et heure', type: 'datetime-local', required: true,
          },
          {
            name: 'president', label: 'Président', resource: 'utilisateurs/comptes', labelField: 'full_name', required: true,
          },
          {
            name: 'secretaire', label: 'Secrétaire', resource: 'utilisateurs/comptes', labelField: 'full_name',
          },
          { name: 'ordre_jour', label: 'Ordre du jour', multiline: true },
          { name: 'pv', label: 'Procès-verbal', multiline: true },
        ]}
        actions={[{ label: 'Marquer tenu', endpoint: 'tenir' }, { label: 'Valider', endpoint: 'valider' }]}
      />
      <WorkflowHistoryPanel
        apiType="secondaire"
        endpoint={selected ? `conseils/conseils-classe/${selected}/historique/` : ''}
        title="Historique du conseil sélectionné"
      />
    </Stack>
  );
};

export default ConseilClassePage;
