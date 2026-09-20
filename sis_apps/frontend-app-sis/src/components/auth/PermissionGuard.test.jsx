import React from 'react';
import { render, screen } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';

import PermissionGuard from './PermissionGuard';

jest.mock('@tanstack/react-query', () => ({
  useQuery: jest.fn(),
}));

describe('PermissionGuard', () => {
  it('renders children when the backend grants the permission', () => {
    useQuery.mockReturnValue({
      data: { permissions: ['notes.view_note'], role: 'custom_role' },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard type="superieur" permission="notes.view_note">
        <div>Notes</div>
      </PermissionGuard>,
    );

    expect(screen.getByText('Notes')).toBeInTheDocument();
  });

  it('keeps legacy roles as a compatibility fallback', () => {
    useQuery.mockReturnValue({
      data: { permissions: [], role: 'enseignant' },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard
        type="secondaire"
        permission="notes.view_evaluation"
        allowedRoles={['enseignant']}
      >
        <div>Évaluations</div>
      </PermissionGuard>,
    );

    expect(screen.getByText('Évaluations')).toBeInTheDocument();
  });

  it('supports additional group checks', () => {
    useQuery.mockReturnValue({
      data: { permissions: ['notes.view_note'], role: 'custom_role', groups: ['finance'] },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard
        type="superieur"
        permission="notes.view_note"
        allowedGroups={['finance']}
      >
        <div>Finance</div>
      </PermissionGuard>,
    );

    expect(screen.getByText('Finance')).toBeInTheDocument();
  });

  it('supports nested attribute checks', () => {
    useQuery.mockReturnValue({
      data: {
        permissions: ['notes.view_note'],
        role: 'custom_role',
        attributes: { domains: ['finance'], visibility: { campus: 'centre' } },
      },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard
        type="superieur"
        permission="notes.view_note"
        requiredAttributes={{ domains: ['finance'], 'visibility.campus': 'centre' }}
      >
        <div>Vue filtrée</div>
      </PermissionGuard>,
    );

    expect(screen.getByText('Vue filtrée')).toBeInTheDocument();
  });

  it('denies access without a permission or compatible role', () => {
    useQuery.mockReturnValue({
      data: { permissions: [], role: 'visiteur' },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard type="superieur" permission="notes.view_note">
        <div>Notes</div>
      </PermissionGuard>,
    );

    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.getByText(/permission/)).toBeInTheDocument();
  });

  it('denies access when a required attribute is missing', () => {
    useQuery.mockReturnValue({
      data: {
        permissions: ['notes.view_note'],
        role: 'custom_role',
        attributes: { visibility: { campus: 'nord' } },
      },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard
        type="superieur"
        permission="notes.view_note"
        requiredAttributes={{ 'visibility.campus': 'centre' }}
      >
        <div>Notes</div>
      </PermissionGuard>,
    );

    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.getByText(/permission/)).toBeInTheDocument();
  });
});
