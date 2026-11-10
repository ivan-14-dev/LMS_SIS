import React, { useId, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Card, Form,
} from '@openedx/paragon';
import { usePractical, usePracticalQuery } from './PracticalContext';
import { errorMessage, isConflict, labelStatus } from './practicalContract';

export const recordType = PropTypes.shape({ id: PropTypes.number, version: PropTypes.number });
export const Failure = ({ error, retry }) => (
  <Alert variant="danger" role="alert">
    {errorMessage(error)}
    {retry && <Button variant="outline-primary" onClick={retry}>Réessayer la lecture</Button>}
  </Alert>
);
Failure.propTypes = { error: PropTypes.shape({ message: PropTypes.string }), retry: PropTypes.func };

export const Field = ({
  label, value, onChange, type = 'text', options, help, required = false,
  emptyOption = 'Tous / sélectionner…', ...rest
}) => {
  const id = useId();
  return (
    <Form.Group controlId={id}>
      <Form.Label>{label}{required ? ' *' : ''}</Form.Label>
      {options ? (
        <Form.Control as="select" value={value ?? ''} onChange={event => onChange(event.target.value)} required={required} {...rest}>
          <option value="">{emptyOption}</option>
          {options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}
        </Form.Control>
      ) : (
        <Form.Control
          as={type === 'textarea' ? 'textarea' : 'input'}
          type={type === 'textarea' ? undefined : type}
          value={type === 'file' ? undefined : (value ?? '')}
          onChange={event => onChange(type === 'file' ? event.target.files?.[0] : event.target.value)}
          required={required}
          aria-describedby={help ? `${id}-help` : undefined}
          {...rest}
        />
      )}
      {help && <small className="d-block text-muted" id={`${id}-help`}>{help}</small>}
    </Form.Group>
  );
};
Field.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func.isRequired,
  type: PropTypes.string,
  required: PropTypes.bool,
  options: PropTypes.arrayOf(PropTypes.arrayOf(PropTypes.string)),
  help: PropTypes.string,
  emptyOption: PropTypes.string,
};

export const Pagination = ({
  data, page, setPage, label, disabled = false,
}) => {
  const multiple = Boolean(data.previous || data.next || page > 1);
  if (!data.count && !multiple) { return null; }
  return (
    <nav aria-label={`Pagination — ${label}`} className="sis-practical-pagination">
      {multiple && <Button type="button" variant="outline-primary" disabled={disabled || !data.previous || page <= 1} onClick={() => setPage(page - 1)}>Page précédente</Button>}
      <span className="sis-practical-pagination__summary" aria-live="polite">
        {multiple ? `Page ${page} — ` : ''}{data.count} résultat(s)
      </span>
      {multiple && <Button type="button" variant="outline-primary" disabled={disabled || !data.next} onClick={() => setPage(page + 1)}>Page suivante</Button>}
    </nav>
  );
};
Pagination.propTypes = {
  data: PropTypes.shape({ count: PropTypes.number, previous: PropTypes.string, next: PropTypes.string }).isRequired,
  page: PropTypes.number.isRequired,
  setPage: PropTypes.func.isRequired,
  label: PropTypes.string.isRequired,
  disabled: PropTypes.bool,
};

export const Collection = ({
  path, schema, title, children, filters, searchable = true, empty = 'Aucun résultat accessible.',
}) => {
  const { busy } = usePractical();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  const query = usePracticalQuery(`${path}${path.includes('?') ? '&' : '?'}page=${page}&page_size=20${searchable ? `&q=${encodeURIComponent(term)}` : ''}`, `Page<${schema}>`);
  const searchResults = () => {
    if (!busy) { setTerm(search.trim()); setPage(1); }
  };
  return (
    <section aria-label={title} className="sis-panel sis-practical-collection">
      <h3>{title}</h3>
      {(searchable || filters) && (
        <div className="sis-practical-collection__toolbar">
          {searchable && (
            <div role="search" aria-label={`Recherche — ${title}`} className="sis-practical-collection__search">
              <Field
                label={`Rechercher — ${title}`}
                value={search}
                onChange={setSearch}
                maxLength={200}
                disabled={busy}
                onKeyDown={event => {
                  if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
                    event.preventDefault(); searchResults();
                  }
                }}
              />
              <Button type="button" aria-label={`Chercher ${title.toLowerCase()}`} disabled={busy} onClick={searchResults}>Rechercher</Button>
            </div>
          )}
          {filters && <div className="sis-practical-collection__filters">{filters}</div>}
        </div>
      )}
      {query.error && <Failure error={query.error} retry={() => query.refetch()} />}
      {query.isFetching && <p role="status">Relecture de {title.toLowerCase()}…</p>}
      {!query.isFetching && !query.error && query.data && (
        <>
          {!query.data.results.length ? (
            <div className="sis-practical-collection__empty" role="status">
              <p>{empty}</p>
            </div>
          ) : <div className="sis-practical-collection__results">{children(query.data.results)}</div>}
          <Pagination data={query.data} page={page} setPage={setPage} label={title} disabled={busy} />
        </>
      )}
    </section>
  );
};
Collection.propTypes = {
  path: PropTypes.string.isRequired,
  schema: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  children: PropTypes.func.isRequired,
  searchable: PropTypes.bool,
  empty: PropTypes.string,
  filters: PropTypes.node,
};

export const CommandForm = ({
  title, initial = {}, build, onSaved, onClose, onConflict, children, blocked = false, version,
}) => {
  const { command, busy } = usePractical();
  const [values, setValues] = useState(initial);
  const [error, setError] = useState(null);
  const [reviewed, setReviewed] = useState(false);
  const [receipt, setReceipt] = useState(false);
  const sending = useRef(false);
  const change = (field, value) => setValues(old => ({ ...old, [field]: value }));
  return (
    <Card className="my-3">
      <Card.Body>
        <form
          aria-label={title}
          onSubmit={async event => {
            event.preventDefault();
            if (sending.current || busy || blocked || receipt || (isConflict(error) && !reviewed)) { return; }
            sending.current = true; setError(null);
            try {
              const result = await command(build(values));
              setReceipt(true);
              await onSaved?.(result);
              onClose();
            } catch (failure) {
              setError(failure); setReviewed(false);
              if (failure.received) { setReceipt(true); }
              if (isConflict(failure)) { onConflict?.(); }
            } finally { sending.current = false; }
          }}
        >
          <h3>{title}</h3>
          {version !== undefined && <p>Version de l’agrégat utilisée : {version}.</p>}
          {error && <Failure error={error} />}
          {receipt && <Alert variant="warning">Ne renvoyez pas cette commande. Fermez le formulaire et relisez l’état enregistré.</Alert>}
          {isConflict(error) && (
            <Alert variant="warning">
              Conflit : les données ont été relues. Aucune écriture ni preuve n’a été renvoyée.
              Vérifiez les nouvelles exigences, décisions et actions avant une nouvelle soumission.
              <Form.Checkbox checked={reviewed} onChange={event => setReviewed(event.target.checked)}>
                J’ai vérifié l’état relu et souhaite réessayer délibérément
              </Form.Checkbox>
            </Alert>
          )}
          <fieldset disabled={busy || blocked || receipt}>
            {children(values, change)}
            <Button type="submit" disabled={isConflict(error) && !reviewed}>Confirmer — {title}</Button>
          </fieldset>
          <Button className="mt-2" variant="outline-primary" disabled={busy} onClick={onClose}>Fermer le formulaire</Button>
        </form>
      </Card.Body>
    </Card>
  );
};
CommandForm.propTypes = {
  title: PropTypes.string.isRequired,
  initial: recordType,
  build: PropTypes.func.isRequired,
  onSaved: PropTypes.func,
  onClose: PropTypes.func.isRequired,
  onConflict: PropTypes.func,
  children: PropTypes.func.isRequired,
  blocked: PropTypes.bool,
  version: PropTypes.number,
};

export const Evidence = ({ evidence }) => {
  const { download, busy } = usePractical();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  if (!evidence) { return <p>Aucune preuve jointe.</p>; }
  return (
    <div className="my-2">
      <p>Preuve : {evidence.nom} — {evidence.taille} octets. Création à la version {evidence.version_creation}.</p>
      {evidence.actions.can_download && (
        <Button
          variant="outline-primary"
          disabled={loading || busy}
          onClick={async () => {
            setLoading(true); setError(null);
            try { await download(evidence); } catch (failure) { setError(failure); } finally { setLoading(false); }
          }}
        >Télécharger {evidence.nom}
        </Button>
      )}
      {error && <Failure error={error} />}
    </div>
  );
};
Evidence.propTypes = {
  evidence: PropTypes.shape({
    nom: PropTypes.string,
    taille: PropTypes.number,
    version_creation: PropTypes.number,
    actions: PropTypes.shape({ can_download: PropTypes.bool }),
  }),
};

export const AuditList = ({ rows }) => (
  <ol>
    {rows.map(item => (
      <li key={item.id} className="my-2">
        {item.action.replace(/_/g, ' ')} — {item.acteur.nom} — {item.created_at}
        {' '}— version {item.version ?? item.version_dossier}
        {item.etat_apres && <> — {labelStatus(item.etat_avant)} → {labelStatus(item.etat_apres)}</>}
        {item.motif && <p>Motif : {item.motif}</p>}
        {item.heures_annulees?.length > 0 && <p>{item.heures_annulees.length} saisie(s) en attente annulée(s).</p>}
      </li>
    ))}
  </ol>
);
AuditList.propTypes = { rows: PropTypes.arrayOf(recordType).isRequired };
