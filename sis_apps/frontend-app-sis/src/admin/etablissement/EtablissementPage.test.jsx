import React from 'react';
import {
  fireEvent, render, screen, within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import EtablissementPage from './EtablissementPage';
import { fetchApi } from '../../services/api';

jest.mock('../../services/api', () => ({
  fetchApi: jest.fn(),
  patchApi: jest.fn(),
  postApi: jest.fn(),
  getCurrentEstablishmentUrl: () => 'https://sis.example/api/v1/etablissement/current/',
}));

const originalResizeObserver = global.ResizeObserver;
beforeAll(() => {
  global.ResizeObserver = jest.fn(() => ({ observe: jest.fn(), disconnect: jest.fn() }));
});
afterAll(() => {
  if (originalResizeObserver === undefined) {
    delete global.ResizeObserver;
  } else {
    global.ResizeObserver = originalResizeObserver;
  }
});

it('renders configuration card titles and their add actions instead of dropping header children', async () => {
  fetchApi.mockResolvedValue({
    nom: 'Établissement', configuration_academique: {}, configuration_schema: {},
  });
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <EtablissementPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole('tab', { name: 'Organisation académique' }));
  const heading = screen.getByRole('heading', { name: 'Dimensions dynamiques', level: 2 });
  const section = heading.closest('.pgn__card');
  fireEvent.click(within(section).getByRole('button', { name: 'Ajouter', exact: true }));
  expect(within(section).getByLabelText('Code')).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Fenêtres globales de soumission', level: 2 })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Mode avancé JSON', level: 2 })).toBeVisible();
});
