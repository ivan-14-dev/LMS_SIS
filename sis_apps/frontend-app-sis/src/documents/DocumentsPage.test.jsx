import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { getConfig } from '@edx/frontend-platform';
import { fetchApi } from '../services/api';
import { downloadPdf, exportRecords, fetchAllResourcePages } from '../services/resources';
import { useCapabilities } from '../components/auth/PermissionGuard';
import DocumentsPage from './DocumentsPage';

jest.mock('@edx/frontend-platform', () => ({ getConfig: jest.fn() }));
jest.mock('../services/api', () => ({ ...jest.requireActual('../services/api'), fetchApi: jest.fn() }));
jest.mock('../services/resources', () => ({
  ...jest.requireActual('../services/resources'),
  downloadPdf: jest.fn(),
  exportRecords: jest.fn(),
  fetchAllResourcePages: jest.fn(),
}));
jest.mock('../components/auth/PermissionGuard', () => ({ useCapabilities: jest.fn() }));
const document = {
  id: 8, eleve_nom: 'Mon dossier', etudiant_nom: 'Mon dossier', moyenne_generale: 0,
};
const renderPage = (variant = 'secondaire') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><DocumentsPage variant={variant} /></MemoryRouter>
  </QueryClientProvider>,
);
beforeEach(() => {
  jest.clearAllMocks();
  getConfig.mockReturnValue({
    SIS_SECONDAIRE_API_URL: 'https://school.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://university.example/api/v1',
  });
  useCapabilities.mockReturnValue({ data: { role: 'eleve' } });
  fetchApi.mockResolvedValue({ count: 1, results: [document], next: null });
  downloadPdf.mockResolvedValue(undefined);
  fetchAllResourcePages.mockResolvedValue([document]);
});

it('downloads a real document endpoint and exports the filtered authorized list without editing controls', async () => {
  renderPage();
  await screen.findByText('Mon dossier');
  expect(screen.getByRole('cell', { name: '0', exact: true })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le PDF' }));
  await waitFor(() => expect(downloadPdf).toHaveBeenCalledWith('https://school.example/api/v1/bulletins/8/pdf_officiel/', 'bulletin-8.pdf'));
  fireEvent.change(screen.getByLabelText('Rechercher'), { target: { value: 'Mon' } });
  await waitFor(() => expect(fetchApi.mock.calls.some(([url]) => url.includes('search=Mon'))).toBe(true));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Exporter la liste filtrée (CSV)' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Exporter la liste filtrée (CSV)' }));
  await waitFor(() => expect(exportRecords).toHaveBeenCalledWith('Bulletins', expect.any(Array), [document]));
  expect(fetchAllResourcePages).toHaveBeenCalledWith('https://school.example/api/v1/bulletins/', { search: 'Mon' });
  expect(screen.queryByRole('button', { name: 'Ajouter' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Modifier' })).not.toBeInTheDocument();
});

it('distinguishes a server failure from an empty collection and exposes download errors', async () => {
  fetchApi.mockRejectedValue(new Error('Accès indisponible'));
  renderPage();
  await screen.findByText(/Impossible de charger les documents/);
  expect(screen.queryByText('Aucun document disponible pour le moment.')).not.toBeInTheDocument();
  fetchApi.mockResolvedValue({ count: 1, results: [document] });
  fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }));
  await screen.findByText('Mon dossier');
  downloadPdf.mockRejectedValue(new Error('Téléchargement refusé'));
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le PDF' }));
  expect(await screen.findByText('Téléchargement refusé')).toBeVisible();
});

it('loads transcripts and attestations from their actual endpoints', async () => {
  useCapabilities.mockReturnValue({ data: { role: 'etudiant' } });
  renderPage('superieur');
  await screen.findByText('Mon dossier');
  fireEvent.click(screen.getByRole('tab', { name: 'Transcripts' }));
  await waitFor(() => expect(fetchApi.mock.calls.some(([url]) => url.includes('/releves/transcripts/'))).toBe(true));
  await screen.findByText('Mon dossier');
  fireEvent.click(screen.getByRole('tab', { name: 'Attestations' }));
  await waitFor(() => expect(fetchApi.mock.calls.some(([url]) => url.includes('/releves/attestations/'))).toBe(true));
});

it('does not request personal documents when the account has no permitted learner or family role', () => {
  useCapabilities.mockReturnValue({ data: { role: 'enseignant' } });
  renderPage();
  expect(screen.getByText(/Cet espace est réservé/)).toBeVisible();
  expect(fetchApi).not.toHaveBeenCalled();
});
