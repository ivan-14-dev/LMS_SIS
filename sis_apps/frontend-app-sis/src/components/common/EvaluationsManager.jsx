import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Button, Stack } from '@mui/material';
import ResourceManager from './ResourceManager';
import GradeEntryDialog from './GradeEntryDialog';
import WorkflowHistoryPanel from './WorkflowHistoryPanel';
import { useCapabilities } from '../auth/PermissionGuard';
import { apiErrorMessage } from '../../services/resources';

const gradeButton = (variant, select, cell) => {
  const row = cell.row.original;
  const allowed = variant === 'secondaire'
    ? ['interrogation', 'ds', 'dm', 'tp', 'oral', 'projet'].includes(row.type)
    : ['cc', 'tp', 'projet'].includes(row.modalite) && !row.anonyme;
  return (
    <Button disabled={!allowed} onClick={() => select(row)}>Saisir les notes</Button>
  );
};
const historyButton = (select, cell) => (
  <Button onClick={() => select(cell.row.original.id)}>Historique</Button>
);
const choices = pairs => pairs.map(([value, label]) => ({ value, label }));

const EvaluationsManager = ({ variant }) => {
  const secondary = variant === 'secondaire';
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState(null);
  const [notice, setNotice] = useState('');
  const capabilities = useCapabilities(variant);
  const roles = secondary
    ? ['enseignant', 'vie_scolaire', 'direction', 'responsable_pedagogique']
    : ['enseignant', 'chercheur', 'scolarite', 'directeur_etudes'];
  const permissions = capabilities.data?.permissions || [];
  const canManage = permissions.includes('*') || permissions.includes('notes.change_evaluation')
    || permissions.includes('notes.add_evaluation') || roles.includes(capabilities.data?.role);
  if (capabilities.error) {
    return <Alert severity="error">{apiErrorMessage(capabilities.error)}</Alert>;
  }
  if (!canManage) { return null; }
  const columns = [
    { Header: 'Titre', accessor: 'titre' },
    { Header: 'Offre historisée', accessor: 'offre_configuration.label' },
    { Header: secondary ? 'Matière' : 'ECUE', accessor: secondary ? 'matiere_nom' : 'ecue_nom' },
    ...(secondary ? [{ Header: 'Classe', accessor: 'classe_nom' }] : []),
    { Header: 'Type', accessor: secondary ? 'type_display' : 'modalite_display' },
    { Header: 'Date', accessor: 'date' },
    { Header: 'Barème', accessor: 'bareme' },
    { Header: 'Coefficient', accessor: 'coefficient' },
    { Header: 'Fin de soumission', accessor: 'fin_soumission' },
    { Header: 'Soumission', accessor: 'soumission_statut' },
    { Header: 'Notes', accessor: 'notes', Cell: gradeButton.bind(null, variant, setSelected) },
    ...(secondary ? [{ Header: 'Historique', accessor: 'historique', Cell: historyButton.bind(null, setHistory) }] : []),
  ];
  const fields = [
    { name: 'titre', label: 'Titre', required: true },
    { name: 'description', label: 'Description' },
    ...(secondary ? [
      {
        name: 'classe', label: 'Classe', resource: 'classes/classes', required: true,
      },
      {
        name: 'matiere', label: 'Matière', resource: 'classes/matieres', required: true,
      },
      {
        name: 'periode', label: 'Période', resource: 'etablissement/periodes', labelField: 'libelle', required: true,
      },
      {
        name: 'enseignant', label: 'Enseignant', resource: 'enseignants/personnel', labelField: 'full_name', required: true,
      },
      {
        name: 'eleve_cible', label: 'Élève ciblé (laisser vide pour la classe)', resource: 'eleves', labelField: 'matricule',
      },
      {
        name: 'type',
        label: 'Type',
        required: true,
        defaultValue: 'ds',
        choices: choices([
          ['interrogation', 'Interrogation'], ['ds', 'Devoir surveillé'], ['dm', 'Devoir maison'],
          ['tp', 'Travaux pratiques'], ['oral', 'Oral'], ['projet', 'Projet'],
          ['examen_blanc', 'Examen blanc'], ['examen_final', 'Examen final'],
        ]),
      },
    ] : [
      {
        name: 'ecue', label: 'ECUE', resource: 'ue-ecue/ecues', required: true,
      },
      {
        name: 'semestre', label: 'Semestre', resource: 'etablissement/semestres', labelField: 'libelle', required: true,
      },
      {
        name: 'enseignant', label: 'Enseignant', resource: 'utilisateurs/comptes', labelField: 'full_name', required: true,
      },
      {
        name: 'modalite',
        label: 'Modalité',
        required: true,
        defaultValue: 'cc',
        choices: choices([
          ['cc', 'Contrôle continu'], ['tp', 'Travaux pratiques'], ['projet', 'Projet'],
          ['examen_ecrit', 'Examen écrit'], ['examen_oral', 'Examen oral'], ['rattrapage', 'Rattrapage'],
        ]),
      },
    ]),
    {
      name: 'date', label: 'Date', type: 'date', required: true,
    },
    {
      name: 'bareme', label: 'Barème (sans offre)', type: 'number', defaultValue: 20, required: true,
    },
    {
      name: 'coefficient', label: 'Coefficient', type: 'number', defaultValue: 1, required: true,
    },
    {
      name: 'ponderation', label: 'Pondération (%)', type: 'number', defaultValue: 100, required: true,
    },
  ];
  return (
    <Stack spacing={2}>
      <Alert severity="info">
        La saisie ci-dessous concerne le contrôle continu non anonyme.
        Les examens et la notation anonyme utilisent leurs parcours dédiés.
        Une nouvelle évaluation hérite des règles de l’offre de sa classe ou formation.
        Son barème chiffré est alors défini automatiquement et reste figé.
      </Alert>
      {notice && <Alert severity="success">{notice}</Alert>}
      <ResourceManager variant={variant} resource="notes/evaluations" title="Évaluations" columns={columns} fields={fields} />
      {selected && (
        <GradeEntryDialog
          key={selected.id}
          variant={variant}
          evaluation={selected}
          onClose={() => setSelected(null)}
          onSaved={() => { setSelected(null); setNotice('Notes enregistrées.'); }}
        />
      )}
      {secondary && (
        <WorkflowHistoryPanel
          apiType="secondaire"
          endpoint={history ? `notes/evaluations/${history}/historique/` : ''}
          title="Historique de l'évaluation"
        />
      )}
    </Stack>
  );
};

EvaluationsManager.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
};

export default EvaluationsManager;
