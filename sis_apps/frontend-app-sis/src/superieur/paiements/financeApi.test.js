import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import { financeRequest, paymentPayload } from './financeApi';
import { isMockMode } from '../../services/mockApi';

jest.mock('@edx/frontend-platform/auth', () => ({ getAuthenticatedHttpClient: jest.fn() }));
jest.mock('../../services/api', () => ({
  getSuperieurApiUrl: () => 'https://school.example.test/api/v1',
  getSecondaireApiUrl: () => 'https://secondary.example.test/api/v1',
  normalizePageResponse: data => data,
}));
jest.mock('../../services/localSession', () => ({ usesLocalSession: () => false }));
jest.mock('../../services/mockApi', () => ({ isMockMode: jest.fn(() => false) }));

describe('finance real API boundary', () => {
  beforeEach(() => jest.clearAllMocks());

  it('refuses simulated finance without contacting a client', async () => {
    isMockMode.mockReturnValueOnce(true);
    await expect(financeRequest('transactions/', 'post', {})).rejects.toThrow('mode simulé');
    expect(getAuthenticatedHttpClient).not.toHaveBeenCalled();
  });

  it('submits only a declaration to the real API, never a confirmation', async () => {
    const client = { post: jest.fn().mockResolvedValue({ data: { id: 8 } }) };
    getAuthenticatedHttpClient.mockReturnValue(client);
    const proof = new File(['%PDF-1.4'], 'test.pdf', { type: 'application/pdf' });
    const payload = paymentPayload({
      facture: '4',
      montant: '25.50',
      mode: 'virement',
      reference_externe: 'BANK-TEST',
      preuve_paiement: proof,
      date_paiement: '2026-11-09',
    });
    await financeRequest('transactions/', 'post', payload);
    expect(client.post).toHaveBeenCalledWith('https://school.example.test/api/v1/paiements/transactions/', payload);
    expect(payload.get('statut')).toBeNull();
    expect(payload.get('montant')).toBe('25.50');
    expect(payload.get('preuve_paiement').name).toBe('test.pdf');
  });

  it.each(['0', '-1', 'NaN', '1.001'])('rejects invalid amount %s before writing', (montant) => {
    expect(() => paymentPayload({ facture: '4', montant, reference_externe: 'BANK-TEST' })).toThrow();
  });

  it('requires evidence and a reconciliation reference for manual payment', () => {
    expect(() => paymentPayload({
      facture: '4', montant: '25', mode: 'especes', reference_externe: '',
    })).toThrow('Référence');
    expect(() => paymentPayload({
      facture: '4', montant: '25', mode: 'especes', reference_externe: 'CASH-TEST',
    })).toThrow('Justificatif');
  });
});
