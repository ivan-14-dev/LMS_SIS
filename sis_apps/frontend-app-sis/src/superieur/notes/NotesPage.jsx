import React from 'react';
import EvaluationsManager from '../../components/common/EvaluationsManager';
import ResourceManager from '../../components/common/ResourceManager';
import PageHeader from '../../components/common/PageHeader';
import RecordsTabs from '../../components/common/RecordsTabs';

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
    <PageHeader title="Évaluations et notes" />
    <RecordsTabs
      label="Gestion des résultats"
      panels={[
        { label: 'Évaluations', content: <EvaluationsManager variant="superieur" showHeading={false} /> },
        {
          label: 'Notes enregistrées',
          content: (
            <ResourceManager
              variant="superieur"
              resource="notes/notes"
              title="Notes enregistrées"
              showHeading={false}
              columns={columns}
              searchable={false}
            />
          ),
        },
      ]}
    />
  </div>
);

export default NotesPage;
