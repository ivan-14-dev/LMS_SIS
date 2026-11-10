import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchApi, putApi } from '../../services/api';
import { fetchAllResourcePages } from '../../services/resources';
import AccountAccessEditor from './AccountAccessEditor';

jest.mock('../../services/api', () => ({ fetchApi: jest.fn(), putApi: jest.fn() }));
jest.mock('../../services/resources', () => ({
  resourceUrl: (_variant, resource) => `https://sis.example/api/v1/${resource}/`,
  fetchAllResourcePages: jest.fn(),
  apiErrorMessage: error => error?.response?.data?.detail || error.message,
}));

const user = { id: 2, username: 'alice', full_name: 'Alice' };
const permission = {
  id: 11, app_label: 'notes', codename: 'view_note', name: 'Voir les notes',
};
let policy;
beforeEach(() => {
  jest.clearAllMocks();
  policy = {
    version: 'a'.repeat(64),
    primary_role: 'eleve',
    roles: [{ code: 'eleve', label: 'Élève' }],
    role_options: [{ code: 'enseignant', label: 'Enseignant' }],
    additional_roles: [],
    user_permissions: [],
    denied_permissions: [],
    disabled_features: [],
    features: [{ code: 'timetable', label: 'Emplois du temps' }],
    editable: true,
    can_edit_roles: true,
    can_restore_features: true,
  };
  fetchAllResourcePages.mockImplementation(async url => (url.includes('/permissions/') ? [permission] : [user]));
  fetchApi.mockImplementation(async () => policy);
  putApi.mockImplementation(async (_url, data) => {
    policy = { ...policy, ...data, version: 'b'.repeat(64) };
    return policy;
  });
});

const choose = async (label, option) => {
  fireEvent.mouseDown(await screen.findByRole('combobox', { name: label }));
  fireEvent.click(await screen.findByRole('option', { name: option }));
};
const open = async () => {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AccountAccessEditor variant="secondaire" />
    </QueryClientProvider>,
  );
  await choose('Compte à configurer', 'Alice (alice)');
  await screen.findByRole('button', { name: 'Enregistrer les accès individuels' });
};

it('sends multiple roles, individual grants and priority denials with a concurrency version', async () => {
  await open();
  await choose('Rôles supplémentaires', 'Enseignant');
  await choose('Permissions ajoutées directement', 'Voir les notes (notes.view_note)');
  await choose('Permissions explicitement retirées', 'Voir les notes (notes.view_note)');
  fireEvent.click(screen.getByRole('checkbox', { name: 'Retirer : Emplois du temps' }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les accès individuels' }));
  await waitFor(() => expect(putApi).toHaveBeenCalledWith(
    'https://sis.example/api/v1/utilisateurs/comptes/2/access-policy/',
    {
      version: 'a'.repeat(64),
      additional_roles: ['enseignant'],
      user_permissions: [11],
      denied_permissions: ['notes.view_note'],
      disabled_features: ['timetable'],
    },
  ));
  expect(await screen.findByText('Accès individuels enregistrés.')).toBeVisible();
});

it('keeps failed or stale updates visible instead of reporting success', async () => {
  putApi.mockRejectedValue({ response: { status: 409, data: { detail: 'Les droits ont changé.' } } });
  await open();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Retirer : Emplois du temps' }));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les accès individuels' }));
  expect(await screen.findByText('Les droits ont changé.')).toBeVisible();
  expect(screen.queryByText('Accès individuels enregistrés.')).not.toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: 'Retirer : Emplois du temps' })).toBeChecked();
});

it('does not edit protected accounts or roles the actor cannot assign', async () => {
  policy.editable = false;
  policy.can_edit_roles = false;
  await open();
  expect(screen.getByRole('combobox', { name: 'Rôles supplémentaires' })).toBeDisabled();
  expect(screen.getByRole('checkbox', { name: 'Retirer : Emplois du temps' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Enregistrer les accès individuels' })).toBeDisabled();
  expect(putApi).not.toHaveBeenCalled();
});
