import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import { getSuperieurApiUrl, getSecondaireApiUrl, normalizePageResponse } from '../../services/api';
import { localHttpClient, usesLocalSession } from '../../services/localSession';
import { isMockMode } from '../../services/mockApi';

export const financeRequest = async (path, method = 'get', data = undefined, variant = 'superieur') => {
  if (isMockMode()) { throw new Error('Finance indisponible en mode simulé : utilisez une API réelle.'); }
  const base = variant === 'secondaire' ? getSecondaireApiUrl() : getSuperieurApiUrl();
  const client = usesLocalSession() ? localHttpClient : getAuthenticatedHttpClient();
  const response = await client[method](`${base}/paiements/${path}`, data);
  return response.data;
};

export const financePage = async (path, variant) => normalizePageResponse(await financeRequest(path, 'get', undefined, variant));

export const paymentPayload = (values) => {
  if (!values.facture || !/^\d+(\.\d{1,2})?$/.test(values.montant) || Number(values.montant) <= 0) {
    throw new Error('Sélectionnez une facture et un montant positif avec au plus deux décimales.');
  }
  if (!values.reference_externe.trim()) { throw new Error('Référence de rapprochement obligatoire.'); }
  if (values.mode !== 'carte' && !values.preuve_paiement) { throw new Error('Justificatif obligatoire.'); }
  const payload = new FormData();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') { payload.append(key, value); }
  });
  return payload;
};
