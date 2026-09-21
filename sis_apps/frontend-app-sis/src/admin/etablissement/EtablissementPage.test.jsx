import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import EtablissementPage from './EtablissementPage';

jest.mock('@tanstack/react-query', () => ({
  useMutation: jest.fn(),
  useQuery: jest.fn(),
  useQueryClient: jest.fn(),
}));

jest.mock('../../components/common', () => ({
  PageHeader: ({ title, subtitle }) => (
    <div>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </div>
  ),
}));

jest.mock('../../services/api', () => ({
  fetchApi: jest.fn(),
  getCurrentEstablishmentUrl: jest.fn(() => '/api/v1/etablissement/current/'),
  patchApi: jest.fn(),
}));

const buildEstablishment = (configurationAcademique = {}) => ({
  nom: 'École test',
  type: 'secondaire',
  fonctionnalites: {},
  configuration_visio: { provider: 'none', public_url: '' },
  configuration_academique: configurationAcademique,
  configuration_schema: {
    dimension_axes: [{ code: 'organizational', label: 'Organisation' }],
    dimension_scopes: [{ code: 'tenant', label: 'Établissement' }],
    validation_scopes: [{ code: 'tenant', label: 'Établissement' }],
    financial_workflow_scopes: [{ code: 'tenant', label: 'Établissement' }],
    report_datasets: [{ code: 'payments', label: 'Paiements' }],
  },
  type_options: [{ value: 'secondaire', label: 'Secondaire' }],
  feature_options: [],
});

describe('EtablissementPage', () => {
  beforeEach(() => {
    useQueryClient.mockReturnValue({ setQueryData: jest.fn() });
    useMutation.mockReturnValue({
      mutate: jest.fn(),
      isSuccess: false,
      isError: false,
    });
  });

  it('renders the structured academic configuration editors', () => {
    useQuery.mockReturnValue({
      data: buildEstablishment({
        dimensions: [{
          code: 'campus',
          label: 'Campus',
          axis: 'organizational',
          scope: 'tenant',
          applicable_to: ['secondaire'],
        }],
      }),
      isLoading: false,
      isError: false,
    });

    render(<EtablissementPage />);

    fireEvent.click(screen.getByRole('tab', { name: /organisation académique/i }));

    expect(screen.getByText('Dimensions dynamiques')).toBeInTheDocument();
    expect(screen.getByDisplayValue('campus')).toBeInTheDocument();
    expect(screen.getByLabelText('Configuration académique complète')).toHaveValue(
      expect.stringContaining('"dimensions"'),
    );
  });

  it('keeps the JSON editor synchronized with structured edits', () => {
    useQuery.mockReturnValue({
      data: buildEstablishment(),
      isLoading: false,
      isError: false,
    });

    render(<EtablissementPage />);

    fireEvent.click(screen.getByRole('tab', { name: /organisation académique/i }));
    fireEvent.click(screen.getAllByRole('button', { name: 'Ajouter' })[0]);
    fireEvent.change(screen.getByLabelText('Code'), { target: { value: 'campus' } });

    expect(screen.getByLabelText('Configuration académique complète')).toHaveValue(
      expect.stringContaining('"code": "campus"'),
    );
  });
});
