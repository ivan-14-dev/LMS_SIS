import React from 'react';
import {
  fireEvent, render, screen, waitFor, within,
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

const user = {
  id: 2, username: 'alice', full_name: 'Alice', roles: [{ code: 'enseignant', label: 'Enseignant' }],
};
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
    effective_permissions: [],
    permission_groups: [],
    permission_scopes: {},
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
  fireEvent.click(within(screen.getByRole('region', { name: 'Permissions ajoutées directement' }))
    .getByRole('checkbox', { name: 'Voir les notes (notes.view_note)' }));
  fireEvent.click(within(screen.getByRole('region', { name: 'Permissions explicitement retirées' }))
    .getByRole('checkbox', { name: 'Voir les notes (notes.view_note)' }));
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

it('filters by an additional role and explains inherited, denied and scoped account permissions', async () => {
  policy.roles.push({ code: 'enseignant', label: 'Enseignant' });
  policy.permission_groups = [{
    id: 7, name: 'Lecteurs', active: true, permissions: ['notes.view_note'],
  }];
  policy.denied_permissions = ['notes.view_note'];
  policy.permission_scopes = { 'notes.view_note': { classes: [3] } };
  await open();
  await choose('Filtrer les comptes par rôle', 'Enseignant');
  expect(screen.queryByRole('button', { name: 'Enregistrer les accès individuels' })).not.toBeInTheDocument();
  await choose('Compte à configurer', 'Alice (alice)');
  fireEvent.click(await screen.findByRole('button', { name: 'Voir les droits enregistrés de ces rôles' }));
  const summary = within(screen.getByRole('region', { name: 'Droits enregistrés du compte' }));
  expect(summary.getByText(/Non accordée — Groupe Lecteurs ; Retrait individuel prioritaire ; Périmètre/)).toBeVisible();
  expect(summary.getByRole('checkbox', { name: 'Voir les notes (notes.view_note)' })).not.toBeChecked();
  expect(summary.getByRole('checkbox', { name: 'Voir les notes (notes.view_note)' })).toBeDisabled();
});
