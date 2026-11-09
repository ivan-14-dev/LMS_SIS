import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Button } from '@openedx/paragon';
import { usePractical, usePracticalQuery } from './PracticalContext';
import {
  AuditList, Collection, CommandForm, Failure, Field, recordType,
} from './PracticalControls';
import { duration, labelStatus, wholeNumber } from './practicalContract';

const prerequisite = 'Aucune convention admissible : une convention existante complète et signée, une inscription éligible dans ce cursus, des acteurs locaux habilités et des dates cohérentes sont nécessaires. Leur création ou régularisation se fait dans les outils institutionnels existants, pas dans cet écran.';
const requirementValues = revision => ({
  titre: revision?.titre || '',
  minutes_requises: revision?.minutes_requises ?? 0,
  competences: (revision?.competences || [{ code: '', label: '' }]).map((item, index) => ({ ...item, key: index + 1 })),
});
const requirementPayload = values => ({
  titre: values.titre.trim(),
  minutes_requises: wholeNumber(values.minutes_requises),
  competences: values.competences.map(({ code, label }) => ({ code: code.trim(), label: label.trim() })),
});

const Requirements = ({ values, change }) => (
  <>
    <Field label="Titre du programme" value={values.titre} onChange={value => change('titre', value)} required maxLength={200} />
    <Field label="Minutes réellement validées requises" type="number" min={0} max={2147483647} step={1} value={values.minutes_requises} onChange={value => change('minutes_requises', value)} required />
    <p>
      La publication exige un seuil positif et au moins une compétence.
      Toutes les compétences publiées devront être acquises.
    </p>
    {values.competences.map((item, index) => (
      <fieldset key={item.key} className="border p-3 mb-2">
        <legend className="h5">Compétence {index + 1}</legend>
        <Field
          label={`Code de compétence ${index + 1}`}
          value={item.code}
          required
          pattern="[a-z][a-z0-9_-]{0,63}"
          maxLength={64}
          onChange={value => change('competences', values.competences.map(row => (row.key === item.key ? { ...row, code: value } : row)))}
        />
        <Field
          label={`Libellé de compétence ${index + 1}`}
          value={item.label}
          required
          maxLength={240}
          onChange={value => change('competences', values.competences.map(row => (row.key === item.key ? { ...row, label: value } : row)))}
        />
        <Button variant="outline-primary" onClick={() => change('competences', values.competences.filter(row => row.key !== item.key))}>Retirer la compétence {index + 1}</Button>
      </fieldset>
    ))}
    <Button
      className="mb-3"
      variant="outline-primary"
      disabled={values.competences.length >= 100}
      onClick={() => change('competences', [...values.competences, {
        key: Math.max(0, ...values.competences.map(item => item.key)) + 1, code: '', label: '',
      }])}
    >Ajouter une compétence
    </Button>
  </>
);
Requirements.propTypes = { values: recordType.isRequired, change: PropTypes.func.isRequired };

export const CreateProgramme = ({ onClose, onCreated }) => {
  const [curriculum, setCurriculum] = useState(null);
  const { busy } = usePractical();
  return (
    <CommandForm
      title="Créer le programme"
      initial={{ ...requirementValues(), code: '' }}
      version={0}
      onClose={onClose}
      onSaved={result => onCreated(result.programme.id)}
      build={values => ({
        path: 'programmes/',
        schema: 'CreateProgramme',
        response: 'ProgrammeMutation',
        payload: {
          version: 0, curriculum: curriculum?.id, code: values.code.trim(), ...requirementPayload(values),
        },
      })}
    >
      {(values, change) => (
        <>
          <Collection path="curriculums/" schema="Curriculum" title="Cursus autorisés" empty="Aucun cursus admissible à la création dans votre périmètre.">
            {rows => rows.map(item => (
              <p key={item.id}>
                <Button variant="link" disabled={busy} onClick={() => setCurriculum(item)}>Choisir {item.libelle}{item.annee ? ` — ${item.annee.libelle}` : ''}</Button>
              </p>
            ))}
          </Collection>
          <p>Cursus sélectionné : {curriculum?.libelle || 'Aucun'}</p>
          <Field label="Code stable du programme" value={values.code} onChange={value => change('code', value)} required pattern="[a-z][a-z0-9_-]{0,63}" maxLength={64} />
          <Requirements values={values} change={change} />
        </>
      )}
    </CommandForm>
  );
};
CreateProgramme.propTypes = { onClose: PropTypes.func.isRequired, onCreated: PropTypes.func.isRequired };

const OpenDossier = ({
  programme, blocked, onClose, onOpened,
}) => {
  const { variant, busy } = usePractical();
  const [convention, setConvention] = useState(null);
  const [partner, setPartner] = useState(null);
  const published = programme.revision_publiee;
  const path = `programmes/${programme.id}/conventions/`;
  return (
    <CommandForm
      title="Ouvrir le dossier pratique"
      version={0}
      blocked={blocked || !published || !programme.actions.can_open_dossier}
      onClose={onClose}
      onSaved={result => onOpened(result.dossier.id)}
      onConflict={() => { setConvention(null); setPartner(null); }}
      build={() => ({
        path: 'dossiers/',
        schema: 'OpenDossier',
        response: 'DossierMutation',
        payload: {
          version: 0,
          programme: programme.id,
          programme_version: programme.version,
          revision: published.numero,
          convention: convention?.id,
          convention_empreinte: convention?.empreinte,
          ...(variant === 'secondaire' ? { partenaire_utilisateur: partner?.utilisateur.id || null } : {}),
        },
      })}
    >
      {() => (
        <>
          <p>
            Programme {programme.code} — révision publiée {published?.numero}.
            Version du programme : {programme.version}.
          </p>
          {published && (
            <Collection key={`${programme.version}-${published.numero}`} path={`${path}?revision=${published.numero}`} schema="ConventionCandidate" title="Conventions complètes admissibles" empty={prerequisite}>
              {rows => rows.map(item => (
                <p key={item.id}>
                  <Button variant="link" disabled={busy} onClick={() => { setConvention(item); setPartner(null); }}>
                    Choisir {item.libelle} — {item.apprenant.utilisateur.nom} — {item.entreprise.nom}
                  </Button>
                </p>
              ))}
            </Collection>
          )}
          {convention && (
            <section aria-label="Convention sélectionnée">
              <h4>{convention.libelle}</h4>
              <p>Apprenant : {convention.apprenant.utilisateur.nom} — {convention.apprenant.matricule}</p>
              <p>Cursus : {convention.curriculum.libelle} — inscription {convention.inscription.annee.libelle}</p>
              <p>Entreprise : {convention.entreprise.nom} — tuteur interne : {convention.tuteur_interne.nom}</p>
              <p>
                Habilitations actuelles du tuteur : validation des heures
                {' '}{convention.habilitations_tuteur.can_validate ? 'autorisée' : 'non autorisée'} ;
                évaluation des compétences
                {' '}{convention.habilitations_tuteur.can_evaluate ? 'autorisée' : 'non autorisée'}.
              </p>
              {(!convention.habilitations_tuteur.can_validate || !convention.habilitations_tuteur.can_evaluate) && (
                <Alert variant="warning">
                  Le tuteur ne dispose pas de toutes les habilitations nécessaires au parcours complet.
                  Vérifiez les habilitations des acteurs affectés avant de poursuivre.
                  L’ouverture du dossier n’accorde aucune permission supplémentaire.
                </Alert>
              )}
              <p>
                Du {convention.date_debut} au {convention.date_fin}.
                Signature complète : {convention.date_signature_complete}.
              </p>
              <p>Missions : {convention.missions}</p>
              {convention.duree_planifiee_minutes !== null && (
                <p>
                  Durée prévisionnelle informative : {duration(convention.duree_planifiee_minutes)}.
                  Elle ne compte jamais comme travail effectué.
                </p>
              )}
              {variant === 'superieur' ? (
                <p>Partenaire issu du contact entreprise actuel : {convention.partenaire_lie?.nom || 'Aucun compte partenaire éligible'}. Aucune autre affectation ne peut être saisie ici.</p>
              ) : (
                <>
                  <Collection
                    key={convention.id}
                    path={`${path}${convention.id}/partenaires/?revision=${published.numero}`}
                    schema="PartnerCandidate"
                    title="Partenaire facultatif"
                    empty="Aucun partenaire habilité dans ce contexte. Le dossier peut être ouvert sans partenaire."
                  >
                    {rows => rows.map(item => (
                      <p key={item.utilisateur.id}>
                        <Button variant="link" disabled={busy} onClick={() => setPartner(item)}>Choisir {item.utilisateur.nom}</Button>
                        {' '}{item.can_consult && 'Consultation. '}{item.can_validate && 'Validation des heures. '}{item.can_evaluate && 'Évaluation des compétences.'}
                      </p>
                    ))}
                  </Collection>
                  <p>Partenaire sélectionné : {partner?.utilisateur.nom || 'Aucun'}</p>
                  {partner && <Button variant="outline-primary" disabled={busy} onClick={() => setPartner(null)}>Retirer le partenaire sélectionné</Button>}
                </>
              )}
            </section>
          )}
        </>
      )}
    </CommandForm>
  );
};
OpenDossier.propTypes = {
  programme: recordType.isRequired,
  blocked: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
  onOpened: PropTypes.func.isRequired,
};

export const ProgrammePanel = ({ id, onOpened, canOpen }) => {
  const { busy } = usePractical();
  const query = usePracticalQuery(`programmes/${id}/`, 'Programme');
  const [dialog, setDialog] = useState(null);
  const programme = query.data;
  const ready = programme && !query.isFetching && !query.error;
  const open = (kind, revision = null) => setDialog({ kind, revision });
  const close = () => setDialog(null);
  const labels = {
    configurer: 'Configurer le brouillon',
    publier: 'Publier les exigences',
    reviser: 'Créer une nouvelle révision',
    archiver: 'Archiver la révision',
  };
  const flag = {
    configurer: 'can_configure', publier: 'can_publish', reviser: 'can_revise', archiver: 'can_archive',
  };
  return (
    <section aria-label="Programme sélectionné">
      {query.error && <Failure error={query.error} retry={() => query.refetch()} />}
      {query.isFetching && <p role="status">Relecture du programme…</p>}
      {ready && (
        <>
          <h2>{programme.revision_courante.titre}</h2>
          <p>
            {programme.code} — {programme.curriculum.libelle}. Version : {programme.version}.
            Révision courante : {programme.revision_courante.numero}
            {' '}({labelStatus(programme.revision_courante.statut)}).
          </p>
          <p>Exigences courantes : {duration(programme.revision_courante.minutes_requises)}.</p>
          <ul>
            {programme.revision_courante.competences.map(item => <li key={item.code}>{item.label} ({item.code})</li>)}
          </ul>
          <Alert variant="info">La publication fige les exigences. Une nouvelle révision ou un archivage ne modifie jamais les dossiers déjà ouverts.</Alert>
          {programme.actions.can_configure && <Button className="mr-2" disabled={busy} onClick={() => open('configurer')}>Configurer le brouillon</Button>}
          {programme.actions.can_publish && <Button className="mr-2" disabled={busy} onClick={() => open('publier')}>Publier les exigences</Button>}
          {canOpen && programme.actions.can_open_dossier && programme.revision_publiee && <Button disabled={busy} onClick={() => open('ouvrir')}>Ouvrir un dossier depuis la révision publiée</Button>}
          <Collection path={`programmes/${id}/revisions/`} schema="ProgrammeRevision" title="Révisions conservées" searchable={false}>
            {rows => rows.map(item => (
              <article key={item.id} className="border-bottom py-3">
                <h4>Révision {item.numero} — {item.titre} — {labelStatus(item.statut)}</h4>
                <p>{duration(item.minutes_requises)} — créée par {item.cree_par.nom} le {item.created_at}</p>
                <ul>
                  {item.competences.map(criterion => (
                    <li key={criterion.code}>{criterion.label} ({criterion.code})</li>
                  ))}
                </ul>
                {item.published_at && <p>Publication : {item.published_at} — {item.publie_par.nom}</p>}
                {item.archived_at && <p>Archivage : {item.archived_at} — {item.archive_par.nom}</p>}
                {programme.actions.can_revise && item.statut !== 'brouillon' && <Button className="mr-2" disabled={busy} onClick={() => open('reviser', item.numero)}>Réviser depuis la révision {item.numero}</Button>}
                {programme.actions.can_archive && item.statut !== 'archive' && <Button disabled={busy} onClick={() => open('archiver', item.numero)}>Archiver la révision {item.numero}</Button>}
              </article>
            ))}
          </Collection>
          <Collection path={`programmes/${id}/historique/`} schema="AuditEvent" title="Historique du programme" searchable={false}>
            {rows => <AuditList rows={rows} />}
          </Collection>
        </>
      )}
      {dialog?.kind === 'ouvrir' && programme && <OpenDossier programme={programme} blocked={!ready || !canOpen} onClose={close} onOpened={onOpened} />}
      {dialog && dialog.kind !== 'ouvrir' && programme && (
        <CommandForm
          key={`${dialog.kind}-${dialog.revision}`}
          title={labels[dialog.kind]}
          initial={{ ...requirementValues(programme.revision_courante), motif: '' }}
          version={programme.version}
          blocked={!ready || !programme.actions[flag[dialog.kind]]}
          onClose={close}
          build={values => ({
            path: `programmes/${id}/${dialog.kind}/`,
            programmeId: id,
            response: 'ProgrammeMutation',
            schema: {
              configurer: 'ConfigureProgramme', publier: 'VersionCommand', reviser: 'ReviseProgramme', archiver: 'ArchiveProgramme',
            }[dialog.kind],
            payload: {
              version: programme.version,
              ...(dialog.kind === 'configurer' ? requirementPayload(values) : {}),
              ...(dialog.kind === 'reviser' ? { revision_source: dialog.revision } : {}),
              ...(dialog.kind === 'archiver' ? { revision: dialog.revision, motif: values.motif.trim() } : {}),
            },
          })}
        >
          {(values, change) => (
            <>
              {dialog.kind === 'configurer' && <Requirements values={values} change={change} />}
              {dialog.kind === 'reviser' && <p>Copier explicitement la révision {dialog.revision} vers un nouveau brouillon. La source restera intacte.</p>}
              {dialog.kind === 'publier' && <p>Publier et figer ces exigences ; l’ancienne publication sera archivée sans modifier les dossiers existants.</p>}
              {dialog.kind === 'archiver' && <><p>Arrêter la sélection future de la révision {dialog.revision} sans la supprimer.</p><Field label="Motif d’archivage" value={values.motif} onChange={value => change('motif', value)} type="textarea" required maxLength={4000} /></>}
            </>
          )}
        </CommandForm>
      )}
    </section>
  );
};
ProgrammePanel.propTypes = {
  id: PropTypes.number.isRequired, onOpened: PropTypes.func.isRequired, canOpen: PropTypes.bool,
};
