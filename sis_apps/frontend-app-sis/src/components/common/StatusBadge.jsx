import React from 'react';
import PropTypes from 'prop-types';
import { Chip } from '@mui/material';

const groups = {
  neutral: {
    brouillon: 'Brouillon', draft: 'Brouillon', inactif: 'Inactif', inactive: 'Inactive', provisoire: 'Provisoire',
  },
  pending: {
    prepare: 'Préparé',
    en_attente: 'En attente',
    pending: 'En attente',
    liste_attente: 'Liste d’attente',
    pre_inscrit: 'Pré-inscrit',
    reserve: 'Sous réserve',
  },
  submitted: {
    soumis: 'Soumis',
    soumise: 'Soumise',
    submitted: 'Soumis',
    deposee: 'Déposée',
    depose: 'Déposé',
    ouvert: 'Ouvert',
    ouverte: 'Ouverte',
    emise: 'Émise',
    propose: 'Proposé',
    queued: 'En file',
  },
  scheduled: {
    planifie: 'Planifié',
    planifiee: 'Planifiée',
    convoque: 'Convoqué',
    assignee: 'Assignée',
    affectee: 'Affectée',
    entretien: 'Entretien planifié',
    preselectionne: 'Présélectionné',
  },
  processing: {
    en_cours: 'En cours',
    processing: 'En cours',
    en_instruction: 'En instruction',
    en_relecture: 'En relecture',
    correction: 'En correction',
    a_moderer: 'À modérer',
    en_mobilite: 'En mobilité',
    contractuel: 'Contractuel',
  },
  approved: {
    valide: 'Validé',
    validee: 'Validée',
    valid: 'Valide',
    validated: 'Validé',
    verified: 'Vérifié',
    accepte: 'Accepté',
    acceptee: 'Acceptée',
    accordee: 'Accordée',
    confirmee: 'Confirmée',
    actif: 'Actif',
    active: 'Active',
    inscrit: 'Inscrit',
    present: 'Présent',
    presente: 'Présentée',
    disponible: 'Disponible',
    acquis: 'Acquis',
    titulaire: 'Titulaire',
    complete: 'Dossier complet',
  },
  completed: {
    termine: 'Terminé',
    terminee: 'Terminée',
    traite: 'Traité',
    done: 'Traité',
    sent: 'Livré',
    resolue: 'Résolue',
    cloturee: 'Clôturée',
    cloture: 'Clôturé',
    closed: 'Clôturé',
    ferme: 'Fermé',
    fermee: 'Fermée',
    finalisee: 'Finalisée',
    effectue: 'Effectué',
    tenu: 'Tenu',
    tenue: 'Tenue',
    published: 'Publié',
    publie: 'Publié',
    publiee: 'Publiée',
    signe: 'Signé',
    payee: 'Payée',
    rendu: 'Rendu',
    soutenu: 'Soutenu',
    soutenue: 'Soutenue',
    delibere: 'Délibéré',
    diplome: 'Diplômé',
    attribue: 'Attribué',
    pourvue: 'Pourvue',
    reuni: 'Réuni',
    passe: 'Passé',
  },
  attention: {
    incomplet: 'Incomplet',
    incomplete: 'Dossier incomplet',
    complement: 'Complément demandé',
    retard: 'Retard',
    en_retard: 'En retard',
    retrying: 'Nouvelle tentative',
    partielle: 'Partiellement payée',
    suspendu: 'Suspendu',
    suspendue: 'Suspendue',
    stagiaire: 'Stagiaire',
    reporte: 'Reporté',
  },
  rejected: {
    refuse: 'Refusé',
    refusee: 'Refusée',
    rejete: 'Rejeté',
    echec: 'Échec',
    failed: 'Échec',
    absent: 'Absent',
    absente: 'Absente',
    non_rendue: 'Non rendue',
    perdu: 'Perdu',
    triche: 'Triche',
    sanctionne: 'Sanctionné',
  },
  revoked: {
    revoque: 'Révoqué', revoquee: 'Révoquée', recours: 'Recours', dead: 'Échec définitif',
  },
  cancelled: {
    annule: 'Annulé',
    annulee: 'Annulée',
    abandon: 'Abandon',
    abandonnee: 'Abandonnée',
    desiste: 'Désisté',
    classe: 'Classé sans suite',
    skipped: 'Ignoré',
    sortie_anticipee: 'Sortie anticipée',
  },
  archived: {
    archive: 'Archivé', archivee: 'Archivée', expire: 'Expiré', expiree: 'Expirée', sortant: 'Sortant',
  },
  adjusted: {
    absent_justifie: 'Absent justifié',
    dispense: 'Dispensé',
    dispensee: 'Dispensée',
    rembourse: 'Remboursé',
    renouvele: 'Renouvelé',
    recuperee: 'Récupérée',
    reopened: 'Réouvert',
    modifie: 'Modifié',
    modifiee: 'Modifiée',
    transfere: 'Transféré',
    transfert: 'Transfert',
    redoublant: 'Redoublant',
    vacataire: 'Vacataire',
    signee_ecole: 'Signée par l’école',
    signee_etablissement: 'Signée par l’établissement',
    signee_entreprise: 'Signée par l’entreprise',
    signee_etudiant: 'Signée par l’étudiant',
    valide_accueil: 'Validé par l’établissement d’accueil',
    valide_local: 'Validé par l’établissement d’origine',
  },
};

const normalize = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .toLowerCase()
  .replace(/[\s’'-]+/g, '_');
const statuses = Object.fromEntries(Object.entries(groups).flatMap(([tone, entries]) => Object.entries(entries)
  .flatMap(([value, label]) => [[value, { label, tone }], [normalize(label), { label, tone }]])));

export const statusPresentation = value => statuses[normalize(value)] || { label: value || 'Non renseigné', tone: 'neutral' };

const StatusBadge = ({ value, label }) => {
  const status = statusPresentation(value);
  return (
    <Chip
      className="sis-status-badge"
      data-status-tone={status.tone}
      size="small"
      variant="outlined"
      label={label || status.label}
      sx={{
        '&.MuiChip-root': {
          color: `var(--sis-status-${status.tone}-text)`,
          backgroundColor: `var(--sis-status-${status.tone}-surface)`,
          borderColor: 'currentColor',
          height: 'auto',
          minHeight: 26,
          maxWidth: '100%',
        },
        '& .MuiChip-label': { whiteSpace: 'normal', py: 0.5, lineHeight: 1.4 },
      }}
    />
  );
};
StatusBadge.propTypes = { value: PropTypes.string, label: PropTypes.string };
StatusBadge.defaultProps = { value: undefined, label: undefined };

export default StatusBadge;
