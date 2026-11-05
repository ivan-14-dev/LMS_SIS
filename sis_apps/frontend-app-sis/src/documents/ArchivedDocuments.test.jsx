import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchApi, postApi } from '../services/api';
import { useCapabilities } from '../components/auth/PermissionGuard';
import { downloadPdf } from '../services/resources';
import ArchivedDocuments from './ArchivedDocuments';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({ SIS_SECONDAIRE_API_URL: 'https://school.example/api/v1' }),
}));
jest.mock('../services/api', () => ({
  ...jest.requireActual('../services/api'), fetchApi: jest.fn(), postApi: jest.fn(),
}));
jest.mock('../services/resources', () => ({ ...jest.requireActual('../services/resources'), downloadPdf: jest.fn() }));
jest.mock('../components/auth/PermissionGuard', () => ({ useCapabilities: jest.fn() }));
jest.mock('../components/common', () => ({
  ...jest.requireActual('../components/common'), WorkflowHistoryPanel: () => null,
}));

const show = () => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ArchivedDocuments variant="secondaire" />
  </QueryClientProvider>,
);
beforeEach(() => {
  jest.clearAllMocks();
  crypto.randomUUID = jest.fn(() => 'new-request-uuid');
  useCapabilities.mockReturnValue({ data: { role: 'eleve', permissions: [] } });
  const archive = {
    id: 'archive-uuid',
    source_type: 'Bulletin signé',
    version: 1,
    statut: 'revoque',
    sha256: 'document-hash',
    motif_revocation: 'Nouvelle version disponible',
  };
  fetchApi.mockImplementation(async url => (url.endsWith('/archive-uuid/')
    ? archive : { count: 1, results: [archive] }));
  postApi.mockResolvedValue({
    integrite: true, statut: 'revoque', empreinte_cle: 'trusted-key-fingerprint', qualification: 'Preuve détachée',
  });
});

it('keeps archive verification and revocation distinct and never exposes learner signing controls', async () => {
  show();
  fireEvent.click(await screen.findByText('Bulletin signé'));
  expect(await screen.findByText(/Nouvelle version disponible/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier l’intégrité' }));
  expect(await screen.findByText(/Intégrité confirmée/)).toHaveTextContent('cette version est révoquée');
  expect(screen.queryByRole('button', { name: 'Ajouter' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Révoquer la version' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le PDF archivé' }));
  await waitFor(() => expect(downloadPdf).toHaveBeenCalledWith('https://school.example/api/v1/core/documents-signes/archive-uuid/pdf/', 'archive-archive-uuid.pdf'));
});

it('uploads the selected PDF and exposes an integrity failure', async () => {
  postApi.mockRejectedValue({ response: { data: { detail: 'Intégrité non confirmée.' } } });
  show();
  fireEvent.click(await screen.findByText('Bulletin signé'));
  await screen.findByText(/Nouvelle version disponible/);
  const file = new File(['%PDF-altered'], 'changed.pdf', { type: 'application/pdf' });
  fireEvent.change(screen.getByLabelText('PDF à comparer (facultatif)'), { target: { files: [file] } });
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier l’intégrité' }));
  expect(await screen.findByText(/Intégrité non confirmée/)).toBeVisible();
  expect(postApi.mock.calls[0][1].get('pdf')).toBe(file);
  expect(screen.queryByText(/Intégrité confirmée/)).not.toBeInTheDocument();
});
