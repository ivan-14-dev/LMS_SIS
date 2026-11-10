import React from 'react';
import {
  fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchApi, putApi } from '../../services/api';
import InstitutionWorkspaceEditor from './InstitutionWorkspaceEditor';

jest.mock('../../services/api', () => ({ fetchApi: jest.fn(), putApi: jest.fn() }));
jest.mock('../../services/resources', () => ({
  resourceUrl: (variant, resource) => `https://${variant}.example/api/v1/${resource}/`,
  getEnabledVariants: () => ['secondaire', 'superieur'],
  apiErrorMessage: error => error.message,
}));
let workspaces;
beforeEach(() => {
  jest.clearAllMocks();
  workspaces = {
    secondaire: {
      id: 'a',
      peer: null,
      home: null,
      variant: 'secondaire',
      version: 'v1',
      user: 1,
      account: 'Compte A',
      name: 'Établissement A',
      can_configure: true,
    },
    superieur: {
      id: 'b',
      peer: null,
      home: null,
      variant: 'superieur',
      version: 'v2',
      user: 2,
      account: 'Compte B',
      name: 'Établissement B',
      can_configure: true,
    },
  };
  fetchApi.mockImplementation(async url => workspaces[url.includes('secondaire') ? 'secondaire' : 'superieur']);
  putApi.mockImplementation(async (url, data) => {
    const key = url.includes('secondaire') ? 'secondaire' : 'superieur';
    const workspace = workspaces[key];
    workspaces[key] = url.endsWith('/workspace-link/')
      ? { ...workspace, account_link: { ...data, version: workspace.version } }
      : { ...workspace, ...data, version: `${workspace.version}-updated` };
    return workspaces[key];
  });
});
const open = async () => {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <InstitutionWorkspaceEditor variant="secondaire" administration />
    </QueryClientProvider>,
  );
  await screen.findByText(/Espace courant : Établissement A/);
  expect(fetchApi.mock.calls.every(([url]) => url.includes('secondaire'))).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier le second espace' }));
  await screen.findByText(/Second espace : Établissement B/);
};
const declare = async () => {
  fireEvent.click(screen.getByRole('checkbox', { name: /ces deux espaces appartiennent/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Réunir les fonctions de ces deux espaces' }));
};

it('requires explicit confirmations of both institutions and both identities', async () => {
  await open();
  expect(screen.getByRole('button', { name: 'Réunir les fonctions de ces deux espaces' })).toBeDisabled();
  await declare();
  await screen.findByText('Rattachement institutionnel confirmé des deux côtés.');
  expect(putApi).toHaveBeenNthCalledWith(1, 'https://secondaire.example/api/v1/etablissement/current/workspace/', {
    version: 'v1', peer: 'b', home: 'a',
  });
  expect(putApi).toHaveBeenNthCalledWith(2, 'https://superieur.example/api/v1/etablissement/current/workspace/', {
    version: 'v2', peer: 'a', home: 'a',
  });
  expect(screen.queryByText('Navigation commune activée pour vos deux comptes.')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox', { name: /les deux comptes affichés sont les miens/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Réunir mes accès autorisés' }));
  await screen.findByText('Navigation commune activée pour vos deux comptes.');
  fireEvent.click(screen.getByRole('button', { name: 'Dissocier mes accès' }));
  await waitFor(() => expect(putApi).toHaveBeenLastCalledWith('https://secondaire.example/api/v1/utilisateurs/comptes/workspace-link/', { peer: null, user: null }));
});

it('does not claim success or associate identities after a partial institution failure', async () => {
  await open();
  putApi.mockImplementationOnce(putApi.getMockImplementation())
    .mockRejectedValueOnce(new Error('Édition concurrente : rechargez.'));
  await declare();
  expect(await screen.findByText(/Édition concurrente : rechargez/)).toBeVisible();
  expect(screen.queryByText('Rattachement institutionnel confirmé des deux côtés.')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Réunir mes accès autorisés' })).not.toBeInTheDocument();
  expect(putApi).toHaveBeenCalledTimes(2);
});
