import React, { useId, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Card, Form,
} from '@openedx/paragon';
import { paginated, useResearch, useResearchQuery } from './ResearchContext';
import {
  errorMessage, isConflict, statusLabel, versionOf,
} from './researchUi';

export const recordType = PropTypes.shape({
  id: PropTypes.oneOfType([PropTypes.number, PropTypes.string]), version: PropTypes.number,
});

export const Failure = ({ error, retry }) => (
  <Alert variant="danger" role="alert">
    {errorMessage(error)}
    {retry && <Button variant="outline-primary" onClick={retry}>Réessayer la lecture</Button>}
  </Alert>
);
Failure.propTypes = { error: PropTypes.shape({ message: PropTypes.string }), retry: PropTypes.func };

export const Field = ({
  label, value, onChange, type = 'text', required = false, options, help, ...rest
}) => {
  const id = useId();
  return (
    <Form.Group controlId={id}>
      <Form.Label>{label}{required ? ' *' : ''}</Form.Label>
      {options ? (
        <Form.Control as="select" value={value ?? ''} onChange={event => onChange(event.target.value)} required={required} {...rest}>
          <option value="">Sélectionner…</option>
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
      {help && <small id={`${id}-help`} className="d-block text-muted">{help}</small>}
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
};

export const Pagination = ({ data, page, setPage }) => (
  <nav aria-label="Pagination" className="d-flex align-items-center my-3">
    <Button variant="outline-primary" disabled={!data.previous || page <= 1} onClick={() => setPage(page - 1)}>Page précédente</Button>
    <span className="mx-3" aria-live="polite">Page {page} — {data.count} résultat(s)</span>
    <Button variant="outline-primary" disabled={!data.next} onClick={() => setPage(page + 1)}>Page suivante</Button>
  </nav>
);
Pagination.propTypes = {
  data: PropTypes.shape({ count: PropTypes.number, next: PropTypes.string, previous: PropTypes.string }).isRequired,
  page: PropTypes.number.isRequired,
  setPage: PropTypes.func.isRequired,
};

export const Collection = ({
  resource, title, onSelect, filter = '', children, searchable = true,
}) => {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  const searchQuery = searchable ? `&search=${encodeURIComponent(term)}` : '';
  const query = useResearchQuery(`${resource}/?page=${page}&page_size=20${searchQuery}${filter}`);
  let data;
  let invalid;
  try { if (query.data) { data = paginated(query.data); } } catch (error) { invalid = error; }
  return (
    <section aria-label={title} className="my-4">
      <h2>{title}</h2>
      {searchable && (
        <form className="d-flex align-items-end" onSubmit={event => { event.preventDefault(); setTerm(search); setPage(1); }}>
          <Field label={`Rechercher — ${title}`} value={search} onChange={setSearch} />
          <Button type="submit" className="ml-2 mb-3">Rechercher</Button>
        </form>
      )}
      {(query.error || invalid) && <Failure error={query.error || invalid} retry={() => query.refetch()} />}
      {query.isFetching && <p role="status">Chargement de {title.toLowerCase()}…</p>}
      {!query.isFetching && !query.error && !invalid && data && (
        <>
          {!data.results.length && <p role="status">Aucun résultat accessible.</p>}
          {children ? children(data.results) : (
            <ul className="list-unstyled">
              {data.results.map(row => (
                <li key={row.id} className="border-bottom py-2">
                  <Button variant="link" onClick={() => onSelect(row.id)}>{row.titre || row.nom}</Button>
                  <span>{row.archive ? 'Archivé' : statusLabel(row.statut)} {row.acronyme}</span>
                </li>
              ))}
            </ul>
          )}
          <Pagination data={data} page={page} setPage={setPage} />
        </>
      )}
    </section>
  );
};
Collection.propTypes = {
  resource: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  onSelect: PropTypes.func,
  filter: PropTypes.string,
  children: PropTypes.func,
  searchable: PropTypes.bool,
};

export const Selector = ({
  label, resource, value, onChange, multiple = false, eligible, searchable = true,
}) => {
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  const [page, setPage] = useState(1);
  const suffix = resource.includes('?') ? '&' : '?';
  const searchParam = resource.startsWith('laboratoires/selecteurs/') ? 'q' : 'search';
  const searchQuery = searchable ? `&${searchParam}=${encodeURIComponent(term)}` : '';
  const query = useResearchQuery(`${resource}${suffix}page=${page}&page_size=20${searchQuery}`);
  let data;
  let invalid;
  try { if (query.data) { data = paginated(query.data); } } catch (error) { invalid = error; }
  const selected = (multiple ? value : [value]).filter(Boolean);
  const rows = data?.results.filter(item => !eligible || eligible(item)) || [];
  return (
    <fieldset className="border p-3 mb-3">
      <legend className="h5">{label}</legend>
      {!selected.length && <p>Aucune sélection.</p>}
      {selected.map(item => (
        <p key={item.id}>
          {item.nom || item.titre || item.reference}
          <Button
            variant="link"
            onClick={() => onChange(multiple ? selected.filter(row => row.id !== item.id) : null)}
          >Retirer {item.nom || item.titre || item.reference}
          </Button>
        </p>
      ))}
      {searchable && (
        <>
          <Field label={`Rechercher — ${label}`} value={search} onChange={setSearch} />
          <Button variant="outline-primary" onClick={() => { setTerm(search); setPage(1); }}>
            Chercher {label.toLowerCase()}
          </Button>
        </>
      )}
      {(query.error || invalid) && <Failure error={query.error || invalid} retry={() => query.refetch()} />}
      {query.isFetching && <p role="status">Chargement des choix autorisés…</p>}
      {!query.isFetching && !query.error && !invalid && data && (
        <>
          {!rows.length && <p>Aucun choix admissible sur cette page.</p>}
          <ul className="list-unstyled">
            {rows.map(item => (
              <li key={item.id}>
                <Button
                  variant="link"
                  disabled={selected.some(row => row.id === item.id)}
                  onClick={() => onChange(multiple ? [...selected, item] : item)}
                >Choisir {item.nom || item.titre || `${item.reference} — ${item.montant} EUR`}
                </Button>
              </li>
            ))}
          </ul>
          <Pagination data={data} page={page} setPage={setPage} />
        </>
      )}
    </fieldset>
  );
};
Selector.propTypes = {
  label: PropTypes.string.isRequired,
  resource: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([recordType, PropTypes.arrayOf(recordType)]),
  onChange: PropTypes.func.isRequired,
  multiple: PropTypes.bool,
  eligible: PropTypes.func,
  searchable: PropTypes.bool,
};

export const Download = ({
  path, filename, kind = 'pdf', children,
}) => {
  const { download, checking } = useResearch();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Button
        variant="outline-primary"
        disabled={busy || checking}
        onClick={async () => {
          setError(null); setBusy(true);
          try { await download(path, filename, kind); } catch (failure) {
            setError(failure);
          } finally { setBusy(false); }
        }}
      >{busy ? 'Téléchargement…' : children}
      </Button>
      {error && <Failure error={error} />}
    </>
  );
};
Download.propTypes = {
  path: PropTypes.string.isRequired,
  filename: PropTypes.string.isRequired,
  kind: PropTypes.string,
  children: PropTypes.node.isRequired,
};

export const CommandForm = ({
  title, path, method = 'post', record, recordPath, initial = {}, build, onSaved, onClose, children, contributor = false,
}) => {
  const { request, checking } = useResearch();
  const [values, setValues] = useState(initial);
  const [version, setVersion] = useState(record?.version);
  const [latest, setLatest] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(false);
  const sending = useRef(false);
  const change = (name, value) => setValues(old => ({ ...old, [name]: value }));
  const finish = async () => { await onSaved(); onClose(); };
  return (
    <Card className="my-3">
      <Card.Body>
        <form
          aria-label={title}
          onSubmit={async event => {
            event.preventDefault();
            if (sending.current || checking || receipt) { return; }
            sending.current = true; setBusy(true); setError(null);
            try {
              const payload = build(values, record ? versionOf({ version }) : undefined);
              await request(path, method, payload);
              setReceipt(true);
              await finish();
            } catch (failure) { setError(failure); } finally { sending.current = false; setBusy(false); }
          }}
        >
          <h3>{title}</h3>
          {record && <p>Version utilisée : {version}. Vos champs restent inchangés lors d’un conflit.</p>}
          {error && <Failure error={error} />}
          {receipt && <Alert variant="warning">Commande reçue par le serveur. Relecture nécessaire avant toute nouvelle opération.</Alert>}
          {isConflict(error) && recordPath && (
            <div className="mb-3">
              <Button
                disabled={busy || checking}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const current = await request(recordPath);
                    versionOf(current);
                    setLatest(current);
                  } catch (failure) {
                    setError(failure);
                  } finally { setBusy(false); }
                }}
              >Relire la version actuelle sans effacer ma saisie
              </Button>
              {latest && (
                <Alert variant="warning">
                  Version serveur : {latest.version}, état : {statusLabel(latest.statut) || 'non archivé'}{latest.archive ? ' — archivé' : ''}.
                  Vérifiez votre saisie avant de la soumettre à nouveau.
                  <dl>
                    {[
                      ['titre', 'Titre actuel'], ['nom', 'Nom actuel'], ['budget', 'Budget actuel (EUR)'],
                      ['date_debut', 'Début actuel'], ['date_fin', 'Fin actuelle'],
                      ['responsable_nom', 'Responsable actuel'],
                    ].filter(([name]) => latest[name] !== undefined).map(([name, label]) => (
                      <React.Fragment key={name}><dt>{label}</dt><dd>{latest[name]}</dd></React.Fragment>
                    ))}
                  </dl>
                  <Button
                    disabled={latest.archive || !(contributor ? latest.can_contribute : latest.can_manage)}
                    onClick={() => { setVersion(versionOf(latest)); setLatest(null); setError(null); }}
                  >Utiliser explicitement cette version
                  </Button>
                </Alert>
              )}
            </div>
          )}
          <fieldset disabled={busy || checking || receipt}>
            {children?.(values, change)}
            <Button type="submit">Confirmer — {title}</Button>
          </fieldset>
          {receipt && (
            <Button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try { await finish(); } catch (failure) { setError(failure); } finally { setBusy(false); }
              }}
            >Relire après enregistrement
            </Button>
          )}
          <Button className="ml-2" variant="tertiary" disabled={busy} onClick={onClose}>Fermer le formulaire</Button>
        </form>
      </Card.Body>
    </Card>
  );
};
CommandForm.propTypes = {
  title: PropTypes.string.isRequired,
  path: PropTypes.string.isRequired,
  method: PropTypes.string,
  record: recordType,
  recordPath: PropTypes.string,
  initial: PropTypes.shape({}),
  build: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  children: PropTypes.func,
  contributor: PropTypes.bool,
};
