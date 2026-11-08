import React from 'react';
import {
  act, fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchApi, patchApi, postApi } from '../../services/api';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import BibliothequePage from './BibliothequePage';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_SECONDAIRE_API_URL: 'https://school.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://university.example/api/v1',
  }),
}));
jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  patchApi: jest.fn(),
  postApi: jest.fn(),
}));
jest.mock('../../components/auth/PermissionGuard', () => ({ useCapabilities: jest.fn() }));

let book;
let loans;
let reservations;
let click;
const originalCreate = URL.createObjectURL;
const originalRevoke = URL.revokeObjectURL;
const baseUrl = variant => `https://${variant === 'secondaire' ? 'school' : 'university'}.example/api/v1/bibliotheque/`;
const permissions = (...values) => useCapabilities.mockReturnValue({
  data: { role: 'eleve', is_staff: false, permissions: values.map(value => `bibliotheque.${value}`) },
});
const show = (variant = 'secondaire') => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const page = (
    <QueryClientProvider client={client}><BibliothequePage variant={variant} /></QueryClientProvider>
  );
  return { ...render(page), client, page };
};
const openBook = async () => {
  fireEvent.click(await screen.findByRole('button', { name: 'Ouvrir Histoire des sciences' }));
  await screen.findByRole('heading', { name: 'Histoire des sciences', level: 2 });
};
const request = async (url, options) => {
  const path = new URL(url).pathname;
  if (path.endsWith('/numerique/')) {
    if (options?.responseType !== 'blob') { throw new Error('Authenticated blob request expected'); }
    return new Blob(['%PDF-1.7'], { type: 'application/pdf' });
  }
  if (path.endsWith('/livres/7/')) { return { ...book }; }
  if (path.endsWith('/livres/7/exemplaires/')) {
    return [{
      id: 12, livre: 7, code_barre: 'EX-12', etat: 'bon', disponible: true,
    }];
  }
  if (path.endsWith('/livres/')) { return { count: 1, results: [{ ...book }] }; }
  if (path.endsWith('/emprunts/')) { return { count: loans.length, results: loans }; }
  if (/\/reservations(?:-bibliotheque)?\/$/.test(path)) { return { count: reservations.length, results: reservations }; }
  throw new Error(`Unexpected request: ${url}`);
};

beforeEach(() => {
  jest.clearAllMocks();
  permissions('consulter_ressource_numerique');
  book = {
    id: 7,
    titre: 'Histoire des sciences',
    auteurs: 'A. Exemple',
    isbn: '9781234567890',
    licence_active: true,
    licence_reference: 'Autorisation éditeur',
    licence_expire_le: null,
    peut_consulter_ressource: true,
    ressource_numerique: 'https://public.invalid/must-never-be-followed.pdf',
  };
  loans = [{
    id: 23, livre_titre: book.titre, emprunteur_nom: 'Lecteur', statut: 'en_cours', statut_display: 'En cours',
  }];
  reservations = [{
    id: 31, livre: 7, livre_titre: book.titre, statut: 'en_attente', date_reservation: '2026-11-08',
  }];
  fetchApi.mockImplementation(request);
  patchApi.mockImplementation(async (url, body) => {
    book = {
      ...book,
      licence_active: body.get('licence_active') === 'true',
      licence_reference: body.get('licence_reference'),
      licence_expire_le: body.get('licence_expire_le') || null,
    };
    return { ...book };
  });
  postApi.mockResolvedValue({ id: 23 });
  URL.createObjectURL = jest.fn(() => 'blob:library-pdf');
  URL.revokeObjectURL = jest.fn();
  click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => {
  click.mockRestore();
  URL.createObjectURL = originalCreate;
  URL.revokeObjectURL = originalRevoke;
});

it.each(['secondaire', 'superieur'])('does not infer %s library permissions from staff or librarian roles', (variant) => {
  useCapabilities.mockReturnValue({ data: { role: 'bibliothecaire', is_staff: true, permissions: [] } });
  show(variant);
  expect(screen.getByText(/nécessite une habilitation explicite/)).toBeVisible();
  expect(fetchApi).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: /Télécharger/ })).not.toBeInTheDocument();
});

it('allows authorized catalogue search but requires the separate download permission', async () => {
  permissions('view_livre');
  show();
  fireEvent.change(await screen.findByRole('textbox', { name: 'Rechercher' }), { target: { value: 'sciences' } });
  await waitFor(() => expect(fetchApi).toHaveBeenCalledWith(expect.stringContaining('search=sciences'), expect.objectContaining({ signal: expect.anything() })));
  await openBook();
  expect(screen.getByText(/Consultation numérique indisponible : habilitation/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Télécharger le PDF autorisé' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Gérer le fichier et la licence' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

it.each([
  [false, false, /licence inactive ou révoquée/],
  [true, false, /licence expirée ou accès non autorisé/],
])('does not expose a file when licence=%s and server authorization=%s', async (active, allowed, message) => {
  book.licence_active = active;
  book.peut_consulter_ressource = allowed;
  book.licence_expire_le = '2020-01-01';
  show();
  await openBook();
  expect(screen.getByText(message)).toBeVisible();
  expect(screen.queryByRole('button', { name: /Télécharger/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

it.each(['secondaire', 'superieur'])('downloads %s PDFs through the session endpoint, never a public URL, then revokes the blob URL', async (variant) => {
  show(variant);
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le PDF autorisé' }));
  expect(await screen.findByText(/PDF reçu/)).toBeVisible();
  expect(fetchApi).toHaveBeenCalledWith(`${baseUrl(variant)}livres/7/numerique/`, { responseType: 'blob' });
  expect(fetchApi.mock.calls.every(([url]) => !url.includes('public.invalid'))).toBe(true);
  expect(click).toHaveBeenCalledTimes(1);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:library-pdf');
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

it.each([403, 404])('purges the previous document and success after a download HTTP %s', async status => {
  const { client } = show();
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le PDF autorisé' }));
  await screen.findByText(/PDF reçu/);
  fetchApi.mockImplementation(async (url, options) => {
    if (url.endsWith('/numerique/')) {
      throw Object.assign(new Error('Accès refusé'), { response: { status, data: new Blob(['Accès refusé']) } });
    }
    return request(url, options);
  });
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le PDF autorisé' }));
  expect(await screen.findByText(/Bibliothèque indisponible/)).toHaveTextContent(`HTTP ${status}`);
  expect(screen.queryByText(/PDF reçu/)).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: book.titre })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Télécharger/ })).not.toBeInTheDocument();
  expect(click).toHaveBeenCalledTimes(1);
  expect(client.getQueriesData({ queryKey: ['library'] }).every(([, data]) => !data)).toBe(true);
});

it('rejects a login page returned as a successful download without offering a false success', async () => {
  fetchApi.mockImplementation((url, options) => (url.endsWith('/numerique/')
    ? Promise.resolve(new Blob(['Login'], { type: 'text/html' })) : request(url, options)));
  show();
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le PDF autorisé' }));
  expect(await screen.findByText(/document PDF valide/)).toBeVisible();
  expect(click).not.toHaveBeenCalled();
  expect(screen.queryByText(/PDF reçu/)).not.toBeInTheDocument();
});

it('removes the previous download confirmation when the server reports a revoked licence', async () => {
  const { client } = show();
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le PDF autorisé' }));
  await screen.findByText(/PDF reçu/);
  book.licence_active = false;
  book.peut_consulter_ressource = false;
  await act(async () => { await client.invalidateQueries({ queryKey: ['library'] }); });
  expect(await screen.findByText(/licence inactive ou révoquée/)).toBeVisible();
  expect(screen.queryByText(/PDF reçu/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Télécharger/ })).not.toBeInTheDocument();
});

it('purges stale catalogue and detail on a failed background refetch', async () => {
  const { client } = show();
  await openBook();
  fetchApi.mockRejectedValue({ response: { status: 403, data: { detail: 'Droits retirés' } } });
  await act(async () => { await client.invalidateQueries({ queryKey: ['library'] }); });
  expect(await screen.findByText(/Droits retirés/)).toBeVisible();
  expect(screen.queryByRole('heading', { name: book.titre })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Télécharger/ })).not.toBeInTheDocument();
});

it('clears library content when explicit capabilities are revoked', async () => {
  const { rerender, client } = show();
  await openBook();
  permissions();
  rerender(<QueryClientProvider client={client}><BibliothequePage variant="secondaire" /></QueryClientProvider>);
  expect(await screen.findByText(/nécessite une habilitation explicite/)).toBeVisible();
  expect(screen.queryByRole('heading', { name: book.titre })).not.toBeInTheDocument();
  expect(client.getQueriesData({ queryKey: ['library'] }).every(([, data]) => !data)).toBe(true);
});

it.each(['secondaire', 'superieur'])('submits the %s licence declaration and selected PDF as authenticated multipart', async (variant) => {
  permissions('change_livre');
  book.licence_active = false;
  book.licence_reference = '';
  show(variant);
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Gérer le fichier et la licence' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Licence de diffusion active' }));
  expect(screen.getByRole('button', { name: 'Enregistrer le fichier et la licence' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Référence ou justificatif/), { target: { value: 'Contrat éditeur 37' } });
  fireEvent.change(screen.getByLabelText('Expiration de licence (facultative)'), { target: { value: '2027-01-31' } });
  const file = new File(['%PDF-test'], 'ouvrage.pdf', { type: 'application/pdf' });
  fireEvent.change(screen.getByLabelText('Ressource numérique (PDF)'), { target: { files: [file] } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le fichier et la licence' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalledWith(`${baseUrl(variant)}livres/7/`, expect.any(FormData)));
  const body = patchApi.mock.calls[0][1];
  expect(body.get('licence_active')).toBe('true');
  expect(body.get('licence_reference')).toBe('Contrat éditeur 37');
  expect(body.get('licence_expire_le')).toBe('2027-01-31');
  expect(body.get('ressource_numerique')).toBe(file);
  expect(await screen.findByText(/Échéance de licence : 2027-01-31/)).toBeVisible();
  expect(await screen.findByText('Fichier et licence enregistrés ; données actualisées.')).toBeVisible();
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});

it('revokes a licence without replacing the existing file or leaving a prior expiry', async () => {
  permissions('change_livre', 'consulter_ressource_numerique');
  book.licence_expire_le = '2027-01-31';
  show();
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Gérer le fichier et la licence' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Licence de diffusion active' }));
  fireEvent.change(screen.getByLabelText('Expiration de licence (facultative)'), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le fichier et la licence' }));
  await waitFor(() => expect(patchApi).toHaveBeenCalled());
  const body = patchApi.mock.calls[0][1];
  expect(body.get('licence_active')).toBe('false');
  expect(body.get('licence_expire_le')).toBe('');
  expect(body.has('ressource_numerique')).toBe(false);
  expect(await screen.findByText(/licence inactive ou révoquée/)).toBeVisible();
});

it('shows rejected licence/file updates without leaving a stale book or announcing success', async () => {
  permissions('change_livre');
  patchApi.mockRejectedValue({ response: { status: 400, data: { ressource_numerique: 'PDF invalide' } } });
  show();
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Gérer le fichier et la licence' }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le fichier et la licence' }));
  expect(await screen.findByText(/PDF invalide/)).toBeVisible();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: book.titre })).not.toBeInTheDocument();
  expect(screen.queryByText(/confirmée par le serveur/)).not.toBeInTheDocument();
});

it.each([
  ['secondaire', 'retourner'],
  ['superieur', 'rendre'],
])('borrows, returns through %s/%s, then reserves the same title for the nonstaff reader', async (variant, action) => {
  permissions('add_emprunt', 'change_emprunt', 'add_reservation');
  postApi.mockImplementation(async url => {
    if (url.endsWith(`/${action}/`)) { loans = loans.map(item => ({ ...item, statut: 'rendu', statut_display: 'Rendu' })); }
    return { id: 23 };
  });
  show(variant);
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Emprunter un exemplaire' }));
  fireEvent.mouseDown(await screen.findByRole('combobox', { name: 'Exemplaire' }));
  fireEvent.click(await screen.findByRole('option', { name: 'EX-12' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer mon emprunt' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${baseUrl(variant)}emprunts/`, { exemplaire: 12 }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole('tab', { name: 'Prêts' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Retourner' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${baseUrl(variant)}emprunts/23/${action}/`, {}));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Retourner' })).not.toBeInTheDocument());
  expect(await screen.findByText('Rendu')).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Catalogue' }));
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Réserver ce titre pour moi' }));
  const resource = variant === 'secondaire' ? 'reservations' : 'reservations-bibliotheque';
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${baseUrl(variant)}${resource}/`, { livre: 7 }));
  expect(postApi.mock.calls).toHaveLength(3);
  expect(patchApi).not.toHaveBeenCalled();
});

it.each([
  ['secondaire', 'reservations', 'cancel'],
  ['superieur', 'reservations-bibliotheque', 'annuler'],
])('uses the existing %s reservation resource and cancellation action', async (variant, resource, action) => {
  permissions('add_reservation', 'change_reservation');
  show(variant);
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Réserver ce titre pour moi' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${baseUrl(variant)}${resource}/`, { livre: 7 }));
  await screen.findByText('Opération confirmée par le serveur.');
  fireEvent.click(screen.getByRole('tab', { name: 'Réservations' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Annuler la réservation' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${baseUrl(variant)}${resource}/31/${action}/`, {}));
});

it('rejects a duplicate loan without a false success and clears stale availability', async () => {
  permissions('add_emprunt');
  postApi.mockRejectedValue({ response: { status: 400, data: { exemplaire: 'Cet exemplaire est déjà emprunté.' } } });
  show();
  await openBook();
  fireEvent.click(screen.getByRole('button', { name: 'Emprunter un exemplaire' }));
  fireEvent.mouseDown(await screen.findByRole('combobox', { name: 'Exemplaire' }));
  fireEvent.click(await screen.findByRole('option', { name: 'EX-12' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer mon emprunt' }));
  expect(await screen.findByText(/déjà emprunté/)).toBeVisible();
  expect(screen.queryByText(/confirmée par le serveur/)).not.toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: book.titre })).not.toBeInTheDocument();
});

it.each([
  ['secondaire', 'reservations', 'fulfil'],
  ['superieur', 'reservations-bibliotheque', 'recuperer'],
])('preserves the %s reservation handover contract without a generic mutation', async (variant, resource, action) => {
  permissions('change_livre');
  show(variant);
  fireEvent.click(await screen.findByRole('tab', { name: 'Réservations' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Remettre un exemplaire' }));
  fireEvent.mouseDown(await screen.findByRole('combobox', { name: 'Exemplaire' }));
  fireEvent.click(await screen.findByRole('option', { name: 'EX-12' }));
  if (variant === 'secondaire') {
    expect(screen.getByRole('button', { name: 'Confirmer la remise' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Date de retour prévue/), { target: { value: '2027-01-31' } });
  } else {
    expect(screen.queryByLabelText(/Date de retour prévue/)).not.toBeInTheDocument();
  }
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer la remise' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${baseUrl(variant)}${resource}/31/${action}/`, {
    exemplaire: 12, ...(variant === 'secondaire' ? { date_retour_prevue: '2027-01-31' } : {}),
  }));
  expect(patchApi).not.toHaveBeenCalled();
});

it('does not announce success when the reservation succeeds but refreshing authoritative data fails', async () => {
  permissions('add_reservation');
  show();
  await openBook();
  postApi.mockImplementation(async () => {
    fetchApi.mockRejectedValue(new Error('Actualisation impossible'));
    return { id: 31 };
  });
  fireEvent.click(screen.getByRole('button', { name: 'Réserver ce titre pour moi' }));
  expect(await screen.findByText(/Actualisation impossible/)).toBeVisible();
  expect(screen.queryByText(/confirmée par le serveur/)).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: book.titre })).not.toBeInTheDocument();
});

it('paginates the existing unpaginated school reservation endpoint without repeating all rows', async () => {
  permissions('view_reservation');
  reservations = Array.from({ length: 26 }, (_, index) => ({
    id: index + 1, livre: 7, livre_titre: `Réservation ${index + 1}`, statut: 'en_attente',
  }));
  fetchApi.mockImplementation((url, options) => (new URL(url).pathname.endsWith('/reservations/')
    ? Promise.resolve(reservations) : request(url, options)));
  show();
  fireEvent.click(await screen.findByRole('tab', { name: 'Réservations' }));
  expect(await screen.findByText('Réservation 1')).toBeVisible();
  expect(screen.queryByText('Réservation 26')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }));
  expect(await screen.findByText('Réservation 26')).toBeVisible();
  expect(screen.queryByText('Réservation 1')).not.toBeInTheDocument();
});
