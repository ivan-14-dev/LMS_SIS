import React from 'react';
import PropTypes from 'prop-types';
import {
  CommandForm, Failure, Field, recordType, Selector,
} from './ResearchControls';
import { useResearch, useResearchQuery } from './ResearchContext';
import {
  decimal, interval, labTypes, multipart, pdfFile, publicationTypes, validDate,
} from './researchUi';

const relation = (row, field, label) => (row?.[field] ? { id: row[field], nom: row[label] || `${field} ${row[field]}` } : null);
const lines = value => String(value || '').split('\n').map(item => item.trim()).filter(Boolean);
const selectedId = (value, label, optional = false) => {
  if (!value?.id && !optional) { throw new Error(`Sélectionnez ${label} parmi les choix autorisés.`); }
  return value?.id || null;
};
const teacherResource = 'laboratoires/selecteurs/?type=enseignants';
const field = (values, change, name, label, props = {}) => (
  <Field label={label} value={values[name]} onChange={value => change(name, value)} {...props} />
);
const teacherSelector = (values, change, name, label, props = {}) => (
  <Selector
    label={label}
    resource={teacherResource}
    value={values[name]}
    onChange={value => change(name, value)}
    {...props}
  />
);

const ProjectRelations = ({
  values, change, publication, legacy, editing,
}) => {
  const project = values.projectSelection;
  const query = useResearchQuery(project ? `projets-recherche/${project.id}/` : null, Boolean(project));
  const team = query.data ? [query.data.responsable, ...(query.data.membres_list || []).map(item => item.id)] : [];
  return (
    <>
      {editing ? <p>Rattachement immuable : {project?.titre || 'Dossier historique sans projet'}</p> : (
        <Selector
          label="Projet de rattachement"
          resource="projets-recherche/"
          value={project}
          onChange={value => change('projectSelection', value)}
          eligible={item => item.can_manage === true && !item.archive}
        />
      )}
      {query.isFetching && project && <p role="status">Lecture de l’équipe du projet…</p>}
      {query.error && <Failure error={query.error} retry={() => query.refetch()} />}
      {project && query.data && !query.error && (
        <p>
          Laboratoire : {query.data.laboratoire_nom}.
          Les encadrants et auteurs doivent appartenir à l’équipe du projet.
        </p>
      )}
      {!project && legacy && <p>Laboratoire historique : {values.labSelection?.nom}</p>}
      {publication ? teacherSelector(values, change, 'authors', 'Auteurs du projet', {
        multiple: true, eligible: item => team.includes(item.id),
      }) : (
        <>
          <Selector
            label="Doctorant local actif"
            resource="laboratoires/selecteurs/?type=etudiants"
            value={values.student}
            onChange={value => change('student', value)}
          />
          {teacherSelector(values, change, 'director', 'Directeur de thèse', { eligible: item => (!project && legacy) || team.includes(item.id) })}
          {teacherSelector(values, change, 'coDirector', 'Co-directeur de thèse (facultatif)', { eligible: item => (!project && legacy) || team.includes(item.id) })}
        </>
      )}
    </>
  );
};
ProjectRelations.propTypes = {
  values: PropTypes.shape({ projectSelection: recordType, labSelection: recordType, student: recordType }).isRequired,
  change: PropTypes.func.isRequired,
  publication: PropTypes.bool,
  legacy: PropTypes.bool,
  editing: PropTypes.bool,
};

const initialValues = (resource, row, project) => {
  const common = { ...row };
  if (resource === 'laboratoires') {
    return {
      ...common,
      type: row.type || 'UMR',
      faculty: relation(row, 'faculte', 'faculte_nom'),
      director: relation(row, 'directeur', 'directeur_nom'),
      tutelle: (row.tutelle || []).join('\n'),
      axes_recherche: (row.axes_recherche || []).join('\n'),
    };
  }
  if (resource === 'projets-recherche') {
    return {
      ...common,
      budget: row.budget ?? '',
      labSelection: relation(row, 'laboratoire', 'laboratoire_nom'),
      lead: relation(row, 'responsable', 'responsable_nom'),
      team: row.membres_list || [],
    };
  }
  return {
    ...common,
    projectSelection: project || (row.projet ? {
      id: row.projet, titre: row.projet_titre, laboratoire: row.laboratoire, laboratoire_nom: row.laboratoire_nom,
    } : null),
    labSelection: relation(row, 'laboratoire', 'laboratoire_nom'),
    type: row.type || 'article',
    authors: row.auteurs_list || [],
    student: relation(row, 'doctorant', 'doctorant_nom'),
    director: relation(row, 'directeur', 'directeur_nom'),
    coDirector: relation(row, 'co_directeur', 'co_directeur_nom'),
    mots_cles: (row.mots_cles || []).join('\n'),
    fichier: undefined,
  };
};

export const metadataPayload = (resource, values, version, legacy = false) => {
  const payload = version ? { version } : {};
  const copy = names => names.forEach(name => { payload[name] = values[name] ?? ''; });
  if (resource === 'laboratoires') {
    copy(['nom', 'acronyme', 'type', 'numero_rnsr']);
    return {
      ...payload,
      faculte: selectedId(values.faculty, 'une faculté', true),
      directeur: selectedId(values.director, 'un directeur', true),
      tutelle: lines(values.tutelle),
      axes_recherche: lines(values.axes_recherche),
    };
  }
  if (resource === 'projets-recherche') {
    copy(['titre', 'acronyme', 'description', 'financeur', 'reference', 'date_debut', 'date_fin']);
    interval(values.date_debut, values.date_fin);
    return {
      ...payload,
      laboratoire: selectedId(values.labSelection, 'un laboratoire'),
      responsable: selectedId(values.lead, 'un responsable'),
      membres: values.team.map(item => item.id),
      budget: decimal(values.budget),
    };
  }
  copy(['titre']);
  payload.projet = selectedId(values.projectSelection, 'un projet', legacy);
  payload.laboratoire = values.projectSelection?.laboratoire || selectedId(values.labSelection, 'un laboratoire');
  if (resource === 'theses') {
    copy(['resume', 'financement']);
    if (values.director?.id === values.coDirector?.id && values.director) {
      throw new Error('Le directeur et le co-directeur doivent être distincts.');
    }
    return {
      ...payload,
      date_debut: validDate(values.date_debut),
      mots_cles: lines(values.mots_cles),
      doctorant: selectedId(values.student, 'un doctorant actif'),
      directeur: selectedId(values.director, 'un directeur'),
      co_directeur: selectedId(values.coDirector, 'un co-directeur', true),
    };
  }
  copy(['type', 'doi', 'url_hal']);
  if (!/^[1-9]\d{0,3}$/.test(String(values.annee))) { throw new Error('Année de publication invalide.'); }
  if (!values.authors.length) { throw new Error('Sélectionnez au moins un auteur du projet.'); }
  const publication = {
    ...payload,
    annee: values.annee,
    auteurs: values.authors.map(item => item.id),
    facteur_impact: values.facteur_impact ? decimal(values.facteur_impact, { digits: 3 }) : null,
  };
  if (values.fichier) { publication.fichier = pdfFile(values.fichier); }
  return values.fichier ? multipart(publication) : publication;
};

const MetadataFields = ({
  resource, values, change, legacy, editing,
}) => {
  if (resource === 'laboratoires') {
    return (
      <>
        {field(values, change, 'nom', 'Nom du laboratoire', { required: true, maxLength: 200 })}
        {field(values, change, 'acronyme', 'Acronyme', { required: true, maxLength: 20 })}
        {field(values, change, 'type', 'Type de laboratoire', { required: true, options: labTypes })}
        <Selector label="Faculté" resource="laboratoires/selecteurs/?type=facultes" value={values.faculty} onChange={value => change('faculty', value)} />
        {teacherSelector(values, change, 'director', 'Directeur du laboratoire (facultatif)')}
        {field(values, change, 'tutelle', 'Tutelles (une par ligne)', { type: 'textarea' })}
        {field(values, change, 'axes_recherche', 'Axes de recherche (un par ligne)', { type: 'textarea' })}
        {field(values, change, 'numero_rnsr', 'Numéro RNSR', { maxLength: 20 })}
      </>
    );
  }
  if (resource === 'projets-recherche') {
    return (
      <>
        {field(values, change, 'titre', 'Titre du projet', { required: true, maxLength: 300 })}
        {field(values, change, 'acronyme', 'Acronyme', { maxLength: 20 })}
        {field(values, change, 'description', 'Description du projet', { type: 'textarea', required: true })}
        {editing ? <p>Laboratoire (rattachement immuable) : {values.labSelection?.nom}</p> : (
          <Selector
            label="Laboratoire"
            resource="laboratoires/"
            value={values.labSelection}
            onChange={value => change('labSelection', value)}
            eligible={item => item.can_manage === true && !item.archive}
          />
        )}
        {teacherSelector(values, change, 'lead', 'Responsable du projet')}
        {teacherSelector(values, change, 'team', 'Membres chercheurs', { multiple: true })}
        {field(values, change, 'financeur', 'Financeur', { maxLength: 200 })}
        {field(values, change, 'reference', 'Référence du projet', { maxLength: 100 })}
        {field(values, change, 'budget', 'Budget (EUR)', { required: true, inputMode: 'decimal', help: 'Décimal exact, par exemple 12500.50. Aucun calcul flottant.' })}
        {field(values, change, 'date_debut', 'Date de début', { required: true, type: 'date' })}
        {field(values, change, 'date_fin', 'Date de fin', { required: true, type: 'date', min: values.date_debut })}
      </>
    );
  }
  return (
    <>
      {field(values, change, 'titre', resource === 'theses' ? 'Titre de la thèse' : 'Titre de la publication', { required: true, maxLength: 300 })}
      <ProjectRelations values={values} change={change} publication={resource !== 'theses'} legacy={legacy} editing={editing} />
      {resource === 'theses' ? (
        <>
          {field(values, change, 'resume', 'Résumé', { type: 'textarea', required: true })}
          {field(values, change, 'mots_cles', 'Mots-clés (un par ligne)', { type: 'textarea' })}
          {field(values, change, 'financement', 'Financement doctoral', { maxLength: 200 })}
          {field(values, change, 'date_debut', 'Date de début de thèse', { required: true, type: 'date' })}
        </>
      ) : (
        <>
          {field(values, change, 'type', 'Type de publication', { required: true, options: publicationTypes })}
          {field(values, change, 'annee', 'Année de publication', { required: true, inputMode: 'numeric', pattern: '[1-9][0-9]{0,3}' })}
          {field(values, change, 'doi', 'DOI', { maxLength: 100 })}
          {field(values, change, 'url_hal', 'URL HAL', { type: 'url' })}
          {field(values, change, 'facteur_impact', 'Facteur d’impact', { inputMode: 'decimal' })}
          <Field label="PDF de la publication" type="file" accept=".pdf,application/pdf" onChange={value => change('fichier', value)} help="Le fichier existant est conservé si aucun remplacement n’est sélectionné. Tout fichier joint doit être un PDF valide." />
          {values.fichier && <p>Fichier sélectionné : {values.fichier.name}</p>}
        </>
      )}
    </>
  );
};
MetadataFields.propTypes = {
  resource: PropTypes.string.isRequired,
  values: PropTypes.shape({
    faculty: recordType,
    labSelection: recordType,
    date_debut: PropTypes.string,
    fichier: PropTypes.shape({ name: PropTypes.string }),
  }).isRequired,
  change: PropTypes.func.isRequired,
  legacy: PropTypes.bool,
  editing: PropTypes.bool,
};

const titles = {
  laboratoires: 'le laboratoire',
  'projets-recherche': 'le projet',
  'productions-scientifiques': 'la publication',
  theses: 'la thèse',
};
export const MetadataEditor = ({
  resource, record, project, onClose,
}) => {
  const { refresh } = useResearch();
  const path = `${resource}/${record ? `${record.id}/` : ''}`;
  const legacy = resource === 'theses' && Boolean(record && !record.projet);
  return (
    <CommandForm
      title={`${record ? 'Modifier' : 'Créer'} ${titles[resource]}`}
      path={path}
      method={record ? 'patch' : 'post'}
      record={record}
      recordPath={record ? path : undefined}
      initial={initialValues(resource, record || {}, project)}
      build={(values, version) => metadataPayload(resource, values, version, legacy)}
      onSaved={refresh}
      onClose={onClose}
    >
      {(values, change) => (
        <MetadataFields
          resource={resource}
          values={values}
          change={change}
          legacy={legacy}
          editing={Boolean(record)}
        />
      )}
    </CommandForm>
  );
};
MetadataEditor.propTypes = {
  resource: PropTypes.string.isRequired, record: recordType, project: recordType, onClose: PropTypes.func.isRequired,
};

export const LifecycleCommand = ({
  resource, record, action, title, onClose,
}) => {
  const { refresh } = useResearch();
  return (
    <CommandForm
      title={title}
      path={`${resource}/${record.id}/${action}/`}
      recordPath={`${resource}/${record.id}/`}
      record={record}
      build={(values, version) => ({
        version, ...(action === 'soutenir' ? { date_soutenance: validDate(values.date_soutenance) } : {}),
      })}
      onSaved={refresh}
      onClose={onClose}
    >
      {(values, change) => (
        <>
          <p>Confirmer cette transition ? Le serveur vérifie les préconditions et conserve l’historique.</p>
          {action === 'archiver' && <p>L’objet archivé ne pourra plus être modifié.</p>}
          {action === 'terminer' && <p>Tous les jalons doivent être acceptés et aucun engagement ne doit rester ouvert.</p>}
          {action === 'soutenir' && field(values, change, 'date_soutenance', 'Date de soutenance', { required: true, type: 'date', min: record.date_debut })}
        </>
      )}
    </CommandForm>
  );
};
LifecycleCommand.propTypes = {
  resource: PropTypes.string.isRequired,
  record: recordType.isRequired,
  action: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  onClose: PropTypes.func.isRequired,
};
