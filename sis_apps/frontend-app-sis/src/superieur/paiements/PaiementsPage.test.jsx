import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import PaiementsPage from './PaiementsPage';
import { financeRequest } from './financeApi';

jest.mock('@tanstack/react-query', () => ({
  useQuery: jest.fn(),
  useQueryClient: () => ({ invalidateQueries: jest.fn().mockResolvedValue() }),
}));
jest.mock('../../components/common', () => ({
  PageHeader: () => <h1>Factures et paiements</h1>,
  WorkflowHistoryPanel: () => null,
  WorkflowNotificationsPanel: () => null,
}));
jest.mock('../../components/auth/PermissionGuard', () => ({
  useCapabilities: () => ({ data: {}, isFetching: false }),
}));
jest.mock('../../components/layout/navigation', () => ({ hasCapability: () => true }));
jest.mock('../../services/resources', () => ({
  apiErrorMessage: error => error.response?.data?.error || error.message,
}));
jest.mock('./financeApi', () => ({
  financeRequest: jest.fn(), financePage: jest.fn(), paymentPayload: jest.fn(),
}));

describe('payment review screen', () => {
  const payment = {
    id: 8,
    numero: 'PAY-8',
    montant: '25.00',
    devise: 'EUR',
    statut: 'en_attente',
    reference_externe: 'BANK-TEST',
    enregistre_par: 12,
    remboursement: {},
  };
  beforeEach(() => {
    jest.clearAllMocks();
    useQuery.mockImplementation(({ queryKey }) => {
      if (queryKey[2] === 'providers') {
        return { data: { carte: 'non_configure', callback: 'non_configure', devises: ['EUR'] } };
      }
      return { data: { results: queryKey[2] === 'payments' ? [payment] : [], next: null, previous: null } };
    });
  });

  it('does not show a receipt before confirmation and exposes server refusals', async () => {
    financeRequest.mockRejectedValueOnce({ response: { data: { error: 'Un contrôleur distinct est obligatoire.' } } });
    render(<PaiementsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Consulter PAY-8' }));
    expect(screen.queryByRole('button', { name: 'Lire le reçu' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Contrôler / rapprocher côté serveur' }));
    expect(await screen.findByText(/Un contrôleur distinct est obligatoire/)).toBeInTheDocument();
    expect(financeRequest).toHaveBeenCalledWith('transactions/8/valider/', 'post', {}, 'superieur');
    expect(screen.queryByText(/Demande traitée par le serveur/)).not.toBeInTheDocument();
  });

  it('renders only the receipt fetched from the server for a confirmed payment', async () => {
    useQuery.mockImplementation(({ queryKey }) => ({
      data: queryKey[2] === 'providers' ? { carte: 'non_configure', callback: 'non_configure' }
        : { results: queryKey[2] === 'payments' ? [{ ...payment, statut: 'valide' }] : [] },
    }));
    financeRequest.mockResolvedValueOnce({ numero: 'SERVER-RECEIPT-8', solde: '75.00', devise: 'EUR' });
    render(<PaiementsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Consulter PAY-8' }));
    fireEvent.click(screen.getByRole('button', { name: 'Lire le reçu' }));
    await waitFor(() => expect(screen.getByText(/SERVER-RECEIPT-8/)).toBeInTheDocument());
    expect(financeRequest).toHaveBeenCalledWith('transactions/8/recu/', 'get', undefined, 'superieur');
  });
});
