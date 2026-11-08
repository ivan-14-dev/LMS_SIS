import { apiErrorMessage } from '../../services/resources';

export const resources = {
  laboratoires: 'Laboratoires',
  'projets-recherche': 'Projets',
  'productions-scientifiques': 'Publications',
  theses: 'Thèses',
};

export const labTypes = [
  ['UMR', 'Unité mixte de recherche'], ['EA', 'Équipe d’accueil'],
  ['FRE', 'Formation de recherche en évolution'], ['USR', 'Unité de service et de recherche'],
  ['individuel', 'Laboratoire individuel'],
];
export const publicationTypes = [
  ['article', 'Article scientifique'], ['communication', 'Communication'],
  ['chapitre', 'Chapitre d’ouvrage'], ['livre', 'Livre'], ['brevet', 'Brevet'],
  ['these', 'Thèse'], ['hdr', 'HDR'],
];
export const operationTypes = [
  ['financement', 'Encaissement confirmé'],
  ['engagement', 'Engagement de budget'],
  ['depense', 'Paiement confirmé'],
  ['annulation_engagement', 'Annulation du reliquat d’engagement'],
  ['contrepassation', 'Contrepassation'],
];

export const statusLabel = value => ({
  propose: 'Proposé',
  accepte: 'Accepté',
  en_cours: 'En cours',
  suspendu: 'Suspendu',
  termine: 'Terminé',
  brouillon: 'Brouillon',
  validee: 'Validée',
  publiee: 'Publiée',
  soutenue: 'Soutenue',
  suspendue: 'Suspendue',
  abandonnee: 'Abandonnée',
  a_faire: 'À faire',
  soumis: 'Soumis',
}[value] || value);

export const commandsFor = (resource, row) => {
  if (!row?.can_manage || row.archive) { return []; }
  if (resource === 'laboratoires') { return row.can_archiver === false ? [] : [['archiver', 'Archiver le laboratoire']]; }
  const transitions = {
    'projets-recherche': {
      propose: [['accepter', 'Accepter le projet']],
      accepte: [['demarrer', 'Démarrer le projet']],
      en_cours: [['suspendre', 'Suspendre le projet'], ['terminer', 'Terminer le projet']],
      suspendu: [['reprendre', 'Reprendre le projet']],
      termine: [['archiver', 'Archiver le projet']],
    },
    'productions-scientifiques': {
      brouillon: [['valider', 'Valider la publication']],
      validee: [['publier', 'Publier la publication']],
      publiee: [['archiver', 'Archiver la publication']],
    },
    theses: {
      en_cours: [['soutenir', 'Enregistrer la soutenance'], ['suspendre', 'Suspendre la thèse'], ['abandonner', 'Abandonner la thèse']],
      suspendue: [['reprendre', 'Reprendre la thèse'], ['abandonner', 'Abandonner la thèse']],
      soutenue: [['archiver', 'Archiver la thèse']],
      abandonnee: [['archiver', 'Archiver la thèse']],
    },
  };
  return (transitions[resource]?.[row.statut] || []).filter(([command]) => row[`can_${command}`] !== false);
};

export const errorMessage = error => {
  const prefixes = {
    401: 'Session expirée. Reconnectez-vous.',
    403: 'Accès refusé ou module Recherche désactivé. Les données privées sont masquées.',
    404: 'Objet indisponible, supprimé ou hors de votre périmètre.',
    409: 'Conflit : état, version ou référence incompatible. Aucun succès ne peut être présumé.',
    400: 'Validation refusée. Vérifiez les champs indiqués.',
  };
  return `${prefixes[error?.response?.status] || 'La demande a échoué.'} ${apiErrorMessage(error)}`;
};
export const isDenied = error => [401, 403, 404].includes(error?.response?.status);
export const isConflict = error => error?.response?.status === 409;

export const decimal = (value, { positive = false, digits = 10 } = {}) => {
  const text = String(value ?? '');
  if (!new RegExp(`^(0|[1-9][0-9]{0,${digits - 1}})(\\.[0-9]{1,2})?$`).test(text)
      || (positive && !/[1-9]/.test(text))) {
    throw new Error('Montant invalide : utilisez un nombre décimal positif, sans séparateur de milliers, avec au plus deux décimales.');
  }
  const [whole, fraction = ''] = text.split('.');
  return `${whole}.${fraction.padEnd(2, '0')}`;
};
export const validDate = value => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '') || value.startsWith('0000')) {
    throw new Error('Date requise au format AAAA-MM-JJ, avec une année positive.');
  }
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
    throw new Error('Date invalide.');
  }
  return value;
};
export const today = () => {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
};
export const interval = (start, end) => {
  validDate(start); validDate(end);
  if (end < start) { throw new Error('La fin doit être postérieure ou égale au début.'); }
};
export const versionOf = row => {
  if (!Number.isSafeInteger(row?.version) || row.version < 1) {
    throw new Error('Version serveur absente ou invalide. Rechargez l’objet avant toute commande.');
  }
  return row.version;
};
export const multipart = payload => {
  const body = new FormData();
  Object.entries(payload).forEach(([name, value]) => {
    if (value === undefined) { return; }
    if (Array.isArray(value)) {
      value.forEach(item => body.append(name, String(item)));
    } else {
      body.append(name, value === null ? '' : value);
    }
  });
  return body;
};
export const pdfFile = file => {
  if (!(file instanceof File) || !/\.pdf$/i.test(file.name)
      || (file.type && file.type !== 'application/pdf') || !file.size) {
    throw new Error('Sélectionnez un fichier PDF non vide. Le serveur vérifie également son contenu.');
  }
  return file;
};
export const newOperationKey = () => {
  if (globalThis.crypto?.randomUUID) { return globalThis.crypto.randomUUID(); }
  if (!globalThis.crypto?.getRandomValues) { throw new Error('Générateur UUID sécurisé indisponible.'); }
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] % 16) + 64;
  bytes[8] = (bytes[8] % 64) + 128;
  const text = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${text.slice(0, 8)}-${text.slice(8, 12)}-${text.slice(12, 16)}-${text.slice(16, 20)}-${text.slice(20)}`;
};
export const operationPayload = (values, project, key) => {
  const date = validDate(values.date_operation);
  if (date > today() || date < project.date_debut) {
    throw new Error('La date doit être comprise entre le début du projet et aujourd’hui.');
  }
  if (!values.reference?.trim() || !values.libelle?.trim()) {
    throw new Error('Une référence unique et un libellé / motif explicite sont obligatoires.');
  }
  if (!(values.justificatif instanceof File) || !values.justificatif.size) {
    throw new Error('Un justificatif réel et non vide est obligatoire.');
  }
  const payload = {
    version: versionOf(project),
    idempotency_key: key,
    type: values.type,
    montant: decimal(values.montant, { positive: true }),
    reference: values.reference.trim(),
    date_operation: date,
    libelle: values.libelle.trim(),
    justificatif: values.justificatif,
  };
  if (['depense', 'annulation_engagement'].includes(values.type)) {
    if (!values.engagement) { throw new Error('Sélectionnez un engagement existant de ce projet.'); }
    payload.engagement = values.engagement;
  }
  if (values.type === 'contrepassation') {
    if (!values.contrepassation_de) { throw new Error('Sélectionnez l’encaissement ou le paiement d’origine.'); }
    payload.contrepassation_de = values.contrepassation_de;
  }
  return payload;
};
