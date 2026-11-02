import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import { fetchApi, postApi } from '../../services/api';
import GradeEntryDialog from './GradeEntryDialog';

jest.mock('@edx/frontend-platform', () => ({
  getConfig: () => ({
    SIS_SECONDAIRE_API_URL: 'https://secondary.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superior.example/api/v1',
  }),
}));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  postApi: jest.fn(),
}));
jest.mock('@edx/frontend-platform/auth', () => ({ getAuthenticatedHttpClient: jest.fn() }));

const show = (variant = 'secondaire', onSaved = jest.fn()) => render(
  <QueryClientProvider client={new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })}
  >
    <GradeEntryDialog
      variant={variant}
      evaluation={{ id: 7, titre: 'Contrôle', bareme: '20.00' }}
      onClose={jest.fn()}
      onSaved={onSaved}
    />
  </QueryClientProvider>,
);

beforeEach(() => {
  jest.clearAllMocks();
  getAuthenticatedHttpClient.mockReturnValue({
    get: async (url, options) => ({ data: await fetchApi(url, options) }),
  });
  fetchApi.mockImplementation(async url => (url.includes('/apprenants/')
    ? { results: [{ id: 1, nom: 'Élève test', matricule: 'M1' }] }
    : [{
      eleve: 1, etudiant: 1, valeur: '12.00', statut: 'presente', appreciation: 'Initiale',
    }]));
});

it.each(['secondaire', 'superieur'])('loads every roster page and sends only changed rows for %s', async (variant) => {
  const base = variant === 'secondaire' ? 'https://secondary.example/api/v1' : 'https://superior.example/api/v1';
  fetchApi.mockImplementation(async (url) => {
    if (url.includes('/notes/')) {
      if (url.endsWith('/notes/')) { return []; }
      const next = `${base}/notes/evaluations/7/apprenants/?page=2`;
      return url.includes('page=2')
        ? { results: [{ id: 51, nom: 'Dernier élève', matricule: 'M51' }] }
        : { results: [{ id: 1, nom: 'Premier élève', matricule: 'M1' }], next };
    }
    throw new Error(`Unexpected URL: ${url}`);
  });
  postApi.mockResolvedValue({ notes_creees: 1 });
  const saved = jest.fn();
  show(variant, saved);
  const note = await screen.findByLabelText('Note M51');
  fireEvent.change(note, { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les notes' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${base}/notes/evaluations/7/saisir_notes/`, [{
    [variant === 'secondaire' ? 'eleve_id' : 'etudiant_id']: 51,
    valeur: '0',
    statut: 'presente',
    appreciation: '',
  }]));
  await waitFor(() => expect(saved).toHaveBeenCalledTimes(1));
});

it('preserves other fields and sends null rather than zero when clearing a grade', async () => {
  postApi.mockResolvedValue({});
  show();
  const note = await screen.findByLabelText('Note M1');
  expect(note).toHaveValue(12);
  fireEvent.change(note, { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les notes' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(expect.any(String), [{
    eleve_id: 1, valeur: null, statut: 'presente', appreciation: 'Initiale',
  }]));
});

it('keeps the draft visible when the server rejects the batch', async () => {
  postApi.mockRejectedValue({ response: { data: { evaluation: 'Période clôturée.' } } });
  const saved = jest.fn();
  show('secondaire', saved);
  fireEvent.change(await screen.findByLabelText('Note M1'), { target: { value: '13' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les notes' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Période clôturée.');
  expect(screen.getByLabelText('Note M1')).toHaveValue(13);
  expect(saved).not.toHaveBeenCalled();
});

it('does not allow saving when the roster cannot be loaded', async () => {
  fetchApi.mockRejectedValue(new Error('Liste indisponible'));
  show();
  expect(await screen.findByRole('alert')).toHaveTextContent('Liste indisponible');
  expect(screen.getByRole('button', { name: 'Enregistrer les notes' })).toBeDisabled();
  expect(postApi).not.toHaveBeenCalled();
});
