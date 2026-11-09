export const practicalPermissions = [
  'stages.gerer_suivi_pratique', 'stages.consulter_suivi_pratique',
  'stages.saisir_heures_pratiques', 'stages.valider_heures_pratiques',
  'stages.evaluer_competences_pratiques',
];
export const queryOptions = {
  retry: false, gcTime: 0, staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: true,
};
export const isDenied = error => [401, 403, 404].includes(error?.response?.status);
export const isConflict = error => error?.response?.status === 409;
export const errorMessage = error => {
  const body = error?.response?.data;
  if (!body || body instanceof Blob) { return error?.message || 'Requête refusée par le serveur.'; }
  return [
    body.detail,
    ...Object.entries(body.errors || {}).map(([field, messages]) => `${field} : ${messages.join(' ')}`),
    ...(body.criteres_non_satisfaits || []).map(item => item.detail),
  ].filter(Boolean).join(' — ') || 'Requête refusée par le serveur.';
};

const text = value => typeof value === 'string';
const boolean = value => typeof value === 'boolean';
const integer = value => Number.isSafeInteger(value) && value >= 0;
const positive = value => integer(value) && value > 0;
const oneOf = (...values) => value => values.includes(value);
const nullable = check => value => value === null || check(value);
const array = check => value => Array.isArray(value) && value.every(check);
const object = fields => value => value !== null && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === Object.keys(fields).length
  && Object.entries(fields).every(([key, check]) => Object.hasOwn(value, key) && check(value[key]));
const date = value => text(value) && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && Number.isFinite(Date.parse(`${value}T00:00:00Z`))
  && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
const time = value => text(value) && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
const endTime = value => value === '24:00' || time(value);
const timestamp = value => text(value) && /Z$/.test(value) && Number.isFinite(Date.parse(value));
const hash = value => text(value) && /^[a-f0-9]{64}$/.test(value);
const code = value => text(value) && /^[a-z][a-z0-9_-]{0,63}$/.test(value);
const permissions = array(oneOf(...practicalPermissions));
const actions = names => object(Object.fromEntries(names.split(' ').map(name => [name, boolean])));
const statuses = oneOf('ouvert', 'clos', 'annule');
const hourStatuses = oneOf('brouillon', 'soumise', 'validee', 'rejetee', 'annulee');
const actor = object({ id: positive, nom: text });
const period = object({
  id: positive, libelle: text, date_debut: date, date_fin: date,
});
const offering = object({
  code: text, label: text, version: positive, mode_evaluation: oneOf('numeric', 'pass_fail', 'competency'), sha256: hash,
});
const curriculum = object({
  id: positive,
  type: oneOf('classe', 'formation'),
  libelle: text,
  code: nullable(text),
  annee: nullable(period),
  offre: nullable(offering),
});
const criterion = object({ code, label: value => text(value) && value.trim().length > 0 && value.length <= 240 });
const revision = object({
  id: positive,
  numero: positive,
  statut: oneOf('brouillon', 'publie', 'archive'),
  titre: text,
  minutes_requises: integer,
  competences: array(criterion),
  offre_source: nullable(offering),
  created_at: timestamp,
  cree_par: actor,
  published_at: nullable(timestamp),
  publie_par: nullable(actor),
  archived_at: nullable(timestamp),
  archive_par: nullable(actor),
});
const snapshot = object({
  programme_id: positive,
  revision_id: positive,
  revision: positive,
  code,
  titre: text,
  curriculum,
  minutes_requises: positive,
  competences: array(criterion),
  offre_source: nullable(offering),
  published_at: timestamp,
  sha256: hash,
});
const programme = object({
  id: positive,
  version: positive,
  etablissement_id: positive,
  code,
  curriculum,
  revision_courante: revision,
  revision_publiee: nullable(revision),
  created_at: timestamp,
  updated_at: timestamp,
  permissions,
  actions: actions('can_configure can_publish can_revise can_archive can_open_dossier'),
});
const learner = object({ id: positive, utilisateur: actor, matricule: text });
const enrolment = object({ id: positive, type: oneOf('inscription', 'inscription_administrative'), annee: period });
const company = object({ id: positive, nom: text });
const dossier = object({
  id: positive,
  version: positive,
  statut: statuses,
  convention_id: positive,
  programme: snapshot,
  apprenant: learner,
  inscription: enrolment,
  entreprise: company,
  tuteur_interne: actor,
  partenaire: nullable(actor),
  partenaire_revoque_le: nullable(timestamp),
  periode: object({ date_debut: date, date_fin: date, fuseau_horaire: text }),
  missions: text,
  liaisons_valides: boolean,
  blocages: array(oneOf('liaison_modifiee', 'acteur_inactif', 'curriculum_inactif', 'fuseau_modifie')),
  created_at: timestamp,
  cree_par: actor,
  closed_at: nullable(timestamp),
  clos_par: nullable(actor),
  cancelled_at: nullable(timestamp),
  annule_par: nullable(actor),
  motif_annulation: nullable(text),
  permissions,
  actions: actions('can_enter_hours can_evaluate can_close can_cancel can_revoke_partner can_view_report can_view_history'),
});
export const evidencePath = value => text(value)
  && /^\/api\/v1\/stages\/pratique\/dossiers\/[1-9]\d*\/(?:heures|evaluations)\/[1-9]\d*\/preuve\/$/.test(value);
const evidence = object({
  nom: text,
  taille: positive,
  sha256: hash,
  content_type: oneOf('application/pdf'),
  version_creation: positive,
  download_url: evidencePath,
  actions: actions('can_download'),
});
const decision = object({
  id: positive,
  heure_id: positive,
  sequence: positive,
  action: oneOf('creation', 'soumission', 'validation', 'rejet', 'annulation', 'invalidation', 'remplacement', 'fermeture'),
  etat_avant: nullable(hourStatuses),
  etat_apres: hourStatuses,
  motif: nullable(text),
  acteur: actor,
  created_at: timestamp,
  version_dossier: positive,
  heure_remplacement_id: nullable(positive),
});
const hour = object({
  id: positive,
  dossier_id: positive,
  date,
  heure_debut: time,
  heure_fin: endTime,
  pause_minutes: integer,
  minutes: positive,
  activite: text,
  statut: hourStatuses,
  saisi_par: actor,
  created_at: timestamp,
  version_creation: positive,
  remplace_id: nullable(positive),
  remplacement_id: nullable(positive),
  preuve: nullable(evidence),
  derniere_decision: decision,
  actions: actions('can_submit can_replace can_cancel can_validate can_reject can_invalidate'),
});
const assessment = object({
  id: positive,
  dossier_id: positive,
  code,
  revision: positive,
  acquise: boolean,
  contexte_professionnel: text,
  date_observation: date,
  motif_revision: nullable(text),
  remplace_id: nullable(positive),
  evalue_par: actor,
  created_at: timestamp,
  version_creation: positive,
  preuve: nullable(evidence),
  effective: boolean,
});
const reportCriterion = object({
  code,
  label: text,
  statut: oneOf('non_evaluee', 'non_acquise', 'acquise'),
  evaluation: nullable(assessment),
  actions: actions('can_evaluate'),
});
const unmet = object({
  type: oneOf('minutes', 'competence'), code: nullable(code), minutes_manquantes: nullable(positive), detail: text,
});
const report = object({
  dossier_id: positive,
  version: positive,
  statut: statuses,
  programme: snapshot,
  heures: object({
    minutes_requises: positive,
    minutes_validees: integer,
    minutes_restantes: integer,
    minutes_excedentaires: integer,
    minutes_brouillon: integer,
    minutes_soumises: integer,
    minutes_rejetees: integer,
    minutes_annulees: integer,
  }),
  competences: array(reportCriterion),
  competences_requises: positive,
  competences_acquises: integer,
  criteres_non_satisfaits: array(unmet),
  seuils_atteints: boolean,
  cloture_reussie: boolean,
  closed_at: nullable(timestamp),
  clos_par: nullable(actor),
  cancelled_at: nullable(timestamp),
  annule_par: nullable(actor),
  motif_annulation: nullable(text),
  actions: actions('can_close can_cancel'),
});
const auditActions = [
  'programme_creation', 'programme_configuration', 'programme_publication', 'programme_revision', 'programme_archivage',
  'dossier_ouverture', 'dossier_cloture', 'dossier_annulation', 'partenaire_revocation',
  'heure_creation', 'heure_soumission', 'heure_validation', 'heure_rejet', 'heure_annulation',
  'heure_invalidation', 'heure_remplacement', 'competence_evaluation',
];
const schemas = {
  Curriculum: curriculum,
  Programme: programme,
  ProgrammeRevision: revision,
  ConventionCandidate: object({
    id: positive,
    empreinte: hash,
    libelle: text,
    statut: oneOf('complete'),
    apprenant: learner,
    curriculum,
    inscription: enrolment,
    entreprise: company,
    tuteur_interne: actor,
    habilitations_tuteur: actions('can_validate can_evaluate'),
    partenaire_lie: nullable(actor),
    mode_partenaire: oneOf('contact_entreprise', 'affectation_explicite'),
    contact_entreprise_id: nullable(positive),
    date_debut: date,
    date_fin: date,
    date_signature_complete: timestamp,
    missions: text,
    duree_planifiee_minutes: nullable(integer),
  }),
  PartnerCandidate: object({
    utilisateur: actor, can_consult: boolean, can_validate: boolean, can_evaluate: boolean,
  }),
  Dossier: dossier,
  Hour: hour,
  HourDecision: decision,
  Assessment: assessment,
  Report: report,
  AuditEvent: object({
    id: positive,
    action: oneOf(...auditActions),
    version: positive,
    acteur: actor,
    created_at: timestamp,
    motif: nullable(text),
    revision_id: nullable(positive),
    heure_id: nullable(positive),
    evaluation_id: nullable(positive),
    heures_annulees: array(positive),
  }),
  Capabilities: object({
    contract_version: oneOf(1),
    variant: oneOf('secondaire', 'superieur'),
    module: oneOf('sis.practical_training'),
    fuseau_horaire: text,
    date_locale: date,
    heure_locale: time,
    permissions,
    actions: actions('can_create_programme can_list_programmes can_open_dossier can_list_dossiers'),
    limits: object({
      max_competences: oneOf(100),
      max_pdf_bytes: positive,
      max_activite_length: oneOf(4000),
      max_contexte_length: oneOf(4000),
      max_motif_length: oneOf(4000),
    }),
  }),
  ProgrammeMutation: object({ version: positive, programme }),
  DossierMutation: object({
    version: positive, dossier, rapport: report, heures_annulees: array(positive),
  }),
  HourMutation: object({ version: positive, heure: hour, heure_precedente: nullable(hour) }),
  AssessmentMutation: object({ version: positive, evaluation: assessment }),
};

export const checked = (name, value) => {
  const pageType = /^Page<(.+)>$/.exec(name);
  const check = pageType ? object({
    count: integer, next: nullable(text), previous: nullable(text), results: array(schemas[pageType[1]]),
  }) : schemas[name];
  if (!check || !check(value)) { throw new Error(`Réponse ${name} incompatible avec le contrat pratique. Aucune opération n’est autorisée sur ces données.`); }
  return value;
};

const nonempty = max => value => text(value) && value === value.trim() && value.length > 0 && value.length <= max;
const requirements = {
  titre: nonempty(200),
  minutes_requises: value => integer(value) && value <= 2147483647,
  competences: value => array(criterion)(value) && value.length <= 100
    && new Set(value.map(item => item.code)).size === value.length,
};
const hourFields = {
  version: positive,
  date,
  heure_debut: time,
  heure_fin: endTime,
  pause_minutes: value => integer(value) && value <= 1439,
  activite: nonempty(4000),
};
export const checkedCommand = (name, value, variant) => {
  const commands = {
    CreateProgramme: {
      version: oneOf(0), curriculum: positive, code, ...requirements,
    },
    ConfigureProgramme: { version: positive, ...requirements },
    VersionCommand: { version: positive },
    ReasonCommand: { version: positive, motif: nonempty(4000) },
    ReviseProgramme: { version: positive, revision_source: positive },
    ArchiveProgramme: { version: positive, revision: positive, motif: nonempty(4000) },
    OpenDossier: {
      version: oneOf(0),
      programme: positive,
      programme_version: positive,
      revision: positive,
      convention: positive,
      convention_empreinte: hash,
      ...(variant === 'secondaire' && Object.hasOwn(value, 'partenaire_utilisateur')
        ? { partenaire_utilisateur: nullable(positive) } : {}),
    },
    RecordHour: hourFields,
    ReplaceHour: { ...hourFields, motif: nonempty(4000) },
    AssessCompetency: {
      version: positive,
      acquise: boolean,
      contexte_professionnel: nonempty(4000),
      date_observation: date,
      ...(Object.hasOwn(value, 'motif_revision') ? { motif_revision: nonempty(4000) } : {}),
    },
  };
  if (!commands[name] || !object(commands[name])(value)) {
    throw new Error('Données invalides : vérifiez les champs obligatoires, les entiers et la version de la commande.');
  }
  return value;
};

export const wholeNumber = value => {
  if (!/^(0|[1-9]\d*)$/.test(String(value)) || !integer(Number(value))) {
    throw new Error('Saisissez un nombre entier positif ou nul.');
  }
  return Number(value);
};
export const multipart = (payload, file, maxBytes) => {
  if (!file) { return payload; }
  if (!/\.pdf$/i.test(file.name) || file.type !== 'application/pdf' || file.size < 1 || file.size > maxBytes) {
    throw new Error(`Une preuve PDF non vide est attendue (maximum ${maxBytes} octets).`);
  }
  const form = new FormData();
  form.append('payload', JSON.stringify(payload));
  form.append('fichier', file);
  return form;
};
export const duration = minutes => `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')} (${minutes} min)`;
export const labelStatus = value => ({
  ouvert: 'Ouvert',
  clos: 'Clôturé avec succès',
  annule: 'Annulé administrativement',
  brouillon: 'Brouillon',
  soumise: 'Soumise',
  validee: 'Validée',
  rejetee: 'Rejetée',
  annulee: 'Annulée',
  publie: 'Publié',
  archive: 'Archivé',
  acquise: 'Acquise',
  non_acquise: 'Non acquise',
  non_evaluee: 'Non évaluée',
}[value] || value);
