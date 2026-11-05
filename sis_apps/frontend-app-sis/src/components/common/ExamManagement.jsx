import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Tab, Tabs,
} from '@mui/material';
import ResourceManager from './ResourceManager';
import WorkflowHistoryPanel from './WorkflowHistoryPanel';
import { useCapabilities } from '../auth/PermissionGuard';

const choices = values => values.map(value => ({ value, label: value }));

const ExamManagement = ({ variant }) => {
  const secondary = variant === 'secondaire';
  const [tab, setTab] = useState('sessions');
  const [selected, setSelected] = useState(null);
  const { data: capabilities } = useCapabilities(variant);
  const canManage = capabilities?.permissions?.some(permission => ['*', 'examens.change_sessionexamen'].includes(permission))
    || ['direction', 'responsable_pedagogique', 'vie_scolaire', 'scolarite', 'directeur_etudes', 'doyen'].includes(capabilities?.role)
    || capabilities?.groups?.includes(secondary ? 'exam_manager_secondary' : 'exam_manager_superieur');
  const learner = secondary ? 'eleve' : 'etudiant';
  const learnerField = {
    name: learner,
    label: secondary ? 'Élève' : 'Étudiant',
    resource: secondary ? 'eleves' : 'etudiants',
    labelField: 'full_name',
    required: true,
    createOnly: true,
  };
  const examField = {
    name: 'epreuve', label: 'Épreuve', resource: 'examens/epreuves', labelField: 'libelle', required: true, createOnly: true,
  };
  const configurations = {
    sessions: {
      title: 'Sessions d’examen',
      searchable: secondary,
      columns: [
        { Header: 'Session', accessor: 'libelle' },
        { Header: 'Début', accessor: 'date_debut' },
        { Header: 'Fin', accessor: 'date_fin' },
        { Header: 'Clôturée', accessor: 'cloturee', Cell: ({ value }) => (value ? 'Oui' : 'Non') },
      ],
      fields: [
        ...(secondary ? [
          { name: 'nom', label: 'Nom', required: true },
          {
            name: 'annee_scolaire', label: 'Année scolaire', resource: 'etablissement/annees', labelField: 'libelle', required: true,
          },
        ] : [
          {
            name: 'semestre', label: 'Semestre', resource: 'etablissement/semestres', labelField: 'libelle', required: true,
          },
          {
            name: 'numero', label: 'Numéro', type: 'number', defaultValue: 1, required: true,
          },
        ]),
        {
          name: 'type',
          label: 'Type',
          required: true,
          choices: choices(secondary ? ['examen_blanc', 'bac', 'brevet', 'controle', 'concours'] : ['normale', 'rattrapage', 'exceptionnelle']),
        },
        {
          name: 'date_debut', label: 'Début', type: 'date', required: true,
        },
        {
          name: 'date_fin', label: 'Fin', type: 'date', required: true,
        },
      ],
      actions: [
        {
          label: 'Clôturer', endpoint: 'cloturer', statusField: 'cloturee', statuses: [false],
        },
        {
          label: 'Rouvrir', endpoint: 'reouvrir', statusField: 'cloturee', statuses: [true],
        },
      ],
    },
    epreuves: {
      title: 'Épreuves',
      columns: [
        { Header: 'Épreuve', accessor: 'libelle' },
        { Header: 'Date', accessor: 'date' },
        { Header: 'Heure', accessor: 'heure_debut' },
        { Header: 'Durée (min)', accessor: 'duree_minutes' },
        { Header: 'Barème', accessor: 'bareme' },
        { Header: 'Soumission', accessor: 'soumission_statut' },
      ],
      fields: [
        {
          name: 'session', label: 'Session', resource: 'examens/sessions', labelField: 'libelle', required: true,
        },
        {
          name: secondary ? 'matiere' : 'ecue',
          label: secondary ? 'Matière' : 'ECUE',
          resource: secondary ? 'classes/matieres' : 'ue-ecue/ecues',
          required: true,
        },
        ...(secondary ? [{
          name: 'classes', label: 'Classes', resource: 'classes/classes', required: true, multiple: true,
        }] : [{ name: 'lieu', label: 'Lieu', required: true }]),
        {
          name: 'date', label: 'Date', type: 'date', required: true,
        },
        {
          name: 'heure_debut', label: 'Heure', type: 'time', required: true,
        },
        {
          name: 'duree_minutes', label: 'Durée (minutes)', type: 'number', defaultValue: 120, required: true,
        },
        {
          name: 'bareme', label: 'Barème', type: 'number', defaultValue: 20, required: true,
        },
        { name: 'debut_soumission', label: 'Ouverture de la saisie', type: 'datetime-local' },
        { name: 'fin_soumission', label: 'Fin de la saisie', type: 'datetime-local' },
      ],
      actions: secondary ? [] : [{ label: 'Générer les convocations', endpoint: 'generer_convocations' }],
    },
    convocations: {
      title: 'Convocations',
      searchable: false,
      columns: [
        { Header: 'Apprenant', accessor: `${learner}_nom` },
        { Header: 'Place', accessor: 'numero_place' },
        { Header: 'Salle', accessor: 'salle' },
        { Header: 'Statut', accessor: 'statut_display' },
      ],
      fields: [
        examField, learnerField,
        { name: 'numero_place', label: 'Numéro de place' },
        { name: 'salle', label: 'Salle' },
      ],
      actions: secondary ? [
        { label: 'Présent', endpoint: 'marquer_present' },
        { label: 'Absent', endpoint: 'marquer_absent' },
      ] : [{
        label: 'Pointer',
        endpoint: 'pointer',
        fields: [{
          name: 'statut', label: 'Présence', required: true, choices: choices(['present', 'absent', 'dispense']),
        }],
      }],
    },
    resultats: {
      title: 'Résultats d’examen',
      searchable: false,
      columns: [
        { Header: 'Apprenant', accessor: `${learner}_nom` },
        { Header: 'Note', accessor: 'note' },
        { Header: 'Statut', accessor: 'statut_display' },
        { Header: 'Mention', accessor: 'mention' },
      ],
      fields: [
        examField, learnerField,
        { name: 'note', label: 'Note', type: 'number' },
        { name: 'appreciation', label: 'Appréciation', multiline: true },
        {
          name: 'type_resultat', label: 'Type de résultat', required: true, defaultValue: 'normal', choices: choices(['normal', 'retake']),
        },
      ],
      actions: [
        { label: 'Soumettre', endpoint: 'soumettre', statuses: ['draft', 'reopened'] },
        { label: 'Vérifier', endpoint: 'verifier', statuses: ['submitted'] },
        { label: 'Valider', endpoint: 'valider', statuses: ['verified'] },
        { label: 'Publier', endpoint: 'publier', statuses: ['validated'] },
        { label: 'Rouvrir', endpoint: 'reouvrir', statuses: ['validated', 'published', 'closed'] },
        { label: 'Clôturer', endpoint: 'cloturer', statuses: ['published', 'validated', 'reopened'] },
      ],
    },
  };
  const configuration = configurations[tab];
  return (
    <Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        Les résultats suivent les étapes soumission, vérification, validation et publication.
        Les périodes clôturées restent protégées.
      </Alert>
      <Tabs value={tab} onChange={(_, value) => { setTab(value); setSelected(null); }} variant="scrollable" scrollButtons="auto" sx={{ mb: 3 }}>
        {Object.entries(configurations).map(([key, item]) => <Tab key={key} value={key} label={item.title} />)}
      </Tabs>
      <ResourceManager
        key={tab}
        variant={variant}
        resource={`examens/${tab}`}
        {...configuration}
        allowCreate={Boolean(canManage)}
        allowEdit={Boolean(canManage)}
        actions={canManage ? configuration.actions : []}
        onSelect={setSelected}
      />
      {['sessions', 'epreuves'].includes(tab) && (
        <WorkflowHistoryPanel
          apiType={variant}
          endpoint={selected ? `examens/${tab}/${selected.id}/historique/` : ''}
          title="Historique de l’examen"
        />
      )}
    </Box>
  );
};

ExamManagement.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default ExamManagement;
