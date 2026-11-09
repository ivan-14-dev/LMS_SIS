import React from 'react';
import PropTypes from 'prop-types';
import { Alert } from '@openedx/paragon';
import { CommandForm, Field, recordType } from './PracticalControls';
import { wholeNumber } from './practicalContract';

export const HourForm = ({
  dossier, capabilities, hour, blocked, onClose,
}) => (
  <CommandForm
    title={hour ? 'Remplacer la saisie horaire' : 'Saisir les heures effectuées'}
    version={dossier.version}
    blocked={blocked}
    onClose={onClose}
    initial={{
      date: hour?.date || '',
      heure_debut: hour?.heure_debut || '',
      heure_fin: hour?.heure_fin || '',
      pause_minutes: hour?.pause_minutes ?? 0,
      activite: hour?.activite || '',
      motif: '',
      file: null,
    }}
    build={values => ({
      path: `dossiers/${dossier.id}/heures/${hour ? `${hour.id}/remplacer/` : ''}`,
      schema: hour ? 'ReplaceHour' : 'RecordHour',
      response: 'HourMutation',
      dossierId: dossier.id,
      payload: {
        version: dossier.version,
        date: values.date,
        heure_debut: values.heure_debut,
        heure_fin: values.heure_fin,
        pause_minutes: wholeNumber(values.pause_minutes),
        activite: values.activite.trim(),
        ...(hour ? { motif: values.motif.trim() } : {}),
      },
      file: values.file,
      maxBytes: capabilities.limits.max_pdf_bytes,
    })}
  >
    {(values, change) => (
      <>
        <Alert variant="info">
          Horloge institutionnelle : {dossier.periode.fuseau_horaire}.
          Date locale du serveur : {capabilities.date_locale}, {capabilities.heure_locale}.
          Ne saisissez que le travail déjà effectué. Les heures sont des minutes locales, pas une durée UTC.
          Séparez les nuits en deux dates (22:00–24:00 puis 00:00–02:00).
          Une transition d’heure saisonnière exige des intervalles séparés non ambigus.
        </Alert>
        <Field
          label="Date locale du travail"
          type="date"
          value={values.date}
          min={dossier.periode.date_debut}
          max={dossier.periode.date_fin < capabilities.date_locale
            ? dossier.periode.date_fin : capabilities.date_locale}
          onChange={value => change('date', value)}
          required
        />
        <Field label="Heure de début (HH:MM)" value={values.heure_debut} onChange={value => change('heure_debut', value)} required pattern="([01][0-9]|2[0-3]):[0-5][0-9]" placeholder="08:30" />
        <Field label="Heure de fin (HH:MM ou 24:00)" value={values.heure_fin} onChange={value => change('heure_fin', value)} required pattern="(([01][0-9]|2[0-3]):[0-5][0-9]|24:00)" placeholder="17:00" help="24:00 signifie la fin exclusive de cette date ; le travail jusqu’à minuit aujourd’hui ne peut pas être enregistré à l’avance." />
        <Field label="Pause en minutes" type="number" min={0} max={1439} step={1} value={values.pause_minutes} onChange={value => change('pause_minutes', value)} required />
        <Field label="Activité professionnelle réalisée" type="textarea" value={values.activite} onChange={value => change('activite', value)} required maxLength={capabilities.limits.max_activite_length} />
        {hour && (
          <>
            <p>
              La saisie et sa preuve originales restent dans l’historique.
              Aucune ancienne preuve n’est copiée automatiquement.
            </p>
            <Field label="Motif de remplacement" type="textarea" value={values.motif} onChange={value => change('motif', value)} required maxLength={capabilities.limits.max_motif_length} />
          </>
        )}
        <Field label="Preuve PDF facultative" type="file" accept=".pdf,application/pdf" onChange={value => change('file', value)} help={`Maximum ${capabilities.limits.max_pdf_bytes} octets. Preuve privée liée à cette saisie immuable.`} />
      </>
    )}
  </CommandForm>
);
HourForm.propTypes = {
  dossier: recordType.isRequired,
  capabilities: recordType.isRequired,
  hour: recordType,
  blocked: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
};

export const AssessmentForm = ({
  dossier, capabilities, criterion, blocked, onClose,
}) => (
  <CommandForm
    title={`Évaluer — ${criterion.label}`}
    version={dossier.version}
    initial={{
      acquise: '', contexte: '', date: '', motif: '', file: null,
    }}
    blocked={blocked}
    onClose={onClose}
    build={values => {
      if (!['oui', 'non'].includes(values.acquise)) { throw new Error('Choisissez explicitement acquise ou non acquise.'); }
      return {
        path: `dossiers/${dossier.id}/competences/${criterion.code}/evaluer/`,
        schema: 'AssessCompetency',
        response: 'AssessmentMutation',
        dossierId: dossier.id,
        payload: {
          version: dossier.version,
          acquise: values.acquise === 'oui',
          contexte_professionnel: values.contexte.trim(),
          date_observation: values.date,
          ...(criterion.evaluation ? { motif_revision: values.motif.trim() } : {}),
        },
        file: values.file,
        maxBytes: capabilities.limits.max_pdf_bytes,
      };
    }}
  >
    {(values, change) => (
      <>
        <p>
          Décision humaine sur la compétence publiée « {criterion.label} » ({criterion.code}).
          Fuseau : {dossier.periode.fuseau_horaire}.
        </p>
        <Field label="Acquisition de la compétence" options={[['oui', 'Acquise'], ['non', 'Non acquise']]} value={values.acquise} onChange={value => change('acquise', value)} required />
        <Field label="Contexte professionnel observé" type="textarea" value={values.contexte} onChange={value => change('contexte', value)} required maxLength={capabilities.limits.max_contexte_length} />
        <Field
          label="Date locale d’observation"
          type="date"
          min={dossier.periode.date_debut}
          max={dossier.periode.date_fin < capabilities.date_locale
            ? dossier.periode.date_fin : capabilities.date_locale}
          value={values.date}
          onChange={value => change('date', value)}
          required
        />
        {criterion.evaluation && (
          <>
            <p>
              Réévaluation : la décision précédente et sa preuve sont conservées.
              La dernière révision devient effective.
            </p>
            <Field label="Motif de réévaluation" type="textarea" value={values.motif} onChange={value => change('motif', value)} required maxLength={capabilities.limits.max_motif_length} />
          </>
        )}
        <Field label="Preuve PDF facultative" type="file" accept=".pdf,application/pdf" onChange={value => change('file', value)} help={`Maximum ${capabilities.limits.max_pdf_bytes} octets.`} />
      </>
    )}
  </CommandForm>
);
AssessmentForm.propTypes = {
  dossier: recordType.isRequired,
  capabilities: recordType.isRequired,
  criterion: recordType.isRequired,
  blocked: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
};

export const DecisionForm = ({
  dossier, hour, action, title, reason = false, blocked, onClose,
}) => (
  <CommandForm
    title={title}
    initial={{ motif: '', confirmation: '' }}
    version={dossier.version}
    blocked={blocked}
    onClose={onClose}
    build={values => ({
      path: `dossiers/${dossier.id}/${hour ? `heures/${hour.id}/` : ''}${action}/`,
      schema: reason ? 'ReasonCommand' : 'VersionCommand',
      response: hour ? 'HourMutation' : 'DossierMutation',
      dossierId: dossier.id,
      payload: { version: dossier.version, ...(reason ? { motif: values.motif.trim() } : {}) },
    })}
  >
    {(values, change) => (
      <>
        {hour && (
          <p>
            {hour.date} — {hour.heure_debut}–{hour.heure_fin} — {hour.activite}.
            Une décision est ajoutée sans effacer l’historique.
          </p>
        )}
        {!hour && action === 'clore' && <Alert variant="warning">Clôture réussie définitive : tous les seuils doivent être atteints. Les brouillons et heures soumises restants seront annulés et conservés dans l’historique. Aucune réouverture n’est possible.</Alert>}
        {!hour && action === 'annuler' && <Alert variant="warning">Annulation administrative définitive, distincte d’une réussite. Les heures déjà validées et toutes les décisions restent conservées ; les saisies en attente seront annulées.</Alert>}
        {action === 'partenaire/revoquer' && <Alert variant="warning">Révocation irréversible de l’accès partenaire à ce seul dossier, même après clôture ou annulation. Aucun fait métier n’est modifié. Les droits de gestion accordés séparément ne sont pas retirés.</Alert>}
        {reason && <Field label="Motif de la décision" value={values.motif} onChange={value => change('motif', value)} type="textarea" required maxLength={4000} />}
      </>
    )}
  </CommandForm>
);
DecisionForm.propTypes = {
  dossier: recordType.isRequired,
  hour: recordType,
  action: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  reason: PropTypes.bool,
  blocked: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
};
