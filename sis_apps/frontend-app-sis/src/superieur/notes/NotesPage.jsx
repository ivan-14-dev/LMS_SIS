import React from 'react';
import EvaluationsManager from '../../components/common/EvaluationsManager';
import ResourceManager from '../../components/common/ResourceManager';
import WorkflowNotificationsPanel from '../../components/common/WorkflowNotificationsPanel';

const columns = [
  { Header: 'Étudiant', accessor: 'etudiant_nom' },
  { Header: 'Matricule', accessor: 'etudiant_matricule' },
  { Header: 'Évaluation', accessor: 'evaluation_titre' },
  { Header: 'Note', accessor: 'valeur' },
  { Header: 'Résultat selon l’offre', accessor: 'resultat_offre.detail' },
  { Header: 'Statut', accessor: 'statut_display' },
  { Header: 'Appréciation', accessor: 'appreciation' },
];

const NotesPage = () => (
  <div>
    <WorkflowNotificationsPanel apiType="superieur" />
    <EvaluationsManager variant="superieur" />
    <ResourceManager
      variant="superieur"
      resource="notes/notes"
      title="Notes enregistrées"
      columns={columns}
      searchable={false}
    />
  </div>
);

export default NotesPage;
