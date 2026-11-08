import React, { useId, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Button, Card } from '@openedx/paragon';
import {
  Download, Failure, Field, Pagination, recordType, Selector,
} from './ResearchControls';
import {
  paginated, useLeaveGuard, useResearch, useResearchQuery,
} from './ResearchContext';
import {
  isConflict, multipart, newOperationKey, operationPayload, operationTypes, today, versionOf,
} from './researchUi';

const reportFields = [
  ['budget', 'Budget'], ['encaissements', 'Encaissements nets'],
  ['depenses', 'Dépenses nettes'], ['engagements_ouverts', 'Engagements ouverts'],
  ['disponible_budgetaire', 'Disponible budgétaire'], ['solde_tresorerie', 'Solde de trésorerie'],
  ['total_debit', 'Total des débits'], ['total_credit', 'Total des crédits'],
];
const eligibleTypes = project => operationTypes.filter(([type]) => {
  if (project.archive) { return false; }
  if (['engagement', 'depense'].includes(type)) { return project.statut === 'en_cours'; }
  if (type === 'financement') { return ['accepte', 'en_cours'].includes(project.statut); }
  return ['accepte', 'en_cours', 'termine'].includes(project.statut);
});
const checkedReport = (data, project) => {
  if (String(data.projet_id) !== String(project.id) || data.devise !== 'EUR'
      || data.rapproche !== true || !Number.isSafeInteger(data.version)
      || reportFields.some(([key]) => typeof data[key] !== 'string' || !/^-?\d+\.\d{2}$/.test(data[key]))) {
    throw new Error('Rapport financier incohérent : aucun solde ni rapprochement positif n’est affiché.');
  }
  return data;
};

const FinanceEditor = ({ project, onClose, onUnverified }) => {
  const { request, refresh, checking } = useResearch();
  const [values, setValues] = useState({
    type: '',
    montant: '',
    reference: '',
    date_operation: '',
    libelle: '',
    justificatif: null,
    engagement: null,
    contrepassation_de: null,
    confirmation: false,
  });
  const [attempt, setAttempt] = useState(null);
  const [version, setVersion] = useState(project.version);
  const [latest, setLatest] = useState(null);
  const [result, setResult] = useState(null);
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const sending = useRef(false);
  const confirmationId = useId();
  const reviewedId = useId();
  const path = `projets-recherche/${project.id}/`;
  useLeaveGuard(Boolean(attempt && !verified));
  const set = (name, value) => setValues(old => ({ ...old, [name]: value }));
  const verify = async (receipt = result) => {
    const [current, currentReport] = await Promise.all([
      request(path), request(`${path}rapport-financier/`),
    ]);
    checkedReport(currentReport, current);
    if (!current.can_finance || versionOf(current) < receipt.version || currentReport.version < receipt.version) {
      throw new Error('La relecture ne confirme pas encore la version financière enregistrée.');
    }
    await refresh();
    setVerified(true);
    onUnverified(false);
  };
  const send = async () => {
    if (sending.current || checking || result) { return; }
    sending.current = true; setBusy(true); setError(null);
    try {
      if (project.archive || !project.can_finance) { throw new Error('Ce projet ne permet plus d’écriture financière.'); }
      if (!values.confirmation) { throw new Error('Confirmez l’opération humaine et son justificatif.'); }
      const payload = attempt || operationPayload({
        ...values, engagement: values.engagement?.id, contrepassation_de: values.contrepassation_de?.id,
      }, { ...project, version }, newOperationKey());
      setAttempt(payload);
      onUnverified(true);
      const response = await request(`${path}operations-financieres/`, 'post', multipart({ ...payload, version }));
      if (!response?.operation?.id || response.operation.reference !== payload.reference
          || response.operation.montant !== payload.montant || typeof response.replayed !== 'boolean'
          || !Number.isSafeInteger(response.version)) {
        throw new Error('Réponse financière non confirmée. Rejouez uniquement la même opération.');
      }
      setResult(response);
      await verify(response);
    } catch (failure) { setError(failure); } finally { sending.current = false; setBusy(false); }
  };
  const locked = Boolean(attempt || busy || checking || project.archive);
  return (
    <Card className="my-3">
      <Card.Body>
        <form aria-label="Enregistrer une opération financière" onSubmit={event => { event.preventDefault(); send(); }}>
          <h3>Enregistrer une opération financière</h3>
          <Alert variant="info">Saisie d’une opération confirmée par une personne habilitée. Aucun virement bancaire n’est exécuté par cette interface.</Alert>
          {project.archive && <Alert variant="warning">Le projet est désormais archivé : aucune nouvelle écriture ni aucun rejeu n’est autorisé.</Alert>}
          {error && <Failure error={error} />}
          {attempt && (
            <p>Référence : {attempt.reference}. Clé d’idempotence : <code>{attempt.idempotency_key}</code>.
              La même tentative conserve ses champs et les mêmes octets de justificatif.
            </p>
          )}
          {result && (
            <Alert variant={verified ? 'success' : 'warning'}>
              {verified
                ? `${result.replayed ? 'Rejeu reconnu, sans nouvelle écriture.' : 'Opération enregistrée.'} Rapport, journal et projet relus sur le serveur.`
                : 'Le serveur a répondu ; le rapport n’a pas encore été relu. Aucun solde n’est présumé.'}
            </Alert>
          )}
          <fieldset disabled={locked}>
            <Field label="Nature de l’opération" value={values.type} onChange={value => set('type', value)} options={eligibleTypes(project)} required />
            <Field label="Montant exact (EUR)" value={values.montant} onChange={value => set('montant', value)} inputMode="decimal" required help="Exemple : 100.05. Pas de virgule, exposant, arrondi ni somme flottante." />
            <Field label="Référence unique de l’opération" value={values.reference} onChange={value => set('reference', value)} maxLength={100} required />
            <Field label="Date de l’opération" type="date" min={project.date_debut} max={today()} value={values.date_operation} onChange={value => set('date_operation', value)} required />
            <Field label="Libellé / motif" value={values.libelle} onChange={value => set('libelle', value)} maxLength={1000} required />
            {['depense', 'annulation_engagement'].includes(values.type) && (
              <Selector
                label="Engagement existant"
                searchable={false}
                resource={`${path}operations-financieres/`}
                value={values.engagement}
                onChange={value => set('engagement', value)}
                eligible={row => row.type === 'engagement'}
              />
            )}
            {values.type === 'annulation_engagement' && <p>Le montant doit être exactement le reliquat de cet engagement, contrôlé par le serveur. Consultez le journal et les paiements / corrections liés.</p>}
            {values.type === 'contrepassation' && (
              <>
                <Selector
                  label="Opération originale à contrepasser"
                  searchable={false}
                  resource={`${path}operations-financieres/`}
                  value={values.contrepassation_de}
                  onChange={value => setValues(old => ({ ...old, contrepassation_de: value, montant: value?.montant || '' }))}
                  eligible={row => ['financement', 'depense'].includes(row.type)}
                />
                <p>
                  Montant identique à l’original ; une seule contrepassation autorisée.
                  Le serveur vérifie les corrections déjà enregistrées.
                </p>
              </>
            )}
            <Field
              label="Justificatif obligatoire"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              onChange={value => set('justificatif', value)}
              required
            />
            {values.justificatif && <p>{values.justificatif.name}</p>}
            <label className="d-block mb-3" htmlFor={confirmationId}>
              <input id={confirmationId} type="checkbox" checked={values.confirmation} onChange={event => set('confirmation', event.target.checked)} required />
              {' '}Je confirme cette opération humaine et la fidélité de son justificatif ; il ne s’agit pas d’un virement automatique.
            </label>
            <Button type="submit">Confirmer l’enregistrement financier</Button>
          </fieldset>
          {attempt && !result && (
            <div className="my-3">
              <Alert variant="warning">
                Une réponse absente ou une erreur ne prouve pas l’absence d’enregistrement.
                Ne créez pas de nouvelle référence pour contourner cette tentative.
              </Alert>
              <Button disabled={busy || checking || project.archive} onClick={send}>
                Rejouer exactement cette opération
              </Button>
              {isConflict(error) && (
                <Button
                  disabled={busy || checking}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      const current = await request(path);
                      versionOf(current);
                      setLatest(current);
                    } catch (failure) {
                      setError(failure);
                    } finally { setBusy(false); }
                  }}
                >Relire la version du projet
                </Button>
              )}
              {latest && (
                <Alert variant="warning">
                  Version actuelle : {latest.version}. Les champs et la clé restent inchangés.
                  <Button
                    disabled={!latest.can_finance || latest.archive}
                    onClick={() => { setVersion(versionOf(latest)); setLatest(null); }}
                  >Utiliser cette version pour le rejeu
                  </Button>
                </Alert>
              )}
              {error?.response?.status === 400 && (
                <Button variant="outline-primary" onClick={() => { setAttempt(null); setError(null); }}>
                  Corriger la saisie refusée (nouvelle tentative)
                </Button>
              )}
              {isConflict(error) && (
                <div className="mt-3">
                  <label htmlFor={reviewedId}>
                    <input id={reviewedId} type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />
                    {' '}J’ai vérifié le journal et le conflit de référence ; je veux corriger cette saisie refusée, et non dupliquer une opération existante.
                  </label>
                  <Button
                    disabled={!reviewed || busy}
                    variant="outline-primary"
                    onClick={() => { setAttempt(null); setError(null); setReviewed(false); }}
                  >Corriger après vérification (nouvelle tentative)
                  </Button>
                </div>
              )}
            </div>
          )}
          {result && !verified && (
            <Button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try { await verify(); setError(null); } catch (failure) {
                  setError(failure);
                } finally { setBusy(false); }
              }}
            >Relire le rapport et le journal
            </Button>
          )}
          <Button
            className="mt-3"
            variant="tertiary"
            disabled={busy || Boolean(attempt && !result && !project.archive)}
            onClick={onClose}
          >Fermer l’opération
          </Button>
          {attempt && !result && <p>Gardez ce formulaire ouvert pour conserver la clé et le fichier de rejeu.</p>}
        </form>
      </Card.Body>
    </Card>
  );
};
FinanceEditor.propTypes = {
  project: recordType.isRequired, onClose: PropTypes.func.isRequired, onUnverified: PropTypes.func.isRequired,
};

const Journal = ({ project }) => {
  const [page, setPage] = useState(1);
  const path = `projets-recherche/${project.id}/`;
  const query = useResearchQuery(`${path}operations-financieres/?page=${page}`);
  let data;
  let invalid;
  try { if (query.data) { data = paginated(query.data); } } catch (error) { invalid = error; }
  return (
    <section aria-label="Journal financier">
      <h3>Journal immuable et justificatifs privés</h3>
      {(query.error || invalid) && <Failure error={query.error || invalid} retry={() => query.refetch()} />}
      {query.isFetching && <p role="status">Chargement du journal…</p>}
      {!query.isFetching && !query.error && !invalid && data && (
        <>
          {!data.results.length && <p>Aucune opération enregistrée.</p>}
          {data.results.map(row => (
            <article key={row.id} className="border p-3 mb-3">
              <h4>{row.reference} — {operationTypes.find(([value]) => value === row.type)?.[1] || row.type}</h4>
              <p>{row.date_operation} — {row.montant} EUR — {row.libelle}</p>
              <p>Identifiant : {row.id}{row.engagement ? ` — engagement lié : ${row.engagement}` : ''}{row.contrepassation_de ? ` — opération originale : ${row.contrepassation_de}` : ''}</p>
              <p>Justificatif : {row.justificatif_nom} — SHA-256 : <code>{row.justificatif_sha256}</code></p>
              <Download path={`${path}justificatifs/${row.id}/`} filename={row.justificatif_nom} kind="proof">Télécharger le justificatif {row.reference}</Download>
              <table className="table table-sm">
                <caption>Écritures — {row.reference} (EUR)</caption>
                <thead><tr><th scope="col">Compte</th><th scope="col">Débit</th><th scope="col">Crédit</th></tr></thead>
                <tbody>{(row.lignes || []).map(line => (
                  <tr key={line.compte}><th scope="row">{line.compte}</th><td>{line.debit}</td><td>{line.credit}</td></tr>
                ))}
                </tbody>
              </table>
              {!row.lignes?.length && <p>Réservation / libération budgétaire, sans mouvement comptable.</p>}
            </article>
          ))}
          <Pagination data={data} page={page} setPage={setPage} />
        </>
      )}
    </section>
  );
};
Journal.propTypes = { project: recordType.isRequired };

const ResearchFinance = ({ project }) => {
  const [editing, setEditing] = useState(false);
  const [unverified, setUnverified] = useState(false);
  const [readError, setReadError] = useState(null);
  const { checking, refresh } = useResearch();
  const path = `projets-recherche/${project.id}/`;
  const report = useResearchQuery(`${path}rapport-financier/`);
  let data;
  let invalid;
  try { if (report.data) { data = checkedReport(report.data, project); } } catch (error) { invalid = error; }
  return (
    <section aria-label="Finances du projet" className="my-4">
      <h2>Finances du projet — EUR</h2>
      <p>
        Sous-journal de recherche : opérations humaines documentées.
        Ni transfert bancaire automatique ni certification bancaire externe.
      </p>
      {(report.error || invalid) && <Failure error={report.error || invalid} retry={() => report.refetch()} />}
      {readError && <Failure error={readError} />}
      {unverified && (
        <Alert variant="warning">
          Les anciens soldes sont masqués après la tentative d’enregistrement.
          <Button
            disabled={checking || report.isFetching}
            onClick={async () => {
              setReadError(null);
              try { await refresh(); setUnverified(false); } catch (error) { setReadError(error); }
            }}
          >Relire les finances sans créer d’opération
          </Button>
        </Alert>
      )}
      {report.isFetching && <p role="status">Vérification du rapport et des écritures…</p>}
      {!unverified && !report.isFetching && !report.error && !invalid && data && (
        <>
          <dl>{reportFields.map(([name, label]) => (
            <React.Fragment key={name}><dt>{label}</dt><dd>{data[name]} EUR</dd></React.Fragment>
          ))}
          </dl>
          <p>Journal rapproché par le serveur — version {data.version}.</p>
          <Download path={`${path}exporter-rapport-financier/`} filename={`recherche-finances-${project.id}.csv`} kind="csv">Exporter le rapport financier complet (CSV)</Download>
        </>
      )}
      {!editing && eligibleTypes(project).length > 0 && (
        <Button className="ml-2" disabled={checking || report.isFetching || Boolean(report.error || invalid)} onClick={() => setEditing(true)}>Nouvelle opération financière</Button>
      )}
      {editing && (
        <FinanceEditor project={project} onClose={() => setEditing(false)} onUnverified={setUnverified} />
      )}
      <Journal project={project} />
    </section>
  );
};
ResearchFinance.propTypes = { project: recordType.isRequired };
export default ResearchFinance;
