import { getConfig } from '@edx/frontend-platform';
import {
  fetchApi, fetchCollection, getAdminApiUrl, getSecondaireApiUrl, getSuperieurApiUrl, normalizePageResponse,
} from './api';

export const getEnabledVariants = () => {
  const mode = getConfig().SIS_MODE || 'dual';
  if (mode === 'dual') { return ['secondaire', 'superieur']; }
  if (['secondaire', 'superieur'].includes(mode)) { return [mode]; }
  throw new Error('SIS_MODE doit être secondaire, superieur ou dual.');
};

export const resourceUrl = (variant, resource) => {
  let base = getSuperieurApiUrl();
  if (variant === 'admin') { base = getAdminApiUrl(); }
  if (variant === 'secondaire') { base = getSecondaireApiUrl(); }
  return `${base.replace(/\/$/, '')}/${resource.replace(/^\/|\/$/g, '')}/`;
};

export const apiErrorMessage = (error) => {
  const body = error?.response?.data;
  if (body && typeof body === 'object') {
    return Object.entries(body).map(([field, messages]) => (
      `${field}: ${typeof messages === 'string' ? messages : JSON.stringify(messages)}`
    )).join(' — ');
  }
  return error?.message || 'La requête a échoué.';
};

export const fetchResourcePage = async (url, params = {}, options = {}) => {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== '' && value != null),
  );
  return normalizePageResponse(await fetchApi(`${url}?${query}`, options));
};

export const fetchAllResourcePages = (url, params = {}, options = {}) => (
  fetchCollection(`${url}?${new URLSearchParams(params)}`, options)
);

export const exportRecords = (title, columns, records) => {
  const cell = (value) => {
    let text = value == null ? '' : String(value);
    if (/^[=+\-@\t\r]/.test(text)) { text = `'${text}`; }
    return `"${text.replace(/"/g, '""')}"`;
  };
  const csv = [
    columns.map(column => cell(column.Header)).join(','),
    ...records.map(row => columns.map(column => cell(
      column.accessor.split('.').reduce((value, key) => value?.[key], row),
    )).join(',')),
  ].join('\r\n');
  const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${title.replace(/[^a-z0-9_-]/gi, '_')}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
};

export const formatGrade = note => (
  note.valeur !== null && note.valeur !== undefined
    ? `${note.valeur}/${note.bareme}`
    : note.resultat_offre?.detail || '—'
);
