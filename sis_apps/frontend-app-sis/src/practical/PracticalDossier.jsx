import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Button } from '@openedx/paragon';
import { useQuery } from '@tanstack/react-query';
import { usePractical } from './PracticalContext';
import {
  AuditList, Evidence, Failure, Field, Pagination, recordType,
} from './PracticalControls';
import { AssessmentForm, DecisionForm, HourForm } from './PracticalDossierForms';
import { duration, labelStatus, queryOptions } from './practicalContract';

const hourCommands = [
  ['can_submit', 'soumettre', 'Soumettre les heures', false],
  ['can_validate', 'valider', 'Valider les heures', false],
  ['can_reject', 'rejeter', 'Rejeter les heures', true],
  ['can_cancel', 'annuler', 'Annuler cette saisie', true],
  ['can_invalidate', 'invalider', 'Invalider les heures validées', true],
];
const dossierCommands = [
  ['can_close', 'clore', 'Clôturer avec succès', false],
  ['can_cancel', 'annuler', 'Annuler administrativement le dossier', true],
  ['can_revoke_partner', 'partenaire/revoquer', 'Révoquer l’accès partenaire à ce dossier', true],
];
const pagePath = (path, page) => `${path}?page=${page}&page_size=20`;
const permissionsFor = (dossier, action) => {
  const { permissions } = dossier;
  const has = suffix => permissions.includes(`stages.${suffix}`);
  if (['can_validate', 'can_reject', 'can_invalidate'].includes(action)) { return has('valider_heures_pratiques'); }
  if (['can_enter_hours', 'can_submit', 'can_replace'].includes(action)) { return has('saisir_heures_pratiques'); }
  if (action === 'can_evaluate') { return has('evaluer_competences_pratiques'); }
  if (action === 'can_cancel') { return has('gerer_suivi_pratique') || has('saisir_heures_pratiques'); }
  return has('gerer_suivi_pratique');
};
const businessAllowed = (dossier, action, flags = dossier.actions) => dossier.statut === 'ouvert'
  && flags[action] && permissionsFor(dossier, action);
const terminalAllowed = (dossier, action) => (action === 'can_revoke_partner'
  ? dossier.actions[action] && permissionsFor(dossier, action)
  : businessAllowed(dossier, action));

const Report = ({
  report, dossier, onEvaluate, disabled,
}) => (
  <section aria-label="Bilan des exigences" className="my-4">
    <h3>Bilan des exigences — révision figée {report.programme.revision}</h3>
    <dl>
      {[
        ['minutes_requises', 'Requises'], ['minutes_validees', 'Validées'],
        ['minutes_restantes', 'Restantes'], ['minutes_excedentaires', 'Excédentaires'],
        ['minutes_brouillon', 'Brouillon'], ['minutes_soumises', 'Soumises'],
        ['minutes_rejetees', 'Rejetées (historique)'], ['minutes_annulees', 'Annulées (historique)'],
      ].map(([field, label]) => (
        <React.Fragment key={field}><dt>{label}</dt><dd>{duration(report.heures[field])}</dd></React.Fragment>
      ))}
    </dl>
    <p>
      Seules les heures actuellement validées contribuent au seuil.
      Les totaux historiques rejetés et annulés peuvent inclure du travail remplacé
      et ne s’additionnent pas au travail reconnu.
    </p>
    <p>{report.competences_acquises} / {report.competences_requises} compétences acquises.</p>
    {report.cloture_reussie ? <p>Clôture réussie enregistrée.</p> : (
      <p>{report.seuils_atteints ? 'Seuils atteints ; cela ne vaut pas clôture.' : 'Seuils non atteints.'}</p>
    )}
    {report.statut === 'annule' && <Alert variant="warning">Dossier annulé administrativement, sans réussite. Motif : {report.motif_annulation}</Alert>}
    {report.criteres_non_satisfaits.length > 0 && <ul>{report.criteres_non_satisfaits.map(item => <li key={`${item.type}-${item.code}`}>{item.detail}</li>)}</ul>}
    {report.competences.map(item => (
      <article key={item.code} className="sis-panel my-2" aria-label={`Compétence — ${item.label}`}>
        <h4>{item.label} — {labelStatus(item.statut)}</h4>
        {item.evaluation ? (
          <>
            <p>
              Révision {item.evaluation.revision} — {item.evaluation.evalue_par.nom}
              {' '}— observation du {item.evaluation.date_observation}
            </p>
            <p>{item.evaluation.contexte_professionnel}</p>
            {item.evaluation.motif_revision && <p>Motif : {item.evaluation.motif_revision}</p>}
            <Evidence evidence={item.evaluation.preuve} />
          </>
        ) : <p>Évaluation en attente.</p>}
        {businessAllowed(dossier, 'can_evaluate') && item.actions.can_evaluate && (
          <Button disabled={disabled} onClick={() => onEvaluate(item.code)}>Évaluer {item.label}</Button>
        )}
      </article>
    ))}
  </section>
);
Report.propTypes = {
  report: recordType.isRequired,
  dossier: recordType.isRequired,
  onEvaluate: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

const PracticalDossier = ({ id, capabilities }) => {
  const {
    key, request, busy, clearNotice,
  } = usePractical();
  const [hoursPage, setHoursPage] = useState(1);
  const [evaluationsPage, setEvaluationsPage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);
  const [decisionsPage, setDecisionsPage] = useState(1);
  const [hourStatus, setHourStatus] = useState('');
  const [historyHour, setHistoryHour] = useState(null);
  const [dialog, setDialog] = useState(null);
  const root = `dossiers/${id}/`;
  const query = useQuery({
    ...queryOptions,
    placeholderData: previous => previous,
    queryKey: [...key, 'dossier-bundle', id, hoursPage, evaluationsPage, historyPage, historyHour, decisionsPage, hourStatus],
    queryFn: async ({ signal }) => {
      const read = (path, schema) => request(path, schema, { signal });
      const attempt = async () => {
        const dossier = await read(root, 'Dossier');
        const [report, hours, evaluations, history, decisions, selectedHour] = await Promise.all([
          dossier.actions.can_view_report ? read(`${root}rapport/`, 'Report') : null,
          read(`${pagePath(`${root}heures/`, hoursPage)}${hourStatus ? `&statut=${hourStatus}` : ''}`, 'Page<Hour>'),
          read(pagePath(`${root}evaluations/`, evaluationsPage), 'Page<Assessment>'),
          dossier.actions.can_view_history ? read(pagePath(`${root}historique/`, historyPage), 'Page<AuditEvent>') : null,
          historyHour && dossier.actions.can_view_history ? read(pagePath(`${root}heures/${historyHour}/decisions/`, decisionsPage), 'Page<HourDecision>') : null,
          historyHour ? read(`${root}heures/${historyHour}/`, 'Hour') : null,
        ]);
        const final = await read(root, 'Dossier');
        if (dossier.id !== id || final.id !== id || hours.results.some(item => item.dossier_id !== id)
          || evaluations.results.some(item => item.dossier_id !== id)
          || (selectedHour && (selectedHour.id !== historyHour || selectedHour.dossier_id !== id))
          || decisions?.results.some(item => item.heure_id !== historyHour)) {
          throw new Error('Relations de dossier incohérentes dans la réponse du serveur.');
        }
        if (dossier.version !== final.version
          || JSON.stringify(dossier.actions) !== JSON.stringify(final.actions)
          || JSON.stringify(dossier.permissions) !== JSON.stringify(final.permissions)
          || (report && (report.version !== final.version || report.dossier_id !== id
            || report.programme.sha256 !== dossier.programme.sha256 || report.statut !== dossier.statut
            || report.actions.can_close !== dossier.actions.can_close
            || report.actions.can_cancel !== dossier.actions.can_cancel))
          || hours.results.some(item => item.version_creation > final.version
            || item.derniere_decision.version_dossier > final.version)
          || evaluations.results.some(item => item.version_creation > final.version)) {
          return null;
        }
        return {
          dossier: final, report, hours, evaluations, history, decisions, selectedHour,
        };
      };
      // Only reads may retry: never reconcile a stale action set with a newer version.
      const bundle = await attempt() || await attempt();
      if (!bundle) { throw new Error('Le dossier change pendant la lecture. Actualisez avant toute opération.'); }
      return bundle;
    },
  });
  const { data } = query;
  const dossier = data?.dossier;
  const ready = Boolean(data && !query.isFetching && !query.isPlaceholderData && !query.error);
  const open = value => { clearNotice(); setDialog(value); };
  const close = () => setDialog(null);
  const currentHour = dialog?.hourId ? data?.hours.results.find(item => item.id === dialog.hourId) : null;
  const currentCriterion = data?.report?.competences.find(item => item.code === dialog?.code);
  const hourAllowed = ready && dialog?.kind === 'hour'
    && (dialog.hourId ? currentHour && businessAllowed(dossier, 'can_replace', currentHour.actions) : businessAllowed(dossier, 'can_enter_hours'));
  const decisionAllowed = ready && dialog?.kind === 'decision' && (dialog.hourId
    ? currentHour && businessAllowed(dossier, dialog.flag, currentHour.actions)
    : terminalAllowed(dossier, dialog.flag));
  return (
    <section aria-label="Dossier pratique sélectionné">
      {query.error && <Failure error={query.error} retry={() => query.refetch()} />}
      {query.isFetching && <p role="status">Relecture cohérente du dossier, des actions et du bilan…</p>}
      {ready && (
        <>
          <h2>{dossier.apprenant.utilisateur.nom} — {dossier.programme.titre}</h2>
          <p>{labelStatus(dossier.statut)} — version {dossier.version}. Matricule : {dossier.apprenant.matricule}.</p>
          <p>
            {dossier.programme.curriculum.libelle} — inscription {dossier.inscription.annee.libelle}
            {' '}— révision publiée figée {dossier.programme.revision}.
          </p>
          <p>Entreprise : {dossier.entreprise.nom}. Tuteur interne : {dossier.tuteur_interne.nom}.</p>
          <p>Partenaire : {dossier.partenaire?.nom || 'Aucun'}{dossier.partenaire_revoque_le ? ` — accès révoqué le ${dossier.partenaire_revoque_le}` : ''}.</p>
          <p>
            Période : {dossier.periode.date_debut} — {dossier.periode.date_fin}.
            Fuseau institutionnel : {dossier.periode.fuseau_horaire}.
          </p>
          <p>Missions : {dossier.missions}</p>
          {dossier.closed_at && <p>Clôture : {dossier.closed_at} — {dossier.clos_par.nom}</p>}
          {dossier.cancelled_at && (
            <p>Annulation : {dossier.cancelled_at} — {dossier.annule_par.nom}. Motif : {dossier.motif_annulation}</p>
          )}
          {(!dossier.liaisons_valides || dossier.blocages.length > 0) && <Alert variant="warning">Le contexte institutionnel empêche de nouvelles opérations : {dossier.blocages.join(', ')}.</Alert>}
          {dossier.statut !== 'ouvert' && <Alert variant="info">Dossier définitif : aucune modification des heures, compétences ou faits métier. Seule la révocation d’un accès partenaire encore présent peut rester autorisée.</Alert>}
          {dossierCommands.map(([flag, action, title, reason]) => terminalAllowed(dossier, flag) && (
            <Button
              className="mr-2 mb-2"
              key={action}
              disabled={busy}
              onClick={() => open({
                kind: 'decision', flag, action, title, reason,
              })}
            >{title}
            </Button>
          ))}
          {data.report && <Report report={data.report} dossier={dossier} disabled={busy} onEvaluate={code => open({ kind: 'assessment', code })} />}
          <section aria-label="Heures effectuées" className="my-4">
            <h3>Heures effectuées</h3>
            {businessAllowed(dossier, 'can_enter_hours') && <Button disabled={busy} onClick={() => open({ kind: 'hour' })}>Saisir les heures effectuées</Button>}
            <Field label="Filtrer les heures par état" options={['brouillon', 'soumise', 'validee', 'rejetee', 'annulee'].map(value => [value, labelStatus(value)])} value={hourStatus} disabled={busy} onChange={value => { setHourStatus(value); setHoursPage(1); setDialog(null); }} />
            {!data.hours.results.length && <p>Aucune heure enregistrée dans cette sélection.</p>}
            {data.hours.results.map(item => (
              <article key={item.id} className="sis-panel my-3" aria-label={`${item.date} ${item.heure_debut}–${item.heure_fin}`}>
                <h4>{item.date} — {item.heure_debut}–{item.heure_fin} — {labelStatus(item.statut)}</h4>
                <p>
                  {duration(item.minutes)} ; pause : {item.pause_minutes} min.
                  Saisie par {item.saisi_par.nom} le {item.created_at}.
                </p>
                <p>{item.activite}</p>
                {item.remplace_id && <p>Cette saisie est une correction ; l’original reste conservé.</p>}
                {item.remplacement_id && (
                  <p>Cette saisie a été remplacée. Le remplacement constitue une nouvelle ligne.</p>
                )}
                <p>Dernière décision : {item.derniere_decision.action} — {item.derniere_decision.acteur.nom}{item.derniere_decision.motif ? ` — ${item.derniere_decision.motif}` : ''}.</p>
                <Evidence evidence={item.preuve} />
                {hourCommands.map(([flag, action, title, reason]) => businessAllowed(dossier, flag, item.actions) && (
                  <Button
                    className="mr-2 mb-2"
                    disabled={busy}
                    key={action}
                    onClick={() => open({
                      kind: 'decision', hourId: item.id, flag, action, title, reason,
                    })}
                  >{title}
                  </Button>
                ))}
                {businessAllowed(dossier, 'can_replace', item.actions) && <Button className="mr-2" disabled={busy} onClick={() => open({ kind: 'hour', hourId: item.id })}>Remplacer cette saisie</Button>}
                {dossier.actions.can_view_history && (
                  <Button disabled={busy} onClick={() => { setHistoryHour(item.id); setDecisionsPage(1); }}>
                    Historique des décisions du {item.date} à {item.heure_debut}
                  </Button>
                )}
              </article>
            ))}
            <Pagination data={data.hours} page={hoursPage} setPage={setHoursPage} label="Heures effectuées" disabled={busy} />
          </section>
          {data.selectedHour && data.decisions && (
            <section aria-label="Décisions horaires conservées">
              <h3>
                Décisions horaires conservées — {data.selectedHour.date}
                {' '}{data.selectedHour.heure_debut}–{data.selectedHour.heure_fin}
              </h3>
              <p>{data.selectedHour.activite}</p>
              <Evidence evidence={data.selectedHour.preuve} />
              <AuditList rows={data.decisions.results} />
              <Pagination data={data.decisions} page={decisionsPage} setPage={setDecisionsPage} label="Décisions horaires" disabled={busy} />
              <Button variant="outline-primary" disabled={busy} onClick={() => setHistoryHour(null)}>Masquer les décisions horaires</Button>
            </section>
          )}
          <section aria-label="Historique des évaluations">
            <h3>Historique immuable des évaluations</h3>
            {!data.evaluations.results.length && <p>Aucune décision de compétence enregistrée.</p>}
            {data.evaluations.results.map(item => (
              <article key={item.id} className="sis-panel my-2">
                <h4>
                  {dossier.programme.competences.find(criterion => criterion.code === item.code)?.label || item.code}
                  {' '}— révision {item.revision}
                </h4>
                <p>{item.acquise ? 'Acquise' : 'Non acquise'} — {item.effective ? 'Décision effective' : 'Décision historique remplacée'}.</p>
                <p>{item.evalue_par.nom} — observation {item.date_observation} — enregistrement {item.created_at}.</p>
                <p>{item.contexte_professionnel}</p>
                {item.motif_revision && <p>Motif : {item.motif_revision}</p>}
                <Evidence evidence={item.preuve} />
              </article>
            ))}
            <Pagination data={data.evaluations} page={evaluationsPage} setPage={setEvaluationsPage} label="Évaluations" disabled={busy} />
          </section>
          {data.history && (
            <section aria-label="Historique du dossier">
              <h3>Historique du dossier</h3>
              <AuditList rows={data.history.results} />
              <Pagination data={data.history} page={historyPage} setPage={setHistoryPage} label="Historique du dossier" disabled={busy} />
            </section>
          )}
        </>
      )}
      {dialog?.kind === 'hour' && dossier && (
        <HourForm key={`hour-${dialog.hourId || 'new'}`} dossier={dossier} capabilities={capabilities} hour={currentHour} blocked={!ready || !hourAllowed} onClose={close} />
      )}
      {dialog?.kind === 'assessment' && dossier && currentCriterion && (
        <AssessmentForm key={dialog.code} dossier={dossier} capabilities={capabilities} criterion={currentCriterion} blocked={!ready || !businessAllowed(dossier, 'can_evaluate') || !currentCriterion.actions.can_evaluate} onClose={close} />
      )}
      {dialog?.kind === 'decision' && dossier && (
        <DecisionForm key={`${dialog.action}-${dialog.hourId || 'dossier'}`} dossier={dossier} hour={currentHour} action={dialog.action} title={dialog.title} reason={dialog.reason} blocked={!ready || !decisionAllowed} onClose={close} />
      )}
    </section>
  );
};
PracticalDossier.propTypes = { id: PropTypes.number.isRequired, capabilities: recordType.isRequired };
export default PracticalDossier;
