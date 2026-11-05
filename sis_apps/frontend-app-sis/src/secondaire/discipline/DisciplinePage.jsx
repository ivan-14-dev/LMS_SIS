import React from 'react';
import ResourceManager from '../../components/common/ResourceManager';
import ResourceWorkspace from '../../components/common/ResourceWorkspace';

const DisciplinePage = () => (
  <ResourceWorkspace title="Discipline">
    <ResourceManager
      variant="secondaire"
      resource="discipline/incidents"
      title="Incidents disciplinaires"
      columns={[
        { Header: 'Date', accessor: 'date_incident' },
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Classe', accessor: 'eleve_classe' },
        { Header: 'Type', accessor: 'type_display' },
        { Header: 'Gravité', accessor: 'gravite_display' },
        { Header: 'Rapporteur', accessor: 'rapporteur_nom' },
        { Header: 'Statut', accessor: 'statut_display' },
      ]}
      fields={[
        {
          name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'matricule', required: true,
        },
        {
          name: 'date_incident', label: 'Date et heure', type: 'datetime-local', required: true,
        },
        {
          name: 'type',
          label: 'Type',
          defaultValue: 'comportement',
          required: true,
          choices: [
            { value: 'comportement', label: 'Comportement' },
            { value: 'violence', label: 'Violence' },
            { value: 'deffaillance', label: 'Défaillance' },
            { value: 'fraude', label: 'Fraude' },
            { value: 'manquement_respect', label: 'Manquement au respect' },
            { value: 'degradation', label: 'Dégradation' },
            { value: 'autre', label: 'Autre' },
          ],
        },
        {
          name: 'gravite',
          label: 'Gravité',
          type: 'number',
          defaultValue: 1,
          required: true,
          choices: [
            { value: 1, label: 'Mineure' }, { value: 2, label: 'Modérée' },
            { value: 3, label: 'Grave' }, { value: 4, label: 'Très grave' },
          ],
        },
        {
          name: 'description', label: 'Description', required: true, multiline: true,
        },
        { name: 'lieu', label: 'Lieu' },
        {
          name: 'rapporteur',
          label: 'Rapporteur',
          resource: 'enseignants/personnel',
          labelField: 'full_name',
          required: true,
        },
      ]}
    />
    <ResourceManager
      variant="secondaire"
      resource="discipline/sanctions"
      title="Sanctions disciplinaires"
      searchable={false}
      columns={[
        { Header: 'Date', accessor: 'date_effet' },
        { Header: 'Élève', accessor: 'eleve_nom' },
        { Header: 'Type', accessor: 'type_display' },
        { Header: 'Motif', accessor: 'motif' },
        { Header: 'Durée (jours)', accessor: 'duree_jours' },
        { Header: 'Fin', accessor: 'date_fin' },
      ]}
      fields={[
        {
          name: 'incident', label: 'Incident', resource: 'discipline/incidents', labelField: 'libelle', required: true,
        },
        {
          name: 'type',
          label: 'Type',
          defaultValue: 'avertissement',
          required: true,
          choices: [
            { value: 'avertissement', label: 'Avertissement' },
            { value: 'heures_colle', label: 'Heures de retenue' },
            { value: 'exclusion_cours', label: 'Exclusion de cours' },
            { value: 'exclusion_temporaire', label: 'Exclusion temporaire' },
            { value: 'exclusion_definitive', label: 'Exclusion définitive' },
            { value: 'travail_interet_general', label: "Travail d'intérêt général" },
            { value: 'autre', label: 'Autre' },
          ],
        },
        {
          name: 'motif', label: 'Motif', required: true, multiline: true,
        },
        {
          name: 'date_effet', label: "Date d'effet", type: 'date', required: true,
        },
        { name: 'date_fin', label: 'Fin', type: 'date' },
        { name: 'duree_jours', label: 'Durée (jours)', type: 'number' },
        { name: 'executee', label: 'Exécutée', type: 'checkbox' },
        { name: 'notifiee_parents', label: 'Parents déjà notifiés', type: 'checkbox' },
        { name: 'date_notification', label: 'Date de notification', type: 'datetime-local' },
      ]}
    />
  </ResourceWorkspace>
);

export default DisciplinePage;
