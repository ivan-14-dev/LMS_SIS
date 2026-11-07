import { useEffect, useState } from 'react';
import { fetchApi } from './api';
import { resourceUrl } from './resources';
import { canEnterPortal, hasCapability } from '../components/layout/navigation';

const universityResources = [
  { value: 'etudiants', label: 'Étudiants', permission: 'etudiants.view_etudiant' },
  { value: 'formations', label: 'Formations', permission: 'formations.view_formation' },
  { value: 'parcours', label: 'Parcours', permission: 'formations.view_parcours' },
];
const documents = [
  { value: 'releves', label: 'Relevés de notes', permission: 'releves.view_relevenotes' },
  { value: 'transcripts', label: 'Transcripts', permission: 'releves.view_transcript' },
  { value: 'attestations', label: 'Attestations', permission: 'releves.view_attestation' },
];

export const academicSearchResources = (variant, capabilities, lmsAdmin = false) => {
  if (!capabilities || !['secondaire', 'superieur'].includes(variant)) { return []; }
  const personal = canEnterPortal(capabilities, 'learner')
    || (variant === 'secondaire' && canEnterPortal(capabilities, 'parent'));
  const resources = (variant === 'secondaire'
    ? [{ value: 'eleves', label: 'Élèves', permission: 'eleves.view_eleve' }]
    : universityResources).filter(resource => hasCapability(capabilities, resource.permission));
  if (lmsAdmin && !personal) {
    resources.push({ value: 'cours', label: 'Cours LMS' });
  }
  if (variant === 'superieur' && !personal && hasCapability(capabilities, 'notes.view_evaluation')) {
    resources.push({ value: 'evaluations_lms', label: 'Évaluations reliées au LMS' });
  }
  const financePermission = variant === 'secondaire' ? 'paiement' : 'paiementfrais';
  const invoicePermission = variant === 'secondaire' ? 'facture' : 'facturefrais';
  if (personal || hasCapability(capabilities, `paiements.change_${financePermission}`)
    || hasCapability(capabilities, `paiements.view_${invoicePermission}`)) {
    resources.push({ value: 'factures', label: 'Factures' });
  }
  if (variant === 'superieur') {
    resources.push(...documents.filter(resource => personal
      || hasCapability(capabilities, resource.permission)
      || hasCapability(capabilities, resource.permission.replace('.view_', '.change_'))));
  } else if (personal || hasCapability(capabilities, 'notes.view_bulletin')) {
    resources.push({ value: 'bulletins', label: 'Bulletins' });
  }
  return resources;
};

export const validSearchTerm = value => {
  const { length } = Array.from(value.trim());
  // Match the server's control-character exclusion without silently truncating input.
  return length >= 2 && length <= 100 && Array.from(value).length <= 100
    && !Array.from(value).some(character => character.charCodeAt(0) < 32
      || (character.charCodeAt(0) >= 127 && character.charCodeAt(0) <= 159));
};

export const academicSearchUrl = (variant, resource, term, page) => (
  `${resourceUrl(variant, 'core/recherche-academique')}?${new URLSearchParams({
    ressource: resource, q: term.trim(), page, page_size: 20,
  })}`
);

export const academicResultPath = (variant, resource, id) => {
  if (!Number.isSafeInteger(id) || id < 1) { return null; }
  if (documents.some(document => document.value === resource)) {
    return `/${variant}/documents/${resource}/${id}`;
  }
  return `/${variant}/${resource}/${id}`;
};

// Search records never enter the shared QueryClient or browser storage. Discard
// responses after unmount/context changes, including clients that ignore abort.
export const usePrivateResource = url => {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({});
  useEffect(() => {
    if (!url) { setState({}); return undefined; }
    const controller = new AbortController();
    let active = true;
    setState({ url, loading: true });
    fetchApi(url, { signal: controller.signal }).then(
      data => { if (active) { setState({ url, data }); } },
      error => { if (active) { setState({ url, error }); } },
    );
    return () => { active = false; controller.abort(); };
  }, [url, attempt]);
  return {
    ...(state.url === url ? state : { loading: Boolean(url) }),
    retry: () => { setState({ url, loading: true }); setAttempt(value => value + 1); },
  };
};
