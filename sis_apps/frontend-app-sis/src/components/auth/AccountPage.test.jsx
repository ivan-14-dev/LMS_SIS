import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '../../test-utils';
import { fetchApi, postApi } from '../../services/api';
import { usesLocalSession } from '../../services/localSession';
import AccountPage from './AccountPage';

jest.mock('../../services/api', () => ({
  fetchApi: jest.fn(),
  postApi: jest.fn(),
  putApi: jest.fn(),
  deleteApi: jest.fn(),
}));
jest.mock('../../services/localSession', () => ({
  usesLocalSession: jest.fn(() => true),
}));
jest.mock('../../services/resources', () => ({
  resourceUrl: (variant, resource) => `/api/${variant}/${resource}/`,
  apiErrorMessage: error => error.message,
  getEnabledVariants: () => ['secondaire', 'superieur'],
}));

beforeEach(() => {
  jest.clearAllMocks();
  usesLocalSession.mockReturnValue(true);
  fetchApi.mockImplementation(url => Promise.resolve(
    url.endsWith('/sessions/') ? [{ jti: 'first' }, { jti: 'second' }] : { username: 'student', mfa_active: false },
  ));
});

it('lists local sessions and revokes only the selected token', async () => {
  let active = ['first', 'second'];
  fetchApi.mockImplementation(url => Promise.resolve(
    url.endsWith('/sessions/')
      ? active.map(jti => ({ jti }))
      : { username: 'student', mfa_active: false },
  ));
  postApi.mockImplementation((url, { jti }) => {
    active = active.filter(token => token !== jti);
    return Promise.resolve({ detail: 'Session révoquée.' });
  });
  render(<AccountPage variant="secondaire" />);

  const buttons = await screen.findAllByRole('button', { name: 'Révoquer la session' });
  expect(buttons).toHaveLength(2);
  fireEvent.click(buttons[1]);

  await waitFor(() => expect(postApi).toHaveBeenCalledWith(
    '/api/secondaire/utilisateurs/comptes/revoke_session/',
    { jti: 'second' },
  ));
  await waitFor(() => expect(screen.getAllByRole('button', { name: 'Révoquer la session' })).toHaveLength(1));
  expect(screen.getByText('Session révoquée.')).toBeInTheDocument();
});

it('reports session lookup failures instead of showing an empty list', async () => {
  fetchApi.mockImplementation(url => (url.endsWith('/sessions/')
    ? Promise.reject(new Error('Indisponible'))
    : Promise.resolve({ username: 'student' })));
  render(<AccountPage variant="superieur" />);

  expect(await screen.findByText('Indisponible')).toBeInTheDocument();
  expect(screen.queryByText('Aucune session JWT non expirée.')).not.toBeInTheDocument();
});

it('does not offer to revoke a session that is already revoked', async () => {
  fetchApi.mockImplementation(url => Promise.resolve(
    url.endsWith('/sessions/')
      ? [{ jti: 'old', revoked: true }, { jti: 'current', revoked: false }]
      : { username: 'student', mfa_active: false },
  ));
  render(<AccountPage variant="secondaire" />);

  expect(await screen.findByText('Révoquée')).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Révoquer la session' })).toHaveLength(1);
});

it('does not request local JWT sessions in federated mode', async () => {
  usesLocalSession.mockReturnValue(false);
  render(<AccountPage variant="superieur" />);

  await screen.findByText('student');
  expect(fetchApi).not.toHaveBeenCalledWith('/api/superieur/utilisateurs/comptes/sessions/');
  expect(screen.queryByText('Sessions SIS locales')).not.toBeInTheDocument();
});
